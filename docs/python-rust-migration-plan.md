# Python + Rust 混合架构迁移方案

> **文档版本**: v1.0  
> **创建日期**: 2026-04-24  
> **状态**: 待评审  

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [业内实践参考](#2-业内实践参考)
3. [架构设计](#3-架构设计)
4. [模块替换策略](#4-模块替换策略)
5. [技术选型](#5-技术选型)
6. [通信方案](#6-通信方案)
7. [实施路径](#7-实施路径)
8. [部署架构](#8-部署架构)
9. [风险评估与应对](#9-风险评估与应对)
10. [验收标准](#10-验收标准)
11. [附录](#11-附录)

---

## 1. 背景与目标

### 1.1 当前痛点

| 指标 | 现状 | 问题 |
|------|------|------|
| **CPU 使用率** | 65-85% | 批量测试期间 CPU 持续满载 |
| **内存占用** | 1.2-1.8GB | Python 对象开销大，GC 频繁 |
| **批量测试耗时** | 45min | 6层校验引擎串行执行效率低 |
| **检索 P99 延迟** | 350ms | BM25 分词+融合计算慢 |
| **并发处理能力** | 50 QPS | GIL 限制多线程并行 |

### 1.2 迁移目标

| 指标 | 目标值 | 改善幅度 |
|------|--------|---------|
| CPU 使用率 | ≤40% | ↓ 50%+ |
| 内存占用 | ≤900MB | ↓ 50% |
| 批量测试耗时 | ≤15min | ↓ 65% |
| 检索 P99 延迟 | ≤150ms | ↓ 55% |
| 并发处理能力 | ≥150 QPS | ↑ 3x |

### 1.3 设计原则

1. **渐进式替换**：不重写整个后端，优先替换瓶颈模块
2. **故障隔离**：Rust 服务崩溃不影响 Python 主流程
3. **零业务中断**：支持灰度发布，平滑过渡
4. **可回退**：每个阶段保留 Python 降级方案

---

## 2. 业内实践参考

### 2.1 知名公司案例

| 公司 | 场景 | 方案 | 效果 |
|------|------|------|------|
| **Meta (Instagram)** | ML 特征工程 | PyO3 嵌入 | 特征计算 30x 提升 |
| **Discord** | 消息读取服务 | 完全重写为 Rust | P99 从 200ms→10ms |
| **Dropbox** | 文件同步引擎 | Python + Rust 混合 | 同步速度 4x 提升 |
| **Cloudflare** | 边缘计算运行时 | Rust 核心 + JS/Python 用户代码 | 冷启动 <5ms |
| **AWS** | Firecracker 微虚拟机 | Rust VMM + Python 管理平面 | 启动 <125ms |

### 2.2 主流架构模式对比

| 模式 | 延迟 | 部署复杂度 | 故障隔离 | 适用场景 |
|------|------|-----------|---------|---------|
| **PyO3 嵌入** | ~0ms | 低 | 无 | CPU 密集计算、序列化 |
| **gRPC 微服务** | 1-3ms | 中 | 完全 | 独立服务、高并发 |
| **Unix Socket** | <1ms | 中 | 部分 | 同机部署、超低延迟 |
| **WASM 插件** | 2-5ms | 高 | 完全 | 插件生态、沙箱 |

---

## 3. 架构设计

### 3.1 总体架构

```
┌─────────────────────────────────────────────────────────┐
│                    前端展示层 (React)                     │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP/REST
┌────────────────────────▼────────────────────────────────┐
│              Python FastAPI (保留)                        │
│  ┌──────────────────────────────────────────────────┐   │
│  │  - Agent 编排 (LangGraph)                         │   │
│  │  - LLM 调用 (LangChain/LlamaIndex)                │   │
│  │  - 业务逻辑协调                                    │   │
│  │  - API 网关 / CORS / 认证                         │   │
│  │  - 配置管理 / 提示词管理                           │   │
│  └──────────────────────────────────────────────────┘   │
└──────┬──────────────┬──────────────┬────────────────────┘
       │ PyO3         │ gRPC         │ Unix Socket
       ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Rust Library │ │ Rust Service │ │ Rust Service │
│ (AHP 评分)   │ │ (6层校验)    │ │ (缓存系统)   │
│ - 零拷贝调用 │ │ - 独立进程   │ │ - 同机部署   │
│ - 同步执行   │ │ - 可扩缩容   │ │ - 共享内存   │
└──────────────┘ └──────────────┘ └──────────────┘
```

### 3.2 数据流向

```
用户请求
  │
  ▼
FastAPI 接收请求
  │
  ├─→ [PyO3] AHP 评分计算 ←────────── 零延迟，同步调用
  │
  ├─→ [gRPC] 6层校验引擎 ←─────────── 1-3ms 网络延迟
  │     │
  │     ├─→ Layer1: 规则校验
  │     ├─→ Layer2: 历史对比
  │     ├─→ Layer3: LLM 诊断 (保留 Python)
  │     ├─→ Layer4: 质量校验
  │     ├─→ Layer5: 效果校验
  │     └─→ Layer6: 回归校验
  │
  ├─→ [Unix Socket] 缓存系统 ←─────── <1ms 本地通信
  │     │
  │     ├─→ L1: Memory LRU (Rust moka)
  │     ├─→ L2: Redis (保留)
  │     └─→ L3: Disk (保留)
  │
  └─→ [保留 Python] LLM 调用 ←─────── 生态成熟，无需替换
```

---

## 4. 模块替换策略

### 4.1 优先级矩阵

| 模块 | CPU 占用 | 内存占用 | 替换收益 | 实施难度 | 优先级 |
|------|---------|---------|---------|---------|--------|
| **6层校验引擎** | 高 | 中 | ★★★★★ | 中 | **P0** |
| **AHP 评分引擎** | 高 | 低 | ★★★★☆ | 低 | **P0** |
| **缓存系统** | 中 | 高 | ★★★★☆ | 中 | **P1** |
| **向量检索预处理** | 中 | 中 | ★★★☆☆ | 中高 | **P1** |
| **文档解析流水线** | 高 | 高 | ★★★☆☆ | 高 | **P2** |

### 4.2 模块详细方案

#### 模块 1：6层校验引擎

**当前代码位置**: `backend/src/core/validation/`

**替换范围**:
- Layer1: 规则引擎校验（格式验证、必填项检查）
- Layer2: 历史对比校验（批量数据对比、差异计算）
- Layer4: 质量校验（覆盖率计算、分块质量评估）
- Layer5: 效果校验（Embedding 匹配度、召回率/精确率）

**保留 Python**:
- Layer3: LLM 诊断校验（依赖 LangChain 调用大模型）
- Layer6: 回归校验（依赖历史数据库查询）

**技术方案**:
```rust
// gRPC 服务定义
service ValidationEngine {
  rpc ValidateLayer1(ValidationRequest) returns (ValidationReport);
  rpc ValidateLayer2(HistoryComparisonRequest) returns (ComparisonReport);
  rpc ValidateLayer4(QualityCheckRequest) returns (QualityReport);
  rpc ValidateLayer5(EffectCheckRequest) returns (EffectReport);
}

// 核心依赖
// - serde_json: JSON 解析
// - rayon: 并行计算
// - strsim: 字符串相似度
```

**预期收益**:
- CPU 使用降低 60-80%
- 批量测试执行速度提升 3-5 倍
- 内存占用降低 50%

---

#### 模块 2：AHP 评分引擎

**当前代码位置**: `backend/src/core/nodes/scoring.py`

**替换范围**:
- 层次分析法矩阵运算
- 特征值计算、一致性检验
- 多维评分向量相似度计算

**技术方案**:
```rust
// PyO3 直接嵌入 Python
use pyo3::prelude::*;
use nalgebra::{DMatrix, DVector};

#[pyfunction]
fn calculate_ahp_scores(matrix: Vec<Vec<f64>>) -> PyResult<Vec<f64>> {
    let mat = DMatrix::from_row_slice(matrix.len(), matrix[0].len(), &matrix.iter().flatten().cloned().collect::<Vec<_>>());
    // 特征值计算、一致性检验
    Ok(scores)
}

#[pymodule]
fn ahp_engine(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(calculate_ahp_scores, m)?)?;
    Ok(())
}
```

**预期收益**:
- 评分延迟降低 70%
- 支持更大规模矩阵运算
- 零网络开销

---

#### 模块 3：三级缓存系统

**当前代码位置**: `backend/src/service/cache_service.py`

**替换范围**:
- L1: Memory LRU 缓存（Python dict → Rust moka）
- 序列化/反序列化（JSON → MessagePack/rkyv）

**保留**:
- L2: Redis（分布式共享）
- L3: Disk（持久化兜底）

**技术方案**:
```rust
// Unix Socket 服务
use moka::sync::Cache;
use axum::{Router, routing::get, extract::State};

#[derive(Clone)]
struct CacheState {
    l1_cache: Cache<String, Vec<u8>>,  // MessagePack 序列化
}

async fn get_cache(State(state): State<CacheState>, key: String) -> Response {
    match state.l1_cache.get(&key) {
        Some(value) => Json(value),
        None => StatusCode::NOT_FOUND,
    }
}
```

**预期收益**:
- 缓存命中率提升 10-15%
- 内存占用降低 40%
- 序列化速度提升 5-10 倍

---

#### 模块 4：向量检索预处理

**当前代码位置**: `backend/src/service/retrieval/`

**替换范围**:
- BM25 全文检索（Python → Rust tantivy）
- 结果融合（分数归一化、排序）
- 查询预处理（分词、同义词扩展）

**保留**:
- Chroma 向量库（生态成熟）
- CrossEncoder 重排序（依赖 ML 模型）

**技术方案**:
```rust
// tantivy 全文检索
use tantivy::{Index, doc, schema::*};

fn build_index() -> Index {
    let mut schema_builder = Schema::builder();
    let title = schema_builder.add_text_field("title", TEXT);
    let body = schema_builder.add_text_field("body", TEXT);
    let schema = schema_builder.build();
    
    Index::create_in_ram(schema)
}
```

**预期收益**:
- 检索延迟降低 40-60%
- 并发查询能力提升 2-3 倍

---

#### 模块 5：文档解析流水线

**当前代码位置**: `backend/src/service/document_ingestion/`

**替换范围**:
- PDF/EPUB 解析
- 文本分块、语义分割
- 元数据提取（正则匹配、NLP 预处理）

**技术方案**:
```rust
// 异步任务队列
use tokio::task;
use lopdf::Document;

async fn parse_pdf(path: &str) -> Result<ParsedDocument> {
    let doc = Document::load(path)?;
    // 并行解析多页
    let pages: Vec<_> = doc.get_pages()
        .into_iter()
        .map(|(page_num, _)| task::spawn(parse_page(page_num)))
        .collect();
    
    Ok(ParsedDocument::from(pages))
}
```

**预期收益**:
- 文档处理速度提升 2-4 倍
- 内存峰值降低 50%

---

## 5. 技术选型

### 5.1 Rust 核心依赖

```toml
# Cargo.toml
[package]
name = "child-assessment-rust"
version = "0.1.0"
edition = "2021"

[dependencies]
# === Web 框架 ===
axum = "0.7"                    # HTTP 服务
tonic = "0.11"                  # gRPC 框架
tokio = { version = "1.36", features = ["full"] }  # 异步运行时

# === 序列化 ===
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
rkyv = "0.7"                    # 零拷贝序列化
rmp-serde = "1.1"               # MessagePack

# === 计算 ===
nalgebra = "0.32"               # 线性代数（AHP 评分）
ndarray = "0.15"                # N维数组
rayon = "1.8"                   # 并行计算

# === 检索 ===
tantivy = "0.21"                # 全文检索引擎
jieba-rs = "0.6"                # 中文分词

# === 缓存 ===
moka = "0.12"                   # 高性能 LRU 缓存

# === Python 集成 ===
pyo3 = { version = "0.20", features = ["extension-module"] }

# === 工具 ===
tracing = "0.1"                 # 结构化日志
tracing-subscriber = "0.3"
thiserror = "1.0"               # 错误处理
uuid = { version = "1.7", features = ["v4"] }

[dev-dependencies]
criterion = "0.5"               # 性能基准测试
tokio-test = "0.4"
```

### 5.2 Python 端依赖

```toml
# pyproject.toml (新增)
[project.optional-dependencies]
rust-integration = [
    "grpcio>=1.60.0",           # gRPC 客户端
    "grpcio-tools>=1.60.0",     # gRPC 代码生成
    "msgpack>=1.0.7",           # MessagePack 序列化
]
```

---

## 6. 通信方案

### 6.1 方案对比

| 方案 | 延迟 | 吞吐量 | 部署复杂度 | 适用场景 |
|------|------|--------|-----------|---------|
| **PyO3 FFI** | ~0ms | 极高 | 低 | AHP 评分、矩阵运算 |
| **Unix Socket** | <1ms | 高 | 中 | 缓存系统、同机服务 |
| **gRPC** | 1-3ms | 极高 | 中 | 6层校验、独立服务 |
| **HTTP/REST** | 5-10ms | 中 | 低 | 低频调用、调试 |

### 6.2 推荐组合

| 模块 | 通信方案 | 理由 |
|------|---------|------|
| AHP 评分 | PyO3 FFI | 零延迟，同步调用 |
| 6层校验 | gRPC | 独立部署，可扩缩容 |
| 缓存系统 | Unix Socket | 超低延迟，同机部署 |
| 文档解析 | gRPC + 消息队列 | 异步任务，资源隔离 |

### 6.3 gRPC 服务定义

```protobuf
// proto/validation.proto
syntax = "proto3";

package validation.v1;

service ValidationEngine {
  // Layer1: 规则引擎校验
  rpc ValidateLayer1(ValidationRequest) returns (ValidationReport);
  
  // Layer2: 历史对比校验
  rpc ValidateLayer2(HistoryComparisonRequest) returns (ComparisonReport);
  
  // Layer4: 质量校验
  rpc ValidateLayer4(QualityCheckRequest) returns (QualityReport);
  
  // Layer5: 效果校验
  rpc ValidateLayer5(EffectCheckRequest) returns (EffectReport);
  
  // 健康检查
  rpc HealthCheck(HealthRequest) returns (HealthResponse);
}

message ValidationRequest {
  string test_run_id = 1;
  repeated TestCaseResult results = 2;
  map<string, string> config = 3;
}

message ValidationReport {
  string report_id = 1;
  bool passed = 2;
  repeated ValidationIssue issues = 3;
  double execution_time_ms = 4;
}

message ValidationIssue {
  string rule_id = 1;
  string severity = 2;  // ERROR, WARNING, INFO
  string message = 3;
  string field_path = 4;
}
```

### 6.4 Python 端 gRPC 客户端

```python
# backend/src/clients/validation_client.py
import grpc
from proto import validation_pb2, validation_pb2_grpc

class ValidationClient:
    def __init__(self, host: str = "localhost", port: int = 50051):
        self.channel = grpc.aio.insecure_channel(f"{host}:{port}")
        self.stub = validation_pb2_grpc.ValidationEngineStub(self.channel)
    
    async def validate_layer1(self, request: dict) -> dict:
        try:
            response = await self.stub.ValidateLayer1(
                validation_pb2.ValidationRequest(**request),
                timeout=30.0
            )
            return self._to_dict(response)
        except grpc.RpcError as e:
            # 降级到 Python 实现
            return await self._fallback_layer1(request)
```

---

## 7. 实施路径

### 7.1 阶段划分

```
Phase 1 (2 周)          Phase 2 (3 周)          Phase 3 (4 周)          Phase 4 (3 周)
┌─────────────┐        ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
│ 基础设施搭建 │        │ 6层校验引擎  │        │ 缓存+检索   │        │ 文档解析    │
│             │        │             │        │             │        │             │
│ • Rust 项目 │        │ • gRPC 服务 │        │ • Unix Sock │        │ • 异步队列  │
│ • PyO3 集成 │   ──→  │ • Layer1/2  │   ──→  │ • moka 缓存 │   ──→  │ • PDF 解析  │
│ • AHP 评分  │        │ • Layer4/5  │        │ • tantivy   │        │ • 分块索引  │
│ • 基准测试  │        │ • 性能验证  │        │ • 性能验证  │        │ • 性能调优  │
└─────────────┘        └─────────────┘        └─────────────┘        └─────────────┘
     │                      │                      │                      │
     ▼                      ▼                      ▼                      ▼
  验收标准:              验收标准:              验收标准:              验收标准:
  • AHP 延迟<10ms        • 校验速度↑3x          • 缓存命中率↑15%       • 解析速度↑2x
  • 编译通过             • gRPC 稳定运行        • 检索延迟↓50%         • 内存峰值↓50%
  • 单元测试 100%        • 降级方案可用         • 并发能力↑2x          • 全链路测试通过
```

### 7.2 详细任务清单

#### Phase 1: 基础设施 + AHP 评分（2 周）

| 任务 | 负责人 | 工期 | 交付物 |
|------|--------|------|--------|
| 创建 Rust 项目结构 | 后端开发 | 2 天 | `backend-rust/` 目录 |
| 配置 PyO3 集成 | 后端开发 | 2 天 | `ahp_engine.so` 可导入 |
| 实现 AHP 矩阵运算 | 后端开发 | 3 天 | `calculate_ahp_scores()` |
| 编写 Python 绑定 | 后端开发 | 2 天 | `import ahp_engine` |
| 性能基准测试 | 后端开发 | 2 天 | 基准测试报告 |
| 集成到现有代码 | 后端开发 | 2 天 | 评分节点调用 Rust |
| 单元测试 | 后端开发 | 1 天 | 测试覆盖率 100% |

#### Phase 2: 6层校验引擎（3 周）

| 任务 | 负责人 | 工期 | 交付物 |
|------|--------|------|--------|
| 定义 gRPC proto | 后端开发 | 2 天 | `validation.proto` |
| 实现 Layer1 规则校验 | 后端开发 | 3 天 | `validate_layer1()` |
| 实现 Layer2 历史对比 | 后端开发 | 4 天 | `validate_layer2()` |
| 实现 Layer4 质量校验 | 后端开发 | 3 天 | `validate_layer4()` |
| 实现 Layer5 效果校验 | 后端开发 | 3 天 | `validate_layer5()` |
| Python gRPC 客户端 | 后端开发 | 2 天 | `ValidationClient` |
| 降级方案实现 | 后端开发 | 2 天 | Python fallback |
| 集成测试 | 后端开发 | 2 天 | 端到端测试通过 |
| 性能验证 | 后端开发 | 1 天 | 性能对比报告 |

#### Phase 3: 缓存 + 检索加速（4 周）

| 任务 | 负责人 | 工期 | 交付物 |
|------|--------|------|--------|
| Unix Socket 通信 | 后端开发 | 3 天 | 本地服务框架 |
| moka LRU 缓存 | 后端开发 | 4 天 | `CacheService` |
| MessagePack 序列化 | 后端开发 | 2 天 | 序列化模块 |
| tantivy 索引构建 | 后端开发 | 5 天 | 全文检索引擎 |
| jieba-rs 中文分词 | 后端开发 | 3 天 | 分词模块 |
| 结果融合算法 | 后端开发 | 3 天 | 分数归一化 |
| Python 客户端适配 | 后端开发 | 3 天 | 缓存客户端 |
| 性能调优 | 后端开发 | 3 天 | 性能优化报告 |
| 集成测试 | 后端开发 | 2 天 | 测试报告 |

#### Phase 4: 文档解析 + 全面调优（3 周）

| 任务 | 负责人 | 工期 | 交付物 |
|------|--------|------|--------|
| lopdf PDF 解析 | 后端开发 | 4 天 | PDF 解析器 |
| EPUB 解析 | 后端开发 | 3 天 | EPUB 解析器 |
| 异步任务队列 | 后端开发 | 3 天 | tokio 任务管理 |
| 语义分块 | 后端开发 | 4 天 | 分块算法 |
| 元数据提取 | 后端开发 | 3 天 | 元数据模块 |
| 与 Python 集成 | 后端开发 | 3 天 | 完整流水线 |
| 全链路性能测试 | 后端开发 | 2 天 | 性能报告 |
| 文档更新 | 后端开发 | 1 天 | 技术文档 |

---

## 8. 部署架构

### 8.1 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  # === Python 主服务 ===
  python-api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - RUST_VALIDATION_HOST=rust-validation
      - RUST_VALIDATION_PORT=50051
      - RUST_CACHE_SOCKET=/tmp/rust-cache.sock
    volumes:
      - ./backend/src:/app/src
      - ./ahp_engine.so:/app/ahp_engine.so  # PyO3 编译产物
    depends_on:
      - rust-validation
      - rust-cache
    networks:
      - app-network

  # === Rust 6层校验服务 ===
  rust-validation:
    build:
      context: ./backend-rust/validation
      dockerfile: Dockerfile
    ports:
      - "50051:50051"  # gRPC
    environment:
      - RUST_LOG=info
      - THREADS=4
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 512M
    networks:
      - app-network

  # === Rust 缓存服务 ===
  rust-cache:
    build:
      context: ./backend-rust/cache
      dockerfile: Dockerfile
    volumes:
      - /tmp/rust-cache.sock:/tmp/rust-cache.sock  # Unix Socket
    environment:
      - RUST_LOG=info
      - CACHE_SIZE_MB=256
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 256M
    networks:
      - app-network

  # === 基础设施 ===
  mysql:
    image: mysql:5.7
    ports:
      - "3306:3306"
    environment:
      - MYSQL_ROOT_PASSWORD=root
    volumes:
      - mysql-data:/var/lib/mysql
    networks:
      - app-network

  redis:
    image: redis:7.0
    ports:
      - "6379:6379"
    networks:
      - app-network

  chroma:
    image: chromadb/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - chroma-data:/chroma/chroma
    networks:
      - app-network

volumes:
  mysql-data:
  chroma-data:

networks:
  app-network:
    driver: bridge
```

### 8.2 Rust 服务 Dockerfile

```dockerfile
# backend-rust/validation/Dockerfile
FROM rust:1.75-slim AS builder

WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src/ ./src/

# 编译优化
RUN cargo build --release
RUN cp target/release/validation-service /usr/local/bin/

# 运行时镜像
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/bin/validation-service /usr/local/bin/

EXPOSE 50051

CMD ["validation-service"]
```

### 8.3 资源分配

| 服务 | CPU | 内存 | 磁盘 |
|------|-----|------|------|
| Python FastAPI | 2 核 | 1GB | 500MB |
| Rust 校验服务 | 2 核 | 512MB | 100MB |
| Rust 缓存服务 | 1 核 | 256MB | 50MB |
| MySQL | 1 核 | 512MB | 5GB |
| Redis | 0.5 核 | 256MB | 100MB |
| **总计** | **6.5 核** | **2.5GB** | **5.75GB** |

**对比当前**: 单 Python 进程 4 核 2GB → 混合架构 6.5 核 2.5GB（可水平扩展）

---

## 9. 风险评估与应对

### 9.1 技术风险

| 风险 | 概率 | 影响 | 应对策略 |
|------|------|------|---------|
| **Rust 学习曲线** | 高 | 中 | 从简单模块开始，提供代码模板 |
| **PyO3 GIL 问题** | 中 | 高 | 使用 `#[pyfunction]` 释放 GIL |
| **gRPC 序列化开销** | 低 | 中 | 使用 Protocol Buffers，避免 JSON |
| **Rust 服务崩溃** | 中 | 高 | Python 端实现熔断器+降级方案 |
| **内存泄漏** | 低 | 高 | 使用 valgrind/cargo-miri 检测 |
| **编译时间长** | 高 | 低 | CI 缓存 + sccache 加速 |

### 9.2 业务风险

| 风险 | 概率 | 影响 | 应对策略 |
|------|------|------|---------|
| **迁移期间功能回归** | 中 | 高 | 每个阶段保留 Python 降级 |
| **性能不达预期** | 低 | 中 | Phase 1 先做基准测试验证 |
| **团队维护能力** | 中 | 高 | 编写详细文档，培训团队 |
| **第三方依赖变更** | 低 | 中 | 锁定依赖版本，定期更新 |

### 9.3 降级方案

```python
# backend/src/core/validation/fallback.py
class ValidationFallback:
    """Rust 服务不可用时的降级方案"""
    
    def __init__(self):
        self.python_validator = PythonValidationEngine()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60
        )
    
    async def validate_layer1(self, request: dict) -> dict:
        """带熔断器的校验调用"""
        try:
            return await self.circuit_breaker.call(
                lambda: self.rust_client.validate_layer1(request)
            )
        except CircuitBreakerOpen:
            # 降级到 Python 实现
            logger.warning("Rust 服务不可用，降级到 Python 实现")
            return await self.python_validator.validate_layer1(request)
```

---

## 10. 验收标准

### 10.1 Phase 1 验收

| 指标 | 目标 | 验证方法 |
|------|------|---------|
| AHP 评分延迟 | <10ms | 基准测试 1000 次调用 |
| Python 导入成功 | `import ahp_engine` 无报错 | 单元测试 |
| 计算结果一致 | 与 Python 实现误差 <0.001 | 对比测试 |
| 编译通过 | `cargo build --release` 成功 | CI 流水线 |

### 10.2 Phase 2 验收

| 指标 | 目标 | 验证方法 |
|------|------|---------|
| 校验速度提升 | ≥3x | 批量测试 100 用例对比 |
| gRPC 稳定性 | 99.9% 可用 | 24 小时压力测试 |
| 降级方案可用 | Rust 宕机时自动切换 | 故障注入测试 |
| 内存占用降低 | ≥50% | `psutil` 监控对比 |

### 10.3 Phase 3 验收

| 指标 | 目标 | 验证方法 |
|------|------|---------|
| 缓存命中率提升 | ≥15% | 监控指标对比 |
| 检索延迟降低 | ≥50% | P99 延迟对比 |
| 并发能力提升 | ≥2x | 并发 100 请求测试 |
| 序列化速度 | ≥5x 提升 | 基准测试 |

### 10.4 Phase 4 验收

| 指标 | 目标 | 验证方法 |
|------|------|---------|
| 文档解析速度 | ≥2x 提升 | 100 份 PDF 对比测试 |
| 内存峰值降低 | ≥50% | 内存监控对比 |
| 全链路测试通过 | 100% | 端到端测试 |
| 性能报告 | 所有指标达标 | 综合性能报告 |

---

## 11. 附录

### 11.1 项目结构

```
child-development-assessment-agent/
├── backend/                          # Python 后端（保留）
│   ├── src/
│   │   ├── core/
│   │   │   ├── nodes/
│   │   │   │   └── scoring.py       # 调用 Rust AHP
│   │   │   └── validation/
│   │   │       └── orchestrator.py  # 调用 Rust gRPC
│   │   ├── clients/
│   │   │   └── validation_client.py # gRPC 客户端
│   │   └── service/
│   │       └── cache_service.py     # 调用 Rust 缓存
│   └── pyproject.toml
│
├── backend-rust/                     # Rust 后端（新增）
│   ├── ahp-engine/                   # PyO3 库
│   │   ├── Cargo.toml
│   │   └── src/
│   │       └── lib.rs
│   │
│   ├── validation/                   # gRPC 服务
│   │   ├── Cargo.toml
│   │   ├── proto/
│   │   │   └── validation.proto
│   │   └── src/
│   │       ├── main.rs
│   │       ├── layer1.rs
│   │       ├── layer2.rs
│   │       ├── layer4.rs
│   │       └── layer5.rs
│   │
│   ├── cache/                        # Unix Socket 服务
│   │   ├── Cargo.toml
│   │   └── src/
│   │       └── main.rs
│   │
│   └── retrieval/                    # 检索加速
│       ├── Cargo.toml
│       └── src/
│           ├── main.rs
│           ├── bm25.rs
│           └── fusion.rs
│
└── docker-compose.yml
```

### 11.2 性能基准测试模板

```rust
// backend-rust/ahp-engine/benches/ahp_benchmark.rs
use criterion::{criterion_group, criterion_main, Criterion};
use ahp_engine::calculate_ahp_scores;

fn bench_ahp_10x10(c: &mut Criterion) {
    let matrix = vec![vec![1.0; 10]; 10];
    c.bench_function("ahp_10x10", |b| {
        b.iter(|| calculate_ahp_scores(matrix.clone()))
    });
}

criterion_group!(benches, bench_ahp_10x10);
criterion_main!(benches);
```

### 11.3 监控指标

```python
# Prometheus 指标
from prometheus_client import Counter, Histogram, Gauge

# Rust 服务调用
rust_validation_requests = Counter(
    'rust_validation_requests_total',
    'Total Rust validation requests',
    ['layer', 'status']
)

rust_validation_duration = Histogram(
    'rust_validation_duration_seconds',
    'Rust validation duration',
    ['layer']
)

rust_cache_hit_rate = Gauge(
    'rust_cache_hit_rate',
    'Rust cache hit rate'
)

# 降级状态
fallback_active = Gauge(
    'fallback_active',
    'Whether fallback is active',
    ['service']
)
```

### 11.4 CI/CD 配置

```yaml
# .github/workflows/rust-ci.yml
name: Rust CI

on:
  push:
    paths:
      - 'backend-rust/**'
  pull_request:
    paths:
      - 'backend-rust/**'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Cache Rust dependencies
        uses: Swatinem/rust-cache@v2
      
      - name: Install Rust
        uses: dtolnay/rust-toolchain@stable
      
      - name: Run tests
        run: |
          cd backend-rust
          cargo test --all-features
      
      - name: Run benchmarks
        run: |
          cd backend-rust
          cargo bench
      
      - name: Build release
        run: |
          cd backend-rust
          cargo build --release
```

---

## 12. 决策记录

### 12.1 为什么选择渐进式替换而非完全重写？

1. **风险可控**：每个阶段可独立验证，失败可回退
2. **业务连续**：不中断现有服务
3. **团队学习**：逐步掌握 Rust，降低学习曲线
4. **投资回报**：优先替换瓶颈，快速看到收益

### 12.2 为什么选择 gRPC 而非 HTTP？

1. **性能**：Protocol Buffers 比 JSON 快 3-5 倍
2. **类型安全**：强类型契约，减少运行时错误
3. **生态**：gRPC 支持流式、双向通信
4. **成熟**：业内广泛使用，工具链完善

### 12.3 为什么保留 Python LLM 调用？

1. **生态成熟**：LangChain/LlamaIndex 生态完善
2. **维护成本**：Rust ML 生态仍在发展中
3. **性能瓶颈不在这里**：LLM 调用延迟主要在网络，不在语言
4. **风险**：重写可能引入兼容性问题

---

**文档结束**
