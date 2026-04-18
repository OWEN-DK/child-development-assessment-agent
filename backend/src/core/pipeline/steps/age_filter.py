from src.core.pipeline.orchestrator import PipelineContext, PipelineStep
from src.utils.logger import logger


class AgeFilterStep(PipelineStep):
    """年龄过滤步骤：根据儿童年龄过滤不适合的检索结果"""

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行年龄过滤"""
        strictness = self.config.get("strictness", 0.7)
        tolerance = self.config.get("tolerance", 2.0)

        age = context.age
        min_age = max(0, age - tolerance)
        max_age = age + tolerance

        logger.debug(f"年龄过滤：年龄={age}岁，允许范围={min_age}-{max_age}岁")

        # 过滤结果
        filtered_results = []
        for result in context.results:
            # 获取结果的年龄范围
            result_min = result.metadata.get("target_age_min", 0)
            result_max = result.metadata.get("target_age_max", 18)

            # 计算匹配度
            overlap = max(0, min(result_max, max_age) - max(result_min, min_age))
            total_range = max(result_max - result_min, max_age - min_age, 1)
            match_rate = overlap / total_range

            if match_rate >= strictness:
                filtered_results.append(result)
            else:
                logger.debug(
                    f"过滤结果：年龄范围{result_min}-{result_max}岁，匹配率{match_rate:.2f} < {strictness}"
                )

        context.results = filtered_results
        context.metadata["age_filtered_count"] = len(filtered_results)
        logger.info(
            f"年龄过滤完成：原始={len(context.results)}, 过滤后={len(filtered_results)}"
        )

        return context
