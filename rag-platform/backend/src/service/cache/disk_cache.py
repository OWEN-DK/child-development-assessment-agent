import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

from src.config import settings
from src.utils.logger import logger


class DiskCache:
    # 类级单例，确保全局只有一个实例
    _instance = None
    _initialized = False

    @staticmethod
    def _json_serializer(obj):
        """JSON 序列化器：正确处理 Pydantic v2 模型和 datetime 对象"""
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="json")
        return str(obj)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 防止重复初始化
        if DiskCache._initialized:
            return
        DiskCache._initialized = True

        self.disk_cache_enabled = getattr(settings, "rag_cache_disk_enabled", True)
        self.disk_cache_dir = self._init_disk_cache_dir()
        self.disk_cache = self._load_disk_cache() if self.disk_cache_enabled else {}
        self.default_ttl = settings.rag_config["cache"]["ttl_seconds"]
        self.disk_persist_interval = getattr(settings, "rag_cache_disk_persist_interval", 300)
        self._persist_lock = threading.Lock()
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
        if not self._persist_lock.acquire(blocking=False):
            return
        try:
            self._do_persist()
        finally:
            self._persist_lock.release()

    def _do_persist(self):
        cache_file = Path(self.disk_cache_dir) / "cache.json"
        temp_file = cache_file.with_suffix(".tmp")
        cache_dir = cache_file.parent
        cache_dir.mkdir(parents=True, exist_ok=True)
        if not os.access(str(cache_dir), os.W_OK):
            logger.error(f"磁盘缓存目录不可写: {cache_dir}")
            return
        persist_data = {}
        current_time = time.time()
        for key, value in self.disk_cache.items():
            expire_at = current_time + self.default_ttl
            persist_data[key] = {"value": value, "expire_at": expire_at, "updated_at": current_time}
        json_str = json.dumps(persist_data, ensure_ascii=False, indent=2, default=DiskCache._json_serializer)
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(json_str)
                f.flush()
                os.fsync(f.fileno())
        except OSError as e:
            logger.error(f"写入临时文件失败: {e}")
            return
        try:
            temp_file.replace(cache_file)
            logger.debug(f"缓存已持久化到磁盘: {len(persist_data)} 条")
        except OSError as e:
            logger.error(f"替换缓存文件失败: {e}")
        finally:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass

    def _start_auto_persist(self):
        if not self.disk_cache_enabled or not self.disk_cache_dir:
            return
        self._persist_thread = None
        self._stop_persist_thread = threading.Event()
        
        def persist_loop():
            while not self._stop_persist_thread.is_set():
                # 使用wait替代sleep，以便能及时响应停止信号
                if self._stop_persist_thread.wait(self.disk_persist_interval):
                    break
                try:
                    self._persist_cache_to_disk()
                except Exception as e:
                    logger.error(f"自动持久化缓存异常: {e}")
        
        self._persist_thread = threading.Thread(target=persist_loop, daemon=False, name="cache-persist")
        self._persist_thread.start()
        logger.info(f"缓存自动持久化已启动，间隔: {self.disk_persist_interval}秒")
    
    def shutdown(self):
        """关闭缓存持久化线程"""
        if hasattr(self, "_stop_persist_thread"):
            self._stop_persist_thread.set()
        if hasattr(self, "_persist_thread") and self._persist_thread is not None and self._persist_thread.is_alive():
            self._persist_thread.join(timeout=5)
            logger.info("缓存持久化线程已关闭")

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
