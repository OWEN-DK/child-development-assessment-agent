import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from src.config import settings
from src.utils.logger import logger


class DiskCache:
    def __init__(self):
        self.disk_cache_enabled = getattr(settings, "rag_cache_disk_enabled", True)
        self.disk_cache_dir = self._init_disk_cache_dir()
        self.disk_cache = self._load_disk_cache() if self.disk_cache_enabled else {}
        self.default_ttl = settings.rag_config["cache"]["ttl_seconds"]
        self.disk_persist_interval = getattr(settings, "rag_cache_disk_persist_interval", 300)
        self._start_auto_persist()

    def _init_disk_cache_dir(self) -> Optional[str]:
        if not self.disk_cache_enabled:
            return None
        cache_dir = getattr(settings, "rag_cache_disk_dir", None)
        if not cache_dir:
            from pathlib import Path
            base_dir = Path(__file__).parent.parent.parent.parent.parent
            cache_dir = str(base_dir / "app_data" / "cache")
        cache_path = Path(cache_dir)
        try:
            cache_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"磁盘缓存目录已创建: {cache_dir}")
            return cache_dir
        except Exception as e:
            logger.error(f"创建磁盘缓存目录失败: {e}")
            return None

    def _load_disk_cache(self) -> dict:
        if not self.disk_cache_enabled or not self.disk_cache_dir:
            return {}
        cache_file = Path(self.disk_cache_dir) / "cache.json"
        if not cache_file.exists():
            return {}
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            current_time = time.time()
            valid_cache = {}
            expired_count = 0
            for key, item in data.items():
                if current_time < item.get("expire_at", 0):
                    valid_cache[key] = item["value"]
                else:
                    expired_count += 1
            logger.info(f"从磁盘加载缓存: {len(valid_cache)} 条有效, {expired_count} 条已过期")
            return valid_cache
        except Exception as e:
            logger.warning(f"加载磁盘缓存失败: {e}")
            return {}

    def _persist_cache_to_disk(self):
        if not self.disk_cache_enabled or not self.disk_cache_dir:
            return
        cache_file = Path(self.disk_cache_dir) / "cache.json"
        temp_file = cache_file.with_suffix(".tmp")
        try:
            persist_data = {}
            current_time = time.time()
            from cachetools import LRUCache
            memory_cache = {}
            timestamps = {}
            for key, value in self.disk_cache.items():
                expire_at = current_time + self.default_ttl
                persist_data[key] = {"value": value, "expire_at": expire_at, "updated_at": current_time}
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(persist_data, f, ensure_ascii=False, indent=2, default=lambda obj: obj.isoformat() if hasattr(obj, "isoformat") else str(obj))
            temp_file.replace(cache_file)
            logger.debug(f"缓存已持久化到磁盘: {len(persist_data)} 条")
        except Exception as e:
            logger.error(f"持久化缓存到磁盘失败: {e}")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    def _start_auto_persist(self):
        if not self.disk_cache_enabled or not self.disk_cache_dir:
            return
        def persist_loop():
            while True:
                time.sleep(self.disk_persist_interval)
                try:
                    self._persist_cache_to_disk()
                except Exception as e:
                    logger.error(f"自动持久化缓存异常: {e}")
        import threading
        thread = threading.Thread(target=persist_loop, daemon=True, name="cache-persist")
        thread.start()
        logger.info(f"缓存自动持久化已启动，间隔: {self.disk_persist_interval}秒")

    def get(self, key: str, default=None):
        if not self.disk_cache_enabled:
            return default
        return self.disk_cache.get(key, default)

    def set(self, key: str, value: Any):
        if not self.disk_cache_enabled:
            return
        self.disk_cache[key] = value

    def delete(self, key: str):
        if not self.disk_cache_enabled:
            return
        if key in self.disk_cache:
            del self.disk_cache[key]

    def clear(self):
        if not self.disk_cache_enabled:
            return
        self.disk_cache.clear()
        self._persist_cache_to_disk()

    def is_enabled(self) -> bool:
        return self.disk_cache_enabled
