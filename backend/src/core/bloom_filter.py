from pybloom_live import BloomFilter

from src.utils.logger import logger


class BloomFilterService:
    """布隆过滤器服务，用于快速判断 ID 是否存在"""

    def __init__(self, capacity: int = 100000, error_rate: float = 0.01):
        self.bloom = BloomFilter(capacity=capacity, error_rate=error_rate)
        self._loaded = False

    async def load_ids(self, ids: list[str]) -> None:
        """加载 ID 到布隆过滤器"""
        for item_id in ids:
            self.bloom.add(item_id)
        self._loaded = True
        logger.info(f"布隆过滤器已加载 {len(ids)} 个 ID")

    def might_contain(self, item_id: str) -> bool:
        """快速判断 ID 是否可能存在"""
        if not self._loaded:
            return True
        return item_id in self.bloom

    def add(self, item_id: str) -> None:
        """添加单个 ID"""
        self.bloom.add(item_id)


bloom_filter_service = BloomFilterService()
