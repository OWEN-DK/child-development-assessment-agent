# Phase 2-6: CacheService 拆分

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `3.4 P2` 节
> **所属 Phase**: Phase 2

## 需求定义

将 `CacheService`（550 行）按单一职责拆分，消除混合的三级缓存管理、缓存键生成、统计等职责。

## 验收标准

- [ ] 单类不超过 200 行
- [ ] 门面类对外 API 保持兼容
- [ ] 子服务通过依赖注入获取
- [ ] 现有测试全部通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/service/cache_service.py` | 删除 | 原 550 行文件 |
| `backend/src/service/cache/__init__.py` | 新增 | 模块入口 |
| `backend/src/service/cache/three_level_cache.py` | 新增 | ThreeLevelCache（三级缓存管理，~200 行） |
| `backend/src/service/cache/key_generator.py` | 新增 | CacheKeyGenerator（缓存键生成，~100 行） |
| `backend/src/service/cache/stats.py` | 新增 | CacheStats（统计，~100 行） |
| `backend/src/service/cache/facade.py` | 新增 | CacheFacade（门面，~100 行） |

## 拆分方案

### 职责划分

| 子服务 | 职责 | 原 CacheService 方法 |
|--------|------|---------------------|
| `ThreeLevelCache` | L1 内存/L2 Redis/L3 磁盘三级缓存管理 | `get`, `set`, `delete`, `_evict` |
| `CacheKeyGenerator` | 缓存键生成、命名空间管理 | `_generate_key`, `_get_namespace` |
| `CacheStats` | 命中率统计、缓存大小、清理 | `get_stats`, `record_hit`, `record_miss` |

### 门面类实现

```python
"""
缓存服务门面类

协调各缓存子服务，对外提供统一缓存 API。
"""

from typing import Optional, Any

from src.service.cache.three_level_cache import ThreeLevelCache
from src.service.cache.key_generator import CacheKeyGenerator
from src.service.cache.stats import CacheStats


class CacheFacade:
    """缓存服务门面类"""

    def __init__(
        self,
        cache: ThreeLevelCache,
        key_gen: CacheKeyGenerator,
        stats: CacheStats,
    ):
        self._cache = cache
        self._key_gen = key_gen
        self._stats = stats

    async def get(self, namespace: str, key: str) -> Any:
        cache_key = self._key_gen.generate(namespace, key)
        value = await self._cache.get(cache_key)
        if value is not None:
            self._stats.record_hit(cache_key)
        else:
            self._stats.record_miss(cache_key)
        return value

    async def set(self, namespace: str, key: str, value: Any, ttl: int = 300) -> None:
        cache_key = self._key_gen.generate(namespace, key)
        await self._cache.set(cache_key, value, ttl)

    async def delete(self, namespace: str, key: str) -> None:
        cache_key = self._key_gen.generate(namespace, key)
        await self._cache.delete(cache_key)

    def get_stats(self) -> dict:
        return self._stats.get_stats()


# 单例
cache_facade: Optional[CacheFacade] = None


def get_cache_facade() -> CacheFacade:
    global cache_facade
    if cache_facade is None:
        cache_facade = CacheFacade(
            cache=ThreeLevelCache(),
            key_gen=CacheKeyGenerator(),
            stats=CacheStats(),
        )
    return cache_facade
```

## 测试方案

1. 三级缓存命中/未命中正确
2. 缓存键生成唯一且可预测
3. 统计数据准确
4. TTL 过期正确

## 注意事项

- L1 内存缓存需限制大小，防止内存泄漏
- L2 Redis 缓存需处理连接失败降级
- L3 磁盘缓存需处理文件不存在
