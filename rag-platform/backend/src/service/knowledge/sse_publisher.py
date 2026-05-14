"""SSE 进度推送器

单知识库多连接广播，支持心跳。
"""
import asyncio
import json
from typing import Any, AsyncGenerator


class SSEPublisher:
    """SSE 进度推送器"""

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}  # kb_id → [queue, ...]

    def subscribe(self, kb_id: str) -> asyncio.Queue:
        """订阅知识库的 SSE 事件"""
        queue = asyncio.Queue()
        if kb_id not in self._subscribers:
            self._subscribers[kb_id] = []
        self._subscribers[kb_id].append(queue)
        return queue

    def unsubscribe(self, kb_id: str, queue: asyncio.Queue) -> None:
        """取消订阅"""
        if kb_id in self._subscribers:
            try:
                self._subscribers[kb_id].remove(queue)
            except ValueError:
                pass
            if not self._subscribers[kb_id]:
                del self._subscribers[kb_id]

    async def publish(self, kb_id: str, event: dict[str, Any]) -> None:
        """发布事件到所有订阅者"""
        if kb_id in self._subscribers:
            for queue in self._subscribers[kb_id]:
                await queue.put(event)

    async def event_stream(
        self, kb_id: str, heartbeat_seconds: int = 15
    ) -> AsyncGenerator[str, None]:
        """SSE 事件流生成器

        Args:
            kb_id: 知识库 ID
            heartbeat_seconds: 心跳间隔

        Yields:
            SSE 格式的事件字符串
        """
        queue = self.subscribe(kb_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=heartbeat_seconds
                    )
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                    # 如果是完成或错误事件，结束流
                    if event.get("event") in ("complete", "error"):
                        break
                except asyncio.TimeoutError:
                    # 发送心跳
                    yield f": heartbeat\n\n"
        finally:
            self.unsubscribe(kb_id, queue)
