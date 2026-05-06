import asyncio
import uuid
from datetime import datetime
from typing import Any

from src.config.core.entities import ConfigVersion
from src.config.core.events import ConfigChangedEvent
from src.core.crypto import crypto_service
from src.core.event_bus import event_bus
from src.utils.logger import logger
from src.utils.serializers import create_serializer, safe_isoformat


_serialize_config_version = create_serializer(
    object,
    {
        "id": None,
        "created_at": safe_isoformat,
        "created_by": None,
        "description": None,
        "config_snapshot": None,
        "parent_version_id": None,
        "is_factory_reset": None,
    }
)


class ConfigManager:
    """配置管理器，支持MySQL持久化、Redis缓存、热更新、版本控制"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._current_version: ConfigVersion | None = None
        self._cache_key_prefix = "config:version:"
        self._lock_name = "config:reload"
        self._version_repo = None
        self._audit_log_repo = None

    def _get_repos(self):
        """懒加载Repository实例"""
        if self._version_repo is None:
            from src.core.database import async_session_factory
            from src.repository import (ConfigAuditLogRepository,
                                        SystemConfigVersionRepository)

            self._version_repo = SystemConfigVersionRepository(async_session_factory)
            self._audit_log_repo = ConfigAuditLogRepository(async_session_factory)
        return self._version_repo, self._audit_log_repo

    def _extract_config_from_settings(self) -> dict[str, Any]:
        from src.config import rules
        from src.config import settings as current_settings

        config = current_settings.model_dump()

        # 将 llm_scene_configs 属性展开为独立的 llm_{scene} 键，供 LLMServiceFactory 使用
        if hasattr(current_settings, "llm_scene_configs"):
            for scene_name, scene_config in current_settings.llm_scene_configs.items():
                config[f"llm_{scene_name}"] = scene_config.model_dump()

        # Add rule configs
        rule_configs = {
            "rule_validation": rules.validation.model_dump(),
            "rule_assessment": rules.assessment.model_dump(),
            "rule_scoring": rules.scoring.model_dump(),
            "rule_preprocessing": rules.preprocessing.model_dump(),
            "rule_metadata": rules.metadata.model_dump(),
        }

        # Flatten rule configs
        for rule_group, rule_values in rule_configs.items():
            for key, value in rule_values.items():
                config[f"{rule_group}_{key}"] = value

        return config

    async def load_latest_version(self) -> None:
        """加载最新配置版本"""
        from src.service.cache_service import cache_service

        # 优先从缓存获取
        cache_key = f"{self._cache_key_prefix}latest"
        cached = await cache_service.get(cache_key)
        if cached:
            self._current_version = ConfigVersion(**cached)
            logger.info(f"配置已从缓存加载，版本: {self._current_version.id}")
            return

        # 缓存未命中，从MySQL查询
        version_repo, _ = self._get_repos()
        latest_orm = await version_repo.get_latest_version()
        if not latest_orm:
            latest_orm = await self._create_initial_version()
        self._current_version = ConfigVersion(
            id=latest_orm.id,
            created_at=latest_orm.created_at,
            created_by=latest_orm.created_by,
            description=latest_orm.description,
            config_snapshot=latest_orm.config_snapshot,
            parent_version_id=latest_orm.parent_version_id,
            is_factory_reset=latest_orm.is_factory_reset,
        )
        await cache_service.set(
            cache_key, self._current_version.model_dump(), expire=3600
        )
        logger.info(f"配置已从数据库加载，版本: {self._current_version.id}")

    async def _create_initial_version(self) -> "ConfigVersionORM":
        """创建初始配置版本"""
        from src.models.config import ConfigAction
        from src.models.config import ConfigVersion as ConfigVersionORM
        from src.repository import ConfigAuditLogRepository

        version_repo, audit_repo = self._get_repos()
        initial_snapshot = self._extract_config_from_settings()
        version_id = (
            f"v_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        )

        version_orm = await version_repo.create(
            {
                "id": version_id,
                "created_at": datetime.now(),
                "created_by": "system",
                "description": "初始配置版本",
                "config_snapshot": initial_snapshot,
                "parent_version_id": None,
                "is_factory_reset": True,
            }
        )

        await audit_repo.create(
            {
                "action": ConfigAction.RESET,
                "from_version": None,
                "to_version": version_id,
                "user": "system",
            }
        )

        return version_orm

    async def save_new_version(
        self,
        config_snapshot: dict[str, Any],
        description: str,
        created_by: str = "system",
    ) -> ConfigVersion:
        """保存新的配置版本"""
        from src.core.distributed_lock import DistributedLock
        from src.models.config import ConfigAction

        async with DistributedLock.execute_with_lock(self._lock_name):
            version_repo, audit_repo = self._get_repos()
            version_id = (
                f"v_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
            )

            await version_repo.create(
                {
                    "id": version_id,
                    "created_at": datetime.now(),
                    "created_by": created_by,
                    "description": description,
                    "config_snapshot": config_snapshot,
                    "parent_version_id": self._current_version.id
                    if self._current_version
                    else None,
                    "is_factory_reset": False,
                }
            )

            await audit_repo.create(
                {
                    "action": ConfigAction.UPDATE,
                    "from_version": self._current_version.id
                    if self._current_version
                    else None,
                    "to_version": version_id,
                    "user": created_by,
                }
            )

            new_version = ConfigVersion(
                id=version_id,
                created_at=datetime.now(),
                created_by=created_by,
                description=description,
                config_snapshot=config_snapshot,
                parent_version_id=self._current_version.id
                if self._current_version
                else None,
                is_factory_reset=False,
            )
            self._current_version = new_version
            from src.service.cache_service import cache_service
            await cache_service.delete(f"{self._cache_key_prefix}latest")
            await cache_service.invalidate_tag("config")
            event_bus.publish(
                ConfigChangedEvent(
                    version_id=new_version.id,
                    changed_keys=list(config_snapshot.keys()),
                )
            )
            logger.info(f"新配置版本已保存: {new_version.id}")
            return new_version

    async def reset_to_factory(
        self, config_snapshot: dict[str, Any], created_by: str = "system"
    ) -> ConfigVersion:
        """
        恢复出厂设置

        - 创建新版本（is_factory_reset=True）
        - 记录 RESET 审计日志
        - 更新当前版本
        """
        from src.core.distributed_lock import DistributedLock
        from src.models.config import ConfigAction

        async with DistributedLock.execute_with_lock(self._lock_name):
            version_repo, audit_repo = self._get_repos()
            version_id = (
                f"v_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
            )

            await version_repo.create(
                {
                    "id": version_id,
                    "created_at": datetime.now(),
                    "created_by": created_by,
                    "description": "恢复出厂设置",
                    "config_snapshot": config_snapshot,
                    "parent_version_id": self._current_version.id
                    if self._current_version
                    else None,
                    "is_factory_reset": True,
                }
            )

            await audit_repo.create(
                {
                    "action": ConfigAction.RESET,
                    "from_version": self._current_version.id
                    if self._current_version
                    else None,
                    "to_version": version_id,
                    "user": created_by,
                }
            )

            new_version = ConfigVersion(
                id=version_id,
                created_at=datetime.now(),
                created_by=created_by,
                description="恢复出厂设置",
                config_snapshot=config_snapshot,
                parent_version_id=self._current_version.id
                if self._current_version
                else None,
                is_factory_reset=True,
            )
            self._current_version = new_version
            from src.service.cache_service import cache_service
            await cache_service.delete(f"{self._cache_key_prefix}latest")
            await cache_service.invalidate_tag("config")
            event_bus.publish(
                ConfigChangedEvent(
                    version_id=new_version.id,
                    changed_keys=list(config_snapshot.keys()),
                )
            )
            logger.info(f"配置已恢复出厂设置: {new_version.id}")
            return new_version

    async def rollback_to_version(
        self, version_id: str, created_by: str = "system"
    ) -> ConfigVersion:
        """回滚到指定版本"""
        from src.core.distributed_lock import DistributedLock
        from src.models.config import ConfigAction

        async with DistributedLock.execute_with_lock(self._lock_name):
            version_repo, audit_repo = self._get_repos()
            target_orm = await version_repo.get_by_id(version_id)
            if not target_orm:
                raise ValueError(f"配置版本不存在: {version_id}")

            rollback_id = (
                f"v_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
            )
            await version_repo.create(
                {
                    "id": rollback_id,
                    "created_at": datetime.now(),
                    "created_by": created_by,
                    "description": f"回滚到版本: {version_id}",
                    "config_snapshot": target_orm.config_snapshot,
                    "parent_version_id": self._current_version.id
                    if self._current_version
                    else None,
                    "is_factory_reset": False,
                }
            )

            await audit_repo.create(
                {
                    "action": ConfigAction.ROLLBACK,
                    "from_version": self._current_version.id
                    if self._current_version
                    else None,
                    "to_version": rollback_id,
                    "user": created_by,
                }
            )

            rollback_version = ConfigVersion(
                id=rollback_id,
                created_at=datetime.now(),
                created_by=created_by,
                description=f"回滚到版本: {version_id}",
                config_snapshot=target_orm.config_snapshot,
                parent_version_id=self._current_version.id
                if self._current_version
                else None,
                is_factory_reset=False,
            )
            self._current_version = rollback_version
            from src.service.cache_service import cache_service
            await cache_service.delete(f"{self._cache_key_prefix}latest")
            await cache_service.invalidate_tag("config")
            event_bus.publish(
                ConfigChangedEvent(
                    version_id=rollback_version.id,
                    changed_keys=list(target_orm.config_snapshot.keys()),
                )
            )
            logger.info(
                f"已回滚到配置版本: {version_id}, 新版本号: {rollback_version.id}"
            )
            return rollback_version

    async def list_versions(self, limit: int = 50) -> list[dict]:
        """列出配置版本"""
        version_repo, _ = self._get_repos()
        versions = await version_repo.get_version_history(skip=0, limit=limit)
        return [_serialize_config_version(v) for v in versions]

    async def get_version(self, version_id: str) -> dict | None:
        """获取指定版本配置"""
        version_repo, _ = self._get_repos()
        version_orm = await version_repo.get_by_id(version_id)
        if not version_orm:
            return None
        return _serialize_config_version(version_orm)

    @property
    def current_config(self) -> dict[str, Any]:
        """获取当前配置"""
        if not self._current_version:
            raise RuntimeError("配置尚未加载，请先调用 load_latest_version()")
        return self._current_version.config_snapshot

    @property
    def current_version_id(self) -> str:
        """获取当前配置版本ID"""
        if not self._current_version:
            raise RuntimeError("配置尚未加载，请先调用 load_latest_version()")
        return self._current_version.id

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self.current_config.get(key, default)

    def get_full_config(self) -> dict[str, Any]:
        """获取完整配置"""
        return self.current_config.copy()

    async def save_sensitive_config(
        self, key: str, value: str, description: str = "", created_by: str = "system"
    ) -> ConfigVersion:
        """保存敏感配置（自动加密）"""
        encrypted_value = crypto_service.encrypt(value)
        new_config = self.current_config.copy()
        new_config[key] = encrypted_value
        return await self.save_new_version(new_config, description, created_by)

    def get_sensitive_config(self, key: str, default: str = None) -> str | None:
        """读取敏感配置（自动解密）"""
        encrypted_value = self.current_config.get(key)
        if not encrypted_value:
            return default
        try:
            return crypto_service.decrypt(encrypted_value)
        except Exception as e:
            logger.error(f"解密敏感配置 {key} 失败: {e}")
            return default


# 全局实例
config_manager = ConfigManager()
