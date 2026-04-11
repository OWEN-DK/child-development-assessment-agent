import hashlib
import json
import time
import asyncio
import os
from pathlib import Path
from typing import Any, Optional, List, Set
from collections import defaultdict
from functools import wraps
from src.config import settings
from src.utils.logger import logger
from src.core.interfaces import ICacheService

try:
    from lru import LRU
except ImportError:
    # 简易LRU实现兜底
    class LRU:
        def __init__(self, maxsize):
            self.maxsize = maxsize
            self.cache = {}
            self.timestamps = {}
        
        def __contains__(self, key):
            return key in self.cache
        
        def __getitem__(self, key):
            if key in self.cache:
                self.timestamps[key] = time.time()
                return self.cache[key]
            raise KeyError(key)
        
        def __setitem__(self, key, value):
            if len(self.cache) >= self.maxsize:
                oldest_key = min(self.timestamps.keys(), key=lambda k: self.timestamps[k])
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
            self.cache[key] = value
            self.timestamps[key] = time.time()
        
        def get(self, key, default=None):
            try:
                return self[key]
            except KeyError:
                return default
        
        def set(self, key, value, expire=None):
            self[key] = value
        
        def __delitem__(self, key):
            if key in self.cache:
                del self.cache[key]
                del self.timestamps[key]
        
        def clear(self):
            self.cache.clear()
            self.timestamps.clear()


class CacheService(ICacheService):
    """生产级统一缓存服务，支持多级缓存、细粒度失效、穿透/击穿/雪崩防护、磁盘持久化"""
    
    def __init__(self):
        self.enabled = settings.rag_config["cache"]["enabled"]
        # 内存缓存（热点数据）
        self.memory_cache = LRU(maxsize=settings.rag_config["cache"]["max_size"] or 10000)
        # Redis缓存（分布式全量数据）
        self.redis_client = self._init_redis_client()
        # 磁盘持久化
        self.disk_cache_enabled = getattr(settings, 'rag_cache_disk_enabled', True)
        self.disk_cache_dir = self._init_disk_cache_dir()
        self.disk_cache = self._load_disk_cache()
        # 布隆过滤器（防穿透），这里使用空结果缓存作为主要防穿透手段
        self.bloom_filter = None
        # 互斥锁（防击穿）
        self.locks = {}
        # 文档哈希到缓存键映射（细粒度失效）
        self.doc_hash_map = defaultdict(set)
        # 缓存标签映射
        self.tag_map = defaultdict(set)
        # 默认TTL
        self.default_ttl = settings.rag_config["cache"]["ttl_seconds"]
        # 磁盘持久化间隔（秒）
        self.disk_persist_interval = getattr(settings, 'rag_cache_disk_persist_interval', 300)
        self._persist_task = None
        self._start_auto_persist()
    
    def _init_disk_cache_dir(self) -> Optional[str]:
        """初始化磁盘缓存目录"""
        if not self.disk_cache_enabled:
            return None
        
        # 优先使用配置的路径
        cache_dir = getattr(settings, 'rag_cache_disk_dir', None)
        if not cache_dir:
            # 使用 app_data 目录
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
        """从磁盘加载缓存数据"""
        if not self.disk_cache_enabled or not self.disk_cache_dir:
            return {}
        
        cache_file = Path(self.disk_cache_dir) / "cache.json"
        if not cache_file.exists():
            logger.info("磁盘缓存文件不存在，将创建新缓存")
            return {}
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 过滤过期缓存
            current_time = time.time()
            valid_cache = {}
            expired_count = 0
            
            for key, item in data.items():
                if current_time < item.get('expire_at', 0):
                    valid_cache[key] = item['value']
                else:
                    expired_count += 1
            
            logger.info(f"从磁盘加载缓存: {len(valid_cache)} 条有效, {expired_count} 条已过期")
            return valid_cache
        except Exception as e:
            logger.warning(f"加载磁盘缓存失败: {e}")
            return {}
    
    def _persist_cache_to_disk(self):
        """将内存缓存持久化到磁盘"""
        if not self.disk_cache_enabled or not self.disk_cache_dir:
            return
        
        cache_file = Path(self.disk_cache_dir) / "cache.json"
        temp_file = cache_file.with_suffix('.tmp')
        
        try:
            # 构建持久化数据
            persist_data = {}
            current_time = time.time()
            
            # 从内存缓存中提取
            memory_cache = getattr(self.memory_cache, 'cache', self.memory_cache)
            timestamps = getattr(self.memory_cache, 'timestamps', {})
            
            for key, value in memory_cache.items():
                expire_at = current_time + self.default_ttl
                if key in timestamps:
                    expire_at = timestamps[key] + self.default_ttl
                
                persist_data[key] = {
                    'value': value,
                    'expire_at': expire_at,
                    'updated_at': current_time
                }
            
            # 原子写入：先写临时文件，再重命名
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(persist_data, f, ensure_ascii=False, indent=2)
            
            temp_file.replace(cache_file)
            logger.debug(f"缓存已持久化到磁盘: {len(persist_data)} 条")
        except Exception as e:
            logger.error(f"持久化缓存到磁盘失败: {e}")
            # 清理临时文件
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
    
    def _start_auto_persist(self):
        """启动自动持久化后台线程"""
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
    
    def _init_redis_client(self):
        """初始化Redis客户端连接池（暂时注释不引入）"""
        # redis_url = getattr(settings, "redis_url", None)
        # if redis_url:
        #     try:
        #         import redis.asyncio as redis
        #         pool = redis.ConnectionPool.from_url(redis_url, decode_responses=True, max_connections=10)
        #         client = redis.Redis(connection_pool=pool)
        #         logger.info(f"Redis client initialized with URL: {redis_url}")
        #         return client
        #     except ImportError:
        #         logger.warning("redis package not installed, Redis cache disabled.")
        #         return None
        #     except Exception as e:
        #         logger.error(f"Failed to initialize Redis client: {e}")
        #         return None
        return None
    
    def _get_cache_key(self, key_prefix: str, args: tuple, kwargs: dict) -> str:
        """生成包含索引版本和配置指纹的缓存键"""
        # 拼接参数
        key_parts = args + tuple(sorted(kwargs.items()))
        # 哈希生成最终键
        key_hash = hashlib.md5(json.dumps(key_parts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return f"rag:cache:{key_prefix}:{key_hash}"
    
    async def get(self, key: str, default: Any = None) -> Any:
        """获取缓存，优先内存，再磁盘，最后Redis"""
        if not self.enabled:
            return default
            
        # 先查内存
        if key in self.memory_cache:
            logger.debug(f"Cache hit (memory): {key}")
            return self.memory_cache[key]
        
        # 再查磁盘缓存
        if self.disk_cache_enabled and key in self.disk_cache:
            value = self.disk_cache[key]
            # 回写到内存
            self.memory_cache[key] = value
            logger.debug(f"Cache hit (disk): {key}")
            return value
        
        # 最后查Redis
        if self.redis_client:
            try:
                redis_value = await self.redis_client.get(key)
                if redis_value:
                    value = json.loads(redis_value)
                    # 回写到内存
                    self.memory_cache[key] = value
                    logger.debug(f"Cache hit (redis): {key}")
                    return value
            except Exception as e:
                logger.warning(f"Redis get failed, falling back to memory only: {e}")
        
        return default
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: int = None, 
        doc_hashes: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        is_hot: bool = False
    ):
        """写入缓存，支持关联文档哈希和标签"""
        if not self.enabled:
            return
            
        expire = expire or self.default_ttl
        # 随机偏移过期时间，防雪崩
        expire += int(time.time()) % 60  # 0-60秒随机偏移
        
        # 写入内存，热点数据永不过期
        if is_hot:
            self.memory_cache[key] = value
        else:
            self.memory_cache.set(key, value, expire=expire)
        
        # 写入磁盘缓存
        if self.disk_cache_enabled:
            self.disk_cache[key] = value
        
        # 写入Redis
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    key, 
                    expire, 
                    json.dumps(value, ensure_ascii=False)
                )
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
        
        # 关联文档哈希
        if doc_hashes:
            for doc_hash in doc_hashes:
                self.doc_hash_map[doc_hash].add(key)
                if self.redis_client:
                    await self.redis_client.sadd(f"rag:doc_map:{doc_hash}", key)
        
        # 关联标签
        if tags:
            for tag in tags:
                self.tag_map[tag].add(key)
                if self.redis_client:
                    await self.redis_client.sadd(f"rag:tag_map:{tag}", key)
    
    async def invalidate_by_doc_hash(self, doc_hash: str):
        """按文档哈希失效缓存"""
        if not self.enabled:
            return
            
        keys_to_remove = self.doc_hash_map.pop(doc_hash, set())
        if self.redis_client:
            try:
                redis_keys = await self.redis_client.smembers(f"rag:doc_map:{doc_hash}")
                keys_to_remove.update(redis_keys)
                await self.redis_client.delete(f"rag:doc_map:{doc_hash}")
            except Exception as e:
                logger.warning(f"Redis doc map get failed: {e}")
        
        for key in keys_to_remove:
            if key in self.memory_cache:
                del self.memory_cache[key]
            if self.redis_client:
                try:
                    await self.redis_client.delete(key)
                except:
                    pass
        
        logger.info(f"Invalidated {len(keys_to_remove)} cache entries for doc hash {doc_hash}")
    
    async def invalidate_by_tag(self, tag: str):
        """按标签失效缓存"""
        if not self.enabled:
            return
            
        keys_to_remove = self.tag_map.pop(tag, set())
        if self.redis_client:
            try:
                redis_keys = await self.redis_client.smembers(f"rag:tag_map:{tag}")
                keys_to_remove.update(redis_keys)
                await self.redis_client.delete(f"rag:tag_map:{tag}")
            except Exception as e:
                logger.warning(f"Redis tag map get failed: {e}")
        
        for key in keys_to_remove:
            if key in self.memory_cache:
                del self.memory_cache[key]
            if self.redis_client:
                try:
                    await self.redis_client.delete(key)
                except:
                    pass
    
    async def get_with_protection(
        self, 
        key: str, 
        load_func, 
        expire: int = None,
        lock_timeout: int = 10,
        **kwargs
    ) -> Any:
        """带穿透/击穿防护的获取方法"""
        if not self.enabled:
            return await load_func(**kwargs)
            
        # 1. 尝试获取缓存
        result = await self.get(key)
        if result is not None:
            # 空结果缓存，防穿透
            if result == "__NULL__":
                return None
            return result
        
        # 2. 布隆过滤器检查，防穿透
        if self.bloom_filter and not self.bloom_filter.contains(key):
            logger.debug(f"Bloom filter blocked key: {key}")
            await self.set(key, "__NULL__", expire=60)  # 空结果缓存1分钟
            return None
        
        # 3. 互斥锁，防击穿
        lock_key = f"rag:lock:{key}"
        lock = self.locks.get(lock_key, asyncio.Lock())
        self.locks[lock_key] = lock
        
        try:
            async with asyncio.timeout(lock_timeout):
                await lock.acquire()
                # 二次检查，避免重复加载
                result = await self.get(key)
                if result is not None:
                    if result == "__NULL__":
                        return None
                    return result
                
                # 加载数据
                result = await load_func(**kwargs)
                
                # 缓存结果
                if result is None:
                    await self.set(key, "__NULL__", expire=60)
                else:
                    await self.set(key, result, expire=expire)
                
                return result
        finally:
            if lock.locked():
                lock.release()
            if lock_key in self.locks and not lock.locked():
                del self.locks[lock_key]
    
    def clear(self):
        """清空所有缓存"""
        self.memory_cache.clear()
        self.doc_hash_map.clear()
        self.tag_map.clear()
        self.locks.clear()
        
        # 清空磁盘缓存
        if self.disk_cache_enabled:
            self.disk_cache.clear()
            self._persist_cache_to_disk()
        
        logger.info("All cache cleared")
    
    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        return {
            "enabled": self.enabled,
            "memory_cache_size": len(getattr(self.memory_cache, 'cache', self.memory_cache)),
            "disk_cache_size": len(self.disk_cache) if self.disk_cache_enabled else 0,
            "disk_cache_enabled": self.disk_cache_enabled,
            "disk_cache_dir": self.disk_cache_dir,
            "max_size": settings.rag_config["cache"]["max_size"],
            "default_ttl": self.default_ttl,
            "redis_enabled": self.redis_client is not None,
            "bloom_filter_enabled": self.bloom_filter is not None,
            "doc_hash_count": len(self.doc_hash_map),
            "tag_count": len(self.tag_map)
        }


# 统一缓存装饰器
def cached(
    expire: int = None, 
    key_prefix: str = "", 
    doc_hash_param: Optional[str] = None,
    tags: Optional[List[str]] = None,
    is_hot: bool = False
):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from src.service.cache_service import cache_service
            
            # 生成缓存键
            cache_key = cache_service._get_cache_key(key_prefix, args, kwargs)
            
            # 提取文档哈希
            doc_hashes = None
            if doc_hash_param and doc_hash_param in kwargs:
                doc_hashes = [kwargs[doc_hash_param]]
            
            # 带防护获取
            async def load_func():
                return await func(*args, **kwargs)
            
            return await cache_service.get_with_protection(
                cache_key, 
                load_func, 
                expire=expire,
                doc_hashes=doc_hashes,
                tags=tags,
                is_hot=is_hot
            )
        return wrapper
    return decorator


# 全局实例
cache_service = CacheService()
