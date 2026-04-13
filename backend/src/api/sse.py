import asyncio
import json
from typing import AsyncGenerator
from fastapi.responses import StreamingResponse
from src.core.redis_client import RedisClient
from src.utils.logger import logger


class SSEPublisher:
    """SSE 发布器（基于Redis Pub/Sub，支持多实例）"""

    _local_subscribers: dict[str, list[asyncio.Queue]] = {}

    @classmethod
    async def subscribe(cls, channel: str) -> AsyncGenerator:
        """订阅频道"""
        queue = asyncio.Queue()

        if channel not in cls._local_subscribers:
            cls._local_subscribers[channel] = []

        cls._local_subscribers[channel].append(queue)

        # 启动 Redis 订阅监听
        redis_task = asyncio.create_task(cls._listen_redis(channel, queue))
        
        # 启动心跳任务，保持连接活跃（避免被反向代理超时断开）
        async def heartbeat():
            while True:
                await asyncio.sleep(30)  # 每30秒发送一次心跳
                await queue.put({
                    "type": "heartbeat",
                    "channel": channel,
                    "timestamp": asyncio.get_event_loop().time()
                })
        
        heartbeat_task = asyncio.create_task(heartbeat())

        try:
            while True:
                message = await queue.get()
                if message is None:  # 停止信号
                    break
                yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
        finally:
            if channel in cls._local_subscribers:
                cls._local_subscribers[channel].remove(queue)
                if not cls._local_subscribers[channel]:
                    del cls._local_subscribers[channel]
            redis_task.cancel()
            heartbeat_task.cancel()
            logger.info(f"SSE 订阅已取消：{channel}")

    @classmethod
    async def _listen_redis(cls, channel: str, queue: asyncio.Queue):
        """监听 Redis 频道"""
        try:
            redis_client = RedisClient.get_client()
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(f"child-dev:sse:{channel}")

            try:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        data = json.loads(message["data"])
                        await queue.put(data)
            finally:
                await pubsub.unsubscribe(f"child-dev:sse:{channel}")
        except Exception as e:
            logger.warning(f"Redis SSE 监听失败，将降级为仅使用本地订阅: {e}")

    @classmethod
    async def publish(cls, channel: str, message: dict):
        """发布消息到 Redis 频道"""
        try:
            redis_client = RedisClient.get_client()
            await redis_client.publish(
                f"child-dev:sse:{channel}", json.dumps(message, ensure_ascii=False)
            )
        except Exception as e:
            logger.debug(f"Redis 发布失败，仅通过本地队列分发: {e}")

        # 同时发送到本地队列（同实例优化）
        if channel in cls._local_subscribers:
            for queue in cls._local_subscribers[channel]:
                await queue.put(message)

    @classmethod
    async def publish_progress(cls, run_id: str, progress: dict):
        """发布进度消息"""
        await cls.publish(
            f"test_run:{run_id}",
            {
                "type": "progress",
                "run_id": run_id,
                **progress,
            },
        )

    @classmethod
    async def publish_complete(cls, run_id: str, summary: dict):
        """发布完成消息"""
        await cls.publish(
            f"test_run:{run_id}",
            {
                "type": "complete",
                "run_id": run_id,
                **summary,
            },
        )


def sse_response(channel: str) -> StreamingResponse:
    """创建 SSE 响应"""
    return StreamingResponse(
        SSEPublisher.subscribe(channel),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
