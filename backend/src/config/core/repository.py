from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import os
import asyncio
from pathlib import Path

from src.config import settings


class ConfigRepository(ABC):
    @abstractmethod
    async def get_active_version(self) -> Optional[str]:
        pass

    @abstractmethod
    async def save_version(self, version_data: Dict[str, Any]) -> str:
        pass

    @abstractmethod
    async def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    async def list_versions(self, limit: int = 50) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def set_active_version(self, version_id: str) -> None:
        pass

    @abstractmethod
    async def append_audit_log(self, audit_entry: Dict[str, Any]) -> None:
        pass


class JsonConfigRepository(ConfigRepository):
    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            base_dir = f"{settings.data_dir}/configs"
        self.base_dir = Path(base_dir)
        self.versions_dir = self.base_dir / "versions"
        self.active_version_file = self.base_dir / "active_version.json"
        self.audit_log_file = self.base_dir / "audit_log.jsonl"
        self._lock = asyncio.Lock()
        self._ensure_dirs()

    def _ensure_dirs(self):
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.versions_dir.mkdir(parents=True, exist_ok=True)

    async def get_active_version(self) -> Optional[str]:
        if not self.active_version_file.exists():
            return None
        try:
            with open(self.active_version_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("version_id")
        except (json.JSONDecodeError, IOError):
            return None

    async def save_version(self, version_data: Dict[str, Any]) -> str:
        async with self._lock:
            version_id = version_data["version_id"]
            file_path = self.versions_dir / f"{version_id}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(version_data, f, indent=2, ensure_ascii=False)
            return version_id

    async def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        file_path = self.versions_dir / f"{version_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    async def list_versions(self, limit: int = 50) -> List[Dict[str, Any]]:
        versions = []
        for file_path in self.versions_dir.glob("v_*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    versions.append(json.load(f))
            except (json.JSONDecodeError, IOError):
                continue
        versions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return versions[:limit]

    async def set_active_version(self, version_id: str) -> None:
        async with self._lock:
            version_data = await self.get_version(version_id)
            if version_data is None:
                raise ValueError(f"Version {version_id} not found")
            with open(self.active_version_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "version_id": version_id,
                        "activated_at": datetime.utcnow().isoformat() + "Z",
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

    async def append_audit_log(self, audit_entry: Dict[str, Any]) -> None:
        async with self._lock:
            with open(self.audit_log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from src.config.core.entities import ConfigVersion as ConfigVersionEntity
from datetime import datetime


class MySQLConfigRepository(ConfigRepository):
    """基于MySQL的配置仓库实现"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_version(self) -> Optional[str]:
        """获取当前激活版本ID"""
        result = await self.session.execute(
            select(ConfigVersion).order_by(desc(ConfigVersion.created_at)).limit(1)
        )
        db_version = result.scalar_one_or_none()
        return db_version.id if db_version else None

    async def save_version(self, version_data: Dict[str, Any]) -> str:
        """保存配置版本"""
        from src.models.config import ConfigVersion

        db_version = ConfigVersion(
            id=version_data["id"],
            created_at=version_data["created_at"],
            created_by=version_data["created_by"],
            description=version_data["description"],
            config_snapshot=version_data["config_snapshot"],
            parent_version_id=version_data["parent_version_id"],
            is_factory_reset=version_data["is_factory_reset"],
        )
        self.session.add(db_version)
        await self.session.flush()
        return version_data["id"]

    async def get_latest_version(self) -> ConfigVersionEntity | None:
        """获取最新配置版本"""
        from src.models.config import ConfigVersion

        result = await self.session.execute(
            select(ConfigVersion).order_by(desc(ConfigVersion.created_at)).limit(1)
        )
        db_version = result.scalar_one_or_none()
        return self._to_entity(db_version) if db_version else None

    async def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取配置版本"""
        db_version = await self.session.get(ConfigVersion, version_id)
        if not db_version:
            return None
        entity = self._to_entity(db_version)
        return entity.model_dump()

    async def get_version_by_id(self, version_id: str) -> ConfigVersionEntity | None:
        """根据ID获取配置版本实体"""
        from src.models.config import ConfigVersion

        db_version = await self.session.get(ConfigVersion, version_id)
        return self._to_entity(db_version) if db_version else None

    async def list_versions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """列出配置版本"""
        from src.models.config import ConfigVersion

        result = await self.session.execute(
            select(ConfigVersion).order_by(desc(ConfigVersion.created_at)).limit(limit)
        )
        return [self._to_entity(v).model_dump() for v in result.scalars().all()]

    async def set_active_version(self, version_id: str) -> None:
        """设置激活版本（MySQL实现中最新版本即为激活版本）"""
        # MySQL版本中无需单独设置，最新版本自动为激活版本
        pass

    async def append_audit_log(self, audit_entry: Dict[str, Any]) -> None:
        """记录配置操作日志"""
        from src.models.config import ConfigAuditLog, ConfigAction

        log = ConfigAuditLog(
            action=ConfigAction(audit_entry["action"]),
            from_version=audit_entry.get("from_version"),
            to_version=audit_entry.get("to_version"),
            user=audit_entry.get("user"),
        )
        self.session.add(log)
        await self.session.flush()

    def _to_entity(self, db_version: "ConfigVersion") -> ConfigVersionEntity:
        """转换数据库模型为实体"""
        return ConfigVersionEntity(
            id=db_version.id,
            created_at=db_version.created_at,
            created_by=db_version.created_by,
            description=db_version.description,
            config_snapshot=db_version.config_snapshot,
            parent_version_id=db_version.parent_version_id,
            is_factory_reset=db_version.is_factory_reset,
        )
