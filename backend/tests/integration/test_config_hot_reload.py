"""配置热重载集成测试

测试 ConfigCache 通过 Redis Pub/Sub 自动刷新配置的完整流程。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import json
from datetime import datetime, timedelta


class TestConfigHotReload:
    """测试配置热重载完整流程"""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """每个测试前重置单例"""
        from src.core.config.cache import ConfigCache

        ConfigCache._instance = None
        yield
        ConfigCache._instance = None

    @pytest.mark.asyncio
    async def test_cache_reload_on_redis_event(self):
        """收到 Redis config_changed 事件后应自动重新加载配置"""
        from src.core.config.cache import ConfigCache

        instance = ConfigCache.get_instance()

        # 模拟 Redis 客户端和 Pub/Sub
        mock_pubsub = MagicMock()

        async def mock_listen_generator():
            while True:
                yield {"type": "subscribe", "channel": "config_changed"}
                await asyncio.sleep(0.1)

        mock_pubsub.listen = mock_listen_generator
        mock_pubsub.subscribe = AsyncMock()

        mock_redis = MagicMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

        # 模拟 reload 被调用
        reload_called = False

        async def mock_reload():
            nonlocal reload_called
            reload_called = True

        with patch.object(instance, "reload", mock_reload):
            await instance.initialize(mock_redis)
            # 等待后台任务启动
            await asyncio.sleep(0.1)

        assert instance._redis_client is mock_redis
        assert reload_called is True

    @pytest.mark.asyncio
    async def test_listen_config_changes_reloads_on_message(self):
        """监听任务收到 message 类型事件时应调用 reload"""
        from src.core.config.cache import ConfigCache

        instance = ConfigCache.get_instance()

        # 模拟 Pub/Sub 消息流
        mock_message = {
            "type": "message",
            "channel": "config_changed",
            "data": '{"event": "config_changed", "change_set_id": "test-id"}',
        }

        # 创建一个会在发送一条消息后停止的异步生成器
        async def mock_listen():
            yield mock_message
            # 等待被取消
            await asyncio.sleep(100)

        mock_pubsub = AsyncMock()
        mock_pubsub.listen = mock_listen

        reload_called = False

        async def mock_reload():
            nonlocal reload_called
            reload_called = True

        with patch.object(instance, "reload", mock_reload):
            task = asyncio.create_task(instance._listen_config_changes(mock_pubsub))
            # 等待消息处理
            await asyncio.sleep(0.2)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        assert reload_called is True

    @pytest.mark.asyncio
    async def test_listen_config_changes_ignores_other_channels(self):
        """非 config_changed 频道的事件不应触发 reload"""
        from src.core.config.cache import ConfigCache

        instance = ConfigCache.get_instance()

        # 模拟其他频道的消息
        mock_message = {
            "type": "message",
            "channel": "other_channel",
            "data": "some data",
        }

        async def mock_listen():
            yield mock_message
            await asyncio.sleep(100)

        mock_pubsub = AsyncMock()
        mock_pubsub.listen = mock_listen

        reload_called = False

        async def mock_reload():
            nonlocal reload_called
            reload_called = True

        with patch.object(instance, "reload", mock_reload):
            task = asyncio.create_task(instance._listen_config_changes(mock_pubsub))
            await asyncio.sleep(0.2)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        assert reload_called is False

    @pytest.mark.asyncio
    async def test_listen_config_changes_ignores_subscribe_messages(self):
        """subscribe 类型的消息不应触发 reload"""
        from src.core.config.cache import ConfigCache

        instance = ConfigCache.get_instance()

        mock_message = {
            "type": "subscribe",
            "channel": "config_changed",
            "data": 1,
        }

        async def mock_listen():
            yield mock_message
            await asyncio.sleep(100)

        mock_pubsub = AsyncMock()
        mock_pubsub.listen = mock_listen

        reload_called = False

        async def mock_reload():
            nonlocal reload_called
            reload_called = True

        with patch.object(instance, "reload", mock_reload):
            task = asyncio.create_task(instance._listen_config_changes(mock_pubsub))
            await asyncio.sleep(0.2)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        assert reload_called is False

    @pytest.mark.asyncio
    async def test_shutdown_cancels_listen_task(self):
        """shutdown 应取消监听任务"""
        from src.core.config.cache import ConfigCache

        instance = ConfigCache.get_instance()

        # 模拟 Redis 客户端和 Pub/Sub
        mock_pubsub = MagicMock()

        # listen() 必须返回异步生成器，无限循环直到被取消
        async def mock_listen_generator():
            while True:
                yield {"type": "subscribe", "channel": "config_changed"}
                await asyncio.sleep(0.1)

        mock_pubsub.listen = mock_listen_generator
        mock_pubsub.subscribe = AsyncMock()

        mock_redis = MagicMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

        with patch.object(instance, "reload", new_callable=AsyncMock):
            await instance.initialize(mock_redis)

        # 等待后台任务启动
        await asyncio.sleep(0.1)

        assert instance._listen_task is not None
        assert not instance._listen_task.done()

        await instance.shutdown()

        # 等待任务真正完成
        await asyncio.sleep(0.1)

        assert instance._listen_task.done()

    @pytest.mark.asyncio
    async def test_shutdown_cancels_cleanup_task(self):
        """shutdown 应取消定期清理任务"""
        from src.core.config.cache import ConfigCache

        instance = ConfigCache.get_instance()

        mock_pubsub = MagicMock()

        async def mock_listen_generator():
            while True:
                yield {"type": "subscribe", "channel": "config_changed"}
                await asyncio.sleep(0.1)

        mock_pubsub.listen = mock_listen_generator
        mock_pubsub.subscribe = AsyncMock()

        mock_redis = MagicMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

        with patch.object(instance, "reload", new_callable=AsyncMock):
            await instance.initialize(mock_redis)

        await asyncio.sleep(0.1)

        assert instance._cleanup_task is not None

        await instance.shutdown()

        await asyncio.sleep(0.1)

        assert instance._cleanup_task.done()

    @pytest.mark.asyncio
    async def test_shutdown_handles_not_initialized(self):
        """未初始化时调用 shutdown 不应抛出异常"""
        from src.core.config.cache import ConfigCache

        instance = ConfigCache.get_instance()

        # 不应抛出异常
        await instance.shutdown()


class TestConfigHotReloadIntegration:
    """集成测试：模拟完整的配置变更流程"""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        from src.core.config.cache import ConfigCache

        ConfigCache._instance = None
        yield
        ConfigCache._instance = None

    @pytest.mark.asyncio
    async def test_full_hot_reload_flow(self):
        """完整热重载流程：初始化 → 发布事件 → 缓存刷新"""
        from src.core.config.cache import ConfigCache

        instance = ConfigCache.get_instance()

        # 1. 模拟初始状态
        initial_config = {"bm25_top_k": 10, "chunk_size": 500}
        instance._cache["cv_initial"] = {
            "config_snapshot": initial_config,
            "loaded_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(minutes=5),
        }
        instance._latest_config_id = "cv_initial"

        # 验证初始配置
        assert instance.get_latest_config() == initial_config

        # 2. 模拟收到 Redis 事件后 reload
        new_config = {"bm25_top_k": 20, "chunk_size": 1000}
        instance._cache["cv_new"] = {
            "config_snapshot": new_config,
            "loaded_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(minutes=5),
        }
        instance._latest_config_id = "cv_new"

        # 验证新配置
        assert instance.get_latest_config() == new_config
        # 旧配置仍然可用（TestRun 快照不受影响）
        assert instance.get_config("cv_initial") == initial_config

    @pytest.mark.asyncio
    async def test_running_testrun_not_affected_by_config_change(self):
        """运行中的 TestRun 使用配置快照，不受配置变更影响"""
        from src.core.config.cache import ConfigCache

        instance = ConfigCache.get_instance()

        # TestRun 创建时快照了 config_version_id
        testrun_config_id = "cv_snapshot_001"
        snapshot_config = {"bm25_top_k": 10}

        instance._cache[testrun_config_id] = {
            "config_snapshot": snapshot_config,
            "loaded_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(minutes=5),
        }

        # 模拟配置变更
        new_config = {"bm25_top_k": 20}
        instance._cache["cv_new"] = {
            "config_snapshot": new_config,
            "loaded_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(minutes=5),
        }
        instance._latest_config_id = "cv_new"

        # TestRun 仍然能获取到快照配置
        assert instance.get_config(testrun_config_id) == snapshot_config
        # 新 TestRun 会使用新配置
        assert instance.get_latest_config() == new_config
