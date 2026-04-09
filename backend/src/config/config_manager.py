import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from src.config import settings, Settings
from src.config.rules import rules
from src.config.config_repository import JsonConfigRepository, ConfigRepository
from src.config.config_events import ConfigChangedEvent, ConfigRollbackEvent, ConfigResetEvent
from src.core.event_bus import event_bus
from src.utils.logger import logger


class ConfigManager:

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._repository = JsonConfigRepository()
        self._memory_cache: Dict[str, Any] = {}
        self._active_version: Optional[str] = None
        self._lock = asyncio.Lock()
        self._load_active_config()
        ConfigManager._initialized = True

    def _load_active_config(self):
        default_config = self._extract_config_from_settings()

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        active_version = loop.run_until_complete(
            self._repository.get_active_version()
        )

        if active_version:
            version_data = loop.run_until_complete(
                self._repository.get_version(active_version)
            )
            if version_data:
                self._memory_cache = {**default_config, **version_data["config_snapshot"]}
                self._active_version = active_version
                logger.info(f"Loaded config version: {active_version}")
        else:
            self._memory_cache = default_config
            logger.info("Using default config from .env.dev")

    def _extract_config_from_settings(self) -> Dict[str, Any]:
        config = settings.model_dump()
        
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

    async def update_config(
        self,
        config_updates: Dict[str, Any],
        description: str = "",
        created_by: str = "system"
    ) -> Dict[str, Any]:
        async with self._lock:
            version_id = self._generate_version_id()
            previous_version = self._active_version

            new_config = {**self._memory_cache, **config_updates}

            version_data = {
                "version_id": version_id,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "created_by": created_by,
                "description": description,
                "config_snapshot": new_config,
                "parent_version_id": previous_version,
                "is_factory_reset": False
            }

            await self._repository.save_version(version_data)

            self._memory_cache = new_config
            self._active_version = version_id

            await self._repository.set_active_version(version_id)

            await self._repository.append_audit_log({
                "timestamp": version_data["created_at"],
                "action": "UPDATE",
                "from_version": previous_version,
                "to_version": version_id,
                "user": created_by
            })

            changed_keys = list(config_updates.keys())
            event_bus.publish(ConfigChangedEvent(
                from_version=previous_version or "initial",
                to_version=version_id,
                changed_keys=changed_keys,
                config_snapshot=new_config
            ))

            logger.info(f"Config updated to version {version_id}")

            return {
                "version_id": version_id,
                "previous_version": previous_version,
                "config_snapshot": new_config,
                "changed_keys": changed_keys
            }

    def get_config_value(self, key: str, default: Any = None) -> Any:
        return self._memory_cache.get(key, default)

    def get_full_config(self) -> Dict[str, Any]:
        return self._memory_cache.copy()

    def get_active_version(self) -> Optional[str]:
        return self._active_version

    async def rollback_to_version(self, version_id: str) -> Dict[str, Any]:
        async with self._lock:
            version_data = await self._repository.get_version(version_id)
            if not version_data:
                raise ValueError(f"Version {version_id} not found")

            previous_version = self._active_version

            self._memory_cache = version_data["config_snapshot"]
            self._active_version = version_id

            await self._repository.set_active_version(version_id)

            await self._repository.append_audit_log({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": "ROLLBACK",
                "from_version": previous_version,
                "to_version": version_id,
                "user": "system"
            })

            event_bus.publish(ConfigRollbackEvent(
                from_version=previous_version or "initial",
                to_version=version_id,
                rollback_at=datetime.utcnow().isoformat() + "Z"
            ))

            return {
                "version_id": version_id,
                "previous_version": previous_version,
                "config_snapshot": self._memory_cache
            }

    async def reset_to_factory(self) -> Dict[str, Any]:
        async with self._lock:
            version_id = self._generate_version_id()
            previous_version = self._active_version

            default_config = self._extract_config_from_settings()

            version_data = {
                "version_id": version_id,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "created_by": "system",
                "description": "Factory reset to .env.dev defaults",
                "config_snapshot": default_config,
                "parent_version_id": previous_version,
                "is_factory_reset": True
            }

            await self._repository.save_version(version_data)
            self._memory_cache = default_config
            self._active_version = version_id
            await self._repository.set_active_version(version_id)

            await self._repository.append_audit_log({
                "timestamp": version_data["created_at"],
                "action": "RESET",
                "from_version": previous_version,
                "to_version": version_id,
                "user": "system"
            })

            event_bus.publish(ConfigResetEvent(
                from_version=previous_version or "initial",
                reset_at=version_data["created_at"]
            ))

            return {
                "version_id": version_id,
                "config_snapshot": default_config
            }

    def _generate_version_id(self) -> str:
        return f"v_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"


config_manager = ConfigManager()
