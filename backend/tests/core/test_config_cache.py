"""配置缓存单例测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import asyncio


class TestConfigCacheSingleton:
    """测试 ConfigCache 单例模式"""

    def test_singleton_returns_same_instance(self):
        """多次调用 get_instance 应返回同一实例"""
        from src.core.config.cache import ConfigCache

        # 重置单例以隔离测试
        ConfigCache._instance = None

        instance1 = ConfigCache.get_instance()
        instance2 = ConfigCache.get_instance()

        assert instance1 is instance2

    def test_singleton_initializes_cache_dict(self):
        """单例应初始化 _cache 字典"""
        from src.core.config.cache import ConfigCache

        ConfigCache._instance = None

        instance = ConfigCache.get_instance()

        assert isinstance(instance._cache, dict)
        assert len(instance._cache) == 0


class TestConfigCacheInitialize:
    """测试 ConfigCache 初始化"""

    @pytest.mark.asyncio
    async def test_initialize_sets_redis_client(self):
        """初始化应设置 Redis 客户端"""
        from src.core.config.cache import ConfigCache

        ConfigCache._instance = None

        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub
        mock_pubsub.subscribe = AsyncMock()

        instance = ConfigCache.get_instance()

        with patch.object(instance, "reload", new_callable=AsyncMock):
            await instance.initialize(mock_redis)

        assert instance._redis_client is mock_redis

    @pytest.mark.asyncio
    async def test_initialize_calls_reload(self):
        """初始化应调用 reload 加载最新配置"""
        from src.core.config.cache import ConfigCache

        ConfigCache._instance = None

        mock_redis = AsyncMock()

        instance = ConfigCache.get_instance()

        # 模拟 reload
        reload_called = False

        async def mock_reload():
            nonlocal reload_called
            reload_called = True

        with patch.object(instance, "reload", mock_reload):
            with patch.object(
                mock_redis, "pubsub", return_value=AsyncMock(subscribe=AsyncMock())
            ):
                await instance.initialize(mock_redis)

        assert reload_called is True


class TestConfigCacheReload:
    """测试 ConfigCache 重新加载"""

    @pytest.mark.asyncio
    async def test_reload_loads_from_database(self):
        """reload 应从数据库加载最新配置"""
        from src.core.config.cache import ConfigCache
        from src.core.database import async_session_factory

        ConfigCache._instance = None

        instance = ConfigCache.get_instance()

        mock_config_version_id = "cv_001"
        mock_config_snapshot = {"bm25_top_k": 15}

        # 创建模拟的 ORM 对象
        mock_orm = MagicMock()
        mock_orm.id = mock_config_version_id
        mock_orm.config_snapshot = mock_config_snapshot

        # 模拟 scalars().first() 链式调用
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_orm

        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        # 模拟 session
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        # 模拟 session factory 上下文管理器
        mock_factory_ctx = AsyncMock()
        mock_factory_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "src.core.config.cache.async_session_factory",
            return_value=mock_factory_ctx,
        ):
            await instance.reload()

        # 验证缓存中有数据
        assert mock_config_version_id in instance._cache
        assert (
            instance._cache[mock_config_version_id]["config_snapshot"]
            == mock_config_snapshot
        )

    @pytest.mark.asyncio
    async def test_reload_handles_no_config(self):
        """无配置时应正常处理"""
        from src.core.config.cache import ConfigCache

        ConfigCache._instance = None

        instance = ConfigCache.get_instance()

        # 模拟 scalars().first() 返回 None
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None

        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_factory_ctx = AsyncMock()
        mock_factory_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "src.core.config.cache.async_session_factory",
            return_value=mock_factory_ctx,
        ):
            # 不应抛出异常
            await instance.reload()


class TestConfigCacheGetConfig:
    """测试获取缓存配置"""

    def test_returns_cached_config(self):
        """应返回缓存中的配置快照"""
        from src.core.config.cache import ConfigCache

        ConfigCache._instance = None

        instance = ConfigCache.get_instance()
        config_id = "cv_test_001"
        mock_snapshot = {"bm25_top_k": 10}

        instance._cache[config_id] = {
            "config_snapshot": mock_snapshot,
            "loaded_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(minutes=5),
        }

        result = instance.get_config(config_id)

        assert result == mock_snapshot

    def test_returns_none_for_missing_config(self):
        """缓存中不存在时应返回 None"""
        from src.core.config.cache import ConfigCache

        ConfigCache._instance = None

        instance = ConfigCache.get_instance()

        result = instance.get_config("nonexistent_id")

        assert result is None

    def test_returns_none_for_expired_config(self):
        """已过期的缓存应返回 None"""
        from src.core.config.cache import ConfigCache

        ConfigCache._instance = None

        instance = ConfigCache.get_instance()
        config_id = "cv_expired_001"

        instance._cache[config_id] = {
            "config_snapshot": {"bm25_top_k": 10},
            "loaded_at": datetime.now() - timedelta(minutes=10),
            "expires_at": datetime.now() - timedelta(minutes=5),
        }

        result = instance.get_config(config_id)

        assert result is None


class TestConfigCacheGetLatestConfig:
    """测试获取最新配置"""

    def test_returns_latest_config(self):
        """应返回最近加载的配置"""
        from src.core.config.cache import ConfigCache

        ConfigCache._instance = None

        instance = ConfigCache.get_instance()
        config_id = "cv_latest_001"
        mock_snapshot = {"bm25_top_k": 20}

        instance._cache[config_id] = {
            "config_snapshot": mock_snapshot,
            "loaded_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(minutes=5),
        }
        instance._latest_config_id = config_id

        result = instance.get_latest_config()

        assert result == mock_snapshot

    def test_returns_none_when_no_latest(self):
        """未加载任何配置时应返回 None"""
        from src.core.config.cache import ConfigCache

        ConfigCache._instance = None

        instance = ConfigCache.get_instance()
        instance._latest_config_id = None

        result = instance.get_latest_config()

        assert result is None


class TestConfigCacheCleanup:
    """测试缓存清理"""

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired_entries(self):
        """应清理已过期的缓存条目"""
        from src.core.config.cache import ConfigCache

        ConfigCache._instance = None

        instance = ConfigCache.get_instance()

        # 添加一个已过期的条目
        instance._cache["cv_expired"] = {
            "config_snapshot": {"bm25_top_k": 10},
            "loaded_at": datetime.now() - timedelta(minutes=10),
            "expires_at": datetime.now() - timedelta(minutes=5),
        }

        # 添加一个未过期的条目
        instance._cache["cv_valid"] = {
            "config_snapshot": {"bm25_top_k": 15},
            "loaded_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(minutes=5),
        }

        await instance._cleanup_expired()

        assert "cv_expired" not in instance._cache
        assert "cv_valid" in instance._cache

    @pytest.mark.asyncio
    async def test_cleanup_handles_empty_cache(self):
        """空缓存清理不应抛出异常"""
        from src.core.config.cache import ConfigCache

        ConfigCache._instance = None

        instance = ConfigCache.get_instance()
        instance._cache = {}

        # 不应抛出异常
        await instance._cleanup_expired()

        assert len(instance._cache) == 0
