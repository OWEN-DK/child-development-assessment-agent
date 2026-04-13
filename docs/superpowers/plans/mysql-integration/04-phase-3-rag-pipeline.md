# Phase 3: RAG 查询流水线声明式重构

> 本文档是 MySQL + Redis 集成重构实施方案的一部分
> 
> **返回索引：** [README.md](./README.md) | [项目概览](./00-overview.md)

---

## Phase 3: RAG 查询流水线声明式重构（周期：4 天）

### 目标
实现 YAML 配置驱动的声明式 RAG 查询流水线，将硬编码的检索逻辑转为可配置的流水线步骤，支持动态插拔和热重载。

### 架构设计

```
┌─────────────────────────────────────────────────┐
│           用户查询 (User Query)                  │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│         YAML 配置文件 (rag_pipeline.yaml)         │
│  steps:                                          │
│    - query_router                                │
│    - cache_check                                 │
│    - query_rewrite                               │
│    - synonym_expansion                           │
│    - age_filter                                  │
│    - hybrid_retrieval                            │
│    - reranking                                   │
│    - deduplication                               │
│    - pageindex_enhancement                       │
│    - result_fusion                               │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│         流水线编排器 (Pipeline Orchestrator)     │
│    - 动态加载配置                                │
│    - 按顺序执行步骤                              │
│    - 错误降级处理                                │
│    - 性能监控                                    │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│         可插拔步骤组件 (Pluggable Steps)         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │  Step 1  │ │  Step 2  │ │  Step N  │        │
│  └──────────┘ └──────────┘ └──────────┘        │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│          返回 KnowledgeItem 列表                  │
└─────────────────────────────────────────────────┘
```

---

### Task 3.1: 创建流水线编排器

**Files:**
- Create: `backend/src/core/pipeline/orchestrator.py`
- Create: `backend/src/core/pipeline/__init__.py`
- Create: `backend/config/rag_pipeline.yaml`

- [ ] **Step 1: 定义 YAML 配置结构**

```yaml
# backend/config/rag_pipeline.yaml
pipeline:
  name: "rag_query_pipeline"
  version: "1.0.0"
  description: "RAG 查询流水线配置"

# 全局配置
global:
  cache_enabled: true
  cache_ttl: 3600
  timeout_ms: 30000
  max_retries: 2

# 双流水线配置（根据查询复杂度路由）
pipelines:
  simple:  # 事实性/定义性问题，跳过大模型重写
    - name: cache_check
      enabled: true
      config:
        cache_key_prefix: "rag:query"
        ttl: 3600
    
    - name: hybrid_retrieval
      enabled: true
      config:
        bm25_top_k: 10
        vector_top_k: 10
        bm25_weight: 0.5
        vector_weight: 0.5
        fusion_mode: "reciprocal_rank"
    
    - name: reranking
      enabled: true
      config:
        model: "BAAI/bge-reranker-v2-m3"
        initial_k: 30
        final_k: 5
    
    - name: deduplication
      enabled: true
      config:
        similarity_threshold: 0.85
        use_exact_match: true
        use_containment: true

  complex:  # 比较分析/多步骤问题，启用全量增强
    - name: cache_check
      enabled: true
      config:
        cache_key_prefix: "rag:query"
        ttl: 3600
    
    - name: query_rewrite
      enabled: true
      config:
        model: "qwen-plus"
        temperature: 0.3
    
    - name: synonym_expansion
      enabled: true
      config:
        model: "qwen-plus"
        max_synonyms: 5
        min_length: 2
        max_length: 10
    
    - name: age_filter
      enabled: true
      config:
        strictness: 0.7
        tolerance: 2
    
    - name: hybrid_retrieval
      enabled: true
      config:
        bm25_top_k: 10
        vector_top_k: 10
        bm25_weight: 0.5
        vector_weight: 0.5
        fusion_mode: "reciprocal_rank"
    
    - name: reranking
      enabled: true
      config:
        model: "BAAI/bge-reranker-v2-m3"
        initial_k: 30
        final_k: 5
    
    - name: deduplication
      enabled: true
      config:
        similarity_threshold: 0.85
        use_exact_match: true
        use_containment: true
    
    - name: pageindex_enhancement
      enabled: true  # 仅复杂查询启用
      config:
        fuse_factor: 1.2
        max_hybrid_supplement: 5

# 错误降级配置
fallback:
  on_step_failure: "skip"  # skip: 跳过失败步骤，abort: 中止流水线
  on_timeout: "return_partial"  # return_partial: 返回部分结果，abort: 中止
  min_results: 3  # 最少返回结果数
```

- [ ] **Step 2: 创建流水线编排器**

```python
import yaml
import time
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass
from src.utils.logger import logger
from src.config import settings

@dataclass
class PipelineContext:
    """流水线上下文"""
    query: str
    age: float
    limit: int = 5
    results: list[Any] = None
    metadata: dict[str, Any] = None
    start_time: float = None
    errors: list[str] = None
    
    def __post_init__(self):
        if self.results is None:
            self.results = []
        if self.metadata is None:
            self.metadata = {}
        if self.errors is None:
            self.errors = []
        if self.start_time is None:
            self.start_time = time.time()

class PipelineStep:
    """流水线步骤基类"""
    
    def __init__(self, name: str, config: dict[str, Any]):
        self.name = name
        self.config = config
    
    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行步骤"""
        raise NotImplementedError

class PipelineOrchestrator:
    """流水线编排器（支持 simple/complex 双流水线）"""
    
    def __init__(self, config_path: str = "config/rag_pipeline.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.step_pipelines = self._initialize_pipelines()
        logger.info(f"RAG 流水线已初始化：{self.config['pipeline']['name']}")
    
    def _load_config(self) -> dict:
        """加载 YAML 配置"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _initialize_pipelines(self) -> dict[str, list[PipelineStep]]:
        """初始化 simple/complex 双流水线"""
        from src.core.pipeline import steps as step_modules
        
        # 步骤名称到类名的显式映射
        STEP_CLASS_MAP = {
            "query_router": "QueryRouterStep",
            "cache_check": "CacheCheckStep",
            "query_rewrite": "QueryRewriteStep",
            "synonym_expansion": "SynonymExpansionStep",
            "age_filter": "AgeFilterStep",
            "hybrid_retrieval": "HybridRetrievalStep",
            "reranking": "RerankingStep",
            "deduplication": "DeduplicationStep",
            "pageindex_enhancement": "PageIndexEnhancementStep",
            "result_fusion": "ResultFusionStep",
        }
        
        pipelines = {}
        for pipeline_name, step_configs in self.config['pipelines'].items():
            step_instances = []
            for step_config in step_configs:
                if not step_config.get('enabled', True):
                    continue
                
                step_name = step_config['name']
                class_name = STEP_CLASS_MAP.get(step_name, f"{step_name.title().replace('_', '')}Step")
                step_class = getattr(step_modules, class_name, None)
                
                if not step_class:
                    logger.warning(f"未找到步骤实现：{step_name} (期望类名: {class_name})")
                    continue
                
                step = step_class(name=step_name, config=step_config.get('config', {}))
                step_instances.append(step)
            
            pipelines[pipeline_name] = step_instances
            logger.info(f"流水线 [{pipeline_name}] 已加载 {len(step_instances)} 个步骤")
        
        return pipelines
    
    async def execute(self, query: str, age: float, limit: int = 5) -> list[Any]:
        """执行流水线（根据查询复杂度自动路由）"""
        # 1. 查询路由（决定使用 simple 还是 complex 流水线）
        query_type = await self._classify_query(query)
        
        # 2. 选择对应流水线
        pipeline_steps = self.step_pipelines.get(query_type, self.step_pipelines['simple'])
        
        # 3. 执行流水线
        context = PipelineContext(query=query, age=age, limit=limit)
        context.metadata['query_type'] = query_type
        
        logger.info(f"开始执行 RAG 流水线 [{query_type}]：{query[:50]}...")
        
        for step in pipeline_steps:
            try:
                elapsed_ms = (time.time() - context.start_time) * 1000
                timeout_ms = self.config['global'].get('timeout_ms', 30000)
                
                if elapsed_ms > timeout_ms:
                    logger.warning(f"流水线超时：{elapsed_ms:.0f}ms")
                    if self.config['fallback']['on_timeout'] == 'abort':
                        break
                    else:
                        continue
                
                logger.debug(f"执行步骤：{step.name}")
                context = await step.execute(context)
                
            except Exception as e:
                logger.error(f"步骤 {step.name} 执行失败：{e}")
                context.errors.append(f"{step.name}: {str(e)}")
                
                if self.config['fallback']['on_step_failure'] == 'abort':
                    raise
                # 否则跳过失败步骤
        
        logger.info(f"RAG 流水线 [{query_type}] 执行完成，返回 {len(context.results)} 个结果")
        return context.results
    
    async def _classify_query(self, query: str) -> str:
        """简单查询分类（可替换为 LLM 分类器）"""
        # 默认使用 complex 流水线，后续可接入 QueryRouter
        return "complex"
    
    def reload_config(self):
        """重新加载配置（热重载）"""
        self.config = self._load_config()
        self.step_pipelines = self._initialize_pipelines()
        logger.info("RAG 流水线配置已热重载")
```

- [ ] **Step 3: 创建步骤模块包**

```python
# backend/src/core/pipeline/steps/__init__.py
from .query_router import QueryRouterStep
from .cache_check import CacheCheckStep
from .query_rewrite import QueryRewriteStep
from .synonym_expansion import SynonymExpansionStep
from .age_filter import AgeFilterStep
from .hybrid_retrieval import HybridRetrievalStep
from .reranking import RerankingStep
from .deduplication import DeduplicationStep
from .pageindex_enhancement import PageIndexEnhancementStep
from .result_fusion import ResultFusionStep

__all__ = [
    "QueryRouterStep",
    "CacheCheckStep",
    "QueryRewriteStep",
    "SynonymExpansionStep",
    "AgeFilterStep",
    "HybridRetrievalStep",
    "RerankingStep",
    "DeduplicationStep",
    "PageIndexEnhancementStep",
    "ResultFusionStep",
]
```

- [ ] **Step 4: 测试编排器**

```bash
cd backend
uv run python -c "
import asyncio
from src.core.pipeline.orchestrator import PipelineOrchestrator

async def test():
    orchestrator = PipelineOrchestrator()
    
    # 测试执行
    results = await orchestrator.execute(
        query='2 岁儿童语言发展迟缓怎么办',
        age=2.0,
        limit=5,
    )
    
    print(f'返回 {len(results)} 个结果')
    for i, result in enumerate(results):
        print(f'{i+1}. {result.content[:50]}...')

asyncio.run(test())
"
```

**Expected:** 流水线正常执行，返回检索结果。

---

### Task 3.2: 实现查询路由步骤

**Files:**
- Create: `backend/src/core/pipeline/steps/query_router.py`

- [ ] **Step 1: 创建查询路由步骤**

```python
from src.core.pipeline.orchestrator import PipelineStep, PipelineContext
from src.core.llm.factory import LLMServiceFactory, LLMFramework
from src.core.llm.base import LLMRequest, LLMMessage
from src.utils.logger import logger

class QueryRouterStep(PipelineStep):
    """查询路由步骤：简单/复杂查询分类"""
    
    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行查询路由"""
        model = self.config.get('model', 'qwen3-omni-flash')
        confidence_threshold = self.config.get('confidence_threshold', 0.8)
        
        # 创建 LLM 实例
        llm = LLMServiceFactory.create(
            framework=LLMFramework.LANGCHAIN,
            model_name=model,
            scenario='query_routing',
            temperature=0.1,
        )
        
        # 构建提示词
        prompt = f"""请判断以下查询的复杂度：
查询：{context.query}

分类标准：
- 简单查询：事实性问题、定义性问题、单一知识点
- 复杂查询：比较分析、多步骤推理、需要综合多个知识点

请返回 JSON 格式：
{{
    "query_type": "simple" or "complex",
    "confidence": 0.0-1.0,
    "reason": "分类理由"
}}
"""
        
        messages = [
            LLMMessage(role='system', content='你是一个查询分类专家'),
            LLMMessage(role='user', content=prompt),
        ]
        
        response = await llm.chat(
            LLMRequest(
                messages=messages,
                model_name=model,
                temperature=0.1,
                max_tokens=256,
                scenario='query_routing',
            )
        )
        
        # 解析响应
        import json
        try:
            result = json.loads(response.content)
            context.metadata['query_type'] = result['query_type']
            context.metadata['routing_confidence'] = result['confidence']
            context.metadata['routing_reason'] = result['reason']
            
            logger.info(f"查询路由：{context.query[:30]}... -> {result['query_type']} (置信度：{result['confidence']:.2f})")
            
        except Exception as e:
            logger.warning(f"查询路由解析失败，降级为复杂查询：{e}")
            context.metadata['query_type'] = 'complex'
            context.metadata['routing_confidence'] = 0.0
        
        return context
```

---

### Task 3.3: 实现混合检索融合步骤

**Files:**
- Create: `backend/src/core/pipeline/steps/hybrid_retrieval.py`

- [ ] **Step 1: 创建混合检索步骤**

```python
from src.core.pipeline.orchestrator import PipelineStep, PipelineContext
from src.service.retrieval_service import RetrievalService
from src.core.hybrid_retrieval import HybridRetriever
from src.utils.logger import logger

class HybridRetrievalStep(PipelineStep):
    """混合检索步骤：BM25 + 向量检索"""
    
    def __init__(self, name: str, config: dict[str, Any]):
        super().__init__(name, config)
        # 单例注入，避免每次调用创建新实例
        from src.service.retrieval_service import RetrievalService
        self._retrieval_service = RetrievalService()
    
    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行混合检索"""
        bm25_top_k = self.config.get('bm25_top_k', 10)
        vector_top_k = self.config.get('vector_top_k', 10)
        bm25_weight = self.config.get('bm25_weight', 0.5)
        
        # 构建扩展查询
        expanded_query = context.query
        if 'synonyms' in context.metadata:
            expanded_query = f"{context.query} {' '.join(context.metadata['synonyms'])}"
        
        # 执行 BM25 检索
        logger.debug(f"执行 BM25 检索：{expanded_query[:50]}...")
        bm25_results = await self._retrieval_service.bm25_search(expanded_query, bm25_top_k)
        
        # 执行向量检索
        logger.debug(f"执行向量检索：{expanded_query[:50]}...")
        vector_results = await self._retrieval_service.vector_search(expanded_query, vector_top_k)
        
        # 融合结果
        context.metadata['bm25_count'] = len(bm25_results)
        context.metadata['vector_count'] = len(vector_results)
        
        hybrid_results = self._fuse_results(
            bm25_results,
            vector_results,
            bm25_weight,
            1.0 - bm25_weight,
        )
        
        context.results = hybrid_results
        logger.info(f"混合检索完成：BM25={len(bm25_results)}, Vector={len(vector_results)}, 融合后={len(hybrid_results)}")
        
        return context
    
    def _fuse_results(self, bm25: list, vector: list, bm25_w: float, vector_w: float) -> list:
        """融合结果"""
        from src.core.hybrid_retrieval import HybridRetriever
        merger = HybridRetriever()
        return merger.fuse(bm25, vector, bm25_w, vector_w)
```

---

### Task 3.4: 实现 PageIndex 索引集成步骤

**Files:**
- Create: `backend/src/core/pipeline/steps/pageindex_enhancement.py`

- [ ] **Step 1: 创建 PageIndex 增强步骤**

```python
from src.core.pipeline.orchestrator import PipelineStep, PipelineContext
from src.core.pageindex_wrapper import PageIndexWrapper
from src.utils.logger import logger

class PageIndexEnhancementStep(PipelineStep):
    """PageIndex 增强步骤：仅复杂查询启用"""
    
    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行 PageIndex 增强"""
        # 检查是否为复杂查询
        query_type = context.metadata.get('query_type', 'simple')
        if query_type != 'complex':
            logger.debug(f"跳过 PageIndex 增强：查询类型为 {query_type}")
            return context
        
        # 检查是否启用
        if not self.config.get('enabled', False):
            logger.debug("PageIndex 增强已禁用")
            return context
        
        # 执行 PageIndex 检索
        logger.info("执行 PageIndex 增强检索")
        pageindex = PageIndexWrapper()
        
        try:
            pageindex_results = await pageindex.search(
                query=context.query,
                age=context.age,
                limit=self.config.get('limit', 5),
            )
            
            # 融合结果
            fuse_factor = self.config.get('fuse_factor', 1.2)
            max_hybrid = self.config.get('max_hybrid 补充', 5)
            
            enhanced_results = self._enhance_with_pageindex(
                context.results,
                pageindex_results,
                fuse_factor,
                max_hybrid,
            )
            
            context.results = enhanced_results
            context.metadata['pageindex_count'] = len(pageindex_results)
            context.metadata['enhanced_count'] = len(enhanced_results)
            
            logger.info(f"PageIndex 增强完成：原始={len(context.results)}, 增强后={len(enhanced_results)}")
            
        except Exception as e:
            logger.error(f"PageIndex 增强失败：{e}")
            context.errors.append(f"pageindex: {str(e)}")
        
        return context
    
    def _enhance_with_pageindex(self, existing: list, pageindex: list, fuse_factor: float, max_hybrid: int) -> list:
        """融合 PageIndex 结果"""
        from src.core.result_fusion import ResultFusion
        fusion = ResultFusion()
        return fusion.fuse_pageindex(existing, pageindex, fuse_factor, max_hybrid)
```

---

### Task 3.5: 修复已知问题

**Files:**
- Modify: `backend/src/service/retrieval_service.py`
- Modify: `backend/src/core/pipeline/steps/synonym_expansion.py`

- [ ] **Step 1: 修复 synonyms 变量未定义**

```python
# 在 retrieval_service.py 中
async def _expand_synonyms(self, query: str, age: float) -> list[str]:
    """同义词扩展"""
    # 确保 synonyms 变量已定义
    synonyms = []
    
    try:
        # ... 现有代码 ...
        # 从 LLM 响应中解析同义词
        response = await llm.chat(request)
        import json
        result = json.loads(response.content)
        synonyms = result.get('synonyms', [])
        
    except Exception as e:
        logger.error(f"同义词扩展失败：{e}")
        # 返回空列表而不是未定义变量
    
    return synonyms
```

- [ ] **Step 2: 修复 pageindex 文件句柄泄漏**

```python
# 在 pageindex_wrapper.py 中
class PageIndexWrapper:
    async def search(self, query: str, age: float, limit: int = 5) -> list:
        """搜索"""
        index = None
        try:
            index = self._load_index()
            # ... 搜索逻辑 ...
            return results
            
        finally:
            # 确保文件句柄关闭
            if index and hasattr(index, 'close'):
                index.close()
```

---

### Phase 3 完成验证

- [ ] 运行单元测试，验证所有步骤功能正常
- [ ] 测试 YAML 配置热重载
- [ ] 验证错误降级机制
- [ ] 检查性能监控数据
- [ ] 确认 PageIndex 集成正常
- [ ] 修复所有已知问题

---

**返回索引：** [README.md](./README.md)
