"""RateLimitService 单元测试

测试滑动窗口限流算法（内存降级模式），覆盖：
- 精确 QPS 限制
- 窗口重置
- max_qps=0 无限流
- 不同端点独立限流
- retry_after_ms 计算
"""
import asyncio
import time

import pytest

from src.service.search.rate_limit_service import RateLimitService


@pytest.fixture
def limiter():
    """无 Redis 的限流服务（使用内存降级）"""
    return RateLimitService(redis_client=None)


class TestRateLimitService:
    """滑动窗口限流测试"""

    @pytest.mark.asyncio
    async def test_exact_qps_limit(self, limiter):
        """1 秒内连续发送 max_qps 次请求——前 max_qps 次通过，后续拒绝"""
        max_qps = 5
        endpoint_id = "ep-test-001"

        results = []
        for _ in range(max_qps + 2):
            result = await limiter.check_and_consume(
                endpoint_id, max_qps, tenant_id="t1", user_id="u1"
            )
            results.append(result.allowed)

        # 前 max_qps 次通过
        assert sum(results[:max_qps]) == max_qps
        # 后续请求被拒绝
        assert all(not r for r in results[max_qps:])

    @pytest.mark.asyncio
    async def test_window_reset_after_wait(self, limiter):
        """等待超过窗口时间后，配额自动重置"""
        max_qps = 2
        endpoint_id = "ep-test-002"

        # 消耗完配额
        await limiter.check_and_consume(endpoint_id, max_qps, "t1", "u1")
        await limiter.check_and_consume(endpoint_id, max_qps, "t1", "u1")

        # 第三次超出
        r = await limiter.check_and_consume(endpoint_id, max_qps, "t1", "u1")
        assert not r.allowed

        # 等待 1.1 秒后窗口过期
        await asyncio.sleep(1.1)
        r = await limiter.check_and_consume(endpoint_id, max_qps, "t1", "u1")
        assert r.allowed

    @pytest.mark.asyncio
    async def test_max_qps_zero_unlimited(self, limiter):
        """max_qps=0 表示不限速"""
        for _ in range(100):
            r = await limiter.check_and_consume("ep-unlimited", 0, "t1", "u1")
            assert r.allowed
            assert r.remaining == -1

    @pytest.mark.asyncio
    async def test_different_endpoints_independent(self, limiter):
        """不同端点的配额互不影响"""
        max_qps = 2

        # 耗尽 ep-a 配额
        await limiter.check_and_consume("ep-a", max_qps, "t1", "u1")
        await limiter.check_and_consume("ep-a", max_qps, "t1", "u1")
        r = await limiter.check_and_consume("ep-a", max_qps, "t1", "u1")
        assert not r.allowed

        # ep-b 不受影响
        r = await limiter.check_and_consume("ep-b", max_qps, "t1", "u1")
        assert r.allowed

    @pytest.mark.asyncio
    async def test_different_tenants_independent(self, limiter):
        """不同租户的配额互不影响"""
        max_qps = 1

        await limiter.check_and_consume("ep-1", max_qps, "t1", "u1")
        r = await limiter.check_and_consume("ep-1", max_qps, "t1", "u1")
        assert not r.allowed

        # 租户 t2 不受影响
        r = await limiter.check_and_consume("ep-1", max_qps, "t2", "u1")
        assert r.allowed

    @pytest.mark.asyncio
    async def test_different_users_independent(self, limiter):
        """不同用户的配额互不影响"""
        max_qps = 1

        await limiter.check_and_consume("ep-1", max_qps, "t1", "u1")
        r = await limiter.check_and_consume("ep-1", max_qps, "t1", "u1")
        assert not r.allowed

        # 用户 u2 不受影响
        r = await limiter.check_and_consume("ep-1", max_qps, "t1", "u2")
        assert r.allowed

    @pytest.mark.asyncio
    async def test_retry_after_ms_positive(self, limiter):
        """被限流后 retry_after_ms > 0"""
        max_qps = 1

        await limiter.check_and_consume("ep-retry", max_qps, "t1", "u1")
        r = await limiter.check_and_consume("ep-retry", max_qps, "t1", "u1")

        assert not r.allowed
        assert r.limit_type == "pipeline"
        assert r.reset_after_ms > 0
        assert r.reset_after_ms <= 1000

    @pytest.mark.asyncio
    async def test_remaining_decreases(self, limiter):
        """remaining 随消耗递减"""
        max_qps = 3
        endpoint_id = "ep-remain"

        r1 = await limiter.check_and_consume(endpoint_id, max_qps, "t1", "u1")
        assert r1.remaining == 2

        r2 = await limiter.check_and_consume(endpoint_id, max_qps, "t1", "u1")
        assert r2.remaining == 1

        r3 = await limiter.check_and_consume(endpoint_id, max_qps, "t1", "u1")
        assert r3.remaining == 0
        assert r3.allowed

    @pytest.mark.asyncio
    async def test_get_stats_throttle_count(self, limiter):
        """get_stats 返回被限流次数"""
        max_qps = 1
        endpoint_id = "ep-stats"

        await limiter.check_and_consume(endpoint_id, max_qps, "t1", "u1")
        await limiter.check_and_consume(endpoint_id, max_qps, "t1", "u1")  # 被限

        stats = limiter.get_stats("search:rate_limit:" + endpoint_id + ":t1:u1")
        assert "throttled_count_5min" in stats
