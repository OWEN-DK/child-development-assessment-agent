import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from src.config import settings
from src.utils.logger import logger


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

    _ever_initialized = False
    _pipelines_ever_loaded = False

    def __init__(self, config_path: str = "config/rag_pipeline.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.step_pipelines = self._initialize_pipelines()
        if not PipelineOrchestrator._ever_initialized:
            PipelineOrchestrator._ever_initialized = True
            logger.info(f"RAG 流水线已初始化：{self.config['pipeline']['name']}")

    def _load_config(self) -> dict:
        """加载 YAML 配置"""
        with open(self.config_path, "r", encoding="utf-8") as f:
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
        for pipeline_name, step_configs in self.config["pipelines"].items():
            step_instances = []
            for step_config in step_configs:
                if not step_config.get("enabled", True):
                    continue

                step_name = step_config["name"]
                class_name = STEP_CLASS_MAP.get(
                    step_name, f"{step_name.title().replace('_', '')}Step"
                )
                step_class = getattr(step_modules, class_name, None)

                if not step_class:
                    logger.warning(
                        f"未找到步骤实现：{step_name} (期望类名: {class_name})"
                    )
                    continue

                step = step_class(name=step_name, config=step_config.get("config", {}))
                step_instances.append(step)

            pipelines[pipeline_name] = step_instances
            if not PipelineOrchestrator._pipelines_ever_loaded:
                logger.info(f"流水线 [{pipeline_name}] 已加载 {len(step_instances)} 个步骤")

        PipelineOrchestrator._pipelines_ever_loaded = True
        return pipelines

    async def execute(self, query: str, age: float, limit: int = 5) -> list[Any]:
        """执行流水线（根据查询复杂度自动路由）"""
        # 1. 查询路由（决定使用 simple 还是 complex 流水线）
        query_type = await self._classify_query(query)

        # 2. 选择对应流水线
        pipeline_steps = self.step_pipelines.get(
            query_type, self.step_pipelines["simple"]
        )

        # 3. 执行流水线
        context = PipelineContext(query=query, age=age, limit=limit)
        context.metadata["query_type"] = query_type

        logger.info(f"开始执行 RAG 流水线 [{query_type}]：{query[:50]}...")

        for step in pipeline_steps:
            try:
                elapsed_ms = (time.time() - context.start_time) * 1000
                timeout_ms = self.config["global"].get("timeout_ms", 30000)

                if elapsed_ms > timeout_ms:
                    logger.warning(f"流水线超时：{elapsed_ms:.0f}ms")
                    if self.config["fallback"]["on_timeout"] == "abort":
                        break
                    else:
                        continue

                logger.debug(f"执行步骤：{step.name}")
                context = await step.execute(context)

            except Exception as e:
                logger.error(f"步骤 {step.name} 执行失败：{e}")
                context.errors.append(f"{step.name}: {str(e)}")

                if self.config["fallback"]["on_step_failure"] == "abort":
                    raise
                # 否则跳过失败步骤

        logger.info(
            f"RAG 流水线 [{query_type}] 执行完成，返回 {len(context.results)} 个结果"
        )

        self._record_metrics(context, query_type)
        return context.results

    def _record_metrics(self, context: PipelineContext, query_type: str):
        """记录 Pipeline 执行指标"""
        elapsed_ms = (time.time() - context.start_time) * 1000

        logger.info(
            f"RAG 流水线 [{query_type}] 执行完成："
            f"{len(context.results)} 个结果，耗时 {elapsed_ms:.0f}ms"
        )

        if context.errors:
            logger.warning(f"流水线执行错误：{', '.join(context.errors)}")

    async def _classify_query(self, query: str) -> str:
        """基于规则简单/复杂查询分类"""
        complex_keywords = [
            "区别",
            "对比",
            "差异",
            "比较",
            "如何",
            "为什么",
            "原因",
            "分析",
            "评估",
        ]

        for keyword in complex_keywords:
            if keyword in query:
                return "complex"

        if len(query) > 20:
            return "complex"

        return "simple"

    def reload_config(self):
        """重新加载配置（热重载）"""
        self.config = self._load_config()
        self.step_pipelines = self._initialize_pipelines()
        logger.info("RAG 流水线配置已热重载")
