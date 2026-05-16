"""SSE 流式搜索集成测试

测试 SSE 事件序列、心跳、断线处理（需完整环境）。
所有测试用 @pytest.mark.integration 标记。
"""
import pytest


pytestmark = pytest.mark.integration


class TestSSEEventSequence:
    """SSE 事件序列"""

    @pytest.mark.asyncio
    async def test_sse_complete_event_sequence(self):
        """完整 SSE 搜索——按序收到全部事件"""
        pytest.skip("需完整环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_sse_answer_streaming_full_text(self):
        """累积 delta_text → 完整答案"""
        pytest.skip("需完整环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_sse_citation_events(self):
        """答案含引用 → 收到 citation 事件"""
        pytest.skip("需完整环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_sse_event_ids_incremental(self):
        """事件 ID 从 0 开始递增"""
        pytest.skip("需完整环境 — 手动执行")


class TestSSEHeartbeat:
    """SSE 心跳"""

    @pytest.mark.asyncio
    async def test_sse_heartbeat(self):
        """空闲时心跳——15 秒内收到 heartbeat"""
        pytest.skip("需完整环境 — 手动执行")


class TestSSEErrorAndClose:
    """SSE 错误与关闭"""

    @pytest.mark.asyncio
    async def test_sse_run_failed_event(self):
        """管道执行失败 → run_failed → close"""
        pytest.skip("需完整环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_sse_timeout_disconnect(self):
        """执行超过 5 分钟 → close (reason=timeout)"""
        pytest.skip("需完整环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_sse_no_reconnect(self):
        """客户端断开 → 服务端不重连推送"""
        pytest.skip("需完整环境 — 手动执行")
