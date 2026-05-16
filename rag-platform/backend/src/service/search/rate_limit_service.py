"""速率限制服务

滑动窗口日志算法（Sliding Window Log），窗口大小 1 秒。
Redis 模式：Sorted Set 实现；内存降级：deque 实现。
"""
import time
from collections import deque
from typing import Optional

from src.schemas.search.rate_limit import RateLimitResult
from src.utils.logger import logger


class RateLimitService:
    """速率限制服务"""

    # 内存降级模式：endpoint_id → deque[timestamp]
    _memory_windows: dict[str, deque] = {}
    # 被限流计数（5 分钟滑动）
    _throttle_counts: dict[str, deque] = {}

    def __init__(self, redis_client=None):
        self._redis = redis_client

    async def check_and_consume(
        self,
        endpoint_id: str,
        max_qps: int,
        tenant_id: str,
        user_id: str,
    ) -> RateLimitResult:
        """检查并消费一次配额

        Args:
            endpoint_id: 端点ID
            max_qps: 最大 QPS（0=不限）
            tenant_id: 租户ID
            user_id: 用户ID

        Returns:
            RateLimitResult 限流结果
        """
        if max_qps <= 0:
            return RateLimitResult(allowed=True, remaining=-1, limit_type="pipeline")

        key = f"search:rate_limit:{endpoint_id}:{tenant_id}:{user_id}"

        if self._redis:
            try:
                return await self._redis_sliding_window(key, max_qps)
            except Exception as e:
                logger.warning(f"Redis 限流失败，降级到内存: {e}")

        return self._memory_sliding_window(f"{endpoint_id}:{tenant_id}:{user_id}", max_qps)

    async def _redis_sliding_window(self, key: str, max_qps: int) -> RateLimitResult:
        """Redis Sorted Set 滑动窗口"""
        now = time.time()
        window_sec = 1.0

        pipe = self._redis.pipeline()
        # 清理过期
        pipe.zremrangebyscore(key, 0, now - window_sec)
        # 添加当前请求
        pipe.zadd(key, {str(now): now})
        # 计数
        pipe.zcount(key, now - window_sec, now)
        # 设置过期
        pipe.expire(key, int(window_sec * 2))
        results = await pipe.execute()

        count = results[2]
        allowed = count <= max_qps
        remaining = max(0, max_qps - count)

        if not allowed:
            # 移除刚添加的记录
            await self._redis.zrem(key, str(now))
            self._record_throttle(key)

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_after_ms=int(window_sec * 1000) if not allowed else 0,
            limit_type="pipeline",
        )

    def _memory_sliding_window(self, endpoint_id: str, max_qps: int) -> RateLimitResult:
        """内存 deque 滑动窗口（降级模式）

        与 Redis 模式 Key 一致：search:rate_limit:{endpoint_id}:{tenant_id}:{user_id}
        """
        now = time.time()
        window_sec = 1.0

        # 使用完整 key 以支持按租户/用户独立限流（与 Redis 模式一致）
        full_key = f"search:rate_limit:{endpoint_id}"
        if full_key not in self._memory_windows:
            self._memory_windows[full_key] = deque()

        window = self._memory_windows[full_key]

        # 清理过期
        while window and window[0] < now - window_sec:
            window.popleft()

        allowed = len(window) < max_qps

        if allowed:
            window.append(now)
            remaining = max_qps - len(window)
        else:
            remaining = 0
            self._record_throttle(full_key)

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_after_ms=int(window_sec * 1000) if not allowed else 0,
            limit_type="pipeline",
        )

    def _record_throttle(self, key: str) -> None:
        """记录被限流事件"""
        now = time.time()
        if key not in self._throttle_counts:
            self._throttle_counts[key] = deque()
        self._throttle_counts[key].append(now)
        # 清理 5 分钟前的记录
        while self._throttle_counts[key] and self._throttle_counts[key][0] < now - 300:
            self._throttle_counts[key].popleft()

    def get_stats(self, endpoint_id: str) -> dict:
        """获取限流统计"""
        throttled = self._throttle_counts.get(endpoint_id, deque())
        now = time.time()
        # 清理过期
        while throttled and throttled[0] < now - 300:
            throttled.popleft()
        return {
            "throttled_count_5min": len(throttled),
        }
