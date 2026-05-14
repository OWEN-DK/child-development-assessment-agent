# ADR-001：PipelineCompiler 与节点执行器技术选型

> 日期：2026-05-14（v3 更新：2026-05-14）
> 状态：**已决定**
> 决策目标：**最低延迟 + 最佳体验**，按组件特性选择语言

---

## 决策

**采用"Python 主体 + Rust 热点"混合架构**：

- **编排框架 + 23 个 I/O 密集型节点**：Python（asyncio）
- **5 个 CPU 密集型热点**：Rust（PyO3 进程内调用）
- **渐进式策略**：先用纯 Python 全部跑通，Phase 8 后 profiling 验证再决定哪些用 Rust 重写

---

## 逐组件技术选型

### 编排框架：Python

| 组件 | 推荐 | 理由 |
|------|------|------|
| PipelineCompiler | **Python** | 拓扑排序/条件边/降级链均 <5ms，asyncio.gather 并行域管道已足够。瓶颈在 LLM API（500-2000ms），不在调度框架 |
| NodeRegistry | **Python** | 字典查找，<0.01ms |
| 配置合并（L0-L3） | **Python** | dict merge，<1ms |
| 条件边求值 | **Python** | if-else 判断，<0.1ms |
| 降级链执行 | **Python** | 异常捕获 + 策略路由，<1ms |

**理由**：编排框架的 CPU 开销占总延迟 < 0.5%。即使 Rust 快 100x，绝对值仅省 ~5ms，对 P95 无可观测影响。

### 23 个 I/O 密集型节点：Python

| 类别 | 节点 | 推荐 | 理由 |
|------|------|------|------|
| **查询理解（7个）** | query_rewrite, synonym_expand, query_decompose, term_normalize, intent_classify, stopword_filter, query_expand | **Python** | 6/7 为 LLM API 调用（500-2000ms），语言对延迟无影响。stopword_filter 为正则匹配但数据量小（单条查询） |
| **检索策略（4个）** | bm25_search, vector_search, hybrid_search, multimodal_search | **Python** | 外部存储调用（Chroma/ES/Milvus SDK），I/O 等待占 95%+ |
| **质量增强（3个）** | rerank, hallucination_check, citation_verify | **Python** | LLM API 调用，延迟由 API 决定 |
| **聚合层（3个）** | query_analyzer, domain_dispatch, unified_generate | **Python** | LLM API 调用 + asyncio.gather 并行分发 |
| **性能优化（2个）** | semantic_cache, rate_limiter | **Python** | Redis/内存 I/O + 轻量计算（<1ms） |
| **答案合成（1个）** | structured_output | **Python** | LLM API 调用 + json-repair 解析 |
| **安全合规（2个）** | content_audit | **Python** | LLM API 调用（规则模式为轻量正则） |

### 5 个 CPU 密集型热点：Python → Rust（渐进式）

以下节点在**大数据量**场景下可能成为瓶颈，先用 Python 实现，profiling 后按需用 Rust + PyO3 重写：

| 节点 | 当前方案 | Rust 候选 | 触发条件 | 预期收益 |
|------|---------|----------|---------|---------|
| **dedup**（MinHash 去重） | `datasketch` 库 | 自研 MinHash + PyO3 | 候选集 > 200 条时 profiling 显示 > 50ms | 5-10x 加速 |
| **cross_dedup**（跨域去重） | `datasketch` 库 | 同 dedup | 多域合并后候选集 > 500 条 | 5-10x 加速 |
| **result_fusion**（RRF 分数融合） | Python 排序 + 加权 | Rust 排序 + PyO3 | 多分支融合，候选集 > 500 条 | 3-5x 加速 |
| **cross_fusion**（跨域融合） | Python 排序 + 加权 | 同 result_fusion | 3+ 域合并，总候选 > 1000 条 | 3-5x 加速 |
| **pii_mask**（PII 脱敏） | Python `re` 模块 | Rust `regex` crate + PyO3 | 批量文档处理（知识库索引时） | 5-10x 加速 |

**额外热点（非节点，但可用 Rust 优化）**：

| 组件 | 当前方案 | Rust 候选 | 触发条件 |
|------|---------|----------|---------|
| BM25 独立索引评分 | `rank_bm25` 库 | `tantivy`（Rust 全文搜索引擎） | 文档量 > 10 万，BM25 检索延迟 > 100ms |
| 文档分块引擎 | Python 字符串切分 | Rust 文本处理 | 批量索引吞吐 < 100 chunk/s |

---

## 为什么不选其他方案

### 不选纯 Rust

- LLM 生态缺失（DashScope/OpenAI/Anthropic 无 Rust SDK），所有 LLM 调用必须自行封装 HTTP
- 跨语言通信开销：Rust ↔ Python 的 PyO3 调用虽是进程内，但序列化/反序列化仍有成本
- 开发周期长：Rust 编译慢 + 类型系统严格 = 迭代速度降低 3-5x
- **CPU 密集型任务仅占总延迟 < 5%**，Rust 的性能优势被 I/O 稀释

### 不选纯 Java

- 跨语言通信：Java ↔ Python 需要 gRPC/HTTP（非进程内），每调用增加 1-5ms
- LLM 生态弱：Python 的 LangChain/LlamaIndex 在 Java 中无等价物
- 部署复杂度：需要维护 JVM + Python 双运行时
- GraalVM Native Image 可缓解启动问题，但无法解决跨语言通信开销

### 不选 LangGraph

- 域管道并发执行需要自定义实现（LangGraph 不支持真正的多子图并行）
- 降级路径需要在节点执行器内部实现（LangGraph 无原生降级概念）
- StateGraph 的 checkpoint 机制对管道场景是过度设计
- 项目已决定不继承原 `backend/` 的 RAG 查询流水线，与 LangGraph 的继承关系已断裂

---

## PyO3 集成方案

### 构建方式

```
rag-platform/
├── backend/
│   ├── src/
│   │   └── core/
│   │       └── pipeline/
│   │           └── nodes/
│   │               └── ...          # Python 节点执行器
│   └── rust/                        # Rust 热点模块
│       ├── Cargo.toml
│       ├── src/
│       │   ├── lib.rs
│       │   ├── minhash.rs           # MinHash 去重
│       │   ├── rrf.rs               # RRF 分数融合
│       │   ├── bm25.rs              # BM25 评分
│       │   ├── pii_regex.rs         # PII 正则匹配
│       │   └── chunker.rs           # 文档分块
│       └── pyproject.toml           # maturin 构建配置
```

### 调用方式

```python
# Python 节点执行器中调用 Rust 模块
try:
    from rag_platform_rust import minhash_dedup, rrf_fusion, bm25_score
    USE_RUST = True
except ImportError:
    USE_RUST = False  # 回退到纯 Python 实现

class DedupExecutor(BaseNodeExecutor):
    async def execute(self, context: NodeContext) -> NodeResult:
        candidates = context.input_data
        if USE_RUST and len(candidates) > 200:
            # 大数据量时用 Rust 加速
            deduped = minhash_dedup(candidates, threshold=0.85)
        else:
            # 小数据量用 Python（启动快，无 FFI 开销）
            deduped = python_minhash_dedup(candidates, threshold=0.85)
        return NodeResult(output=deduped)
```

### 渐进式策略

| 阶段 | 动作 |
|------|------|
| Phase 3（一期） | 全部 28 个节点用 Python 实现，跑通闭环 |
| Phase 8（二期） | profiling 识别热点，确认哪些节点 CPU 占比 > 10% |
| Phase 8+ | 对确认的热点用 Rust + PyO3 重写，保留 Python 回退路径 |

---

## 性能预估

| 场景 | 纯 Python | Python + Rust 热点 | 目标 |
|------|-----------|-------------------|------|
| 单域 P95 | ~800ms | ~750ms | < 3000ms |
| 3 域 P95 | ~1200ms | ~1100ms | < 5000ms |
| 编译耗时 | ~5ms | ~5ms | < 100ms |
| MinHash 去重（500 条） | ~50ms | ~5ms | — |
| RRF 融合（1000 条） | ~30ms | ~8ms | — |

**结论**：Python 方案已满足所有性能目标。Rust 热点是锦上添花，非必须。

---

## 后果

- PipelineCompiler 用 Python 实现，`asyncio.gather` 并行域管道
- 28 种节点执行器全部先用 Python 实现
- `backend/rust/` 目录预留给 Rust 热点模块（Phase 8+ 启用）
- Python 节点执行器中预留 `USE_RUST` 开关，支持渐进式切换
- 不引入 Java 运行时依赖

---

## 变更历史

| 日期 | 变更 |
|------|------|
| 2026-05-14 | 初始创建：选定纯 Python DAG |
| 2026-05-14 | v2 更新：开放 Python/Java/Rust 选型，增加性能对比矩阵 |
| 2026-05-14 | v3 更新：决定"Python 主体 + Rust 热点"混合架构，逐组件技术选型，状态改为"已决定" |
