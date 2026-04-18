import difflib

from src.core.pipeline.orchestrator import PipelineContext, PipelineStep
from src.utils.logger import logger


class DeduplicationStep(PipelineStep):
    """去重步骤：去除重复或高度相似的检索结果"""

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行去重"""
        similarity_threshold = self.config.get("similarity_threshold", 0.85)
        use_exact_match = self.config.get("use_exact_match", True)
        use_containment = self.config.get("use_containment", True)

        if not context.results:
            logger.debug("没有结果需要去重")
            return context

        unique_results = []
        seen_contents = set()

        for result in context.results:
            content = result.content.strip()

            # 精确匹配去重
            if use_exact_match:
                if content in seen_contents:
                    logger.debug(f"过滤重复结果：精确匹配 '{content[:50]}...'")
                    continue
                seen_contents.add(content)

            # 包含关系去重
            if use_containment:
                is_duplicate = False
                for unique in unique_results:
                    unique_content = unique.content.strip()
                    if content in unique_content or unique_content in content:
                        logger.debug(
                            f"过滤包含结果：'{content[:50]}...' 已存在于已有结果中"
                        )
                        is_duplicate = True
                        break
                if is_duplicate:
                    continue

            # 相似度去重
            is_similar = False
            for unique in unique_results:
                unique_content = unique.content.strip()
                similarity = difflib.SequenceMatcher(
                    None, content, unique_content
                ).ratio()
                if similarity >= similarity_threshold:
                    logger.debug(
                        f"过滤相似结果：相似度{similarity:.2f} >= {similarity_threshold}，'{content[:50]}...'"
                    )
                    is_similar = True
                    break
            if is_similar:
                continue

            unique_results.append(result)

        context.results = unique_results
        context.metadata["deduplicated_count"] = len(unique_results)
        logger.info(
            f"去重完成：原始={len(context.results)}, 去重后={len(unique_results)}"
        )

        return context
