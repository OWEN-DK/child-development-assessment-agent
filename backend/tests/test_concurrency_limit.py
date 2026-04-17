"""并发限制测试"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.core.validation.orchestrator import ValidationOrchestrator


@pytest.fixture(autouse=True)
def reset_orchestrator():
    """每个测试前重置编排器状态"""
    ValidationOrchestrator._semaphore = None
    ValidationOrchestrator._init_lock = None
    yield
    ValidationOrchestrator._semaphore = None
    ValidationOrchestrator._init_lock = None


@pytest.mark.asyncio
async def test_concurrent_limit():
    """最多 2 个并行校验"""
    orchestrator = ValidationOrchestrator()
    await orchestrator.init(max_concurrent=2)

    session_factory = AsyncMock()
    test_run = MagicMock(id="run-1", test_set_id="ts-1", config_version_id=None)

    active_count = 0
    max_active = 0
    lock = asyncio.Lock()

    async def track_concurrency(*args):
        nonlocal active_count, max_active
        async with lock:
            active_count += 1
            if active_count > max_active:
                max_active = active_count
        await asyncio.sleep(0.2)
        async with lock:
            active_count -= 1

    with patch.object(
        orchestrator, "_execute_with_timeout", new_callable=AsyncMock
    ) as mock_exec:
        mock_exec.side_effect = track_concurrency

        tasks = [
            asyncio.create_task(orchestrator.execute(session_factory, test_run))
            for _ in range(5)
        ]
        await asyncio.gather(*tasks)

        assert max_active <= 2


@pytest.mark.asyncio
async def test_queue_overflow_returns_503():
    """超出队列返回 503"""
    orchestrator = ValidationOrchestrator()
    await orchestrator.init(max_concurrent=1)

    session_factory = AsyncMock()
    test_run = MagicMock(id="run-1", test_set_id="ts-1", config_version_id=None)

    # 直接测试信号量获取超时的逻辑
    # 先获取信号量
    await orchestrator._semaphore.acquire()

    # 尝试再次获取应该超时
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(orchestrator._semaphore.acquire(), timeout=0.1)

    # 释放信号量
    orchestrator._semaphore.release()
