from src.core.pageindex_wrapper import PageIndexWrapper
from src.core.pipeline.orchestrator import PipelineContext, PipelineStep
from src.utils.logger import logger


class PageIndexEnhancementStep(PipelineStep):
    """PageIndex 增强步骤：仅复杂查询启用"""

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行 PageIndex 增强"""
        # 检查是否为复杂查询
        query_type = context.metadata.get("query_type", "simple")
        if query_type != "complex":
            logger.debug(f"跳过 PageIndex 增强：查询类型为 {query_type}")
            return context

        # 检查是否启用
        if not self.config.get("enabled", False):
            logger.debug("PageIndex 增强已禁用")
            return context

        # 执行 PageIndex 检索
        logger.info("执行 PageIndex 增强检索")
        pageindex = PageIndexWrapper()

        try:
            pageindex_results = await pageindex.search(
                query=context.query,
                age=context.age,
                limit=self.config.get("limit", 5),
            )

            # 融合结果
            fuse_factor = self.config.get("fuse_factor", 1.2)
            max_hybrid = self.config.get("max_hybrid_supplement", 5)

            enhanced_results = self._enhance_with_pageindex(
                context.results,
                pageindex_results,
                fuse_factor,
                max_hybrid,
            )

            context.results = enhanced_results
            context.metadata["pageindex_count"] = len(pageindex_results)
            context.metadata["enhanced_count"] = len(enhanced_results)

            logger.info(
                f"PageIndex 增强完成：原始={len(context.results)}, 增强后={len(enhanced_results)}"
            )

        except Exception as e:
            logger.error(f"PageIndex 增强失败：{e}")
            context.errors.append(f"pageindex: {str(e)}")

        return context

    def _enhance_with_pageindex(
        self, existing: list, pageindex: list, fuse_factor: float, max_hybrid: int
    ) -> list:
        """融合 PageIndex 结果"""
        from src.core.result_fusion import ResultFusion

        fusion = ResultFusion()
        return fusion.fuse_pageindex(existing, pageindex, fuse_factor, max_hybrid)
