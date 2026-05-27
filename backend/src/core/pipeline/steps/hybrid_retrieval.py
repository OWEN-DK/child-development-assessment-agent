from typing import Any

from src.core.pipeline.orchestrator import PipelineContext, PipelineStep
from src.utils.logger import logger


class HybridRetrievalStep(PipelineStep):
    """混合检索步骤：BM25 + 向量检索"""

    def __init__(self, name: str, config: dict[str, Any]):
        super().__init__(name, config)
        # 懒加载：避免 __init__ 中触发 DI 递归
        # (HybridRetrievalStep → IRetrievalService → RetrievalFacade
        #  → PipelineOrchestrator → step 实例化 → 回到这里)
        self.__retrieval_service = None

    @property
    def _retrieval_service(self):
        """懒加载 IRetrievalService，打破 __init__ 中的 DI 循环依赖"""
        if self.__retrieval_service is None:
            from src.core.di_container import injector
            from src.core.interfaces import IRetrievalService
            self.__retrieval_service = injector.get(IRetrievalService)
        return self.__retrieval_service

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行混合检索"""
        bm25_top_k = self.config.get("bm25_top_k", 10)
        vector_top_k = self.config.get("vector_top_k", 10)
        bm25_weight = self.config.get("bm25_weight", 0.5)

        # 构建扩展查询
        expanded_query = context.query
        if "synonyms" in context.metadata:
            expanded_query = f"{context.query} {' '.join(context.metadata['synonyms'])}"

        # 执行 BM25 检索
        logger.debug(f"执行 BM25 检索：{expanded_query[:50]}...")
        bm25_results = await self._retrieval_service.bm25_search(
            expanded_query, bm25_top_k
        )

        # 执行向量检索
        logger.debug(f"执行向量检索：{expanded_query[:50]}...")
        vector_results = await self._retrieval_service.vector_search(
            expanded_query, vector_top_k
        )

        # 融合结果
        context.metadata["bm25_count"] = len(bm25_results)
        context.metadata["vector_count"] = len(vector_results)

        hybrid_results = self._fuse_results(
            bm25_results,
            vector_results,
            bm25_weight,
            1.0 - bm25_weight,
        )

        context.results = hybrid_results
        logger.info(
            f"混合检索完成：BM25={len(bm25_results)}, Vector={len(vector_results)}, 融合后={len(hybrid_results)}"
        )

        return context

    def _fuse_results(
        self, bm25: list, vector: list, bm25_w: float, vector_w: float
    ) -> list:
        """融合结果"""
        from src.core.hybrid_retrieval import HybridRetrievalMerger

        return HybridRetrievalMerger.merge_results(
            bm25_nodes=bm25,
            vector_nodes=vector,
            bm25_weight=bm25_w,
            vector_weight=vector_w,
        )
