from src.core.pipeline.orchestrator import PipelineContext, PipelineStep
from src.utils.logger import logger


class ResultFusionStep(PipelineStep):
    """结果融合步骤：归一化分数，合并多源结果"""

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行结果融合"""
        if not context.results:
            logger.debug("没有结果需要融合")
            return context

        # 归一化分数到0-1范围
        scores = [result.score for result in context.results]
        min_score = min(scores) if scores else 0
        max_score = max(scores) if scores else 1

        if max_score > min_score:
            for result in context.results:
                result.normalized_score = (result.score - min_score) / (
                    max_score - min_score
                )
        else:
            for result in context.results:
                result.normalized_score = 1.0

        # 按归一化分数排序
        context.results.sort(key=lambda x: x.normalized_score, reverse=True)

        # 截断到limit个结果
        context.results = context.results[: context.limit]

        context.metadata["fused_count"] = len(context.results)
        logger.info(f"结果融合完成：返回{len(context.results)}个结果")

        return context
