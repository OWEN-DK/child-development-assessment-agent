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
            with open(self.active_version_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("version_id")
        except (json.JSONDecodeError, IOError):
            return None

    async def save_version(self, version_data: Dict[str, Any]) -> str:
        async with self._lock:
            version_id = version_data["version_id"]
            file_path = self.versions_dir / f"{version_id}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(version_data, f, indent=2, ensure_ascii=False)
            return version_id

    async def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        file_path = self.versions_dir / f"{version_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    async def list_versions(self, limit: int = 50) -> List[Dict[str, Any]]:
        versions = []
        for file_path in self.versions_dir.glob("v_*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
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
            with open(self.active_version_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "version_id": version_id,
                    "activated_at": datetime.utcnow().isoformat() + "Z"
                }, f, indent=2, ensure_ascii=False)

    async def append_audit_log(self, audit_entry: Dict[str, Any]) -> None:
        async with self._lock:
            with open(self.audit_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
