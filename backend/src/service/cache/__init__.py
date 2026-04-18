from src.service.cache.disk_cache import DiskCache
from src.service.cache.facade import CacheFacade, cache_service, cached
from src.service.cache.redis_cache import RedisCache

CacheService = CacheFacade

__all__ = [
    "CacheService",
    "CacheFacade",
    "RedisCache",
    "DiskCache",
    "cached",
    "cache_service",
]
