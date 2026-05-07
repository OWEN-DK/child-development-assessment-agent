import asyncio
import json
import re
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from fastapi.responses import StreamingResponse

from src.core.redis_client import RedisClient
from src.utils.logger import logger

# 心跳间隔（秒），匹配前端45秒超时阈值（容忍3个周期）
HEARTBEAT_INTERVAL = 15

# 队列最大大小，防止内存泄漏
MAX_QUEUE_SIZE = 100

# 从频道名中提取run_id的正则（匹配 test_run:{uuid} 格式）
_RUN_ID_PATTERN = re.compile(r"^test_run:(.+)$")


def _extract_run_id(channel: str) -> Optional[str]:
    """从频道名中提取run_id，仅适用于test_run:{run_id}格式"""
    match = _RUN_ID_PATTERN.match(channel)
    return match.group(1) if match else None


class SSEPublisher:
    """SSE 发布器（基于Redis Pub/Sub，支持多实例，Redis不可用时降级到内存队列）"""

    _local_subscribers: dict[str, list[asyncio.Queue]] = {}
    _redis_available: Optional[bool] = None
    _redis_last_check: float = 0.0
    _REDIS_CHECK_INTERVAL: float = 30.0  # 30 秒检查一次，避免每次 publish 都 PING

    @classmethod
    async def _check_redis_availability(cls) -> bool:
        """检查 Redis 是否可用"""
        try:
            redis_client = RedisClient.get_client()
            return await redis_client.ping()
        except Exception:
            return False

    @classmethod
    async def _get_redis_availability(cls) -> bool:
        """获取 Redis 可用性状态（带 TTL 缓存，避免每次发布都 PING）"""
        now = asyncio.get_event_loop().time()
        if cls._redis_available is not None and (now - cls._redis_last_check) < cls._REDIS_CHECK_INTERVAL:
            return cls._redis_available
        cls._redis_available = await cls._check_redis_availability()
        cls._redis_last_check = now
        if not cls._redis_available:
            logger.warning("Redis 不可用，SSE 将降级到内存队列模式")
        return cls._redis_available

    @classmethod
    async def subscribe(cls, channel: str) -> AsyncGenerator:
        """订阅频道"""
        queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)

        if channel not in cls._local_subscribers:
            cls._local_subscribers[channel] = []

        cls._local_subscribers[channel].append(queue)

        # 心跳任务（始终运行）
        async def heartbeat():
            run_id = _extract_run_id(channel)
            try:
                while True:
                    try:
                        await asyncio.sleep(HEARTBEAT_INTERVAL)
                        heartbeat_data = {
                            "type": "heartbeat",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        if run_id:
                            heartbeat_data["run_id"] = run_id
                        queue.put_nowait(heartbeat_data)
                    except asyncio.QueueFull:
                        pass  # 队列已满说明消费者还在处理，无需担心
                    except asyncio.CancelledError:
                        break  # 快速退出
            except asyncio.CancelledError:
                return

        heartbeat_task = asyncio.create_task(heartbeat())

        # Redis 监听任务（仅在 Redis 可用时创建）
        redis_task = None
        redis_available = await cls._check_redis_availability()
        if redis_available:
            redis_task = asyncio.create_task(cls._listen_redis(channel, queue))

        try:
            while True:
                message = await queue.get()
                if message is None:
                    break
                yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            raise
        finally:
            # 先发送停止信号，让yield循环退出
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass  # 队列已满说明消费者还在处理
            except Exception:
                pass

            # 再移除队列引用
            if channel in cls._local_subscribers:
                try:
                    cls._local_subscribers[channel].remove(queue)
                except ValueError:
                    pass  # 队列已被移除
                if not cls._local_subscribers[channel]:
                    del cls._local_subscribers[channel]

            # 最后取消后台任务
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

            if redis_task:
                redis_task.cancel()
                try:
                    await redis_task
                except asyncio.CancelledError:
                    pass

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
                        try:
                            await queue.put(data)
                        except asyncio.QueueFull:
                            logger.warning(f"SSE 队列已满 channel={channel}，丢弃消息")
            finally:
                await pubsub.unsubscribe(f"child-dev:sse:{channel}")
                await pubsub.close()
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.warning(f"Redis SSE 监听失败，将降级为仅使用本地订阅: {e}")

    @classmethod
    async def publish(cls, channel: str, message: dict):
        """发布 SSE 消息

        优先通过 Redis Pub/Sub 发布（支持多实例），
        如果 Redis 不可用，仅发布到本地队列（单实例模式）。
        """
        from decimal import Decimal

        from fastapi.encoders import jsonable_encoder

        try:
            safe_message = jsonable_encoder(
                message,
                custom_encoder={Decimal: lambda v: float(v)}
            )
        except Exception as e:
            logger.error(f"SSE 消息序列化失败: {e}")
            return

        # 始终发布到本地队列（同实例订阅者）
        if channel in cls._local_subscribers:
            for q in cls._local_subscribers[channel]:
                try:
                    q.put_nowait(safe_message)
                except asyncio.QueueFull:
                    logger.warning(f"SSE 本地队列已满 channel={channel}，丢弃消息")
                except Exception as e:
                    logger.debug(f"发布到本地队列失败: {e}")

        # 尝试通过 Redis Pub/Sub 发布（跨实例）
        redis_available = await cls._get_redis_availability()
        if redis_available:
            try:
                redis_client = RedisClient.get_client()
                await redis_client.publish(
                    f"child-dev:sse:{channel}",
                    json.dumps(safe_message, ensure_ascii=False),
                )
            except Exception as e:
                logger.warning(f"通过 Redis 发布消息失败: {e}，仅使用本地队列")
                cls._redis_available = False

    @classmethod
    async def publish_event(cls, channel: str, event_type: str, data: dict):
        """统一事件发布入口
        Args:
            channel: SSE频道名，如 test_run:{run_id}
            event_type: 事件类型，如 run_started, progress, case_result 等
            data: 事件数据（不含type字段）
        """
        payload = {"type": event_type, **data}
        await cls.publish(channel, payload)

    @classmethod
    def get_subscriber_stats(cls) -> dict:
        """获取订阅者统计信息（用于诊断）"""
        stats = {}
        for channel, queues in cls._local_subscribers.items():
            stats[channel] = {
                "subscriber_count": len(queues),
                "queue_sizes": [q.qsize() for q in queues],
            }
        return stats


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
