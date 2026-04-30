import hashlib
import json

from src.core.pipeline.orchestrator import PipelineContext, PipelineStep
from src.service.cache_service import CacheService
from src.utils.logger import logger


class CacheCheckStep(PipelineStep):
    """缓存检查步骤：命中直接返回结果，未命中继续执行"""

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self._cache_service = CacheService()
        self._prefix = self.config.get("cache_key_prefix", "rag:query")
        self._ttl = self.config.get("ttl", 3600)

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行缓存检查"""
        # 生成缓存键
        key = self._generate_cache_key(context.query, context.limit)

        # 检查缓存
        cached = await self._cache_service.get(key)
        if cached:
            try:
                results = json.loads(cached)
                context.results = results
                context.metadata["cache_hit"] = True
                logger.info(
                    f"缓存命中：{context.query[:50]}...，返回{len(results)}个结果"
                )
                # 缓存命中直接返回，跳过后续步骤
                return context
            except Exception as e:
                logger.warning(f"缓存解析失败：{e}")

        context.metadata["cache_hit"] = False
        logger.debug(f"缓存未命中：{context.query[:50]}...")
        return context

    def _generate_cache_key(self, query: str, limit: int) -> str:
        """生成缓存键"""
        raw = f"{query}:{limit}".encode("utf-8")
        hash_str = hashlib.md5(raw).hexdigest()
        return f"{self._prefix}:{hash_str}"
