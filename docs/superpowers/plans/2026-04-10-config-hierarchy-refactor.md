# 配置系统层级重构实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构配置系统目录结构，实现清晰的层级划分，修复已知 Bug，补全前端缺失文件。

**Architecture:** 将平铺的配置文件按功能域分组为 `core/`（基础设施）、`modules/`（配置模块）、`rules/`（业务规则）三个子目录，拆分臃肿的 `rag_settings.py`，更新所有导入路径，补全前端缺失文件。

**Tech Stack:** Python 3.13, Pydantic Settings, FastAPI, React 19, TypeScript, SCSS Module

---

## Chunk 1: 后端目录重组与文件迁移

### 文件结构总览

**创建的新目录：**
- `backend/src/config/core/` — 配置基础设施
- `backend/src/config/modules/` — 配置模块
- `backend/src/config/modules/models/` — AI 模型配置
- `backend/src/config/modules/rag/` — RAG 知识库配置
- `backend/src/config/rules/` — 业务规则

**移动的文件：**
| 原文件 | 新位置 |
|--------|--------|
| `config_manager.py` | `core/manager.py` |
| `config_repository.py` | `core/repository.py` |
| `config_events.py` | `core/events.py` |
| `app_settings.py` | `modules/app.py` |
| `log_settings.py` | `modules/logging.py` |
| `path_settings.py` | `modules/paths.py` |
| `model_settings.py` | `modules/models/llm.py` |
| `embedding_settings.py` | `modules/models/embedding.py` |
| `ml_scoring_settings.py` | `modules/models/ml_scoring.py` |
| `vector_store_settings.py` | `modules/rag/vector_store.py` |
| `semantic_splitter_settings.py` | `modules/rag/chunking.py` |
| `pageindex_settings.py` | `modules/rag/pageindex.py` |
| `query_fusion_settings.py` | `modules/rag/retrieval.py` |
| `rules.py` | `rules/rules.py` |
| `rules.json` | `rules/rules.json` |

**删除的文件：**
- `rag_settings.py`（拆分为 4 个文件）

**新增的文件：**
- `modules/rag/core.py` — RAG 核心设置
- `modules/rag/pipeline.py` — RAG 导入流水线设置
- `modules/rag/__init__.py` — RAG 模块聚合
- `modules/models/__init__.py` — 模型模块聚合
- `modules/__init__.py` — 配置模块聚合
- `core/__init__.py` — 核心模块聚合
- `rules/__init__.py` — 规则模块聚合

---

### Task 1: 创建目录结构与 `__init__.py` 文件

**Files:**
- Create: `backend/src/config/core/__init__.py`
- Create: `backend/src/config/modules/__init__.py`
- Create: `backend/src/config/modules/models/__init__.py`
- Create: `backend/src/config/modules/rag/__init__.py`
- Create: `backend/src/config/rules/__init__.py`

- [ ] **Step 1: 创建所有子目录和 `__init__.py` 文件**

```bash
cd backend/src/config
mkdir -p core modules/models modules/rag rules
touch core/__init__.py modules/__init__.py modules/models/__init__.py modules/rag/__init__.py rules/__init__.py
```

---

### Task 2: 移动配置基础设施文件

**Files:**
- Move: `config_manager.py` → `core/manager.py`
- Move: `config_repository.py` → `core/repository.py`
- Move: `config_events.py` → `core/events.py`

- [ ] **Step 1: 移动文件并重命名**

```bash
cd backend/src/config
mv config_manager.py core/manager.py
mv config_repository.py core/repository.py
mv config_events.py core/events.py
```

- [ ] **Step 2: 更新 `core/manager.py` 中的导入路径**

修改前：
```python
from src.config.config_repository import JsonConfigRepository
from src.config.config_events import ConfigChangedEvent, ConfigRollbackEvent, ConfigResetEvent
```

修改后：
```python
from src.config.core.repository import JsonConfigRepository
from src.config.core.events import ConfigChangedEvent, ConfigRollbackEvent, ConfigResetEvent
```

- [ ] **Step 3: 更新 `core/repository.py` 中的导入路径（如有）**

检查 `core/repository.py` 是否有导入其他配置模块的路径，如有则更新。

---

### Task 3: 移动基础配置模块

**Files:**
- Move: `app_settings.py` → `modules/app.py`
- Move: `log_settings.py` → `modules/logging.py`
- Move: `path_settings.py` → `modules/paths.py`

- [ ] **Step 1: 移动文件并重命名**

```bash
cd backend/src/config
mv app_settings.py modules/app.py
mv log_settings.py modules/logging.py
mv path_settings.py modules/paths.py
```

- [ ] **Step 2: 检查并更新导入路径**

检查这 3 个文件是否导入了其他配置模块，如有则更新为新路径。

---

### Task 4: 移动 AI 模型配置模块

**Files:**
- Move: `model_settings.py` → `modules/models/llm.py`
- Move: `embedding_settings.py` → `modules/models/embedding.py`
- Move: `ml_scoring_settings.py` → `modules/models/ml_scoring.py`

- [ ] **Step 1: 移动文件并重命名**

```bash
cd backend/src/config
mv model_settings.py modules/models/llm.py
mv embedding_settings.py modules/models/embedding.py
mv ml_scoring_settings.py modules/models/ml_scoring.py
```

- [ ] **Step 2: 检查并更新导入路径**

检查这 3 个文件是否导入了其他配置模块，如有则更新为新路径。

---

### Task 5: 移动 RAG 相关配置模块

**Files:**
- Move: `vector_store_settings.py` → `modules/rag/vector_store.py`
- Move: `semantic_splitter_settings.py` → `modules/rag/chunking.py`
- Move: `pageindex_settings.py` → `modules/rag/pageindex.py`
- Move: `query_fusion_settings.py` → `modules/rag/retrieval.py`

- [ ] **Step 1: 移动文件并重命名**

```bash
cd backend/src/config
mv vector_store_settings.py modules/rag/vector_store.py
mv semantic_splitter_settings.py modules/rag/chunking.py
mv pageindex_settings.py modules/rag/pageindex.py
mv query_fusion_settings.py modules/rag/retrieval.py
```

- [ ] **Step 2: 检查并更新导入路径**

检查这 4 个文件是否导入了其他配置模块，如有则更新为新路径。

---

### Task 6: 移动业务规则文件

**Files:**
- Move: `rules.py` → `rules/rules.py`
- Move: `rules.json` → `rules/rules.json`

- [ ] **Step 1: 移动文件**

```bash
cd backend/src/config
mv rules.py rules/rules.py
mv rules.json rules/rules.json
```

- [ ] **Step 2: 更新 `rules/rules.py` 中的路径引用**

修改前：
```python
RULES_JSON_PATH = Path(__file__).parent / "rules.json"
```

保持不变（因为 `rules.json` 在同一目录）。

---

### Task 7: 拆分 `rag_settings.py`

**Files:**
- Read: `rag_settings.py` (原文件，需在移动前读取)
- Create: `modules/rag/core.py`
- Create: `modules/rag/pipeline.py`
- Modify: `modules/rag/retrieval.py` (原 `query_fusion_settings.py`)
- Modify: `modules/rag/chunking.py` (原 `semantic_splitter_settings.py`)
- Delete: `rag_settings.py` (原文件)

- [ ] **Step 1: 读取原 `rag_settings.py` 内容**

原文件包含约 210 行，212 个字段。需在移动前完整读取内容。

- [ ] **Step 2: 创建 `modules/rag/core.py`**

从原 `rag_settings.py` 提取以下字段（完整代码）：

```python
"""RAG 核心配置：缓存、监控、通用开关"""

from pydantic import Field
from pydantic_settings import BaseSettings


class RagCoreSettings(BaseSettings):
    """RAG 核心配置"""

    # 通用开关
    rag_enabled: bool = Field(default=True, validation_alias="RAG_ENABLED", description="是否启用 RAG 系统")
    rag_default_top_k: int = Field(default=10, validation_alias="RAG_DEFAULT_TOP_K", description="默认返回结果数")
    rag_search_mode: str = Field(default="hybrid", validation_alias="RAG_SEARCH_MODE", description="搜索模式：hybrid/vector/bm25")

    # 缓存配置
    rag_cache_enabled: bool = Field(default=True, validation_alias="RAG_CACHE_ENABLED", description="是否启用缓存")
    rag_cache_max_size: int = Field(default=1000, validation_alias="RAG_CACHE_MAX_SIZE", description="缓存最大条目数")
    rag_cache_ttl_seconds: int = Field(default=3600, validation_alias="RAG_CACHE_TTL_SECONDS", description="缓存过期时间（秒）")

    # 监控配置
    rag_monitoring_enabled: bool = Field(default=True, validation_alias="RAG_MONITORING_ENABLED", description="是否启用监控")
    rag_monitoring_log_level: str = Field(default="INFO", validation_alias="RAG_MONITORING_LOG_LEVEL", description="监控日志级别")
    rag_monitoring_metrics_interval: int = Field(default=60, validation_alias="RAG_MONITORING_METRICS_INTERVAL", description="指标采集间隔（秒）")

    class Config:
        env_file = ".env.dev"
        env_file_encoding = "utf-8"
```

- [ ] **Step 3: 创建 `modules/rag/pipeline.py`**

从原 `rag_settings.py` 提取以下字段（完整代码）：

```python
"""RAG 导入流水线配置：解析/元数据提取/持久化/分层生成"""

from pydantic import Field
from pydantic_settings import BaseSettings


class RagPipelineSettings(BaseSettings):
    """RAG 导入流水线配置"""

    # 解析并发
    rag_vl_max_workers: int = Field(default=2, validation_alias="RAG_VL_MAX_WORKERS", description="VL 解析器最大并发线程数")
    rag_upload_max_concurrent_tasks: int = Field(default=5, validation_alias="RAG_UPLOAD_MAX_CONCURRENT_TASKS", description="文档上传最大并发任务数")
    rag_temp_upload_dir: str = Field(default="./temp_uploads", validation_alias="RAG_TEMP_UPLOAD_DIR", description="临时上传文件存储目录")

    # 元数据提取
    rag_metadata_extraction_concurrency: int = Field(default=20, validation_alias="RAG_METADATA_EXTRACTION_CONCURRENCY", description="元数据提取最大并发数")

    # 自动持久化
    rag_auto_persist_enabled: bool = Field(default=True, validation_alias="RAG_AUTO_PERSIST_ENABLED", description="是否启用自动持久化")
    rag_auto_persist_interval: int = Field(default=300, validation_alias="RAG_AUTO_PERSIST_INTERVAL", description="自动持久化间隔（秒）")

    # 分层内容生成
    rag_layered_content_enabled: bool = Field(default=True, validation_alias="RAG_LAYERED_CONTENT_ENABLED", description="是否启用分层内容生成")
    rag_layered_content_enable_llm_generation: bool = Field(default=True, validation_alias="RAG_LAYERED_CONTENT_ENABLE_LLM_GENERATION", description="是否启用 LLM 生成")
    rag_layered_content_enable_local_fallback: bool = Field(default=True, validation_alias="RAG_LAYERED_CONTENT_ENABLE_LOCAL_FALLBACK", description="是否启用本地知识库兜底")
    rag_layered_content_l0_max_length: int = Field(default=100, validation_alias="RAG_LAYERED_CONTENT_L0_MAX_LENGTH", description="L0 摘要最大长度")
    rag_layered_content_l1_max_length: int = Field(default=500, validation_alias="RAG_LAYERED_CONTENT_L1_MAX_LENGTH", description="L1 概览最大长度")
    rag_layered_content_batch_size: int = Field(default=20, validation_alias="RAG_LAYERED_CONTENT_BATCH_SIZE", description="分层生成批次大小")
    rag_layered_content_large_batch_threshold: int = Field(default=1000, validation_alias="RAG_LAYERED_CONTENT_LARGE_BATCH_THRESHOLD", description="大批次阈值")
    rag_layered_content_large_batch_size: int = Field(default=10, validation_alias="RAG_LAYERED_CONTENT_LARGE_BATCH_SIZE", description="大批次处理时的批次大小")
    rag_layered_content_concurrency_limit: int = Field(default=8, validation_alias="RAG_LAYERED_CONTENT_CONCURRENCY_LIMIT", description="分层生成最大并发数")

    class Config:
        env_file = ".env.dev"
        env_file_encoding = "utf-8"
```

- [ ] **Step 4: 更新 `modules/rag/retrieval.py`**

在原 `query_fusion_settings.py` 基础上，从原 `rag_settings.py` 添加检索相关字段。完整代码：

```python
"""RAG 检索配置：BM25/向量融合、重排序、查询路由、年龄过滤"""

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Dict


class RagRetrievalSettings(BaseSettings):
    """RAG 检索配置"""

    # BM25 相关
    rag_hybrid_bm25_weight: float = Field(default=0.5, validation_alias="RAG_HYBRID_BM25_WEIGHT", description="混合检索 BM25 权重")
    rag_hybrid_bm25_top_k: int = Field(default=10, validation_alias="RAG_HYBRID_BM25_TOP_K", description="BM25 返回 Top K")
    bm25_scale_factor: float = Field(default=5, validation_alias="BM25_SCALE_FACTOR", description="BM25 分数缩放因子")

    # 向量相关
    rag_hybrid_vector_weight: float = Field(default=0.5, validation_alias="RAG_HYBRID_VECTOR_WEIGHT", description="混合检索向量权重")
    rag_hybrid_vector_top_k: int = Field(default=10, validation_alias="RAG_HYBRID_VECTOR_TOP_K", description="向量检索返回 Top K")
    rag_vector_base_threshold: float = Field(default=0.5, validation_alias="RAG_VECTOR_BASE_THRESHOLD", description="向量检索最低分数阈值")

    # 融合相关
    rag_hybrid_merge_mode: str = Field(default="OR", validation_alias="RAG_HYBRID_MERGE_MODE", description="合并模式：OR/AND")
    rag_hybrid_bm25_weight_dense: float = Field(default=0.7, validation_alias="RAG_HYBRID_BM25_WEIGHT_DENSE", description="密集场景 BM25 权重")
    rag_hybrid_vector_weight_dense: float = Field(default=0.3, validation_alias="RAG_HYBRID_VECTOR_WEIGHT_DENSE", description="密集场景向量权重")
    rag_hybrid_base_threshold: float = Field(default=0.1, validation_alias="RAG_HYBRID_BASE_THRESHOLD", description="混合检索最低分数阈值")
    rag_relative_cutoff_ratio: float = Field(default=0.3, validation_alias="RAG_RELATIVE_CUTOFF_RATIO", description="相对截断比例")
    hybrid_weights: Dict[str, float] = Field(
        default_factory=lambda: {"default": 0.5, "keyword_query": 0.7, "semantic_query": 0.3},
        description="不同查询类型的 BM25 权重"
    )

    # 搜索页面专用
    rag_search_bm25_weight: float = Field(default=0.5, validation_alias="RAG_SEARCH_BM25_WEIGHT", description="搜索页面 BM25 权重")
    rag_search_vector_weight: float = Field(default=0.5, validation_alias="RAG_SEARCH_VECTOR_WEIGHT", description="搜索页面向量权重")
    rag_search_no_match_vector_penalty: float = Field(default=0.5, validation_alias="RAG_SEARCH_NO_MATCH_VECTOR_PENALTY", description="无关键词匹配惩罚")
    rag_search_score_threshold_hybrid: float = Field(default=0.25, validation_alias="RAG_SEARCH_SCORE_THRESHOLD_HYBRID", description="搜索页面混合阈值")
    rag_search_score_threshold_vector: float = Field(default=0.25, validation_alias="RAG_SEARCH_SCORE_THRESHOLD_VECTOR", description="搜索页面向量阈值")
    rag_search_relative_cutoff_ratio: float = Field(default=0.5, validation_alias="RAG_SEARCH_RELATIVE_CUTOFF_RATIO", description="搜索页面截断比例")
    rag_search_min_similarity_threshold: float = Field(default=0.2, validation_alias="RAG_SEARCH_MIN_SIMILARITY_THRESHOLD", description="搜索页面最小相似度")

    # 重排序相关
    rag_reranker_model: str = Field(default="BAAI/bge-reranker-v2-m3", validation_alias="RAG_RERANKER_MODEL", description="重排序模型")
    rag_reranker_initial_k: int = Field(default=30, validation_alias="RAG_RERANKER_INITIAL_K", description="重排序前初始结果数")
    rag_reranker_final_k: int = Field(default=5, validation_alias="RAG_RERANKER_FINAL_K", description="重排序后最终返回数")

    # 查询路由相关
    rag_query_rewrite_enabled: bool = Field(default=True, validation_alias="RAG_QUERY_REWRITE_ENABLED", description="是否启用查询重写")
    query_router_llm_enabled: bool = Field(default=True, validation_alias="QUERY_ROUTER_LLM_ENABLED", description="查询路由 LLM 开关")
    query_router_confidence_threshold: float = Field(default=0.8, validation_alias="QUERY_ROUTER_CONFIDENCE_THRESHOLD", description="路由置信度阈值")
    query_router_llm_max_retries: int = Field(default=2, validation_alias="QUERY_ROUTER_LLM_MAX_RETRIES", description="路由 LLM 最大重试次数")

    # 年龄过滤相关
    rag_age_filter_strictness: float = Field(default=0.7, validation_alias="RAG_AGE_FILTER_STRICTNESS", description="年龄过滤严格程度")
    rag_age_filter_tolerance: int = Field(default=2, validation_alias="RAG_AGE_FILTER_TOLERANCE", description="年龄容忍范围（岁）")
    rag_age_fit_weight: float = Field(default=0.3, validation_alias="RAG_AGE_FIT_WEIGHT", description="年龄适配度权重")

    # 融合配置
    fusion_score_boost_for_pageindex: float = Field(default=1.2, validation_alias="FUSION_SCORE_BOOST_FOR_PAGEINDEX", description="PageIndex 分数提升")
    fusion_hybrid_supplement_limit: int = Field(default=5, validation_alias="FUSION_HYBRID_SUPPLEMENT_LIMIT", description="混合补充限制")
    fusion_dedup_normalize: bool = Field(default=True, validation_alias="FUSION_DEDUP_NORMALIZE", description="去重归一化")

    # 通用阈值
    rag_similarity_threshold: float = Field(default=0.7, validation_alias="RAG_SIMILARITY_THRESHOLD", description="相似度阈值")
    rag_min_result_count: int = Field(default=3, validation_alias="RAG_MIN_RESULT_COUNT", description="最小结果数量")
    rag_ocr_extraction_rate_threshold: float = Field(default=0.5, validation_alias="RAG_OCR_EXTRACTION_THRESHOLD", description="OCR 提取率阈值")
    rag_ocr_min_avg_length_threshold: int = Field(default=100, validation_alias="RAG_OCR_MIN_AVG_TEXT_LENGTH", description="OCR 平均长度阈值")

    class Config:
        env_file = ".env.dev"
        env_file_encoding = "utf-8"
```

- [ ] **Step 5: 更新 `modules/rag/chunking.py`**

在原 `semantic_splitter_settings.py` 基础上，从原 `rag_settings.py` 添加分块相关字段。完整代码：

```python
"""RAG 分块配置：基础分块、长章节分块、语义分块"""

from pydantic import Field
from pydantic_settings import BaseSettings


class RagChunkingSettings(BaseSettings):
    """RAG 分块配置"""

    # 基础分块
    rag_chunk_size: int = Field(default=1024, validation_alias="RAG_CHUNK_SIZE", description="默认分块大小（字符）")
    rag_chunk_overlap: int = Field(default=200, validation_alias="RAG_CHUNK_OVERLAP", description="分块重叠大小（字符）")
    rag_pdf_chunk_size: int = Field(default=1536, validation_alias="RAG_PDF_CHUNK_SIZE", description="PDF 分块大小（字符）")
    rag_epub_chunk_target_size: int = Field(default=1024, validation_alias="RAG_EPUB_CHUNK_TARGET_SIZE", description="EPUB 分块目标大小（字符）")

    # 长章节分块
    semantic_splitter_chapter_max_size: int = Field(default=3000, validation_alias="SEMANTIC_SPLITTER_CHAPTER_MAX_SIZE", description="长章节最大大小")
    semantic_splitter_chapter_split_threshold: int = Field(default=50, validation_alias="SEMANTIC_SPLITTER_CHAPTER_SPLIT_THRESHOLD", description="长章节分割阈值")

    class Config:
        env_file = ".env.dev"
        env_file_encoding = "utf-8"
```

- [ ] **Step 6: 删除原 `rag_settings.py`**

```bash
cd backend/src/config
rm rag_settings.py
```

---

### Task 8: 重写 `__init__.py` 聚合入口（原 `settings.py` 迁移）

**Files:**
- Modify: `__init__.py`（原 `settings.py` 重命名而来）
- Delete: `settings.py`（内容已迁移到 `__init__.py`）

- [ ] **Step 1: 将 `settings.py` 重命名为 `__init__.py`**

```bash
cd backend/src/config
mv settings.py __init__.py
```

- [ ] **Step 2: 重写 `__init__.py` 头部导入和 Settings 类**

```python
"""配置系统聚合入口

通过多重继承将所有 Settings 子类合并为统一的 Settings 类。
原 settings.py 内容已迁移至此文件。
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pydantic import Field
from pydantic_settings import SettingsConfigDict
from threading import RLock
import asyncio

# 可选导入 watchdog
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    Observer = None
    FileSystemEventHandler = object
    WATCHDOG_AVAILABLE = False

# 导入各个配置模块（新路径）
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

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent.parent.parent.resolve()


@dataclass
class ConfigFieldMetadata:
    key: str
    category: str
    description: str
    hot_reloadable: bool
    requires_restart: bool
    affected_components: list[str]
    field_type: str
    default_value: Any


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
    
    # 规则相关配置（合并到 rules.py 体系）
    rule_metadata_development_domains: List[str] = Field(
        default_factory=lambda: [
            "粗大动作", "精细动作", "认知能力", "语言发展", "社交情感", "感觉统合"
        ],
        description="儿童发展领域标签列表"
    )
    rule_metadata_age_patterns: List[str] = Field(
        default_factory=lambda: [
            r"(\d+)~(\d+)个月", r"(\d+)-(\d+)个月", r"适合(\d+)到(\d+)岁", 
            r"(\d+)岁左右", r"(\d+)月龄", r"(\d+)岁"
        ],
        description="规则提取年龄的正则表达式列表"
    )
    rule_metadata_difficulty_easy_threshold: int = Field(
        300,
        description="内容长度低于此值判定为简单难度"
    )
    rule_metadata_difficulty_hard_threshold: int = Field(
        1000,
        description="内容长度高于此值判定为困难难度"
    )

    def _infer_category(self, field_name: str) -> str:
        """根据字段名前缀自动推导分类"""
        if field_name.startswith(("rag_hybrid_", "rag_search_", "rag_cache_")):
            return "混合检索配置"
        elif field_name.startswith("model_"):
            return "模型设置"
        elif field_name.startswith("rag_reranker_"):
            return "重排序配置"
        elif field_name.startswith(("rag_chunk_", "semantic_splitter_")):
            return "分块配置"
        elif field_name.startswith("embedding_"):
            return "Embedding配置"
        elif field_name.startswith("pageindex_"):
            return "PageIndex配置"
        elif field_name.startswith("rag_"):
            return "RAG配置"
        elif field_name.startswith("ml_"):
            return "ML评分配置"
        elif field_name.startswith("query_router_") or field_name.startswith("fusion_"):
            return "查询与融合配置"
        elif field_name.startswith("rule_metadata_"):
            return "规则元数据配置"
        elif field_name.startswith("log_"):
            return "日志配置"
        elif field_name.startswith("data_dir") or field_name.startswith("rag_storage_dir"):
            return "路径配置"
        elif field_name.startswith("rule_validation_"):
            return "校验规则配置"
        elif field_name.startswith("rule_assessment_"):
            return "评估规则配置"
        elif field_name.startswith("rule_scoring_"):
            return "评分规则配置"
        elif field_name.startswith("rule_preprocessing_"):
            return "预处理规则配置"
        else:
            return "其他配置"

    def _is_hot_reloadable(self, field_name: str) -> bool:
        hot_reload_prefixes = (
            "rag_hybrid_", "rag_search_", "rag_cache_", "rag_reranker_",
            "rag_similarity_threshold", "rag_min_result_count",
            "rag_age_filter_", "query_router_", "fusion_",
            "rag_layered_content_", "bm25_scale_factor",
            "hybrid_weights", "rag_chunk_", "semantic_splitter_",
            "embedding_batch_size", "rule_",
        )
        cold_reload_prefixes = (
            "model_", "dashscope_api_key", "pageindex_",
            "rag_storage_dir", "data_dir", "log_",
            "vector_store_", "ml_scoring_model_path",
            "rag_upload_max_concurrent_tasks", "rag_temp_upload_dir",
            "rag_metadata_extraction_concurrency", "rag_vl_max_workers",
        )
        if field_name.startswith(hot_reload_prefixes):
            return True
        if field_name.startswith(cold_reload_prefixes):
            return False
        return True

    def _get_affected_components(self, field_name: str) -> list[str]:
        components = []
        if "hybrid" in field_name or "search" in field_name:
            components.append("混合检索引擎")
        if "reranker" in field_name:
            components.append("重排序器")
        if "chunk" in field_name or "splitter" in field_name:
            components.append("文档分块")
        if "embedding" in field_name:
            components.append("Embedding模型")
        if "cache" in field_name:
            components.append("缓存系统")
        if "age_filter" in field_name:
            components.append("年龄过滤")
        if "pageindex" in field_name:
            components.append("PageIndex服务")
        if "query_router" in field_name or "fusion" in field_name:
            components.append("查询路由与融合")
        if "layered_content" in field_name:
            components.append("分层内容生成")
        if not components:
            components.append("通用配置")
        return components

    def get_all_config_metadata(self) -> Dict[str, ConfigFieldMetadata]:
        metadata = {}
        for field_name, field_info in self.model_fields.items():
            category = self._infer_category(field_name)
            hot_reloadable = self._is_hot_reloadable(field_name)
            annotation = field_info.annotation
            type_name = annotation.__name__ if hasattr(annotation, '__name__') else str(annotation)
            metadata[field_name] = ConfigFieldMetadata(
                key=field_name,
                category=category,
                description=field_info.description or "",
                hot_reloadable=hot_reloadable,
                requires_restart=not hot_reloadable,
                affected_components=self._get_affected_components(field_name),
                field_type=type_name,
                default_value=field_info.default
            )
        return metadata

    @property
    def llm_models(self) -> Dict[str, str]:
        return {
            "report_generation": self.model_report_generation,
            "assessment": self.model_assessment,
            "validation": self.model_validation,
            "query_rewrite": self.model_query_rewrite,
            "metadata_extraction": self.model_metadata_extraction,
        }

    @property
    def rag_config(self) -> Dict[str, Any]:
        return {
            "hybrid_retrieval": {
                "bm25_weight": self.rag_hybrid_bm25_weight,
                "vector_weight": self.rag_hybrid_vector_weight,
                "merge_mode": self.rag_hybrid_merge_mode,
                "bm25_top_k": self.rag_hybrid_bm25_top_k,
                "vector_top_k": self.rag_hybrid_vector_top_k,
            },
            "cache": {
                "enabled": self.rag_cache_enabled,
                "max_size": self.rag_cache_max_size,
                "ttl_seconds": self.rag_cache_ttl_seconds,
            },
            "query_rewrite": {"enabled": self.rag_query_rewrite_enabled},
            "filters": {
                "similarity_threshold": self.rag_similarity_threshold,
                "min_result_count": self.rag_min_result_count,
            },
            "layered_content": {
                "enabled": self.rag_layered_content_enabled,
                "enable_llm_generation": self.rag_layered_content_enable_llm_generation,
                "enable_local_fallback": self.rag_layered_content_enable_local_fallback,
                "l0_max_length": self.rag_layered_content_l0_max_length,
                "l1_max_length": self.rag_layered_content_l1_max_length,
                "batch_size": self.rag_layered_content_batch_size,
                "large_batch_threshold": self.rag_layered_content_large_batch_threshold,
                "large_batch_size": self.rag_layered_content_large_batch_size,
                "concurrency_limit": self.rag_layered_content_concurrency_limit,
            }
        }

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env.dev"), env_file_encoding="utf-8", extra="ignore"
    )
```

- [ ] **Step 3: 添加配置实例管理和热重载逻辑**

```python
# 配置实例管理
_settings_instance = None
_lock = RLock()

def get_settings() -> Settings:
    """获取配置单例"""
    global _settings_instance
    if _settings_instance is None:
        with _lock:
            if _settings_instance is None:
                _settings_instance = Settings()
    return _settings_instance

def reload_settings() -> Settings:
    """重新加载配置并同步更新 ConfigManager 缓存
    
    实现失败回退机制：重载失败时返回原有配置实例
    通过公共方法同步缓存，不直接访问私有属性
    """
    global _settings_instance
    with _lock:
        try:
            new_settings = Settings()
            new_settings.model_validate(new_settings.model_dump())
            old_settings = _settings_instance
            _settings_instance = new_settings
            logger.info("配置重载成功")
            
            # 通过公共方法同步更新 ConfigManager 缓存
            from .core.manager import config_manager
            config_manager.sync_cache_from_settings(new_settings)
            
            # 对比变更并派发事件
            if old_settings:
                changed_fields = compare_config_changes(old_settings, new_settings)
                if changed_fields:
                    logger.info(f"配置变更字段: {list(changed_fields.keys())}")
                    
            return new_settings
        except Exception as e:
            logger.error(f"配置重载失败，保留原有配置: {e}")
            return _settings_instance if _settings_instance else Settings()

def compare_config_changes(old_settings: Settings, new_settings: Settings) -> Dict[str, tuple[Any, Any]]:
    """比较新旧配置的差异"""
    changes = {}
    for field_name in old_settings.model_fields.keys():
        old_value = getattr(old_settings, field_name)
        new_value = getattr(new_settings, field_name)
        if old_value != new_value:
            changes[field_name] = (old_value, new_value)
    return changes
```

- [ ] **Step 4: 添加文件系统监控和导出**

```python
# 文件系统监控实现
class ConfigFileChangeHandler(FileSystemEventHandler):
    """配置文件变更处理器"""
    def on_modified(self, event):
        if event.is_directory:
            return
        file_path = Path(event.src_path)
        if file_path.suffix in ('.py', '.env') and not file_path.name.startswith('__'):
            logger.info(f"检测到配置文件变更: {file_path}")
            reload_settings()

def start_config_watcher() -> Optional[Observer]:
    """启动配置文件监控"""
    if not WATCHDOG_AVAILABLE:
        logger.warning("watchdog 库未安装，配置热更新功能不可用")
        return None
    
    event_handler = ConfigFileChangeHandler()
    observer = Observer()
    config_dir = Path(__file__).parent
    observer.schedule(event_handler, str(config_dir), recursive=False)
    env_file = BASE_DIR / ".env.dev"
    if env_file.exists():
        observer.schedule(event_handler, str(env_file), recursive=False)
    observer.start()
    logger.info("配置文件监控已启动")
    return observer

# 初始化嵌入模型
def init_embedding_model():
    """初始化嵌入模型"""
    try:
        from llama_index.core import Settings as LlamaSettings
        from src.core.embedding import SafeDashScopeEmbedding
        
        LlamaSettings.embed_model = SafeDashScopeEmbedding(
            model_name=settings.embedding_model_name,
            api_key=settings.dashscope_api_key,
            embed_batch_size=settings.embedding_batch_size,
        )
        logger.info("LlamaIndex 嵌入模型初始化成功，使用模型: %s", settings.embedding_model_name)
    except Exception as e:
        logger.error(f"初始化嵌入模型失败: {e}")

# 自动初始化嵌入模型
init_embedding_model()

# 对外导出统一的 settings 实例
settings = get_settings()

# 业务规则（独立单例）
from .rules.rules import rules

# 配置基础设施（按需导入）
from .core.manager import ConfigManager, config_manager
from .core.repository import ConfigRepository, JsonConfigRepository
from .core.events import ConfigChangedEvent, ConfigRollbackEvent, ConfigResetEvent

__all__ = [
    "settings",
    "rules",
    "Settings",
    "get_settings",
    "reload_settings",
    "start_config_watcher",
    "ConfigFieldMetadata",
    "config_manager",
    "ConfigManager",
    "ConfigRepository",
    "JsonConfigRepository",
    "ConfigChangedEvent",
    "ConfigRollbackEvent",
    "ConfigResetEvent",
]
```

---

### Task 9: 更新所有外部导入路径

**Files:**
- 全局搜索并替换导入路径

- [ ] **Step 1: 全局搜索旧导入路径**

```bash
cd backend/src
grep -r "from src.config.config_manager import" --include="*.py"
grep -r "from src.config.config_repository import" --include="*.py"
grep -r "from src.config.config_events import" --include="*.py"
grep -r "from src.config.app_settings import" --include="*.py"
grep -r "from src.config.log_settings import" --include="*.py"
grep -r "from src.config.path_settings import" --include="*.py"
grep -r "from src.config.model_settings import" --include="*.py"
grep -r "from src.config.embedding_settings import" --include="*.py"
grep -r "from src.config.ml_scoring_settings import" --include="*.py"
grep -r "from src.config.vector_store_settings import" --include="*.py"
grep -r "from src.config.semantic_splitter_settings import" --include="*.py"
grep -r "from src.config.pageindex_settings import" --include="*.py"
grep -r "from src.config.query_fusion_settings import" --include="*.py"
grep -r "from src.config.rag_settings import" --include="*.py"
grep -r "from src.config.rules import" --include="*.py"
grep -r "from src.config import config_manager" --include="*.py"
```

- [ ] **Step 2: 批量替换为新路径**

| 旧导入 | 新导入 |
|--------|--------|
| `from src.config.config_manager import` | `from src.config.core.manager import` |
| `from src.config.config_repository import` | `from src.config.core.repository import` |
| `from src.config.config_events import` | `from src.config.core.events import` |
| `from src.config.app_settings import` | `from src.config.modules.app import` |
| `from src.config.log_settings import` | `from src.config.modules.logging import` |
| `from src.config.path_settings import` | `from src.config.modules.paths import` |
| `from src.config.model_settings import` | `from src.config.modules.models.llm import` |
| `from src.config.embedding_settings import` | `from src.config.modules.models.embedding import` |
| `from src.config.ml_scoring_settings import` | `from src.config.modules.models.ml_scoring import` |
| `from src.config.vector_store_settings import` | `from src.config.modules.rag.vector_store import` |
| `from src.config.semantic_splitter_settings import` | `from src.config.modules.rag.chunking import` |
| `from src.config.pageindex_settings import` | `from src.config.modules.rag.pageindex import` |
| `from src.config.query_fusion_settings import` | `from src.config.modules.rag.retrieval import` |
| `from src.config.rag_settings import` | `from src.config.modules.rag.core import`（或 `pipeline`/`retrieval`/`chunking`） |
| `from src.config.rules import` | `from src.config.rules.rules import` |

- [ ] **Step 3: 修复 `age_filter.py` 导入路径 Bug**

修改前：
```python
from backend.src.config import settings
```

修改后：
```python
from src.config import settings
```

---

### Task 10: 更新 ConfigController 导入路径并修复私有访问

**Files:**
- Modify: `backend/src/controller/config_controller.py`
- Modify: `backend/src/config/core/manager.py`（原 `config_manager.py`）

- [ ] **Step 1: 在 `core/manager.py` 中添加公共方法**

在 `ConfigManager` 类中新增两个公共方法，替代直接访问私有属性：

```python
def list_versions(self, limit: int = 50) -> list:
    """列出所有配置版本（公共方法，替代直接访问 _repository）"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(self._repository.list_versions(limit=limit))

def sync_cache_from_settings(self, new_settings) -> None:
    """从 Settings 实例同步缓存（公共方法，替代直接访问 _memory_cache）"""
    self._memory_cache.clear()
    for field_name, field_value in new_settings.model_dump().items():
        self._memory_cache[field_name] = field_value
    logger.info("ConfigManager 缓存已从 Settings 同步")
```

- [ ] **Step 2: 更新 ConfigController 导入路径**

修改前：
```python
from src.config.config_manager import config_manager
```

修改后：
```python
from src.config.core.manager import config_manager
```

- [ ] **Step 3: 修复直接访问私有属性问题**

修改 `config_controller.py` 第 115 行：

修改前：
```python
versions = await config_manager._repository.list_versions(limit=limit)
```

修改后：
```python
versions = config_manager.list_versions(limit=limit)
```

同时更新返回格式（因为 `list_versions()` 返回同步结果而非 awaitable）：

```python
@router.get("/versions")
async def list_versions(limit: int = 50):
    versions = config_manager.list_versions(limit=limit)
    active_version = config_manager.get_active_version()

    return [
        {
            "version_id": v["version_id"],
            "created_at": v["created_at"],
            "created_by": v.get("created_by", "system"),
            "description": v.get("description", ""),
            "is_active": v["version_id"] == active_version,
            "parent_version_id": v.get("parent_version_id"),
            "is_factory_reset": v.get("is_factory_reset", False)
        }
        for v in versions
    ]
```

---

### Task 10.5: 更新 DI 容器和 EventBus 相关导入

**Files:**
- Modify: `backend/src/core/di_container.py`
- Modify: `backend/src/core/event_bus.py`（如有导入配置模块）
- Modify: `backend/src/service/rag_test_manager.py`

- [ ] **Step 1: 更新 DI 容器导入路径**

`di_container.py` 中的导入修改：

修改前：
```python
from src.config import settings
```

修改后（保持不变，因为 `__init__.py` 仍然导出 `settings`）：
```python
from src.config import settings
```

- [ ] **Step 2: 更新 rag_test_manager.py 导入路径**

修改前：
```python
from src.config.config_manager import config_manager
```

修改后：
```python
from src.config.core.manager import config_manager
```

- [ ] **Step 3: 全局验证所有导入路径**

执行以下命令验证无遗漏：

```bash
cd backend/src
grep -r "from src\.config\.config_manager import" --include="*.py"
grep -r "from src\.config\.config_repository import" --include="*.py"
grep -r "from src\.config\.config_events import" --include="*.py"
grep -r "from src\.config\.rag_settings import" --include="*.py"
```

所有命令应返回空结果，表示旧路径已全部替换。

---

### Task 11: 补全 `rules.json` 的 `metadata` 部分

**Files:**
- Modify: `rules/rules.json`

- [ ] **Step 1: 添加 `metadata` 部分**

```json
{
  "validation": { ... },
  "assessment": { ... },
  "scoring": { ... },
  "preprocessing": { ... },
  "metadata": {
    "default_topics": ["感觉统合", "儿童发展"],
    "default_brain_regions": ["全脑"],
    "default_developmental_domains": ["粗大动作", "精细动作", "语言发展", "认知能力", "社交情感", "感觉统合"],
    "difficulty_levels": ["入门", "基础", "进阶", "挑战"]
  }
}
```

---

### Task 12: 补全 `.env.dev.example`

**Files:**
- Modify: `backend/.env.dev.example`

- [ ] **Step 1: 重写完整的 `.env.dev.example`**

对比 `.env.dev` 和 `.env.dev.example`，补全所有缺失项。完整内容如下：

```bash
# ============================================
# 应用基础配置
# ============================================
APP_NAME="Child Development Assessment Agent"    # 应用名称
APP_VERSION="0.1.0"                             # 应用版本号
DEBUG=True                                      # 是否开启调试模式
APP_HOST="127.0.0.1"                            # 服务监听地址
APP_PORT=8000                                   # 服务监听端口
APP_RELOAD=True                                 # 是否开启自动重载（开发环境使用）
ENVIRONMENT=development                         # 运行环境（development/production）

# ============================================
# 日志配置
# ============================================
LOG_LEVEL="INFO"                                # 日志输出级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）
LOG_FILE="logs/app.log"                         # 日志文件存储路径
LLAMA_INDEX_LOG_LEVEL=INFO                      # LlamaIndex 日志级别

# ============================================
# 模型配置
# ============================================
DASHSCOPE_API_KEY=""                            # 阿里云灵积（DashScope）API密钥
OPENAI_API_KEY=""                               # OpenAI API密钥（备用）
MODEL_REPORT_GENERATION="qwen3.5-plus"          # 报告生成模型
MODEL_ASSESSMENT="qwen3.5-plus"                 # 儿童发展评估模型
MODEL_VALIDATION="qwen3.5-turbo"                # 数据校验与标准化模型
MODEL_QUERY_REWRITE="qwen3-omni-flash"          # RAG查询重写模型
MODEL_METADATA_EXTRACTION="qwen3-omni-flash"    # 文档元数据提取模型
MODEL_VL_PARSING="qwen3-omni-flash"             # 视觉解析（扫描版PDF OCR）模型
MODEL_QUERY_CLASSIFICATION="qwen3-omni-flash"   # 查询分类模型
ML_SCORING_QWEN_MODEL="qwen3.5-turbo"           # ML评分Qwen模型

# ============================================
# RAG 基础配置
# ============================================
RAG_HYBRID_BM25_WEIGHT=0.5                      # 混合检索中BM25关键词检索的权重
RAG_HYBRID_VECTOR_WEIGHT=0.5                    # 混合检索中向量语义检索的权重
BM25_SCALE_FACTOR=5                             # BM25分数缩放因子，用于sigmoid校准到[0,1]区间
RAG_HYBRID_MERGE_MODE="OR"                      # 混合检索结果合并模式（OR/AND）
RAG_HYBRID_BM25_TOP_K=10                        # BM25检索返回的最大结果数
RAG_HYBRID_VECTOR_TOP_K=10                      # 向量检索返回的最大结果数
RAG_CACHE_ENABLED=True                          # 是否开启RAG查询缓存
RAG_CACHE_MAX_SIZE=1000                         # RAG缓存最大条目数
RAG_CACHE_TTL_SECONDS=3600                      # RAG缓存过期时间（秒，默认1小时）
RAG_QUERY_REWRITE_ENABLED=True                  # 是否开启RAG查询重写优化
RAG_SIMILARITY_THRESHOLD=0.7                    # 检索结果相似度最低阈值
RAG_MIN_RESULT_COUNT=3                          # 检索结果最少返回条数
RAG_STORAGE_DIR="./storage"                     # RAG索引存储目录

# ============================================
# RAG 分块配置
# ============================================
RAG_CHUNK_SIZE=1024                             # 通用文本分块大小（字符）
RAG_EPUB_CHUNK_TARGET_SIZE=1024                 # EPUB文件分块目标大小（字符）
RAG_PDF_CHUNK_SIZE=1536                         # PDF文件分块大小（字符）
RAG_CHUNK_OVERLAP=200                           # 分块重叠字符数

# ============================================
# RAG OCR 配置
# ============================================
RAG_OCR_EXTRACTION_THRESHOLD=0.5                # OCR提取率阈值（低于此值判定为扫描版PDF）
RAG_OCR_MIN_AVG_TEXT_LENGTH=100                 # OCR平均文本长度阈值（低于此值判定为扫描版PDF）

# ============================================
# RAG 混合检索密集模式权重
# ============================================
RAG_HYBRID_BM25_WEIGHT_DENSE=0.7                # 密集模式下BM25检索的权重
RAG_HYBRID_VECTOR_WEIGHT_DENSE=0.3              # 密集模式下向量检索的权重

# ============================================
# RAG 阈值配置
# ============================================
RAG_HYBRID_BASE_THRESHOLD=0.1                   # 混合检索基础阈值
RAG_VECTOR_BASE_THRESHOLD=0.5                   # 纯向量检索基础阈值
RAG_RELATIVE_CUTOFF_RATIO=0.3                   # 相对截断比例（得分低于最高分*该比例的结果会被过滤）

# ============================================
# RAG 搜索页面配置
# ============================================
RAG_SEARCH_BM25_WEIGHT=0.5                      # 搜索页面BM25权重
RAG_SEARCH_VECTOR_WEIGHT=0.5                    # 搜索页面向量权重
RAG_SEARCH_NO_MATCH_VECTOR_PENALTY=0.5          # 无关键词匹配时向量检索惩罚系数
RAG_SEARCH_SCORE_THRESHOLD_HYBRID=0.25          # 搜索页面混合得分阈值
RAG_SEARCH_SCORE_THRESHOLD_VECTOR=0.25          # 搜索页面向量得分阈值
RAG_SEARCH_RELATIVE_CUTOFF_RATIO=0.5            # 搜索页面结果相对截断比例
RAG_SEARCH_MIN_SIMILARITY_THRESHOLD=0.2         # 搜索页面最小相似度阈值

# ============================================
# RAG 年龄过滤配置
# ============================================
RAG_AGE_FILTER_STRICTNESS=0.7                   # 年龄过滤严格程度（0-1，0最宽松，1最严格）
RAG_AGE_FILTER_TOLERANCE=2                      # 年龄过滤弹性容忍范围（岁）
RAG_AGE_FIT_WEIGHT=0.3                          # 年龄适配度在最终得分中的权重

# ============================================
# RAG 重排序配置
# ============================================
RAG_RERANKER_MODEL="BAAI/bge-reranker-v2-m3"    # Cross-Encoder重排序模型名称
RAG_RERANKER_INITIAL_K=30                       # 重排序前初始检索结果数量
RAG_RERANKER_FINAL_K=5                          # 重排序后最终返回结果数量

# ============================================
# RAG 自动持久化配置
# ============================================
RAG_AUTO_PERSIST_ENABLED=True                   # 是否启用索引自动持久化
RAG_AUTO_PERSIST_INTERVAL=300                   # 自动持久化间隔（秒），默认5分钟

# ============================================
# RAG 性能配置
# ============================================
RAG_VL_MAX_WORKERS=2                            # 多模态处理最大线程数
RAG_UPLOAD_MAX_CONCURRENT_TASKS=5               # 文档上传最大并发任务数
RAG_TEMP_UPLOAD_DIR="./temp_uploads"            # 临时上传文件存储目录
RAG_METADATA_EXTRACTION_CONCURRENCY=20          # 元数据提取最大并发数

# ============================================
# RAG 分层内容生成配置
# ============================================
RAG_LAYERED_CONTENT_ENABLED=True                # 是否启用分层内容生成功能
RAG_LAYERED_CONTENT_ENABLE_LLM_GENERATION=True  # 是否启用LLM内容生成
RAG_LAYERED_CONTENT_ENABLE_LOCAL_FALLBACK=True  # 是否启用本地知识库内容兜底
RAG_LAYERED_CONTENT_L0_MAX_LENGTH=100           # L0层（摘要）最大长度
RAG_LAYERED_CONTENT_L1_MAX_LENGTH=500           # L1层（详细）最大长度
RAG_LAYERED_CONTENT_BATCH_SIZE=20               # 分层内容生成批处理大小
RAG_LAYERED_CONTENT_LARGE_BATCH_THRESHOLD=1000  # 大批次内容阈值
RAG_LAYERED_CONTENT_LARGE_BATCH_SIZE=10         # 大批次处理时的批次大小
RAG_LAYERED_CONTENT_CONCURRENCY_LIMIT=8         # 分层内容生成最大并发数

# ============================================
# RAG 监控配置
# ============================================
RAG_MONITORING_ENABLED=True                     # 是否启用RAG监控
RAG_MONITORING_LOG_LEVEL="INFO"                 # 监控日志级别
RAG_MONITORING_METRICS_INTERVAL=60              # 指标采集间隔（秒）

# ============================================
# PageIndex 配置（外部知识图谱，当前禁用）
# ============================================
PAGEINDEX_ENABLED=False                         # 是否启用PageIndex
PAGEINDEX_BASE_URL="https://api.pageindex.ai"   # PageIndex API基础URL
PAGEINDEX_API_KEY="local-dev-key"               # PageIndex API密钥
PAGEINDEX_MAX_CONCURRENCY=5                     # 最大并发请求数
PAGEINDEX_MAX_TREE_DEPTH=3                      # 知识图谱最大遍历深度
PAGEINDEX_TIMEOUT_SECONDS=10                    # API请求超时时间（秒）
PAGEINDEX_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5   # 熔断器失败阈值
PAGEINDEX_CIRCUIT_BREAKER_RESET_TIMEOUT=60      # 熔断器重置超时（秒）
PAGEINDEX_MAX_RETRIES=3                         # 最大重试次数
PAGEINDEX_RETRY_BASE_DELAY=0.5                  # 重试基础延迟（秒）
PAGEINDEX_RETRY_MAX_DELAY=10.0                  # 重试最大延迟（秒）
PAGEINDEX_FALLBACK_TO_HYBRID=True               # 失败时降级到混合检索

# ============================================
# 查询路由配置
# ============================================
QUERY_ROUTER_LLM_ENABLED=True                   # 是否启用LLM查询路由
QUERY_ROUTER_CONFIDENCE_THRESHOLD=0.8           # 路由置信度阈值
QUERY_ROUTER_LLM_MAX_RETRIES=2                  # 路由LLM最大重试次数

# ============================================
# 结果融合配置
# ============================================
FUSION_SCORE_BOOST_FOR_PAGEINDEX=1.2            # PageIndex结果分数提升倍数
FUSION_HYBRID_SUPPLEMENT_LIMIT=5                # 混合检索补充结果上限
FUSION_DEDUP_NORMALIZE=True                     # 是否启用去重归一化

# ============================================
# Embedding 模型配置
# ============================================
EMBEDDING_MODEL_NAME="text-embedding-v4"        # 嵌入模型名称
EMBEDDING_MAX_TEXT_LENGTH=1536                  # Embedding文本最大长度（字符）
EMBEDDING_BATCH_SIZE=10                         # Embedding批处理大小

# ============================================
# 向量存储配置
# ============================================
VECTOR_STORE_TYPE="chroma"                      # 向量存储类型（chroma/pinecone/milvus/weaviate）
VECTOR_STORE_CONFIG={"persist_dir": "./storage/vector_store", "collection_name": "child_development"}

# ============================================
# 语义分块配置
# ============================================
SEMANTIC_SPLITTER_BUFFER_SIZE=5                 # 语义分块时比较的前后段落数
SEMANTIC_SPLITTER_BREAKPOINT_THRESHOLD=90       # 语义分块相似度阈值（百分比）
SEMANTIC_SPLITTER_CHAPTER_BUFFER_SIZE=3         # 长章节语义分块时比较的前后段落数
SEMANTIC_SPLITTER_CHAPTER_BREAKPOINT_THRESHOLD=75  # 长章节语义分块相似度阈值（百分比）

# ============================================
# ML 评分配置
# ============================================
ML_SCORING_ENABLED=False                        # 是否启用ML评分
ML_SCORING_MODE="qwen"                          # ML评分模式
ML_SCORING_MODEL_PATH="./models/scoring_xgb.model"  # ML评分模型路径
ML_SCORING_WEIGHT_AHP=0.7                       # AHP评分权重
ML_SCORING_WEIGHT_ML=0.3                        # ML评分权重
```

- [ ] **Step 2: 验证默认值一致性**

确保以下关键配置与 `.env.dev` 一致：
- `RAG_CHUNK_SIZE=1024` ✅
- `RAG_EPUB_CHUNK_TARGET_SIZE=1024` ✅
- `RAG_PDF_CHUNK_SIZE=1536` ✅
- `RAG_CHUNK_OVERLAP=200` ✅
- `EMBEDDING_MODEL_NAME=text-embedding-v4` ✅
- `RAG_VL_MAX_WORKERS=2` ✅
- `RAG_SEARCH_BM25_WEIGHT=0.5` ✅
- `SEMANTIC_SPLITTER_BUFFER_SIZE=5` ✅
- `SEMANTIC_SPLITTER_BREAKPOINT_THRESHOLD=90` ✅

---

## Chunk 2: 前端适配

### Task 13: 创建缺失的 SCSS 文件

**Files:**
- Create: `frontend/src/components/config/ConfigVersionSelector.module.scss`
- Create: `frontend/src/pages/SystemConfigPage.module.scss`

- [ ] **Step 1: 创建 `ConfigVersionSelector.module.scss`**

```scss
.versionSelector {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.versionList {
  max-height: 300px;
  overflow-y: auto;
}

.versionItem {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  margin-bottom: 4px;

  &:hover {
    background-color: #fafafa;
  }

  &.active {
    border-color: #1890ff;
    background-color: #e6f7ff;
  }
}

.versionInfo {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.versionId {
  font-weight: 500;
  font-size: 14px;
}

.versionTime {
  font-size: 12px;
  color: #8c8c8c;
}

.versionActions {
  display: flex;
  gap: 8px;
}
```

- [ ] **Step 2: 创建 `SystemConfigPage.module.scss`**

```scss
.configPage {
  display: flex;
  gap: 24px;
  height: 100%;
}

.sidebar {
  width: 240px;
  flex-shrink: 0;
  border-right: 1px solid #f0f0f0;
  padding-right: 16px;
}

.content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.title {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}

.formContainer {
  flex: 1;
  overflow-y: auto;
}
```

---

### Task 14: 更新前端配置分类映射

**Files:**
- Modify: `frontend/src/pages/SystemConfigPage.tsx`
- Modify: `frontend/src/store/configStore.ts`

- [ ] **Step 1: 更新分类映射**

在 `SystemConfigPage.tsx` 或 `configStore.ts` 中更新分类树：

```typescript
const CATEGORY_TREE = [
  {
    key: 'app',
    title: '📦 应用设置',
    children: [
      { key: 'app', title: '基础配置' },
      { key: 'logging', title: '日志配置' },
      { key: 'paths', title: '路径配置' },
    ],
  },
  {
    key: 'models',
    title: '🤖 AI 模型',
    children: [
      { key: 'models.llm', title: 'LLM 模型' },
      { key: 'models.embedding', title: 'Embedding 模型' },
      { key: 'models.ml_scoring', title: 'ML 评分模型' },
    ],
  },
  {
    key: 'rag',
    title: '📚 RAG 知识库',
    children: [
      { key: 'rag.core', title: '核心设置' },
      { key: 'rag.retrieval', title: '检索配置' },
      { key: 'rag.chunking', title: '分块配置' },
      { key: 'rag.vector_store', title: '向量库' },
      { key: 'rag.pageindex', title: '知识图谱' },
      { key: 'rag.pipeline', title: '导入流水线' },
    ],
  },
  {
    key: 'rules',
    title: '⚙️ 业务规则',
    children: [
      { key: 'rules', title: '规则定义' },
    ],
  },
];
```

---

### Task 15: 后端 ConfigController 返回 `category` 元数据

**Files:**
- Modify: `backend/src/controller/config_controller.py`
- Modify: `backend/src/api/config/types.py` (前端类型定义)

- [ ] **Step 1: 更新后端返回格式**

在 `ConfigFieldMetadata` 中增加 `category` 字段：

```python
class ConfigFieldMetadata(BaseModel):
    key: str
    value: Any
    type: str
    category: str  # 新增：分类标识
    description: str
    env_var: str
```

- [ ] **Step 2: 更新前端类型定义**

```typescript
export interface ConfigFieldMetadata {
  key: string;
  value: any;
  type: 'bool' | 'int' | 'float' | 'str' | 'dict' | 'list';
  category: string;  // 新增
  description: string;
  env_var: string;
}
```

---

## Chunk 3: 验证与测试

### Task 16: 运行后端验证

- [ ] **Step 1: 进入后端目录**

```bash
cd backend
```

- [ ] **Step 2: 运行类型检查**

```bash
uv run python -c "from src.config import settings, rules; print('导入成功')"
```

- [ ] **Step 3: 运行测试**

```bash
uv run pytest tests/ -v --tb=short
```

- [ ] **Step 4: 启动服务验证**

```bash
uv run python src/server.py
```

访问 `http://localhost:8000/docs` 验证 API 文档正常加载。

---

### Task 17: 运行前端验证

- [ ] **Step 1: 进入前端目录**

```bash
cd frontend
```

- [ ] **Step 2: 安装依赖（如有变更）**

```bash
npm install --legacy-peer-deps
```

- [ ] **Step 3: 运行构建**

```bash
npm run build
```

- [ ] **Step 4: 运行 Lint 检查**

```bash
npm run lint
```

- [ ] **Step 5: 启动开发服务器**

```bash
npm run dev
```

访问配置页面，验证分类树和表单渲染正常。

---

### Task 18: 手动验证配置页面功能

- [ ] **Step 1: 验证分类树渲染**

打开系统配置页面，确认左侧分类树按新层级结构展示。

- [ ] **Step 2: 验证配置加载**

点击不同分类，确认右侧表单正确加载对应配置项。

- [ ] **Step 3: 验证配置保存**

修改任意配置项并保存，确认保存成功且后端返回正确响应。

- [ ] **Step 4: 验证版本列表**

打开版本选择器，确认历史版本列表正常展示。

- [ ] **Step 5: 验证回滚功能**

选择一个历史版本并回滚，确认回滚成功且配置值正确恢复。

---

## 提交规范

每个 Task 完成后应提交一个 commit，提交信息格式：

```
refactor(config): [简短描述]

例如：
refactor(config): move config infrastructure to core/
refactor(config): split rag_settings.py into modules
refactor(config): update all import paths
refactor(config): add missing frontend SCSS files
fix(config): fix age_filter.py import path
fix(config): complete .env.dev.example
```
