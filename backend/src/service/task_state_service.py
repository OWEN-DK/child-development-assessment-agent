"""统一任务状态服务（Redis Hash + Lua 脚本原子更新）"""

import asyncio
import json
import time
from decimal import Decimal
from typing import Any, Optional


class DecimalEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理Decimal类型"""
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)

import redis.asyncio as redis

from src.core.redis_client import RedisClient
from src.schemas.task import TERMINAL_STATES, TaskState, TaskStatus
from src.utils.logger import logger

# Lua 脚本：原子执行 终态校验 + HSET + EXPIRE + 活跃任务索引维护
_UPDATE_TASK_LUA_SCRIPT = """
local unpack = table.unpack or unpack
local key = KEYS[1]
local active_set_key = KEYS[2]
local new_status = ARGV[1]
local ttl = tonumber(ARGV[2])
local force_ttl = ARGV[3] == '1'
local task_id = ARGV[4]
local task_type = ARGV[5]

-- 1. 终态保护：检查当前状态是否为终态
local current_status = redis.call('HGET', key, 'status')
local terminal_states = {'completed', 'failed', 'cancelled'}

if current_status then
    local is_terminal = false
    for _, state in ipairs(terminal_states) do
        if current_status == state then
            is_terminal = true
            break
        end
    end
    
    -- 当前是终态，且新状态不是终态，拒绝更新
    if is_terminal then
        local new_is_terminal = false
        for _, state in ipairs(terminal_states) do
            if new_status == state then
                new_is_terminal = true
                break
            end
        end
        if not new_is_terminal then
            return 0  -- 拒绝更新
        end
    end
end

-- 2. 自动填充时间戳
if new_status == 'running' then
    local started_at = redis.call('HGET', key, 'started_at')
    if not started_at or started_at == '' then
        local time_result = redis.call('TIME')
        redis.call('HSET', key, 'started_at', time_result[1] .. '.' .. time_result[2])
    end
elseif new_status == 'completed' or new_status == 'failed' or new_status == 'cancelled' then
    local time_result = redis.call('TIME')
    redis.call('HSET', key, 'completed_at', time_result[1] .. '.' .. time_result[2])
    
    -- 从活跃任务索引中移除
    redis.call('SREM', active_set_key, task_id)
end

-- 3. 更新 status 字段（必须单独处理，因为 status 在 ARGV[1] 中）
if new_status and new_status ~= '' then
    redis.call('HSET', key, 'status', new_status)
end

-- 4. 原子写入所有其他更新字段（HSET）
local argv_len = #ARGV
if argv_len > 5 then
    local fields = {}
    for i = 6, argv_len, 2 do
        table.insert(fields, ARGV[i])
        table.insert(fields, ARGV[i + 1])
    end
    if #fields > 0 then
        redis.call('HSET', key, unpack(fields))
    end
end

-- 5. 原子设置 TTL（与 HSET 同一脚本，保证一致性）
-- running 状态默认不续期（仅 create 时设置），除非强制刷新（force_ttl=1）
if ttl > 0 and (new_status ~= 'running' or force_ttl) then
    redis.call('EXPIRE', key, ttl)
end

return 1  -- 更新成功
"""

# Lua 脚本：创建任务（包含初始状态 + 活跃任务索引）
_CREATE_TASK_LUA_SCRIPT = """
local unpack = table.unpack or unpack
local key = KEYS[1]
local active_set_key = KEYS[2]
local ttl = tonumber(ARGV[1])

-- 写入所有字段
local field_count = (#ARGV - 1) / 2
if field_count > 0 then
    local fields = {}
    for i = 2, #ARGV, 2 do
        table.insert(fields, ARGV[i])
        table.insert(fields, ARGV[i + 1])
    end
    redis.call('HSET', key, unpack(fields))
end

-- 设置 TTL
redis.call('EXPIRE', key, ttl)

-- 添加到活跃任务索引
-- ARGV[2] 是 field 名 "task_id", ARGV[3] 是实际的 task_id 值
local task_id = ARGV[3]
redis.call('SADD', active_set_key, task_id)

return 1
"""


class TaskStateService:
    """统一任务状态服务
    
    特性：
    - Redis Hash 存储（原子更新）
    - Lua 脚本保证终态保护 + TTL 一致性
    - 内存兜底（仅单实例部署）
    - 取消信号管理
    - 活跃任务索引（Set）
    """

    # TTL 映射（秒）
    TTL_MAP = {
        TaskStatus.PENDING: 86400,      # 24 小时
        TaskStatus.RUNNING: 7200,       # 2 小时
        TaskStatus.COMPLETED: 3600,     # 1 小时
        TaskStatus.FAILED: 86400,       # 24 小时
        TaskStatus.CANCELLED: 600,      # 10 分钟
        TaskStatus.RETRYING: 7200,      # 2 小时
    }

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        multi_instance: bool = False,
    ):
        self.redis_client = redis_client or RedisClient.get_client()
        self.multi_instance = multi_instance
        
        # 内存兜底（仅单实例部署时启用）
        self.fallback_to_memory = not multi_instance
        self._memory_cache: dict[str, TaskState] = {}
        self._cache_ttl: dict[str, float] = {}
        self._redis_available = True
        
        # 取消信号
        self._cancellation_signals: dict[str, asyncio.Event] = {}
        
        # Lua 脚本引用
        self._update_script: Optional[Any] = None
        self._create_script: Optional[Any] = None

    def _build_key(self, task_id: str, task_type: str) -> str:
        """构建 Redis Key"""
        return f"task:{task_type}:{task_id}"

    def _build_active_set_key(self, task_type: str) -> str:
        """构建活跃任务索引 Set Key"""
        return f"task:active:{task_type}"

    def _get_ttl(self, status: TaskStatus) -> int:
        """根据状态获取 TTL"""
        return self.TTL_MAP.get(status, 3600)

    async def _ensure_scripts_loaded(self):
        """加载 Lua 脚本到 Redis"""
        if not self._redis_available:
            return

        try:
            if self._update_script is None:
                self._update_script = self.redis_client.register_script(_UPDATE_TASK_LUA_SCRIPT)
            if self._create_script is None:
                self._create_script = self.redis_client.register_script(_CREATE_TASK_LUA_SCRIPT)
        except Exception as e:
            logger.warning(f"Failed to load Redis scripts: {e}")
            self._redis_available = False

    async def create(self, state: TaskState, ttl: Optional[int] = None) -> None:
        """创建任务状态（初始状态）
        
        Args:
            state: 任务状态对象
            ttl: 过期时间（秒），默认根据状态自动设置
        """
        ttl = ttl or self._get_ttl(state.status)
        key = self._build_key(state.task_id, state.task_type)
        active_set_key = self._build_active_set_key(state.task_type)
        
        await self._ensure_scripts_loaded()
        
        # 构建 Hash 字段
        hash_data = state.to_redis_hash()
        argv = [str(ttl)]
        for field, value in hash_data.items():
            argv.append(field)
            if isinstance(value, Decimal):
                argv.append(str(float(value)))
            else:
                argv.append(value)
        
        try:
            await self._create_script(keys=[key, active_set_key], args=argv)
            logger.debug(f"Task {state.task_id} created with status={state.status.value}")
        except Exception as e:
            logger.error(f"Failed to create task {state.task_id}: {e}")
            self._redis_available = False

            if not self.fallback_to_memory:
                raise

            self._memory_cache[state.task_id] = state
            self._cache_ttl[state.task_id] = time.time() + 300
            logger.warning(
                f"Task {state.task_id} created in memory cache due to Redis failure"
            )

    async def update(
        self,
        task_id: str,
        task_type: str,
        updates: dict[str, Any],
        force_ttl: bool = False,
    ) -> bool:
        """原子更新任务状态
        
        Args:
            task_id: 任务 ID
            task_type: 任务类型
            updates: 需要更新的字段
            force_ttl: 是否强制刷新 TTL（running 状态默认不续期）
            
        Returns:
            bool: 更新是否成功（终态保护拒绝时返回 False）
        """
        key = self._build_key(task_id, task_type)
        active_set_key = self._build_active_set_key(task_type)
        new_status = updates.get("status")
        
        await self._ensure_scripts_loaded()
        
        # 构建 ARGV 参数
        ttl = self._get_ttl(TaskStatus(new_status)) if new_status else 3600
        argv = [
            new_status or "",
            str(ttl),
            "1" if force_ttl else "0",
            task_id,
            task_type,
        ]
        
        # 添加其他字段
        for field, value in updates.items():
            if field == "status":
                continue  # 已添加到 ARGV[1]
            if isinstance(value, (dict, list)):
                argv.append(field)
                argv.append(json.dumps(value, cls=DecimalEncoder))
            elif isinstance(value, Decimal):
                argv.append(field)
                argv.append(str(float(value)))
            else:
                argv.append(field)
                argv.append(str(value) if value is not None else "")
        
        try:
            if self._redis_available:
                result = await self._update_script(keys=[key, active_set_key], args=argv)
                success = result == 1

                if not success:
                    logger.warning(
                        f"Task {task_id} update rejected (terminal state protection): "
                        f"status={new_status}"
                    )

                return success

            # 降级到内存缓存
            return self._update_memory(task_id, updates, task_type)
        except Exception as e:
            logger.error(f"Redis update failed for task {task_id}: {e}")

            if not self.fallback_to_memory:
                logger.error("Redis unavailable in multi-instance mode, fallback disabled")
                self._redis_available = False
                return False

            self._redis_available = False
            return self._update_memory(task_id, updates, task_type)

    async def get(self, task_id: str, task_type: str) -> Optional[TaskState]:
        """获取任务状态"""
        key = self._build_key(task_id, task_type)
        
        try:
            if self._redis_available:
                data = await self.redis_client.hgetall(key)
                if data:
                    return TaskState.from_redis_hash(data, task_type)
        except Exception as e:
            logger.error(f"Redis get failed for task {task_id}: {e}")
            self._redis_available = False
        
        # 降级到内存缓存
        if self.fallback_to_memory and task_id in self._memory_cache:
            if time.time() < self._cache_ttl.get(task_id, 0):
                return self._memory_cache[task_id]
            else:
                del self._memory_cache[task_id]
                self._cache_ttl.pop(task_id, None)
        
        return None

    async def delete(self, task_id: str, task_type: str) -> bool:
        """删除任务状态（同时从活跃任务索引和内存缓存中移除）"""
        # 始终清理内存缓存
        self._memory_cache.pop(task_id, None)
        self._cache_ttl.pop(task_id, None)
        key = f"{task_type}:{task_id}"
        self._cancellation_signals.pop(key, None)

        try:
            redis_key = self._build_key(task_id, task_type)
            active_set_key = self._build_active_set_key(task_type)
            await self.redis_client.delete(redis_key)
            await self.redis_client.srem(active_set_key, task_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete task {task_id} from Redis: {e}")
            # Redis 失败但内存已清理，仍返回 True（单实例场景下内存是 source of truth）
            if self.fallback_to_memory:
                return True
            return False

    async def list_active(self, task_type: Optional[str] = None) -> list[TaskState]:
        """列出所有活跃任务（非终态）
        
        使用 Redis Set 索引，避免 scan_iter 全量扫描。
        Redis 不可用时从内存缓存兜底。
        """
        result = []
        
        try:
            if not self._redis_available:
                raise RuntimeError("Redis unavailable, using memory fallback")

            if task_type:
                keys = [self._build_active_set_key(task_type)]
            else:
                keys = []
                async for key in self.redis_client.scan_iter(match="task:active:*"):
                    keys.append(key)
            
            for active_set_key in keys:
                task_ids = await self.redis_client.smembers(active_set_key)
                extracted_type = active_set_key.replace("task:active:", "")
                
                for tid in task_ids:
                    state = await self.get(tid, extracted_type)
                    if state and state.is_active:
                        result.append(state)
        except Exception as e:
            logger.warning(f"Redis list_active failed, falling back to memory: {e}")
            self._redis_available = False
            now = time.time()
            for tid, state in self._memory_cache.items():
                if now > self._cache_ttl.get(tid, 0):
                    continue
                if task_type and state.task_type != task_type:
                    continue
                if state.is_active:
                    result.append(state)
        
        return result

    async def list_recent(self, task_type: Optional[str] = None, limit: int = 50) -> list[TaskState]:
        """列出最近的任务（包括活跃任务和最近的终态任务）
        
        使用 scan_iter 扫描所有任务，按 created_at 倒序排列。
        Redis 不可用时从内存缓存兜底。
        
        Args:
            task_type: 任务类型过滤（可选）
            limit: 返回数量限制（默认 50）
        """
        result = []
        
        try:
            if not self._redis_available:
                raise RuntimeError("Redis unavailable, using memory fallback")

            pattern = f"task:{task_type}:*" if task_type else "task:*"
            
            # 扫描所有任务 Key
            async for key in self.redis_client.scan_iter(match=pattern, count=100):
                # 跳过活跃任务索引 Set
                if key.startswith("task:active:"):
                    continue
                
                try:
                    hash_data = await self.redis_client.hgetall(key)
                    if not hash_data:
                        continue
                    
                    # 从 key 中提取 task_type: task:{task_type}:{task_id}
                    key_parts = key.split(":")
                    if len(key_parts) < 3:
                        continue
                    
                    extracted_type = key_parts[1]
                    
                    state = TaskState.from_redis_hash(hash_data, extracted_type)
                    if state:
                        result.append(state)
                except Exception as e:
                    logger.warning(f"Failed to parse task from {key}: {e}")
                    continue
            
        except Exception as e:
            logger.warning(f"Redis list_recent failed, falling back to memory: {e}")
            self._redis_available = False
            now = time.time()
            for tid, state in self._memory_cache.items():
                if now > self._cache_ttl.get(tid, 0):
                    continue
                if task_type and state.task_type != task_type:
                    continue
                result.append(state)

        # 按 created_at 倒序排列
        result.sort(key=lambda x: x.created_at, reverse=True)
        
        # 限制返回数量
        return result[:limit]

    async def cancel(self, task_id: str, task_type: str) -> bool:
        """取消任务
        
        1. 设置取消信号
        2. 更新 Redis 状态为 cancelled
        3. 推送 SSE 取消事件（由调用方负责）
        """
        # 设置取消信号（key包含task_type，避免不同类型任务冲突）
        key = f"{task_type}:{task_id}"
        if key in self._cancellation_signals:
            self._cancellation_signals[key].set()
        
        # 更新 Redis 状态
        success = await self.update(task_id, task_type, {
            "status": TaskStatus.CANCELLED.value,
        })
        
        if success:
            logger.info(f"Task {task_id} (type={task_type}) cancelled")
        
        return success

    def get_cancellation_signal(self, task_id: str, task_type: str) -> asyncio.Event:
        """获取任务的取消信号"""
        key = f"{task_type}:{task_id}"
        if key not in self._cancellation_signals:
            self._cancellation_signals[key] = asyncio.Event()
        return self._cancellation_signals[key]

    async def check_cancellation(self, task_id: str, task_type: str) -> bool:
        """检查任务是否被取消"""
        key = f"{task_type}:{task_id}"
        signal = self._cancellation_signals.get(key)
        if signal and signal.is_set():
            return True
        return False

    def cleanup_cancellation_signal(self, task_id: str, task_type: str):
        """清理取消信号（任务终态后调用）"""
        key = f"{task_type}:{task_id}"
        self._cancellation_signals.pop(key, None)

    # ==================== 内存兜底方法 ====================

    def _update_memory(self, task_id: str, updates: dict[str, Any], task_type: str = "memory_fallback") -> bool:
        """内存缓存兜底（仅单实例部署）"""
        if task_id not in self._memory_cache:
            fallback_state = TaskState.create(task_id=task_id, task_type=task_type)
            self._memory_cache[task_id] = fallback_state
            self._cache_ttl[task_id] = time.time() + 300
        
        state = self._memory_cache[task_id]
        
        # 终态保护：已完成任务不可逆转为非终态
        new_status = updates.get("status")
        if state.is_terminal and new_status:
            new_status_enum = TaskStatus(new_status) if isinstance(new_status, str) else new_status
            if new_status_enum not in TERMINAL_STATES:
                return False
        
        for key, value in updates.items():
            if hasattr(state, key):
                setattr(state, key, value)
        
        # 设置内存 TTL（5 分钟后清理）
        self._cache_ttl[task_id] = time.time() + 300
        return True

    async def restore_redis_sync(self):
        """Redis 恢复后同步内存数据（仅单实例部署）"""
        if not self._redis_available:
            try:
                await self.redis_client.ping()
                self._redis_available = True
            except Exception:
                return
            
            logger.info("Redis recovered, syncing memory cache...")
            synced_count = 0
            
            for task_id, state in list(self._memory_cache.items()):
                try:
                    key = self._build_key(task_id, state.task_type)
                    hash_data = state.to_redis_hash()
                    await self.redis_client.hset(key, mapping=hash_data)
                    await self.redis_client.expire(key, self._get_ttl(state.status))
                    synced_count += 1
                except Exception as e:
                    logger.error(f"Failed to sync task {task_id} to Redis: {e}")
            
            logger.info(f"Synced {synced_count} tasks to Redis")

    async def cleanup_expired_memory_cache(self):
        """清理过期的内存缓存（每 1 分钟执行）"""
        now = time.time()
        expired_keys = [
            key for key, ttl in self._cache_ttl.items()
            if now > ttl
        ]
        for key in expired_keys:
            self._memory_cache.pop(key, None)
            self._cache_ttl.pop(key, None)
