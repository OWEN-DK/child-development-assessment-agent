from src.core.pipeline.orchestrator import PipelineContext, PipelineStep
from src.core.reranker import CrossEncoderReranker as Reranker
from src.utils.logger import logger


class RerankingStep(PipelineStep):
    """重排序步骤：使用CrossEncoder模型对检索结果重新排序"""

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self._reranker = Reranker()
        self._initial_k = self.config.get("initial_k", 30)
        self._final_k = self.config.get("final_k", 5)

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行重排序"""
        if not context.results:
            logger.debug("没有结果需要重排序")
            return context

        # 取前initial_k个结果进行重排序
        candidates = context.results[: self._initial_k]

        # 执行重排序
        try:
            ranked_results = await self._reranker.rerank(
                query=context.query, candidates=candidates, top_k=self._final_k
            )

            context.results = ranked_results
            context.metadata["reranked_count"] = len(ranked_results)
            logger.info(
                f"重排序完成：原始={len(candidates)}, 重排序后={len(ranked_results)}"
            )

        except Exception as e:
            logger.warning(f"重排序失败，使用原始排序：{e}")
            context.results = candidates[: self._final_k]

        return context
