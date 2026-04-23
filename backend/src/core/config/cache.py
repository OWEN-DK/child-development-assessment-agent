"""配置缓存单例

提供配置快照的内存缓存，支持 Redis Pub/Sub 事件驱动的自动刷新和过期清理。
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import async_session_factory
from src.models.rag_eval.config_version import RagEvalConfigVersion
from src.utils.logger import logger


class ConfigCache:
    """配置缓存单例

    Features:
        - 单例模式：全局唯一实例
        - 内存缓存：以 config_version_id 为键存储配置快照
        - 自动过期：缓存条目 5 分钟后自动清理
        - Redis 事件驱动：监听 config_changed 事件自动刷新
        - 并发安全：使用 asyncio.Lock 防止并发刷新
    """

    _instance: "ConfigCache | None" = None

    def __new__(cls) -> "ConfigCache":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        """初始化实例属性"""
        self._cache: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._redis_client = None
        self._latest_config_id: str | None = None
        self._cache_ttl_minutes = 5  # 缓存过期时间（分钟）
        self._listen_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._polling_task: asyncio.Task | None = None  # 轮询任务（pubsub降级备份）
        self._pubsub = None  # 持有pubsub实例避免被提前GC
        self._initialized = False
        self._ever_initialized = False

    @classmethod
    def get_instance(cls) -> "ConfigCache":
        """获取单例实例

        Returns:
            ConfigCache: 单例实例
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self, redis_client: Any) -> None:
        """初始化缓存

        加载最新配置并订阅 Redis 事件。
        幂等操作：如果已初始化则跳过，防止 uvicorn reload 时重复创建后台任务。

        Args:
            redis_client: Redis 异步客户端实例
        """
        if self._ever_initialized:
            logger.debug("ConfigCache 已初始化过，跳过重复初始化")
            return
        self._ever_initialized = True

        self._redis_client = redis_client

        # 加载最新配置
        await self.reload()

        # 启动后台监听任务（内部自动处理订阅和重连）
        self._listen_task = asyncio.create_task(self._listen_config_changes())
        logger.info("ConfigCache 已启动配置变更监听任务")

        # 启动定时轮询任务（pubsub降级备份，每分钟拉取最新配置）
        self._polling_task = asyncio.create_task(self._periodic_polling())
        logger.info("ConfigCache 已启动配置轮询备份任务")

        # 启动后台清理任务
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        self._initialized = True
        logger.info("ConfigCache 初始化完成")

    async def reload(self) -> None:
        """从数据库重新加载最新配置

        使用锁防止并发刷新。
        """
        async with self._lock:
            try:
                async with async_session_factory() as session:
                    stmt = (
                        select(RagEvalConfigVersion)
                        .order_by(desc(RagEvalConfigVersion.created_at))
                        .limit(1)
                    )
                    result = await session.execute(stmt)
                    latest = result.scalars().first()

                    if latest:
                        now = datetime.now()
                        self._cache[latest.id] = {
                            "config_snapshot": latest.config_snapshot,
                            "loaded_at": now,
                            "expires_at": now
                            + timedelta(minutes=self._cache_ttl_minutes),
                        }
                        self._latest_config_id = latest.id
                        logger.info(
                            f"ConfigCache 已加载最新配置: version_id={latest.id}"
                        )
                    else:
                        logger.info("ConfigCache 数据库中无配置记录")
            except Exception as e:
                logger.error(f"ConfigCache 重新加载失败: {e}")

    def get_config(self, config_version_id: str) -> dict[str, Any] | None:
        """获取缓存中的配置快照

        Args:
            config_version_id: 配置版本ID

        Returns:
            dict | None: 配置快照，不存在或已过期时返回 None
        """
        entry = self._cache.get(config_version_id)
        if entry is None:
            return None

        # 检查是否过期
        if datetime.now() > entry["expires_at"]:
            # 过期条目将在后台清理任务中移除
            return None

        return entry["config_snapshot"]

    def get_latest_config(self) -> dict[str, Any] | None:
        """获取最近加载的配置快照

        Returns:
            dict | None: 最新配置快照，未加载时返回 None
        """
        if self._latest_config_id is None:
            return None
        return self.get_config(self._latest_config_id)

    async def _listen_config_changes(self) -> None:
        """后台任务：监听 Redis 配置变更事件
        收到 config_changed 事件后自动重新加载配置。
        最多重试3次，失败后放弃pubsub，完全依赖轮询备份。
        """
        retry_count = 0
        max_retries = 3  # 最多重试3次
        subscribed = False  # 标记是否已记录订阅日志
        while retry_count < max_retries:
            try:
                if not self._pubsub:
                    # 创建pubsub并订阅
                    self._pubsub = self._redis_client.pubsub()
                    await self._pubsub.subscribe("config_changed")
                    # 仅在首次订阅时记录日志，避免超时重连时日志过多
                    if not subscribed:
                        logger.info("ConfigCache 已订阅 Redis config_changed 事件")
                        subscribed = True
                    retry_count = 0  # 连接成功重置重试计数
                
                async for message in self._pubsub.listen():
                    if (
                        message["type"] == "message"
                        and message["channel"] == "config_changed"
                    ):
                        logger.info("ConfigCache 收到 config_changed 事件，开始重新加载")
                        await self.reload()
            except asyncio.CancelledError:
                logger.info("ConfigCache 监听任务已取消")
                break
            except Exception as e:
                from redis.exceptions import TimeoutError
                # 超时是正常情况（长时间无消息），不增加重试计数，直接重连继续监听
                if isinstance(e, TimeoutError):
                    logger.debug("ConfigCache pubsub 监听超时（无新消息），将重连继续监听")
                else:
                    retry_count += 1
                    if retry_count >= max_retries:
                        logger.error(f"ConfigCache 监听事件连续失败{max_retries}次，放弃pubsub监听，将使用轮询模式: {e}")
                        break
                    logger.error(f"ConfigCache 监听事件异常，将在5秒后重试({retry_count}/{max_retries}): {e}")
                    await asyncio.sleep(5)
                    # 非超时异常需要重置订阅状态
                    subscribed = False
                
                try:
                    # 关闭旧的pubsub连接
                    if self._pubsub:
                        await self._pubsub.unsubscribe()
                        await self._pubsub.close()
                except:
                    pass
                self._pubsub = None
        
        # 清理pubsub资源
        try:
            if self._pubsub:
                await self._pubsub.unsubscribe()
                await self._pubsub.close()
        except:
            pass
        self._pubsub = None

    async def _periodic_polling(self) -> None:
        """定时轮询配置：每分钟自动拉取最新配置，作为pubsub的降级备份"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟拉取一次
                await self.reload()
                logger.debug("ConfigCache 轮询已更新最新配置")
            except asyncio.CancelledError:
                logger.info("ConfigCache 轮询任务已取消")
                break
            except Exception as e:
                logger.error(f"ConfigCache 轮询异常: {e}")
                await asyncio.sleep(60)  # 异常时也等待1分钟再重试

    async def _cleanup_expired(self) -> None:
        """清理已过期的缓存条目"""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self._cache.items() if now > entry["expires_at"]
        ]
        for key in expired_keys:
            del self._cache[key]
        if expired_keys:
            logger.info(f"ConfigCache 已清理 {len(expired_keys)} 个过期条目")

    async def _periodic_cleanup(self) -> None:
        """定期清理过期缓存条目"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"ConfigCache 定期清理异常: {e}")

    def clear(self) -> None:
        """清空所有缓存（主要用于测试）"""
        self._cache.clear()
        self._latest_config_id = None

    async def shutdown(self) -> None:
        """关闭缓存服务，取消后台任务
        在应用关闭时调用，确保后台任务正确清理。
        """
        # 取消监听任务
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                logger.info("ConfigCache 监听任务已关闭")

        # 清理pubsub资源
        try:
            if self._pubsub:
                await self._pubsub.unsubscribe()
                await self._pubsub.close()
                self._pubsub = None
                logger.info("ConfigCache pubsub 连接已关闭")
        except:
            pass

        # 取消清理任务
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                logger.info("ConfigCache 清理任务已关闭")

        # 取消轮询任务
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                logger.info("ConfigCache 轮询任务已关闭")

        self._initialized = False
        logger.info("ConfigCache 已关闭")
