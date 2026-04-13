# RAG 查询流水线编排设计文档

**日期**: 2026-04-10  
**状态**: 已审核  
**作者**: AI Assistant
**版本**: v1.1 (优化版)

---

## 1. 背景与目标

### 1.1 现状问题

| 问题 | 位置 | 影响 | 严重度 |
|------|------|------|--------|
| **QueryRouter 孤岛** | `query_router.py` 已实现但未被检索流水线调用 | 复杂查询增强形同虚设 | **严重** |
| **PageIndex 孤岛** | `pageindex_wrapper.py` 完整实现但从未接入 | 代码浪费 | **中等** |
| **ResultFusion 孤岛** | `result_fusion.py` 已实现但无调用方 | 代码浪费 | **中等** |
| **LLM 无条件执行** | `retrieval_service.py:153-154` | 简单查询也执行查询重写+同义词扩展，浪费 2 次 LLM 调用 | **严重** |
| **年龄过滤重复** | `retrieval_service.py` 和 `age_filter.py` 各有一套实现 | 维护成本高，逻辑可能不一致 | **中等** |
| **同义词扩展 Bug** | `retrieval_service.py:883` | 使用了未定义变量 `synonyms`（应为 `result_text`） | **严重** |
| **PageIndex 文件句柄泄漏** | `pageindex_wrapper.py:251-253` | `open()` 在 `with` 块外调用且未关闭，文件句柄泄漏 | **中等** |
| **流水线硬编码** | `retrieval_service.py` 中 if-else 控制流程 | 新增查询类型需修改核心逻辑 | **中等** |

### 1.2 重构目标

1. **声明式流水线**：通过 YAML 文件定义查询处理步骤，代码与配置分离
2. **查询类型路由**：简单查询跳过 LLM 增强，复杂查询启用完整链路
3. **步骤可插拔**：每个处理步骤是独立类，可独立测试和替换
4. **修复已知 Bug**：同义词扩展变量、PageIndex 文件句柄泄漏
5. **保留 PageIndex**：YAML 中 `enabled: false`，不引入但保留代码
6. **与现有配置系统融合**：Pydantic + 环境变量 + 热重载
7. **性能提升**：简单查询延迟降低50%+，Token消耗降低60%+
8. **可观测性增强**：完善指标埋点和错误日志，便于监控和排查

---

## 2. 架构设计

### 2.1 整体架构

```
用户查询
    │
    ▼
┌─────────────────────────────────────────┐
│  QueryRouter (查询路由器)                │
│  简单/复杂分类                           │
└─────────────────┬───────────────────────┘
                  │ query_type
                  ▼
┌─────────────────────────────────────────┐
│  PipelineOrchestrator (流水线编排器)     │
│  根据 query_type 加载对应 YAML 配置      │
│  按顺序执行启用的步骤                    │
│  失败自动降级、缓存已执行步骤            │
└─────────────────┬───────────────────────┘
                  │
    ┌─────────────┴─────────────┐
    │                           │
    ▼                           ▼
简单查询流水线              复杂查询流水线
    │                           │
    ▼                           ▼
┌──────────┐              ┌──────────────┐
│ 步骤列表  │              │ 步骤列表      │
│          │              │              │
│ cache    │              │ cache        │
│ retrieval│              │ rewrite      │
│ rerank   │              │ synonym      │
│ dedup    │              │ age_filter   │
│ convert  │              │ retrieval    │
│          │              │ [pageindex]  │ ← enabled: false
│          │              │ rerank       │
│          │              │ dedup        │
│          │              │ convert      │
└──────────┘              └──────────────┘
    │                           │
    └─────────────┬─────────────┘
                  │
                  ▼
         List[KnowledgeItem]
```

### 2.2 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| `PipelineOrchestrator` | `backend/src/core/query_pipeline_orchestrator.py` | 加载配置、编排步骤执行、失败处理、降级逻辑 |
| `PipelineContext` | `backend/src/core/query_pipeline_orchestrator.py` | 步骤间传递的上下文对象，包含输入、中间状态、输出、执行元数据 |
| `PipelineStep` (Protocol) | `backend/src/core/query_pipeline_orchestrator.py` | 步骤抽象接口 |
| 步骤实现 | `backend/src/core/pipeline_steps/` | 各处理步骤的具体实现（可插拔） |
| `QueryPipelineSettings` | `backend/src/config/modules/rag/query_pipeline.py` | 流水线配置模块 |
| YAML 配置 | `backend/src/config/query_pipeline.yaml` | 声明式流水线定义 |

---

## 3. 配置设计

### 3.1 YAML 配置文件

**文件位置**: `backend/src/config/query_pipeline.yaml`

```yaml
# RAG 查询流水线配置
# 环境变量替换由 load_pipeline_config() 函数处理
# 语法: ${ENV_VAR:default_value}

pipelines:
  # 简单查询流水线（事实性/定义性问题）
  simple:
    - name: cache_check
      enabled: true
      description: "缓存检查，命中则直接返回"
      timeout: 5
    
    - name: hybrid_retrieval
      enabled: true
      description: "BM25 + 向量混合检索"
      params:
        bm25_top_k: 10
        vector_top_k: 10
        merge_mode: "OR"
      timeout: 10
    
    - name: rerank
      enabled: true
      description: "Cross-Encoder 重排序"
      params:
        initial_k: 30
        final_k: 5
      timeout: 15
    
    - name: dedup
      enabled: true
      description: "内容去重"
      timeout: 3
    
    - name: convert_to_knowledge
      enabled: true
      description: "转换为 KnowledgeItem"
      timeout: 3

  # 复杂查询流水线（比较分析/多步骤问题）
  complex:
    - name: cache_check
      enabled: true
      description: "缓存检查"
      timeout: 5
    
    - name: query_rewrite
      enabled: true
      description: "LLM 查询重写，将自然语言转为检索关键词"
      timeout: 10
    
    - name: synonym_expand
      enabled: true
      description: "LLM 同义词扩展"
      timeout: 10
    
    - name: age_filter
      enabled: true
      description: "动态年龄过滤"
      timeout: 3
    
    - name: hybrid_retrieval
      enabled: true
      description: "BM25 + 向量混合检索"
      params:
        bm25_top_k: 15
        vector_top_k: 15
        merge_mode: "OR"
      timeout: 10
    
    # PageIndex 步骤（保留但不启用，位置在retrieval之后rerank之前）
    - name: pageindex
      enabled: false
      description: "PageIndex 推理检索（预留）"
      timeout: 20
    
    - name: rerank
      enabled: true
      description: "Cross-Encoder 重排序"
      params:
        initial_k: 30
        final_k: 5
      timeout: 15
    
    - name: dedup
      enabled: true
      description: "内容去重"
      timeout: 3
    
    - name: convert_to_knowledge
      enabled: true
      description: "转换为 KnowledgeItem，计算年龄适配度"
      timeout: 3

  # 默认查询流水线（未分类或降级情况）
  default:
    - name: cache_check
      enabled: true
      timeout: 5
    
    - name: hybrid_retrieval
      enabled: true
      params:
        bm25_top_k: 10
        vector_top_k: 10
      timeout: 10
    
    - name: rerank
      enabled: true
      params:
        initial_k: 30
        final_k: 5
      timeout: 15
    
    - name: dedup
      enabled: true
      timeout: 3
    
    - name: convert_to_knowledge
      enabled: true
      timeout: 3

# 全局设置
global:
  # 步骤超时（秒），可被步骤级timeout覆盖
  step_timeout: 30
  
  # 是否启用步骤级监控
  enable_step_monitoring: true
  
  # 失败策略: "fail_fast" | "continue_with_warning" | "fallback_to_default"
  failure_strategy: "fallback_to_default"
```

### 3.2 Pydantic 配置模块

**文件位置**: `backend/src/config/modules/rag/query_pipeline.py`

```python
"""RAG 查询流水线配置"""

import re
import os
import yaml
import hashlib
import threading
from pathlib import Path
from typing import Any, Optional, Callable
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger


class PipelineStepConfig(BaseModel):
    """单个流水线步骤配置"""
    
    name: str = Field(..., description="步骤标识")
    enabled: bool = Field(default=True, description="是否启用")
    description: str = Field(default="", description="步骤描述")
    params: dict[str, Any] = Field(default_factory=dict, description="步骤参数")
    timeout: Optional[int] = Field(default=None, description="步骤级超时（秒），优先级高于全局配置")


class GlobalPipelineSettings(BaseModel):
    """全局设置模型"""
    step_timeout: int = Field(default=30, description="步骤超时（秒）")
    enable_step_monitoring: bool = Field(default=True, description="是否启用步骤级监控")
    failure_strategy: str = Field(default="fallback_to_default", description="失败策略")


class GlobalPipelineConfig(BaseModel):
    """全局流水线配置模型"""
    pipelines: dict[str, list[PipelineStepConfig]] = Field(default_factory=dict)
    global_: GlobalPipelineSettings = Field(alias="global")
    
    class Config:
        populate_by_name = True


class QueryPipelineSettings(BaseSettings):
    """RAG 查询流水线配置（环境变量加载入口）"""
    
    # 流水线定义（从 YAML 加载）
    rag_query_pipeline_yaml_path: str = Field(
        default="",
        validation_alias="RAG_QUERY_PIPELINE_YAML_PATH",
        description="YAML 配置文件路径，为空时使用内置默认值"
    )
    
    # 全局设置
    rag_pipeline_step_timeout: int = Field(
        default=30,
        validation_alias="RAG_PIPELINE_STEP_TIMEOUT",
        description="步骤超时（秒）"
    )
    rag_pipeline_enable_monitoring: bool = Field(
        default=True,
        validation_alias="RAG_PIPELINE_ENABLE_MONITORING",
        description="是否启用步骤级监控"
    )
    rag_pipeline_failure_strategy: str = Field(
        default="fallback_to_default",
        validation_alias="RAG_PIPELINE_FAILURE_STRATEGY",
        description="失败策略: fail_fast / continue_with_warning / fallback_to_default"
    )
    
    # 功能开关
    rag_pipeline_enabled: bool = Field(
        default=False,
        validation_alias="RAG_PIPELINE_ENABLED",
        description="是否启用新流水线，false时使用旧逻辑"
    )
    
    model_config = SettingsConfigDict(
        env_file=".env.dev",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def _resolve_env_vars(text: str) -> str:
    """解析 YAML 中的环境变量替换 ${ENV_VAR:default_value}
    
    示例: ${RAG_HYBRID_BM25_TOP_K:10} → 读取环境变量，不存在则用 10
    """
    pattern = r'\$\{(\w+):([^}]*)\}'
    
    def replacer(match):
        env_var = match.group(1)
        default = match.group(2)
        return os.environ.get(env_var, default)
    
    return re.sub(pattern, replacer, text)


def _get_builtin_defaults() -> dict:
    """返回内置默认配置，与YAML默认配置完全一致"""
    return {
        "pipelines": {
            "simple": [
                {"name": "cache_check", "enabled": True, "timeout": 5},
                {"name": "hybrid_retrieval", "enabled": True, "params": {"bm25_top_k": 10, "vector_top_k": 10}, "timeout": 10},
                {"name": "rerank", "enabled": True, "params": {"initial_k": 30, "final_k": 5}, "timeout": 15},
                {"name": "dedup", "enabled": True, "timeout": 3},
                {"name": "convert_to_knowledge", "enabled": True, "timeout": 3},
            ],
            "complex": [
                {"name": "cache_check", "enabled": True, "timeout": 5},
                {"name": "query_rewrite", "enabled": True, "timeout": 10},
                {"name": "synonym_expand", "enabled": True, "timeout": 10},
                {"name": "age_filter", "enabled": True, "timeout": 3},
                {"name": "hybrid_retrieval", "enabled": True, "params": {"bm25_top_k": 15, "vector_top_k": 15}, "timeout": 10},
                {"name": "pageindex", "enabled": False, "timeout": 20},
                {"name": "rerank", "enabled": True, "params": {"initial_k": 30, "final_k": 5}, "timeout": 15},
                {"name": "dedup", "enabled": True, "timeout": 3},
                {"name": "convert_to_knowledge", "enabled": True, "timeout": 3},
            ],
            "default": [
                {"name": "cache_check", "enabled": True, "timeout": 5},
                {"name": "hybrid_retrieval", "enabled": True, "params": {"bm25_top_k": 10, "vector_top_k": 10}, "timeout": 10},
                {"name": "rerank", "enabled": True, "params": {"initial_k": 30, "final_k": 5}, "timeout": 15},
                {"name": "dedup", "enabled": True, "timeout": 3},
                {"name": "convert_to_knowledge", "enabled": True, "timeout": 3},
            ]
        },
        "global": {
            "step_timeout": 30,
            "enable_step_monitoring": True,
            "failure_strategy": "fallback_to_default"
        }
    }


def load_pipeline_config(yaml_path: str = "") -> dict:
    """加载 YAML 配置文件
    
    优先级:
    1. 环境变量 RAG_QUERY_PIPELINE_YAML_PATH 指定的文件
    2. 默认路径：从配置目录获取 query_pipeline.yaml
    3. 内置默认配置（硬编码兜底）
    """
    if yaml_path:
        path = Path(yaml_path)
    else:
        # 从配置系统获取配置目录，避免相对路径问题
        from src.config import settings
        path = Path(settings.path_config_dir) / "query_pipeline.yaml"
    
    if path.exists():
        raw_text = path.read_text(encoding="utf-8")
        resolved_text = _resolve_env_vars(raw_text)
        config = yaml.safe_load(resolved_text)
        
        # 使用Pydantic自动解析和类型转换，校验配置格式
        try:
            # 解析为全局配置结构
            global_config = GlobalPipelineConfig(**config)
            return global_config.model_dump(by_alias=True)
        except ValidationError as e:
            logger.error(f"YAML 配置解析失败，使用内置默认配置: {e}")
            return _get_builtin_defaults()
    
    logger.warning(f"YAML 配置文件不存在: {path}，使用内置默认配置")
    return _get_builtin_defaults()
```

**与现有配置系统的对接**：

`QueryPipelineSettings` 需要加入 `backend/src/config/__init__.py` 的 `Settings` 多重继承链：

```python
# backend/src/config/__init__.py 修改
from .modules.rag.query_pipeline import QueryPipelineSettings  # 新增导入

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
    QueryPipelineSettings,  # 新增
):
    """统一的配置类，聚合所有拆分后的配置"""
```

同时在 `_infer_category` 方法中增加映射：

```python
def _infer_category(self, field_name: str) -> str:
    # ... 现有逻辑 ...
    elif field_name.startswith("rag_pipeline_"):
        return "rag.pipeline"
    # ...
```

---

## 4. 核心编排器

### 4.1 PipelineContext（上下文对象）

```python
"""backend/src/core/query_pipeline_orchestrator.py"""

from dataclasses import dataclass, field
from typing import Optional
from llama_index.core.schema import NodeWithScore
from src.model.knowledge_item import KnowledgeItem


@dataclass
class PipelineContext:
    """流水线执行上下文，步骤间传递数据"""
    
    # 输入
    query: str                                    # 原始查询
    age: Optional[int] = None                     # 儿童年龄
    limit: int = 5                                # 返回数量限制
    query_type: str = "default"                   # 查询类型: simple/complex/default
    
    # 中间状态
    rewritten_query: Optional[str] = None         # 重写后的查询（默认优先使用）
    synonyms: list[str] = field(default_factory=list)  # 同义词列表
    age_filter: Optional[dict] = None             # 年龄过滤条件（MetadataFilter 参数）
    retrieval_results: list[NodeWithScore] = field(default_factory=list)  # 混合检索原始结果
    pageindex_results: list[NodeWithScore] = field(default_factory=list)  # PageIndex检索结果（预留）
    
    # 输出
    final_results: list[KnowledgeItem] = field(default_factory=list)  # 最终 KnowledgeItem 列表
    
    # 执行元数据
    execution_log: list[dict] = field(default_factory=list)  # 步骤执行日志
    executed_steps: set[str] = field(default_factory=set)    # 已成功执行的步骤集合（用于降级去重）
    start_time: Optional[float] = None            # 开始时间戳
    cache_hit: bool = False                       # 是否命中缓存
    ab_test_variant: Optional[str] = None         # A/B 测试变体标识
```

**类型说明**：
- `retrieval_results`: 使用 `list[NodeWithScore]`（LlamaIndex 标准类型），而非 `list[Any]`
- `final_results`: 使用 `list[KnowledgeItem]`（项目已有模型）
- `age_filter`: 使用 `dict` 存储 MetadataFilter 的构建参数，由 `AgeFilterStep` 构建，`HybridRetrievalStep` 消费
- `synonyms`/`rewritten_query`: 供下游步骤消费，提升检索效果

### 4.2 PipelineStep（步骤抽象）

```python
from typing import Protocol


class PipelineStep(Protocol):
    """流水线步骤抽象接口"""
    
    async def execute(self, context: PipelineContext, params: dict = None) -> PipelineContext:
        """执行步骤，返回更新后的上下文
        
        Args:
            context: 流水线执行上下文
            params: YAML 中定义的步骤参数，优先级高于 settings 环境变量
        """
        ...
    
    @property
    def name(self) -> str:
        """步骤标识"""
        ...
```

### 4.3 PipelineOrchestrator（编排器）

```python
import asyncio
import time
import threading
from typing import Optional, Callable
from prometheus_client import Histogram, Counter, Info

from loguru import logger
from src.config import settings


# Prometheus 指标定义
STEP_DURATION = Histogram(
    "rag_pipeline_step_duration_seconds",
    "RAG流水线步骤执行耗时",
    ["step_name", "query_type", "status"]
)

STEP_TOTAL = Counter(
    "rag_pipeline_step_total",
    "RAG流水线步骤执行总次数",
    ["step_name", "query_type", "status"]
)

QUERY_TOTAL = Counter(
    "rag_pipeline_queries_total",
    "RAG流水线查询总次数",
    ["query_type", "result"]
)

CACHE_HIT_TOTAL = Counter(
    "rag_pipeline_cache_hit_total",
    "RAG流水线缓存命中次数"
)


class PipelineStepTimeoutError(Exception):
    """步骤超时异常"""
    pass


# 全局单例和锁
_orchestrator_instance: Optional["PipelineOrchestrator"] = None
_instance_lock = threading.Lock()


def get_orchestrator(step_factory: dict[str, Callable] = None) -> "PipelineOrchestrator":
    """获取 PipelineOrchestrator 单例（线程安全）
    
    Args:
        step_factory: 步骤工厂，仅在首次调用时传入
    
    Returns:
        单例编排器实例
    """
    global _orchestrator_instance
    if _orchestrator_instance is None:
        with _instance_lock:
            # 双重检查锁，避免多线程竞争
            if _orchestrator_instance is None:
                if step_factory is None:
                    raise RuntimeError("首次调用 get_orchestrator 时必须传入 step_factory")
                _orchestrator_instance = PipelineOrchestrator(step_factory)
    return _orchestrator_instance


class PipelineOrchestrator:
    """流水线编排器（单例模式）
    
    职责:
    1. 加载 YAML 配置
    2. 根据查询类型选择对应流水线
    3. 按顺序执行启用的步骤
    4. 处理失败策略
    5. 指标埋点和监控
    
    注意: 通过 get_orchestrator() 获取单例，确保配置缓存和步骤实例缓存有效。
    """
    
    def __init__(self, step_factory: dict[str, Callable]):
        """
        Args:
            step_factory: 步骤工厂 {step_name: StepClass}
                         使用工厂模式延迟实例化，避免启动时加载所有模型
        """
        self._step_factory = step_factory
        self._step_instances: dict[str, PipelineStep] = {}  # 缓存已实例化的步骤
        self._config_cache: dict[str, list[PipelineStepConfig]] = {}
    
    def clear_cache(self):
        """清除所有缓存（配置+步骤实例），用于热重载"""
        self._config_cache.clear()
        self._step_instances.clear()
        logger.info("流水线配置和步骤实例缓存已清除")
    
    def _get_step(self, name: str) -> Optional[PipelineStep]:
        """延迟获取步骤实例（工厂模式）"""
        if name not in self._step_instances:
            factory = self._step_factory.get(name)
            if factory:
                self._step_instances[name] = factory()
            else:
                return None
        return self._step_instances[name]
    
    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行流水线"""
        context.start_time = time.time()
        try:
            # 1. 加载对应类型的流水线配置
            pipeline_config = self._load_pipeline(context.query_type)
            
            # 2. 按顺序执行步骤
            for step_config in pipeline_config:
                if not step_config.enabled:
                    continue
                
                step = self._get_step(step_config.name)
                if not step:
                    logger.warning(f"步骤 {step_config.name} 未注册，跳过")
                    continue
                
                try:
                    context = await self._execute_step(step, context, step_config.params, step_config.timeout)
                except Exception as e:
                    context = await self._handle_failure(context, step_config, e)
                    if context is None:
                        break  # fail_fast
            
            QUERY_TOTAL.labels(context.query_type, "success").inc()
            return context
            
        except Exception as e:
            QUERY_TOTAL.labels(context.query_type, "failed").inc()
            logger.error(f"流水线执行失败: {str(e)} | 查询: {context.query} | 年龄: {context.age}")
            raise
    
    def _load_pipeline(self, query_type: str) -> list[PipelineStepConfig]:
        """加载指定类型的流水线配置"""
        if query_type not in self._config_cache:
            from src.config.modules.rag.query_pipeline import load_pipeline_config
            
            raw_config = load_pipeline_config(settings.rag_query_pipeline_yaml_path)
            pipelines = raw_config.get("pipelines", {})
            
            # 解析为 PipelineStepConfig 列表
            for ptype, steps in pipelines.items():
                self._config_cache[ptype] = [
                    PipelineStepConfig(**s) for s in steps
                ]
        
        return self._config_cache.get(query_type, self._config_cache.get("default", []))
    
    async def _execute_step(
        self, 
        step: PipelineStep, 
        context: PipelineContext, 
        params: dict,
        step_timeout: Optional[int] = None
    ) -> PipelineContext:
        """执行单个步骤，带超时和监控"""
        start = time.time()
        # 优先级：步骤级超时 > 全局超时
        timeout = step_timeout if step_timeout is not None else settings.rag_pipeline_step_timeout
        status = "success"
        try:
            result = await asyncio.wait_for(
                step.execute(context, params),
                timeout=timeout
            )
            elapsed = time.time() - start
            
            # 记录执行成功，加入已执行步骤集合
            result.executed_steps.add(step.name)
            result.execution_log.append({
                "step": step.name,
                "status": "success",
                "duration_ms": elapsed * 1000,
            })
            
            if settings.rag_pipeline_enable_monitoring:
                logger.info(f"步骤 {step.name} 执行完成，耗时 {elapsed*1000:.0f}ms")
                # 上报成功指标
                STEP_DURATION.labels(step.name, context.query_type, "success").observe(elapsed)
                STEP_TOTAL.labels(step.name, context.query_type, "success").inc()
            
            return result
            
        except asyncio.TimeoutError:
            status = "failed"
            elapsed = time.time() - start
            # 上报失败指标
            STEP_DURATION.labels(step.name, context.query_type, "failed").observe(elapsed)
            STEP_TOTAL.labels(step.name, context.query_type, "failed").inc()
            # 错误日志增加关键上下文
            logger.error(
                f"步骤 {step.name} 执行超时: {timeout}s | "
                f"查询: {context.query} | 年龄: {context.age} | 查询类型: {context.query_type} | "
                f"耗时: {elapsed*1000:.0f}ms"
            )
            raise PipelineStepTimeoutError(f"步骤 {step.name} 超时（{timeout}s）")
            
        except Exception as e:
            status = "failed"
            elapsed = time.time() - start
            # 上报失败指标
            STEP_DURATION.labels(step.name, context.query_type, "failed").observe(elapsed)
            STEP_TOTAL.labels(step.name, context.query_type, "failed").inc()
            # 错误日志增加关键上下文
            logger.error(
                f"步骤 {step.name} 执行失败: {str(e)} | "
                f"查询: {context.query} | 年龄: {context.age} | 查询类型: {context.query_type} | "
                f"耗时: {elapsed*1000:.0f}ms | 超时设置: {timeout}s"
            )
            raise
    
    async def _handle_failure(
        self, 
        context: PipelineContext, 
        step_config: PipelineStepConfig, 
        error: Exception
    ) -> Optional[PipelineContext]:
        """处理步骤失败"""
        strategy = settings.rag_pipeline_failure_strategy
        
        if strategy == "fail_fast":
            logger.error(f"步骤 {step_config.name} 失败，终止流水线: {error}")
            return None
        
        elif strategy == "continue_with_warning":
            logger.warning(f"步骤 {step_config.name} 失败，继续执行: {error}")
            context.execution_log.append({
                "step": step_config.name,
                "status": "failed",
                "error": str(error),
            })
            return context
        
        elif strategy == "fallback_to_default":
            logger.warning(f"步骤 {step_config.name} 失败，降级到 default 流水线，已执行步骤: {context.executed_steps}")
            return await self._execute_fallback(context, step_config.name)
        
        return context
    
    async def _execute_fallback(
        self, 
        context: PipelineContext, 
        failed_step: str
    ) -> PipelineContext:
        """降级到 default 流水线执行，跳过已成功执行的步骤"""
        context.query_type = "default"
        default_config = self._load_pipeline("default")
        
        for step_config in default_config:
            if not step_config.enabled:
                continue
            
            # 跳过已成功执行的步骤
            if step_config.name in context.executed_steps:
                logger.debug(f"降级流水线跳过已执行步骤: {step_config.name}")
                continue
            
            step = self._get_step(step_config.name)
            if not step:
                continue
            
            try:
                context = await self._execute_step(step, context, step_config.params, step_config.timeout)
            except Exception as e:
                logger.error(f"降级流水线步骤 {step_config.name} 也失败: {e}")
                context.execution_log.append({
                    "step": step_config.name,
                    "status": "failed",
                    "error": str(e),
                })
        
        return context
```

### 4.4 热重载支持
```python
# backend/src/config/__init__.py 中的 ConfigFileChangeHandler 修改
class ConfigFileChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return
        file_path = Path(event.src_path)
        # 增加 .yaml 文件监控
        if file_path.suffix in ('.py', '.env', '.yaml') and not file_path.name.startswith('__'):
            logger.info(f"检测到配置文件变更: {file_path}")
            if file_path.suffix == '.yaml':
                # YAML 文件变更：清除流水线配置和步骤实例缓存
                from src.core.query_pipeline_orchestrator import _orchestrator_instance
                if _orchestrator_instance:
                    _orchestrator_instance.clear_cache()
            else:
                reload_settings()
```

---

## 5. 步骤实现

### 5.1 步骤目录结构

```
backend/src/core/pipeline_steps/
├── __init__.py              # 步骤注册表（工厂模式）
├── base.py                  # 步骤基类
├── cache_check.py           # 缓存检查
├── query_rewrite.py         # 查询重写
├── synonym_expand.py        # 同义词扩展
├── age_filter.py            # 年龄过滤
├── hybrid_retrieval.py      # 混合检索
├── rerank.py                # Cross-Encoder 重排序
├── dedup.py                 # 内容去重
├── convert_to_knowledge.py  # 转换为 KnowledgeItem
└── pageindex.py             # PageIndex 推理检索（预留，enabled: false）
```

### 5.2 步骤基类

**文件**: `backend/src/core/pipeline_steps/base.py`

```python
"""步骤基类，提供通用功能"""

from abc import ABC
from loguru import logger


class BasePipelineStep(ABC):
    """步骤基类"""
    
    @property
    def name(self) -> str:
        """步骤标识，子类必须实现"""
        raise NotImplementedError
    
    def _log_skip(self, context, reason: str):
        """记录步骤跳过日志"""
        from src.core.query_pipeline_orchestrator import STEP_TOTAL
        context.execution_log.append({
            "step": self.name,
            "status": "skipped",
            "reason": reason,
        })
        # 上报跳过指标
        STEP_TOTAL.labels(self.name, context.query_type, "skipped").inc()
        logger.debug(f"步骤 {self.name} 跳过: {reason} | 查询: {context.query} | 年龄: {context.age}")
    
    def _log_success(self, context, detail: str = ""):
        """记录步骤成功日志"""
        context.execution_log.append({
            "step": self.name,
            "status": "success",
            "detail": detail,
        })
```

### 5.3 步骤注册表（工厂模式）

**文件**: `backend/src/core/pipeline_steps/__init__.py`

```python
"""步骤注册表（工厂模式，延迟实例化，依赖DI容器）"""

from typing import Callable


def get_step_factory() -> dict[str, Callable]:
    """从DI容器获取步骤工厂"""
    from src.core.di_container import get_container
    container = get_container()
    return {
        "cache_check": lambda: container.get(CacheCheckStep),
        "query_rewrite": lambda: container.get(QueryRewriteStep),
        "synonym_expand": lambda: container.get(SynonymExpandStep),
        "age_filter": lambda: container.get(AgeFilterStep),
        "hybrid_retrieval": lambda: container.get(HybridRetrievalStep),
        "rerank": lambda: container.get(RerankStep),
        "dedup": lambda: container.get(DedupStep),
        "convert_to_knowledge": lambda: container.get(ConvertToKnowledgeStep),
        "pageindex": lambda: container.get(PageIndexStep),
    }


# 导出步骤类供DI容器注册
from .cache_check import CacheCheckStep
from .query_rewrite import QueryRewriteStep
from .synonym_expand import SynonymExpandStep
from .age_filter import AgeFilterStep
from .hybrid_retrieval import HybridRetrievalStep
from .rerank import RerankStep
from .dedup import DedupStep
from .convert_to_knowledge import ConvertToKnowledgeStep
from .pageindex import PageIndexStep
```

### 5.4 关键步骤实现示例

**查询重写步骤**: `backend/src/core/pipeline_steps/query_rewrite.py`

```python
"""查询重写步骤

从 RetrievalService._rewrite_query 迁移而来。
"""

from src.core.pipeline_steps.base import BasePipelineStep
from src.config import settings
from src.core.prompts import QUERY_REWRITE_PROMPT  # 使用现有常量名
from loguru import logger


class QueryRewriteStep(BasePipelineStep):
    """查询重写步骤"""
    
    def __init__(self, llm = None):
        # 优先使用注入的LLM实例，否则懒加载
        self._llm = llm if llm else self._get_llm()
    
    @property
    def name(self) -> str:
        return "query_rewrite"
    
    def _get_llm(self):
        """从DI容器获取LLM单例"""
        from src.core.di_container import get_container
        container = get_container()
        return container.get("query_rewrite_llm")
    
    async def execute(self, context, params: dict = None) -> "PipelineContext":
        """执行查询重写"""
        if not settings.rag_query_rewrite_enabled:
            self._log_skip(context, "查询重写未启用")
            return context
        
        try:
            rewritten = await self._rewrite_with_llm(context.query)
            context.rewritten_query = rewritten
            self._log_success(context, f"重写: {context.query} → {rewritten}")
        except Exception as e:
            logger.warning(f"查询重写失败，使用原始查询: {e}")
            context.rewritten_query = context.query  # 降级为原始查询
        
        return context
    
    async def _rewrite_with_llm(self, query: str) -> str:
        """LLM 重写（从 RetrievalService._rewrite_query 迁移）"""
        from langchain_core.messages import HumanMessage, SystemMessage
        
        prompt = QUERY_REWRITE_PROMPT.format(query=query)
        
        response = await self._llm.ainvoke([
            SystemMessage(content="你是一个查询重写专家，将用户查询重写为更适合检索的关键词短语。"),
            HumanMessage(content=prompt),
        ])
        
        return response.content.strip()
```

**混合检索步骤**: `backend/src/core/pipeline_steps/hybrid_retrieval.py`
```python
"""混合检索步骤"""

from src.core.pipeline_steps.base import BasePipelineStep
from src.config import settings
from llama_index.core.vector_stores import MetadataFilter
from loguru import logger


class HybridRetrievalStep(BasePipelineStep):
    """混合检索步骤"""
    
    def __init__(self, retriever = None):
        self._retriever = retriever if retriever else self._get_retriever()
    
    @property
    def name(self) -> str:
        return "hybrid_retrieval"
    
    def _get_retriever(self):
        """从DI容器获取混合检索器实例"""
        from src.core.di_container import get_container
        container = get_container()
        return container.get("hybrid_retriever")
    
    async def execute(self, context, params: dict = None) -> "PipelineContext":
        """执行混合检索"""
        params = params or {}
        
        # 优先使用重写后的查询，回退到原始查询
        search_query = context.rewritten_query if context.rewritten_query else context.query
        
        # 同义词拼接：将同义词拼接进查询用于BM25检索
        if context.synonyms:
            search_query = f"{search_query} {' '.join(context.synonyms)}"
        
        # 使用 age_filter 构建 MetadataFilter
        if context.age_filter:
            metadata_filter = MetadataFilter(**context.age_filter)
        else:
            metadata_filter = None
        
        # 从 params 读取，fallback 到 settings
        bm25_top_k = params.get("bm25_top_k", settings.rag_hybrid_bm25_top_k)
        vector_top_k = params.get("vector_top_k", settings.rag_hybrid_vector_top_k)
        merge_mode = params.get("merge_mode", settings.rag_hybrid_merge_mode)
        
        # 执行检索
        context.retrieval_results = await self._retriever.aretrieve(
            query=search_query,
            metadata_filter=metadata_filter,
            bm25_top_k=bm25_top_k,
            vector_top_k=vector_top_k,
            merge_mode=merge_mode
        )
        
        self._log_success(context, f"检索到 {len(context.retrieval_results)} 条结果，查询: {search_query}")
        return context
```

---

## 6. 检索服务重构

### 6.1 重构前（当前）

```python
# retrieval_service.py 中的 retrieve_knowledge 方法
async def retrieve_knowledge(self, query, age, limit):
    # 1. 缓存检查
    # 2. A/B 测试变体分配
    # 3. 查询重写（无条件执行）
    # 4. 同义词扩展（无条件执行）
    # 5. 年龄过滤
    # 6. 混合检索
    # 7. 重排序
    # 8. 去重
    # 9. 转换为 KnowledgeItem
    # 10. 缓存写入 + A/B 指标记录 + 监控埋点
    # ... 所有逻辑硬编码在一个方法中，约 600 行
```

### 6.2 重构后

```python
# retrieval_service.py 中的 retrieve_knowledge 方法
async def retrieve_knowledge(self, query: str, age: int, limit: int = 5) -> list[KnowledgeItem]:
    """检索知识（重构后）"""
    from src.config import settings
    
    # 开关：未启用新流水线时走旧逻辑
    if not settings.rag_pipeline_enabled:
        return await self._retrieve_knowledge_old(query, age, limit)
    
    from src.core.query_router import QueryRouter
    from src.core.query_pipeline_orchestrator import PipelineContext, get_orchestrator
    from src.core.pipeline_steps import get_step_factory
    
    # 1. 查询分类
    router = QueryRouter()
    classification = router.classify(query)
    
    # 2. 构建上下文
    context = PipelineContext(
        query=query,
        age=age,
        limit=limit,
        query_type=classification.query_type.value,
    )
    
    # 3. A/B 测试变体分配（保留现有逻辑）
    context.ab_test_variant = self._assign_ab_variant(query)
    
    # 4. 执行流水线（使用单例，缓存有效）
    orchestrator = get_orchestrator(get_step_factory())
    result = await orchestrator.execute(context)
    
    # 5. 缓存写入（如果未命中）
    if not context.cache_hit:
        await self._write_cache(query, age, limit, result.final_results, context.query_type)
    
    # 6. A/B 测试指标记录（保留现有逻辑）
    self._record_ab_metrics(context)
    
    # 7. 监控埋点（保留现有逻辑）
    self._record_monitoring_metrics(context)
    
    return result.final_results

# 保留旧逻辑作为回退方案
async def _retrieve_knowledge_old(self, query: str, age: int, limit: int = 5) -> list[KnowledgeItem]:
    """原有硬编码检索逻辑，作为回退方案"""
    # 原有600行逻辑不变
    pass
```

### 6.3 缓存Key优化
```python
def _get_cache_key(self, query: str, age: int, limit: int, query_type: str) -> str:
    """缓存键计算：包含query_type避免不同类型查询结果互相污染"""
    key_str = f"{query}:{age}:{limit}:{query_type}"
    return hashlib.md5(key_str.encode("utf-8")).hexdigest()
```

### 6.4 A/B 测试和监控处理

A/B 测试和监控逻辑**不迁移到步骤中**，保留在 `RetrievalService` 层：

| 逻辑 | 位置 | 原因 |
|------|------|------|
| A/B 变体分配 | `RetrievalService._assign_ab_variant` | 属于实验框架，与流水线无关 |
| A/B 指标记录 | `RetrievalService._record_ab_metrics` | 属于实验框架，在流水线执行后记录 |
| 监控埋点 | `RetrievalService._record_monitoring_metrics` | 属于可观测性，在流水线执行后记录 |
| 缓存写入 | `RetrievalService._write_cache` | 缓存检查是步骤，但写入在流水线外（避免步骤间耦合） |

### 6.5 search_content 方法处理

`search_content` 方法**保持不变**，不接入流水线编排：

- 它是搜索页面专用接口，无年龄过滤、无缓存、有分页
- 与 `retrieve_knowledge` 的业务语义不同
- 未来如需统一，可新增一条 `search` 流水线配置

### 6.6 改动对比

| 改动项 | 重构前 | 重构后 |
|--------|--------|--------|
| 查询分类 | 未使用 | 调用 QueryRouter |
| 查询重写 | 无条件执行 | 仅复杂查询执行 |
| 同义词扩展 | 无条件执行 | 仅复杂查询执行 |
| 流水线控制 | if-else 硬编码 | YAML 声明式配置 |
| 步骤扩展 | 修改核心方法 | 新增步骤类 + 更新 YAML |
| A/B 测试 | 混在流水线中 | 保留在 RetrievalService 层 |
| 监控埋点 | 混在流水线中 | 保留在 RetrievalService 层 |
| 回退机制 | 无 | 支持开关切回旧逻辑 |
| 代码行数 | ~600 行单文件 | ~100 行编排 + 步骤类 |

---

## 7. Bug 修复

### 7.1 同义词扩展未定义变量

**文件**: `backend/src/service/retrieval_service.py:883`

**问题**: JSON 解析失败时 fallback 中使用了 `synonyms` 变量，但该变量未定义

**修复**:
```python
# 修复前
except json.JSONDecodeError:
    logger.warning(f"同义词 JSON 解析失败: {synonyms}")  # synonyms 未定义

# 修复后
except json.JSONDecodeError:
    logger.warning(f"同义词 JSON 解析失败: {result_text}")  # 使用正确的变量
```

### 7.2 PageIndex 文件句柄泄漏

**文件**: `backend/src/core/pageindex_wrapper.py:243-253`

**问题**: `with open(file_path, 'rb') as f:` 块内只有 `pass`，然后在块外又调用 `open(file_path, 'rb')` 创建新文件对象传给 `aiohttp.FormData`，该文件对象**从未关闭**，导致文件句柄泄漏。

**修复**: 使用 try/finally 确保文件句柄关闭（aiohttp 没有 `open_file` API）：

```python
# 修复前
with open(file_path, 'rb') as f:
    pass  # 空操作，f 在此处关闭

# 文件句柄泄漏：open() 创建的文件对象从未关闭
data.add_field('file',
              open(file_path, 'rb'),
              filename=os.path.basename(file_path))

# 修复后：使用 try/finally 确保文件关闭
file_handle = open(file_path, 'rb')
try:
    data.add_field('file', file_handle, filename=os.path.basename(file_path))
    
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            f"{self.base_url}/api/v1/documents",
            data=data,
            headers=headers
        ) as response:
            if response.status not in (200, 201):
                error_text = await response.text()
                logger.error(f"PageIndex document ingestion failed: {response.status} - {error_text}")
                return False
            return True
finally:
    file_handle.close()  # 确保文件关闭
```

---

## 8. 年龄过滤统一

### 8.1 现状

| 文件 | 实现 | 问题 |
|------|------|------|
| `retrieval_service.py` | `_build_age_filters()` 方法 | 硬编码逻辑 |
| `backend/src/core/age_filter.py` | `DynamicAgeFilter` 类 | 分阶段配置，未被使用 |

### 8.2 统一方案

删除 `retrieval_service.py` 中的 `_build_age_filters()` 方法，统一使用 `DynamicAgeFilter`：

```python
# pipeline_steps/age_filter.py
from src.core.pipeline_steps.base import BasePipelineStep
from src.core.age_filter import DynamicAgeFilter
from loguru import logger


class AgeFilterStep(BasePipelineStep):
    """年龄过滤步骤"""
    
    def __init__(self, age_filter = None):
        self._age_filter = age_filter if age_filter else DynamicAgeFilter()
    
    @property
    def name(self) -> str:
        return "age_filter"
    
    async def execute(self, context: PipelineContext, params: dict = None) -> PipelineContext:
        """执行年龄过滤"""
        if context.age is None:
            self._log_skip(context, "未提供年龄信息")
            return context
        
        # build_age_filters 返回 (filters, config) 元组
        filters, config = self._age_filter.build_age_filters(context.age)
        context.age_filter = filters
        self._log_success(context, f"年龄过滤条件: {config}")
        
        return context
```

`HybridRetrievalStep` 消费 `context.age_filter`：
```python
# pipeline_steps/hybrid_retrieval.py
async def execute(self, context: PipelineContext, params: dict = None) -> PipelineContext:
    params = params or {}
    
    # 使用 age_filter 构建 MetadataFilter
    if context.age_filter:
        metadata_filter = MetadataFilter(**context.age_filter)
    else:
        metadata_filter = None
    
    # 从 params 读取，fallback 到 settings
    bm25_top_k = params.get("bm25_top_k", settings.rag_hybrid_bm25_top_k)
    vector_top_k = params.get("vector_top_k", settings.rag_hybrid_vector_top_k)
    
    # 执行检索...
```

---

## 9. 配置优先级说明

YAML `params` 和环境变量的优先级关系：

| 配置源 | 优先级 | 说明 |
|--------|--------|------|
| YAML `params` | **高** | 步骤级配置，覆盖环境变量 |
| YAML `timeout` | **高** | 步骤级超时，覆盖全局超时 |
| 环境变量 | **中** | 全局默认值 |
| 代码硬编码 | **低** | 兜底默认值 |

实现方式：步骤类读取参数时，优先从 `params` 读取，不存在则从 `settings` 读取：

```python
# 示例：HybridRetrievalStep
async def execute(self, context, params):
    bm25_top_k = params.get("bm25_top_k", settings.rag_hybrid_bm25_top_k)
    vector_top_k = params.get("vector_top_k", settings.rag_hybrid_vector_top_k)
```

---

## 10. 改动文件清单

### 10.1 新增文件

| 文件 | 职责 |
|------|------|
| `backend/src/config/modules/rag/query_pipeline.py` | 流水线配置模块 |
| `backend/src/config/query_pipeline.yaml` | YAML 配置文件 |
| `backend/src/core/query_pipeline_orchestrator.py` | 流水线编排器 |
| `backend/src/core/pipeline_steps/__init__.py` | 步骤工厂注册表 |
| `backend/src/core/pipeline_steps/base.py` | 步骤基类 |
| `backend/src/core/pipeline_steps/cache_check.py` | 缓存检查步骤 |
| `backend/src/core/pipeline_steps/query_rewrite.py` | 查询重写步骤 |
| `backend/src/core/pipeline_steps/synonym_expand.py` | 同义词扩展步骤 |
| `backend/src/core/pipeline_steps/age_filter.py` | 年龄过滤步骤 |
| `backend/src/core/pipeline_steps/hybrid_retrieval.py` | 混合检索步骤 |
| `backend/src/core/pipeline_steps/rerank.py` | 重排序步骤 |
| `backend/src/core/pipeline_steps/dedup.py` | 内容去重步骤 |
| `backend/src/core/pipeline_steps/convert_to_knowledge.py` | 转换为 KnowledgeItem 步骤 |
| `backend/src/core/pipeline_steps/pageindex.py` | PageIndex 步骤（预留） |

### 10.2 修改文件

| 文件 | 改动 |
|------|------|
| `backend/src/service/retrieval_service.py` | 重构 `retrieve_knowledge` 使用编排器，保留旧逻辑作为回退，修复同义词变量Bug，优化缓存Key |
| `backend/src/config/__init__.py` | 聚合 `QueryPipelineSettings`，更新 `_infer_category` 映射，修改热重载处理器支持yaml |
| `backend/src/core/pageindex_wrapper.py` | 修复文件句柄泄漏 Bug |
| `backend/.env.dev` | 新增流水线相关配置 |
| `backend/.env.dev.example` | 新增流水线配置示例 |
| `/AGENTS.md` | 新增RAG流水线架构说明 |
| `/CLAUDE.md` | 新增模块、配置、文件结构说明 |
| `/docs/RAG_SYSTEM_COMPLETE_DOCUMENTATION.md` | 同步新的流水线架构 |
| `/docs/配置系统文档.md` | 更新新增的流水线配置项 |

### 10.3 不修改文件

| 文件 | 原因 |
|------|------|
| `backend/src/core/query_router.py` | 保持不变，继续提供分类功能 |
| `backend/src/core/result_fusion.py` | 保留但不接入（PageIndex 未启用） |
| `backend/src/core/age_filter.py` | 保持不变，作为统一年龄过滤实现 |
| `search_content` 相关逻辑 | 保持不变，搜索页面专用接口 |

---

## 11. 配置项汇总

### 11.1 新增环境变量

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `RAG_QUERY_PIPELINE_YAML_PATH` | `""` | YAML 配置文件路径，为空时使用默认路径 |
| `RAG_PIPELINE_STEP_TIMEOUT` | `30` | 全局步骤超时（秒） |
| `RAG_PIPELINE_ENABLE_MONITORING` | `True` | 是否启用步骤级监控 |
| `RAG_PIPELINE_FAILURE_STRATEGY` | `fallback_to_default` | 失败策略 |
| `RAG_PIPELINE_ENABLED` | `False` | 是否启用新流水线，false时使用旧逻辑 |

### 11.2 保留现有环境变量

以下环境变量继续有效，作为步骤参数的全局默认值：

| 环境变量 | 用途 | 被哪个步骤使用 |
|----------|------|---------------|
| `RAG_CACHE_ENABLED` | 缓存检查步骤 | `CacheCheckStep` |
| `RAG_QUERY_REWRITE_ENABLED` | 查询重写步骤 | `QueryRewriteStep` |
| `RAG_HYBRID_BM25_TOP_K` | 混合检索步骤 | `HybridRetrievalStep` |
| `RAG_HYBRID_VECTOR_TOP_K` | 混合检索步骤 | `HybridRetrievalStep` |
| `RAG_RERANKER_INITIAL_K` | 重排序步骤 | `RerankStep` |
| `RAG_RERANKER_FINAL_K` | 重排序步骤 | `RerankStep` |
| `RAG_AGE_FILTER_STRICTNESS` | 年龄过滤步骤 | `AgeFilterStep` |

---

## 12. 性能预期

### 12.1 简单查询

| 指标 | 重构前 | 重构后 | 改善 |
|------|--------|--------|------|
| LLM 调用次数 | 2 次（重写+同义词） | 0 次 | **-100%** |
| 平均延迟（缓存未命中） | ~3-5 秒 | ~1-2 秒 | **-50%~60%** |
| 平均延迟（缓存命中） | ~3-5 秒 | ~50-200ms | **-95%+** |
| Token 消耗 | ~2000 tokens | 0 tokens | **-100%** |

**说明**: 缓存命中时，编排器单例的 `_config_cache` 和 `_step_instances` 已预热，仅需执行 `CacheCheckStep`（内存查找），无 YAML 加载和模型初始化开销。

### 12.2 复杂查询

| 指标 | 重构前 | 重构后 | 改善 |
|------|--------|--------|------|
| LLM 调用次数 | 2 次 | 2 次 | 持平 |
| 平均延迟 | ~5-8 秒 | ~5-8 秒 | 持平 |
| 可维护性 | 硬编码 | YAML 配置 | **显著提升** |
| 可观测性 | 只有日志 | 全链路指标埋点 | **显著提升** |

---

## 13. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| YAML 解析失败 | 流水线无法加载 | 内置默认配置兜底 + 启动时校验 |
| 步骤注册遗漏 | 运行时 KeyError | 单元测试覆盖所有步骤 |
| 上下文传递错误 | 步骤间数据丢失 | 类型提示 + 单元测试 |
| 性能回退 | 延迟增加 | 基准测试对比重构前后指标 |
| 配置热重载失效 | 修改 YAML 不生效 | 通过 ConfigFileChangeHandler 监听 `.yaml` 文件变更，调用 `clear_cache()` 清除所有缓存 |
| API兼容性风险 | 影响前端/调用方 | 1. 新增兼容性测试用例，确保返回格式完全一致<br>2. 上线前diff测试，差异率<0.1%才可上线<br>3. 灰度发布，逐步放量 |
| 依赖注入风险 | 测试困难 | 步骤类构造函数增加默认参数，兼容无DI场景，单元测试全部使用Mock |
| 配置迁移风险 | 服务启动失败 | 1. 上线前配置校验，打印所有加载配置<br>2. 原有配置保留3个版本过渡，添加deprecation警告 |
| YAML配置错误 | 流水线加载失败 | 1. 启动时校验格式，失败用默认配置<br>2. 新增配置校验接口<br>3. 配置变更走评审流程 |

### 13.1 快速回滚方案
1. **开关回滚**：设置`RAG_PIPELINE_ENABLED=false`，立即切回原有硬编码逻辑
2. **代码回滚**：保留原有`_retrieve_knowledge_old`方法，随时可恢复
3. **告警自动回滚**：配置错误率>1%、延迟超过阈值时自动触发告警，10分钟内未恢复自动回滚

---

## 14. 实施步骤（7个阶段，总周期14天）

### Phase 0: 前置准备（1天）
1. 新增`RAG_PIPELINE_ENABLED`开关，默认false，保留原有检索逻辑作为回退方案
2. 补充DI容器的步骤类依赖注册
3. 新增兼容性测试用例框架，准备1000条标准测试数据集

### Phase 1: Bug 修复（优先，1天）
1. 修复 `retrieval_service.py` 同义词扩展未定义变量
2. 修复 `pageindex_wrapper.py` 文件句柄泄漏
3. 验证修复后的功能正常

### Phase 2: 基础设施搭建（2天）
1. 创建 `backend/src/config/modules/rag/query_pipeline.py` 配置模块
2. 创建 `backend/src/config/query_pipeline.yaml` 默认配置文件
3. 创建 `backend/src/core/query_pipeline_orchestrator.py` 编排器
4. 创建 `backend/src/core/pipeline_steps/` 目录结构和基类
5. 更新 `backend/src/config/__init__.py` 聚合入口
6. 新增Prometheus指标定义
7. 更新热重载处理器支持yaml文件监控

### Phase 3: 步骤迁移（3天）
1. 迁移 `cache_check` 逻辑到 `pipeline_steps/cache_check.py`
2. 迁移 `query_rewrite` 逻辑到 `pipeline_steps/query_rewrite.py`
3. 迁移 `synonym_expand` 逻辑到 `pipeline_steps/synonym_expand.py`
4. 迁移 `age_filter` 逻辑到 `pipeline_steps/age_filter.py`
5. 迁移 `hybrid_retrieval` 逻辑到 `pipeline_steps/hybrid_retrieval.py`
6. 迁移 `rerank` 逻辑到 `pipeline_steps/rerank.py`
7. 迁移 `dedup` 逻辑到 `pipeline_steps/dedup.py`
8. 迁移 `convert_to_knowledge` 逻辑到 `pipeline_steps/convert_to_knowledge.py`
9. 完成步骤级单元测试，覆盖率>80%

### Phase 4: 检索服务重构（2天）
1. 重构 `retrieval_service.py` 的 `retrieve_knowledge` 方法，集成编排器
2. 保留原有逻辑为`_retrieve_knowledge_old`作为回退
3. 新增开关逻辑：`RAG_PIPELINE_ENABLED=true`时走新流水线，否则走旧逻辑
4. 完成集成测试，验证simple/complex/default三种流水线功能正常
5. 完成兼容性测试，验证返回结果与旧逻辑一致

### Phase 5: 灰度验证（3天）
1. 测试环境验证所有功能正常，性能指标达标（简单查询P95<2s）
2. 线上灰度10%流量，监控错误率、延迟、Token消耗指标
3. 对比新旧逻辑的结果一致性，差异率<0.1%
4. 验证热重载、降级策略、缓存等功能正常
5. 灰度期间无问题，逐步提升到50%、100%流量

### Phase 6: 文档同步（1天）
1. 更新 `AGENTS.md` 新增流水线架构说明
2. 更新 `CLAUDE.md` 新增模块、配置、文件结构说明
3. 更新 `docs/RAG_SYSTEM_COMPLETE_DOCUMENTATION.md` 同步新架构
4. 更新配置系统文档，补充新增配置项说明

### Phase 7: 全量上线与收尾（1天）
1. 全量流量切到新流水线，监控24小时无异常
2. 删除旧的硬编码流水线逻辑（可选，下个版本删除）
3. 清理冗余配置项，添加deprecation警告
4. 输出上线报告，性能提升数据汇总

---

## 15. 测试策略

### 15.1 单元测试

| 测试目标 | 测试内容 |
|----------|---------|
| `PipelineOrchestrator` | 配置加载、步骤执行、失败策略、降级去重 |
| 各步骤类 | 输入输出正确性、边界条件、跳过逻辑 |
| YAML 配置解析 | 格式校验、环境变量替换、默认路径兜底 |
| `_resolve_env_vars` | 环境变量替换正确性、默认值回退 |

### 15.2 集成测试

| 测试场景 | 验证内容 |
|----------|---------|
| 简单查询 | 跳过 LLM 增强，直接检索 |
| 复杂查询 | 执行完整链路（重写→同义词→年龄过滤→检索→重排序→去重→转换） |
| 缓存命中 | 直接返回缓存结果，跳过后续步骤，缓存key包含query_type |
| 步骤失败 | 降级策略正确执行（跳过已执行步骤） |
| PageIndex 未启用 | 步骤被跳过，不影响流水线 |
| YAML 配置无效 | 使用内置默认配置兜底，不崩溃 |
| QueryRouter 分类失败 | 降级到 default 流水线 |
| 空索引（corpus_size=0） | 流水线正常执行，返回空列表 |
| 步骤返回空结果 | 下游步骤正确处理空输入 |
| 开关回退 | RAG_PIPELINE_ENABLED=false时正确使用旧逻辑 |

### 15.3 性能测试

| 指标 | 测量方法 | 验收标准 |
|------|---------|----------|
| 简单查询延迟 | 100 次请求 P50/P95/P99 | P95 < 2s |
| 复杂查询延迟 | 50 次请求 P50/P95/P99 | P95 < 8s |
| 缓存命中延迟 | 50 次请求 P50/P95/P99 | P95 < 200ms |
| LLM 调用次数 | 监控计数器 | 简单查询调用次数为0 |
| Token 消耗 | LLM API 统计 | 整体降低60%+ |
| 结果一致性 | 新旧逻辑对比 | 差异率 < 0.1% |

---

## ✅ 验收标准
1. **功能验收**：所有检索场景功能正常，与旧逻辑返回结果一致性>99.9%
2. **性能验收**：简单查询P95延迟降低50%以上，Token消耗降低60%以上
3. **可观测性验收**：所有指标正常上报，错误日志包含完整上下文
4. **兼容性验收**：配置修改热重载生效，失败降级策略正常执行
5. **文档验收**：所有架构文档、配置文档同步更新完毕
