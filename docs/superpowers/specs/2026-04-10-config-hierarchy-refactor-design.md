# 配置系统层级重构设计文档

**日期**: 2026-04-10  
**状态**: 待审核  
**作者**: AI Assistant

---

## 1. 背景与目标

### 1.1 现状问题

当前 `backend/src/config/` 目录存在以下问题：

| 问题 | 描述 | 影响 |
|------|------|------|
| 职责混乱 | 配置模块、版本管理、事件定义、业务规则全部平铺在同一目录 | 新开发者难以理解各文件职责 |
| 粒度不均 | `rag_settings.py` 47 个字段，`log_settings.py` 仅 2 个字段 | 大文件难以维护，小文件过度拆分 |
| 缺乏层级 | 所有配置文件平铺，没有按功能域分组 | 前端配置树分类不直观 |
| `.env.dev.example` 过时 | 缺少约 45 个配置项 | 新开发者无法按文档上手 |
| 前端缺失文件 | `ConfigVersionSelector.module.scss` 和 `SystemConfigPage.module.scss` 不存在 | 前端构建可能失败 |

### 1.2 重构目标

1. **一看就懂**：目录名直白，不需要猜
2. **最多 2 级**：避免过深嵌套
3. **前端对应**：后端目录结构 = 前端配置树结构
4. **向后兼容**：ConfigManager 版本快照格式不变

---

## 2. 目标目录结构

```
backend/src/config/
│
├── core/                          # 配置系统核心（基础设施）
│   ├── manager.py                 # 配置管理器（版本控制/回滚）
│   ├── repository.py              # 配置存储（JSON 文件读写）
│   └── events.py                  # 配置变更事件
│
├── modules/                       # 配置模块（所有可配置项）
│   │
│   ├── app.py                     # 应用基础（名称/端口/调试）
│   ├── logging.py                 # 日志（级别/路径）
│   ├── paths.py                   # 路径（数据目录/存储目录）
│   │
│   ├── models/                    # AI 模型配置
│   │   ├── llm.py                 # LLM 模型（qwen-plus/turbo 等）
│   │   ├── embedding.py           # Embedding 模型
│   │   └── ml_scoring.py          # ML 评分模型
│   │
│   └── rag/                       # RAG 知识库配置
│       ├── core.py                # RAG 核心（缓存/监控/通用参数）
│       ├── retrieval.py           # 检索配置（BM25/向量/融合/重排序）
│       ├── chunking.py            # 分块配置（语义分块/章节分块）
│       ├── vector_store.py        # 向量库配置（Chroma/连接参数）
│       ├── pageindex.py           # 知识图谱增强（PageIndex）
│       └── pipeline.py            # 导入流水线（解析/元数据提取/持久化）
│
├── rules/                         # 业务规则（不可运行时修改）
│   ├── rules.py                   # 规则加载器
│   └── rules.json                 # 规则数据
│
└── __init__.py                    # 聚合入口（导出 Settings 单例）
```

---

## 3. 前端配置树映射

后端目录结构直接映射为前端配置树：

```
系统配置
├── 📦 应用设置
│   ├── 基础配置 (app.py)
│   ├── 日志配置 (logging.py)
│   └── 路径配置 (paths.py)
│
├── 🤖 AI 模型
│   ├── LLM 模型 (llm.py)
│   ├── Embedding 模型 (embedding.py)
│   └── ML 评分模型 (ml_scoring.py)
│
├── 📚 RAG 知识库
│   ├── 核心设置 (core.py)
│   ├── 检索配置 (retrieval.py)
│   ├── 分块配置 (chunking.py)
│   ├── 向量库 (vector_store.py)
│   ├── 知识图谱 (pageindex.py)
│   └── 导入流水线 (pipeline.py)
│
└── ⚙️ 业务规则（只读）
    └── 规则定义 (rules.json)
```

---

## 4. 文件迁移对照表

### 4.1 配置基础设施

| 原文件 | 新位置 | 变更 |
|--------|--------|------|
| `config_manager.py` | `core/manager.py` | 重命名 |
| `config_repository.py` | `core/repository.py` | 重命名 |
| `config_events.py` | `core/events.py` | 重命名 |

### 4.2 配置模块

| 原文件 | 新位置 | 变更 |
|--------|--------|------|
| `app_settings.py` | `modules/app.py` | 重命名 |
| `log_settings.py` | `modules/logging.py` | 重命名 |
| `path_settings.py` | `modules/paths.py` | 重命名 |
| `model_settings.py` | `modules/models/llm.py` | 移动 + 重命名 |
| `embedding_settings.py` | `modules/models/embedding.py` | 移动 + 重命名 |
| `ml_scoring_settings.py` | `modules/models/ml_scoring.py` | 移动 + 重命名 |
| `vector_store_settings.py` | `modules/rag/vector_store.py` | 移动 + 重命名 |
| `semantic_splitter_settings.py` | `modules/rag/chunking.py` | 移动 + 合并 |
| `pageindex_settings.py` | `modules/rag/pageindex.py` | 移动 + 重命名 |
| `query_fusion_settings.py` | `modules/rag/retrieval.py` | 移动 + 合并 |

### 4.3 RAG 核心拆分

| 原文件 | 新位置 | 变更 |
|--------|--------|------|
| `rag_settings.py` (部分) | `modules/rag/core.py` | 拆分：缓存/监控/通用 |
| `rag_settings.py` (部分) | `modules/rag/retrieval.py` | 拆分：检索/融合/重排序 |
| `rag_settings.py` (部分) | `modules/rag/chunking.py` | 拆分：分块参数 |
| `rag_settings.py` (部分) | `modules/rag/pipeline.py` | 拆分：流水线配置 |

### 4.4 业务规则

| 原文件 | 新位置 | 变更 |
|--------|--------|------|
| `rules.py` | `rules/rules.py` | 移动 |
| `rules.json` | `rules/rules.json` | 移动 |

---

## 5. `rag_settings.py` 拆分方案

原文件 47 个字段，按职责拆分为 4 个文件：

### 5.1 `modules/rag/core.py` — RAG 核心设置 (~10 字段)

```python
class RagCoreSettings(BaseSettings):
    """RAG 核心配置：缓存、监控、通用开关"""
    
    # 缓存
    rag_cache_enabled: bool
    rag_cache_max_size: int
    rag_cache_ttl: int
    
    # 监控
    rag_monitoring_enabled: bool
    rag_monitoring_interval: int
    
    # 通用
    rag_enabled: bool
    rag_default_top_k: int
    rag_search_mode: str  # "hybrid" / "vector" / "bm25"
```

### 5.2 `modules/rag/retrieval.py` — 检索配置 (~15 字段)

```python
class RagRetrievalSettings(BaseSettings):
    """检索配置：BM25/向量/融合/重排序/查询路由"""
    
    # BM25
    rag_hybrid_bm25_top_k: int
    rag_hybrid_bm25_weight: float
    rag_search_bm25_weight: float
    bm25_scale_factor: float
    
    # 向量
    rag_hybrid_vector_top_k: int
    rag_hybrid_vector_weight: float
    rag_vector_base_threshold: float
    
    # 融合
    rag_hybrid_merge_mode: str
    rag_relative_cutoff_ratio: float
    fusion_enabled: bool
    fusion_normalize: bool
    
    # 重排序
    rag_reranker_enabled: bool
    rag_reranker_model: str
    rag_reranker_initial_k: int
    rag_reranker_final_k: int
    
    # 查询路由
    query_router_enabled: bool
    query_router_model: str
    query_router_confidence_threshold: float
```

### 5.3 `modules/rag/chunking.py` — 分块配置 (~8 字段)

```python
class RagChunkingSettings(BaseSettings):
    """分块配置：语义分块/章节分块"""
    
    # 基础分块
    rag_chunk_size: int
    rag_chunk_overlap: int
    rag_pdf_chunk_size: int
    rag_epub_chunk_target_size: int
    
    # 语义分块
    semantic_splitter_buffer_size: int
    semantic_splitter_breakpoint_threshold: float
    
    # 长章节分块
    semantic_splitter_chapter_max_size: int
    semantic_splitter_chapter_split_threshold: float
```

### 5.4 `modules/rag/pipeline.py` — 导入流水线配置 (~5 字段)

```python
class RagPipelineSettings(BaseSettings):
    """导入流水线：解析/元数据提取/持久化/分层生成"""
    
    # 解析并发
    rag_vl_max_workers: int
    rag_upload_max_concurrent_tasks: int
    
    # 元数据提取
    rag_metadata_extraction_concurrency: int
    
    # 自动持久化
    rag_auto_persist_enabled: bool
    rag_auto_persist_interval: int
    
    # 分层内容生成
    rag_layered_content_enabled: bool
    rag_layered_content_batch_size: int
    rag_layered_content_max_concurrency: int
```

---

## 6. `__init__.py` 聚合逻辑

```python
"""配置系统聚合入口

通过多重继承将所有 Settings 子类合并为统一的 Settings 类。
"""

from pydantic_settings import BaseSettings

# 配置基础设施（不继承，独立使用）
# from .core.manager import ConfigManager
# from .core.repository import ConfigRepository
# from .core.events import ConfigChangedEvent

# 配置模块
from .modules.app import AppSettings
from .modules.logging import LogSettings
from .modules.paths import PathSettings
from .modules.models.llm import ModelSettings
from .modules.models.embedding import EmbeddingSettings
from .modules.models.ml_scoring import MLScoringSettings
from .modules.rag.core import RagCoreSettings
from .modules.rag.retrieval import RagRetrievalSettings
from .modules.rag.chunking import RagChunkingSettings
from .modules.rag.vector_store import VectorStoreSettings
from .modules.rag.pageindex import PageIndexSettings
from .modules.rag.pipeline import RagPipelineSettings


class Settings(
    AppSettings,
    LogSettings,
    PathSettings,
    ModelSettings,
    EmbeddingSettings,
    MLScoringSettings,
    RagCoreSettings,
    RagRetrievalSettings,
    RagChunkingSettings,
    VectorStoreSettings,
    PageIndexSettings,
    RagPipelineSettings,
):
    """统一配置类，通过多重继承聚合所有配置模块"""
    pass


# 单例
settings = Settings()

# 业务规则（独立单例）
from .rules.rules import rules

__all__ = ["settings", "rules"]
```

---

## 7. 前端改动清单

### 7.1 缺失文件补全

| 文件 | 状态 | 操作 |
|------|------|------|
| `frontend/src/components/config/ConfigVersionSelector.module.scss` | 缺失 | 创建 |
| `frontend/src/pages/SystemConfigPage.module.scss` | 缺失 | 创建 |

### 7.2 配置分类映射

前端 `SystemConfigPage` 的分类树需与后端目录对应：

```typescript
// 分类 key 映射
const CATEGORY_MAP = {
  'app': '应用设置',
  'logging': '日志配置',
  'paths': '路径配置',
  'models.llm': 'LLM 模型',
  'models.embedding': 'Embedding 模型',
  'models.ml_scoring': 'ML 评分模型',
  'rag.core': 'RAG 核心设置',
  'rag.retrieval': '检索配置',
  'rag.chunking': '分块配置',
  'rag.vector_store': '向量库',
  'rag.pageindex': '知识图谱',
  'rag.pipeline': '导入流水线',
  'rules': '业务规则',
};
```

### 7.3 ConfigController 适配

后端 `ConfigController` 返回的配置字段需包含 `category` 元数据，用于前端分类：

```python
class ConfigFieldMetadata(BaseModel):
    key: str
    value: Any
    type: str  # "bool" / "int" / "float" / "str" / "dict" / "list"
    category: str  # "app" / "rag.retrieval" / "models.llm" 等
    description: str
    env_var: str
```

---

## 8. 向后兼容策略

### 8.1 ConfigManager 版本快照

- 现有版本快照（`data/configs/versions/`）保持原格式
- 新快照使用新字段名（带 `category` 元数据）
- 回滚时自动转换旧格式到新格式

### 8.2 环境变量名不变

所有环境变量名（如 `RAG_HYBRID_BM25_TOP_K`）保持不变，仅改变 Python 文件位置。

### 8.3 API 端点不变

`/api/v1/config` 等端点保持原样，仅响应格式增加 `category` 字段。

---

## 9. 实施步骤

### Phase 1: 后端文件迁移
1. 创建新目录结构
2. 移动并重命名文件
3. 更新所有导入路径
4. 拆分 `rag_settings.py`
5. 更新 `__init__.py` 聚合逻辑

### Phase 2: 前端适配
1. 创建缺失的 SCSS 文件
2. 更新配置分类映射
3. 适配 ConfigController 返回格式

### Phase 3: 修复已知 Bug
1. 修复 `age_filter.py` 导入路径
2. 补全 `.env.dev.example`
3. 补全 `rules.json` 的 `metadata` 部分
4. 修复 `reload_settings()` 缓存同步
5. 修复 ConfigController 访问私有属性

### Phase 4: 验证
1. 运行后端测试
2. 运行前端构建
3. 手动验证配置页面功能

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 导入路径遗漏 | 运行时 ImportError | 全局搜索旧路径，确保无遗漏 |
| ConfigManager 快照不兼容 | 回滚失败 | 编写格式转换逻辑 |
| 前端分类映射错误 | 配置项显示错乱 | 编写单元测试验证映射 |
| `.env.dev.example` 遗漏 | 新开发者无法上手 | 脚本自动生成 |
