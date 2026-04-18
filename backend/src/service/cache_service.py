"""
向后兼容模块：CacheService 已拆分为子服务模块。
此文件保留原有导入路径的兼容性。
"""
from src.service.cache import (CacheService, DiskCache, RedisCache,
                               cache_service, cached)

__all__ = [
    "CacheService",
    "RedisCache",
    "DiskCache",
    "cached",
    "cache_service",
]
