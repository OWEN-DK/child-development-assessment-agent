# 任务状态管理系统重构需求文档

> **版本**: v1.0  
> **创建日期**: 2026-04-20  
> **状态**: 待评审  
> **优先级**: P0（高）

---

## 一、背景与问题

### 1.1 现状概述

系统当前存在 6 种任务类型，每种任务的状态管理实现方式不同：

| 任务类型 | 状态存储 | 进度推送 | 状态值 |
|----------|----------|----------|--------|
| 文档上传/索引 | Redis String | Polling | `pending/processing/success/failed/cancelled` |
| 草稿矩阵生成 | 内存（AsyncTaskManager） | SSE | `pending/processing/success/failed/cancelled` |
| RAG 评估测试 | MySQL（TestRun 表） | SSE | `pending/running/completed/failed/cancelled` |
| PDF 导出 | Redis String | SSE + Polling | `pending/processing/completed/failed` |
| 分层内容生成 | 进程内存（Dict） | Polling | `running/completed` |
| 文档导入（旧） | 本地 JSON 文件 | Polling | `pending/running/completed/failed` |

### 1.2 核心问题

#### 问题 1：状态值混乱（严重）

- **现象**：`success` vs `completed`、`processing` vs `running` 混用
- **影响**：前端需要为每种任务类型写不同的状态判断逻辑，容易遗漏
- **示例**：
  ```typescript
  // 文档上传
  if (task.status === 'success') { ... }
  
  // RAG 评估
  if (task.status === 'completed') { ... }  // 同样的语义，不同的值！
  ```

#### 问题 2：竞态条件导致状态丢失（严重）

- **现象**：页面一直显示"正在索引"，但后端日志显示任务已完成
- **根因**：`progress_callback` 使用 `call_soon_threadsafe` + `ensure_future` 异步调度，导致：
  1. 进度回调调度到事件循环（未立即执行）
  2. 主流程继续执行，写入 `status=success`
  3. 之前调度的进度回调此时才执行，覆盖 `status` 为 `processing`
- **影响**：用户看到任务卡住，实际已完成；文档列表不刷新

#### 问题 3：非原子状态更新（严重）

- **现象**：并发更新时可能丢失字段
- **根因**：`update_status` 使用 GET → merge → SET 三步操作
  ```python
  value = await redis.get(key)        # 步骤 1：读取
  status = json.loads(value)
  status.update(updates)              # 步骤 2：合并
  await redis.setex(key, ttl, ...)    # 步骤 3：写入
  ```
- **影响**：两个并发更新同时执行时，后一个会覆盖前一个的修改

#### 问题 4：状态存储分散（中等）

- **现象**：Redis、本地文件、内存、MySQL 4 种存储方式
- **影响**：
  - 重启后部分任务状态丢失（内存存储）
  - 多实例部署时状态不同步（本地文件）
  - TTL 不一致（1 小时 / 24 小时 / 7 天）

#### 问题 5：推送方式不统一（中等）

- **现象**：有的用 SSE，有的用 Polling，有的两者都用
- **影响**：前端维护多套状态消费逻辑，代码重复

---

## 二、目标

### 2.1 业务目标

1. **消除状态卡住问题**：任务完成后，前端 3 秒内显示成功状态
2. **统一状态语义**：所有任务类型使用相同的状态值
3. **支持多实例部署**：状态存储在 Redis，所有实例共享

### 2.2 技术目标

1. **原子状态更新**：使用 Redis Hash + HSET，单次操作完成
2. **消除竞态条件**：进度回调同步执行，不异步调度
3. **统一推送协议**：SSE 优先，Polling 降级兜底
4. **终态保护**：任务进入终态（completed/failed/cancelled）后不可逆

---

## 三、详细设计

### 3.1 统一状态机

```
┌─────────────────────────────────────────────────────────┐
│                    标准任务状态机                          │
│                                                         │
│  PENDING ──→ RUNNING ───┬──→ COMPLETED                  │
│    ↑                    ├──→ FAILED                     │
│    │                    └──→ CANCELLED                  │
│    │                          ↑                         │
│    └──── (可重试) ──────── RETRYING (可选)               │
│                                                         │
│  终态（不可逆）：COMPLETED, FAILED, CANCELLED             │
└─────────────────────────────────────────────────────────┘
```

**状态定义**：

| 状态 | 含义 | 是否终态 | 前端行为 |
|------|------|----------|----------|
| `pending` | 已创建，等待执行 | 否 | 显示"等待中" |
| `running` | 正在执行 | 否 | 显示进度条，监听 SSE |
| `completed` | 执行成功 | **是** | 显示成功，3 秒后移除 |
| `failed` | 执行失败 | **是** | 显示错误，保留 1 小时 |
| `cancelled` | 用户取消 | **是** | 显示已取消，3 秒后移除 |
| `retrying` | 失败重试中（可选） | 否 | 显示"重试中" |

### 3.2 统一任务状态模型

**存放位置**：`backend/src/schemas/task.py`（遵循实体类集中管理规范）

```python
class TaskState(BaseModel):
    """统一任务状态模型（Redis Hash 存储结构）"""
    
    # 标识
    task_id: str
    task_type: str  # "upload" / "draft_generation" / "export" / "test_run"
    
    # 状态
    status: TaskStatus  # pending/running/completed/failed/cancelled
    stage: Optional[str]  # 阶段（可选，如 "parsing" / "indexing"）
    progress: float = 0.0  # 0-100
    message: Optional[str]  # 用户可见消息
    
    # 结果（终态时填充）
    error: Optional[str]  # 失败时填充
    result: Optional[dict]  # 成功时填充
    
    # 时间戳（Unix 时间戳）
    created_at: float
    started_at: Optional[float]
    completed_at: Optional[float]
    
    # 元数据（扩展字段）
    metadata: dict = {}
```

### 3.3 Redis 存储结构

**Key 命名规范**：`task:{task_type}:{task_id}`

**示例**：
```
task:upload:57865dda-11b7-4310-8a9f-8b66e276b74b
task:draft_generation:abc123
task:export:def456
```

**Hash 字段**：
```
HGETALL task:upload:57865dda-11b7-4310-8a9f-8b66e276b74b
  1) "task_id"       → "57865dda-11b7-4310-8a9f-8b66e276b74b"
  2) "task_type"     → "upload"
  3) "status"        → "running"
  4) "stage"         → "indexing"
  5) "progress"      → "99.0"
  6) "message"       → "索引构建完成，正在保存数据"
  7) "created_at"    → "1776651144.6777012"
  8) "started_at"    → "1776651145.1234567"
  9) "completed_at"  → (nil)
 10) "metadata"      → "{\"filename\":\"学习之道.epub\"}"
```

**TTL 策略（强制过期，所有 Key 必须设置 TTL）**：

| 任务状态 | TTL | 说明 | 清理策略 |
|----------|-----|------|----------|
| `pending` | 24 小时 | 等待执行的任务 | 超时自动删除，防止僵尸任务 |
| `running` | 2 小时 | 正在执行的任务 | 超时视为异常，看门狗标记为 `failed` |
| `completed` | 1 小时 | 成功完成的任务 | 用户可见期，过期自动删除 |
| `failed` | 24 小时 | 失败的任务 | 保留较长时间供用户查看错误，过期自动删除 |
| `cancelled` | 10 分钟 | 用户取消的任务 | 快速清理，过期自动删除 |

**强制 TTL 规则**：
1. **创建时必须设置 TTL**：`create()` 方法必须传入 `ttl` 参数，默认 3600 秒
2. **running 状态不续期**：`update()` 时若新状态为 `running`，不刷新 TTL（除非传入 `force_ttl=True`），确保看门狗可检测卡住任务
3. **其他状态正常续期**：`update()` 时若新状态非 `running`，根据状态重新设置 TTL
4. **Lua 脚本原子执行**：HSET + EXPIRE 在同一脚本中，不会出现设置了值但没有 TTL 的情况
5. **禁止无 TTL 的 Key**：任何写入操作必须携带 TTL，违反则抛出异常

**TTL 原子续期机制（Lua 脚本内执行）**：

```python
# Lua 脚本中自动根据状态设置 TTL
_UPDATE_TASK_LUA_SCRIPT = """
local key = KEYS[1]
local new_status = ARGV[1]
local force_ttl = ARGV[3] == '1'

-- TTL 映射表（秒）
local ttl_map = {
    pending = 86400,      -- 24 小时
    running = 7200,       -- 2 小时（仅 create 时设置，update 不续期）
    completed = 3600,     -- 1 小时
    failed = 86400,       -- 24 小时
    cancelled = 600,      -- 10 分钟
}

-- ... 终态校验和 HSET 逻辑 ...

-- 根据新状态自动设置 TTL（原子操作）
-- 注意：running 状态仅在 create 时设置 TTL，update 时不续期
-- 这样看门狗可以通过 TTL 剩余时间判断任务是否卡住
local ttl = ttl_map[new_status] or 3600
if new_status ~= 'running' or force_ttl then
    redis.call('EXPIRE', key, ttl)
end

return 1
"""
```

**TTL 策略设计说明**：

| 状态 | TTL 设置时机 | 续期策略 | 设计理由 |
|------|------------|---------|---------|
| `pending` | create/update | 每次 update 续期 | 等待中的任务可能长期 pending，需持续续期 |
| `running` | 仅 create 时 | **不续期** | 确保看门狗可通过 TTL 剩余时间检测卡住任务 |
| `completed` | update（终态转换） | 设置一次 | 完成后固定 1 小时可见期 |
| `failed` | update（终态转换） | 设置一次 | 失败后固定 24 小时供排查 |
| `cancelled` | update（终态转换） | 设置一次 | 取消后快速清理 |

**running 状态不续期的原因**：
1. 任务创建时设置 2 小时 TTL
2. 如果任务正常运行，会在 2 小时内完成并转换为终态，终态转换时重新设置 TTL
3. 如果任务卡住（死循环/阻塞），TTL 会在 2 小时后自然过期，Redis 自动删除 Key
4. 看门狗检测 `started_at` 超过 2 小时的任务，主动标记为 `failed` 并延长 TTL 供排查
5. 两者形成双重保护：TTL 过期自动清理 + 看门狗主动标记失败

**运行中超时检测（看门狗机制）**：

```python
# 后台定时任务（每 5 分钟执行一次）
async def check_stuck_tasks():
    """检测并处理卡住的任务"""
    pattern = "task:*"
    async for key in redis_client.scan_iter(match=pattern):
        task = await redis_client.hgetall(key)
        if task["status"] == "running":
            started_at = float(task["started_at"])
            elapsed = time.time() - started_at
            
            # 运行超过 2 小时，标记为失败
            if elapsed > 7200:
                await redis_client.hset(key, mapping={
                    "status": "failed",
                    "error": "任务执行超时（> 2 小时）",
                    "completed_at": time.time()
                })
                await redis_client.expire(key, 86400)  # 延长 TTL 供查看
                logger.warning(f"Task {task['task_id']} marked as failed due to timeout")
```

**内存占用估算**：

| 任务数量 | 平均大小 | 总内存 | 说明 |
|----------|----------|--------|------|
| 100 个活跃任务 | 500 bytes | 50 KB | 正常运行 |
| 1000 个活跃任务 | 500 bytes | 500 KB | 高负载 |
| 5000 个历史任务（终态） | 500 bytes | 2.5 MB | TTL 未过期 |
| **峰值** | - | **< 10 MB** | 可接受范围 |

---

### 3.4 兜底方案（多级降级）

#### 兜底策略总览

```
┌─────────────────────────────────────────────────────────┐
│                    多级降级架构                           │
│                                                         │
│  第 1 层：Redis（主存储，所有任务类型）                    │
│    ↓ 失败                                                │
│  第 2 层：本地内存缓存（进程级兜底）                        │
│    ↓ 失败                                                │
│  第 3 层：MySQL 复用（仅 test_run 类型）                   │
│    ↓ 失败                                                │
│  第 4 层：前端本地状态（用户体验兜底）                      │
└─────────────────────────────────────────────────────────┘
```

#### 兜底 1：Redis 宕机 → 本地内存缓存（仅单实例部署）

> **⚠️ 重要限制**：内存兜底**仅适用于单实例部署**。多实例部署时，实例 A 写入的内存缓存实例 B 读不到，Redis 恢复后 `restore_redis_sync()` 也只同步本实例数据。
> 
> **多实例部署策略**：Redis 宕机时直接返回错误 + 前端降级提示，不启用内存兜底。通过 `settings.MULTI_INSTANCE_DEPLOYMENT` 配置开关控制。

**场景**：Redis 连接失败、网络中断、Redis 进程崩溃（单实例部署）

**方案**：

```python
class TaskStateService:
    def __init__(self, fallback_to_memory: bool = True, multi_instance: bool = False):
        # 多实例部署时禁用内存兜底（避免数据不一致）
        self.fallback_to_memory = fallback_to_memory and not multi_instance
        self._memory_cache: dict[str, TaskState] = {}
        self._cache_ttl: dict[str, float] = {}
        self._redis_available = True
    
    async def _check_redis_health(self) -> bool:
        """检查 Redis 健康状态"""
        try:
            await self.redis_client.ping()
            return True
        except Exception:
            return False
    
    async def update(self, task_id: str, task_type: str, updates: dict) -> bool:
        """带兜底的状态更新"""
        try:
            # 尝试写入 Redis
            if self._redis_available:
                await self._update_redis(task_id, task_type, updates)
                return True
        except Exception as e:
            logger.error(f"Redis update failed: {e}")
            self._redis_available = False
        
        # 多实例部署：直接返回失败，不启用内存兜底
        if not self.fallback_to_memory:
            logger.error("Redis unavailable in multi-instance mode, fallback disabled")
            return False
        
        # 降级到内存缓存（仅单实例部署）
        return self._update_memory(task_id, updates)
    
    def _update_memory(self, task_id: str, updates: dict) -> bool:
        """内存缓存兜底（仅单实例部署）"""
        if task_id not in self._memory_cache:
            return False
        
        state = self._memory_cache[task_id]
        for key, value in updates.items():
            setattr(state, key, value)
        
        # 设置内存 TTL（5 分钟后清理）
        self._cache_ttl[task_id] = time.time() + 300
        return True
    
    async def get(self, task_id: str, task_type: str) -> TaskState | None:
        """带兜底的状态查询"""
        # 1. 尝试 Redis
        if self._redis_available:
            try:
                state = await self._get_redis(task_id, task_type)
                if state:
                    return state
            except Exception:
                self._redis_available = False
        
        # 2. 降级到内存（仅单实例部署）
        if self.fallback_to_memory and task_id in self._memory_cache:
            # 检查内存 TTL
            if time.time() < self._cache_ttl.get(task_id, 0):
                return self._memory_cache[task_id]
            else:
                del self._memory_cache[task_id]
        
        return None
    
    async def restore_redis_sync(self):
        """Redis 恢复后同步内存数据（仅单实例部署）"""
        if not self._redis_available:
            self._redis_available = await self._check_redis_health()
            
            if self._redis_available:
                logger.info("Redis recovered, syncing memory cache...")
                for task_id, state in self._memory_cache.items():
                    await self._update_redis(task_id, state.task_type, state.model_dump())
                logger.info(f"Synced {len(self._memory_cache)} tasks to Redis")
```

**内存清理定时任务**：

```python
async def cleanup_expired_memory_cache():
    """清理过期的内存缓存（每 1 分钟执行）"""
    now = time.time()
    expired_keys = [
        key for key, ttl in self._cache_ttl.items()
        if now > ttl
    ]
    for key in expired_keys:
        self._memory_cache.pop(key, None)
        self._cache_ttl.pop(key, None)
```

#### 兜底 2：test_run 类型复用现有 TestRun.status 字段

**场景**：RAG 评估测试任务（运行时间长，结果需要长期保存）

**方案**：不新建 `task_state` 表，直接复用现有 `test_runs` 表的 `status` 字段。

**现有 TestRun 模型结构**（已满足需求）：

```python
# models/test_case.py:209-258
class TestRun(Base):
    __tablename__ = "test_runs"
    
    id: Mapped[str]                    # task_id
    status: Mapped[TestRunStatus]      # running/completed/failed/cancelled
    created_at: Mapped[datetime]       # created_at
    started_at: Mapped[datetime|None]  # started_at
    completed_at: Mapped[datetime|None] # completed_at
    config_snapshot: Mapped[dict|None] # metadata
    # ... 其他字段
```

**TestRunStatus 枚举适配**（需新增 `pending` 状态以匹配统一状态机）：

```python
# models/test_case.py:41-45（需修改）
class TestRunStatus(PyEnum):
    PENDING = "pending"      # 新增：已创建，等待执行
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

**注意**：`pending` 状态为新增，需同步更新：
1. `TestRun` 表 `status` 字段的默认值（如需要）
2. 前端测试运行列表的状态过滤逻辑

**适配策略**：

```python
class TestRunTaskStateAdapter:
    """test_run 类型的 Redis + MySQL 双写适配器
    
    - Redis 作为主存储（快速查询 + SSE 推送）
    - MySQL TestRun.status 作为持久化兜底
    - 中间状态定期同步（stage 变化或进度每增加 10%）
    """
    
    # 上次同步到 MySQL 的进度值，用于判断是否需要同步
    _last_synced_progress: dict[str, float] = {}
    # 上次同步的 stage 值
    _last_synced_stage: dict[str, str] = {}
    
    async def update(self, task_id: str, updates: dict) -> bool:
        # 1. 更新 Redis（含兜底逻辑）
        success = await redis_task_state_service.update(task_id, "test_run", updates)
        
        if not success:
            return False
        
        # 2. 判断是否需要同步到 MySQL
        new_status = updates.get("status")
        new_progress = updates.get("progress")
        new_stage = updates.get("stage")
        
        should_sync = False
        
        # 终态必须同步
        if new_status in ("completed", "failed", "cancelled"):
            should_sync = True
        
        # stage 变化时同步（如 parsing → indexing）
        if new_stage and new_stage != self._last_synced_stage.get(task_id):
            should_sync = True
            self._last_synced_stage[task_id] = new_stage
        
        # 进度每增加 10% 同步一次
        if new_progress is not None:
            last_progress = self._last_synced_progress.get(task_id, 0)
            if new_progress - last_progress >= 10:
                should_sync = True
                self._last_synced_progress[task_id] = new_progress
        
        if should_sync:
            await self._sync_to_mysql(task_id, updates)
        
        return success
    
    async def get(self, task_id: str) -> TaskState | None:
        # 1. 优先从 Redis 读取
        state = await redis_task_state_service.get(task_id, "test_run")
        if state:
            return state
        
        # 2. Redis 失败时，从 MySQL TestRun 表读取
        return await self._load_from_mysql(task_id)
    
    async def _sync_to_mysql(self, task_id: str, updates: dict):
        """同步状态到 MySQL TestRun 表"""
        async with db_session_factory() as session:
            stmt = select(TestRun).where(TestRun.id == task_id)
            result = await session.execute(stmt)
            test_run = result.scalar_one_or_none()
            
            if not test_run:
                return
            
            new_status = updates.get("status")
            if new_status:
                test_run.status = TestRunStatus(new_status)
            
            if new_status in ("completed", "failed", "cancelled"):
                test_run.completed_at = datetime.utcnow()
                # 清理同步记录
                self._last_synced_progress.pop(task_id, None)
                self._last_synced_stage.pop(task_id, None)
            
            # 同步进度和阶段信息（扩展 TestRun 表或存入 config_snapshot）
            if "progress" in updates or "stage" in updates:
                snapshot = test_run.config_snapshot or {}
                if "progress" in updates:
                    snapshot["last_progress"] = updates["progress"]
                if "stage" in updates:
                    snapshot["last_stage"] = updates["stage"]
                test_run.config_snapshot = snapshot
            
            await session.commit()
    
    async def _load_from_mysql(self, task_id: str) -> TaskState | None:
        """从 MySQL TestRun 表恢复状态"""
        async with db_session_factory() as session:
            stmt = select(TestRun).where(TestRun.id == task_id)
            result = await session.execute(stmt)
            test_run = result.scalar_one_or_none()
            
            if not test_run:
                return None
            
            snapshot = test_run.config_snapshot or {}
            return TaskState(
                task_id=test_run.id,
                task_type="test_run",
                status=test_run.status.value,
                progress=snapshot.get("last_progress", 0.0),
                stage=snapshot.get("last_stage"),
                created_at=test_run.created_at.timestamp(),
                started_at=test_run.started_at.timestamp() if test_run.started_at else None,
                completed_at=test_run.completed_at.timestamp() if test_run.completed_at else None,
                metadata=snapshot,
            )
```

**适用场景**：

| 任务类型 | 是否持久化到 MySQL | 原因 |
|----------|------------|------|
| upload | ❌ 否 | 短任务（< 10 分钟），Redis 足够 |
| draft_generation | ❌ 否 | 短任务，失败可重新生成 |
| export | ❌ 否 | 短任务（< 60 秒），Redis 足够 |
| test_run | ✅ 是 | 运行时间长（可能数小时），复用 TestRun.status |
| layered_generation | ❌ 否 | 短任务，进程内存 + Redis |
| document_import（旧） | ❌ 否 | 待废弃，迁移到 upload |

#### 兜底 3：前端本地状态（用户体验兜底）

**场景**：后端完全不可用、网络断开

**方案**：

```typescript
// hooks/useTaskProgress.ts
import { useState, useEffect, useRef } from 'react';

interface LocalTaskState {
  taskId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  message: string;
  lastUpdated: number;
}

export function useTaskProgress(options: UseTaskProgressOptions) {
  const [status, setStatus] = useState<TaskStatus>('pending');
  const [progress, setProgress] = useState(0);
  const [isOffline, setIsOffline] = useState(false);
  const localStateRef = useRef<LocalTaskState | null>(null);
  
  // 保存到 localStorage（页面刷新后恢复）
  useEffect(() => {
    const key = `task:${options.taskId}`;
    const saved = localStorage.getItem(key);
    if (saved) {
      localStateRef.current = JSON.parse(saved);
      setStatus(localStateRef.current.status);
      setProgress(localStateRef.current.progress);
    }
  }, [options.taskId]);
  
  // 监听网络状态
  useEffect(() => {
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => {
      setIsOffline(true);
      console.warn('Network disconnected, using local state');
    };
    
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);
  
  // 定期保存状态到 localStorage
  const saveToLocal = (newStatus: TaskStatus, newProgress: number) => {
    const state: LocalTaskState = {
      taskId: options.taskId,
      status: newStatus,
      progress: newProgress,
      message: isOffline ? '网络连接已断开，显示最后已知状态' : '',
      lastUpdated: Date.now(),
    };
    localStateRef.current = state;
    localStorage.setItem(`task:${options.taskId}`, JSON.stringify(state));
  };
  
  // ... SSE 和 Polling 逻辑 ...
  
  return { 
    status, 
    progress, 
    isOffline,
    // 其他字段
  };
}
```

**前端降级 UI**：

```typescript
// 显示离线提示
{isOffline && (
  <Alert
    type="warning"
    message="网络连接已断开"
    description="当前显示最后已知状态，网络恢复后将自动同步"
    showIcon
  />
)}

// 任务卡住时的手动刷新按钮
{status === 'running' && progress < 100 && (
  <Button 
    icon={<ReloadOutlined />} 
    onClick={() => refreshTaskStatus()}
  >
    刷新状态
  </Button>
)}
```

#### 兜底 4：任务恢复机制（后端重启）

**场景**：后端服务重启，内存中的活跃任务丢失

**方案**：

```python
# server.py - 启动时恢复任务
async def recover_active_tasks_on_startup():
    """服务启动时恢复活跃任务"""
    logger.info("Checking for active tasks to recover...")
    
    # 1. 从 Redis 扫描所有任务
    pattern = "task:*"
    recovered_count = 0
    
    async for key in redis_client.scan_iter(match=pattern):
        task = await redis_client.hgetall(key)
        
        # 2. 只恢复 running 状态的任务
        if task["status"] == "running":
            task_id = task["task_id"]
            task_type = task["task_type"]
            
            # 3. 检查是否真的在运行（通过进程/线程池）
            is_actually_running = await check_if_task_in_execution(task_id)
            
            if not is_actually_running:
                # 4. 标记为失败（服务重启导致中断）
                await redis_client.hset(key, mapping={
                    "status": "failed",
                    "error": "服务重启，任务中断",
                    "completed_at": time.time()
                })
                await redis_client.expire(key, 86400)
                logger.warning(f"Task {task_id} marked as failed (server restart)")
                recovered_count += 1
    
    logger.info(f"Recovered {recovered_count} interrupted tasks")
```

---

### 3.5 原子更新服务

**核心方法**：

```python
class TaskStateService:
    async def create(state: TaskState, ttl: int = 3600) -> None:
        """创建任务状态（初始状态）
        同时写入活跃任务索引 Set: task:active:{task_type}
        """
        
    async def update(task_id: str, task_type: str, updates: dict, force_ttl: bool = False) -> bool:
        """原子更新任务状态（使用 Lua 脚本 + HSET + EXPIRE）
        如果状态转换为终态，从活跃任务索引 Set 中移除
        """
        
    async def get(task_id: str, task_type: str) -> TaskState | None:
        """获取任务状态"""
        
    async def delete(task_id: str, task_type: str) -> bool:
        """删除任务状态（同时从活跃任务索引 Set 中移除）"""
        
    async def list_active(task_type: str | None = None) -> list[TaskState]:
        """列出所有活跃任务（非终态）
        使用 Redis Set 索引，避免 scan_iter 全量扫描
        """
```

**活跃任务索引 Set**：

为避免 `scan_iter` 全量扫描的性能问题，维护一个 Redis Set 记录活跃任务 ID：

```
# Set 结构：task:active:{task_type}
SMEMBERS task:active:upload
  1) "57865dda-11b7-4310-8a9f-8b66e276b74b"
  2) "abc123..."

# 创建任务时添加
SADD task:active:upload "57865dda-11b7-4310-8a9f-8b66e276b74b"

# 任务完成时移除
SREM task:active:upload "57865dda-11b7-4310-8a9f-8b66e276b74b"

# 列出活跃任务（O(N)，N 为活跃任务数，远小于 scan_iter）
SMEMBERS task:active:upload
```

**list_active 实现**：

```python
async def list_active(self, task_type: str | None = None) -> list[TaskState]:
    """列出所有活跃任务"""
    if task_type:
        # 指定类型：直接读取对应 Set
        keys = [f"task:active:{task_type}"]
    else:
        # 所有类型：scan 所有 active Set
        keys = []
        async for key in self.redis_client.scan_iter(match="task:active:*"):
            keys.append(key)
    
    result = []
    for key in keys:
        task_ids = await self.redis_client.smembers(key)
        for task_id in task_ids:
            state = await self.get(task_id, key.replace("task:active:", ""))
            if state:
                result.append(state)
    
    return result
```

**Lua 脚本集成**：在创建/更新/删除时同步维护 Set 索引：

```lua
-- 创建任务时
redis.call('SADD', 'task:active:' .. task_type, task_id)

-- 任务转换为终态时
redis.call('SREM', 'task:active:' .. task_type, task_id)
```

**终态保护 + 原子更新（Lua 脚本实现）**：

```python
# Lua 脚本：原子执行 终态校验 + HSET + EXPIRE
_UPDATE_TASK_LUA_SCRIPT = """
local key = KEYS[1]
local new_status = ARGV[1]
local ttl = tonumber(ARGV[2])
local force_ttl = ARGV[3] == '1'

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
    if not started_at then
        local time = redis.call('TIME')
        redis.call('HSET', key, 'started_at', time[1] .. '.' .. time[2])
    end
elseif new_status == 'completed' or new_status == 'failed' or new_status == 'cancelled' then
    local time = redis.call('TIME')
    redis.call('HSET', key, 'completed_at', time[1] .. '.' .. time[2])
end

-- 3. 原子写入所有更新字段（HSET）
local field_count = #ARGV - 2  -- 减去 status 和 ttl
if field_count > 0 then
    local fields = {}
    for i = 3, #ARGV, 2 do
        table.insert(fields, ARGV[i])
        table.insert(fields, ARGV[i + 1])
    end
    redis.call('HSET', key, table.unpack(fields))
end

-- 4. 原子设置 TTL（与 HSET 同一脚本，保证一致性）
-- running 状态默认不续期（ARGV[3] == "0"），除非强制刷新（ARGV[3] == "1"）
if ttl > 0 and (new_status ~= 'running' or ARGV[3] == '1') then
    redis.call('EXPIRE', key, ttl)
end

return 1  -- 更新成功
"""

class TaskStateService:
    TERMINAL_STATES = {"completed", "failed", "cancelled"}
    
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self._update_script = None
    
    async def _ensure_script_loaded(self):
        """加载 Lua 脚本到 Redis"""
        if self._update_script is None:
            self._update_script = self.redis_client.register_script(_UPDATE_TASK_LUA_SCRIPT)
    
    async def update(self, task_id: str, task_type: str, updates: dict, force_ttl: bool = False) -> bool:
        """原子更新任务状态
        
        使用 Lua 脚本保证：终态校验 + HSET + EXPIRE 全部原子执行
        并发安全：不会出现 GET → merge → SET 的竞态条件
        
        Args:
            task_id: 任务 ID
            task_type: 任务类型（用于构建 Redis Key 和活跃任务索引）
            updates: 需要更新的字段
            force_ttl: 是否强制刷新 TTL（running 状态默认不续期，除非 force_ttl=True）
        """
        await self._ensure_script_loaded()
        
        key = f"task:{task_type}:{task_id}"
        new_status = updates.get("status")
        ttl = self._get_ttl_by_status(new_status) if new_status else 3600
        
        # 构建 ARGV 参数：[status, ttl, force_ttl, field1, value1, field2, value2, ...]
        argv = [new_status or "", str(ttl), "1" if force_ttl else "0"]
        for field, value in updates.items():
            argv.append(field)
            argv.append(json.dumps(value) if isinstance(value, (dict, list)) else str(value))
        
        result = await self._update_script(keys=[key], args=argv)
        return result == 1
    
    def _get_ttl_by_status(self, status: str) -> int:
        """根据状态返回对应 TTL"""
        ttl_map = {
            "pending": 86400,      # 24 小时
            "running": 7200,       # 2 小时
            "completed": 3600,     # 1 小时
            "failed": 86400,       # 24 小时
            "cancelled": 600,      # 10 分钟
        }
        return ttl_map.get(status, 3600)
```

**Lua 脚本优势**：

| 对比项 | 旧方案（GET → merge → SET） | 新方案（Lua 脚本） |
|--------|---------------------------|-------------------|
| 原子性 | ❌ 三步操作，并发时丢失更新 | ✅ 单脚本原子执行 |
| 终态保护 | ❌ 校验和写入分离，可能被覆盖 | ✅ 校验和写入在同一脚本 |
| TTL 一致性 | ❌ HSET 成功后 EXPIRE 可能失败 | ✅ HSET + EXPIRE 同脚本 |
| 网络往返 | 3 次（GET + SET + EXPIRE） | 1 次（EVALSHA） |

### 3.6 修复竞态条件

**旧方案（有问题）**：

```python
def progress_callback(stage, progress, message):
    main_loop.call_soon_threadsafe(
        lambda: asyncio.ensure_future(_update_status_async(...))
    )

await rag_service.ingest_book(progress_callback=progress_callback)
# 此时 progress_callback 调度的 future 可能还未执行！
await task_status_service.update_status(task_id, {"status": "success"})
# 之前的 future 执行后，覆盖了 status！
```

**新方案（修复）**：

```python
async def progress_callback(stage, progress, message):
    """同步进度回调（直接 await，保证顺序）"""
    await task_state_service.update(task_id, task_type="upload", updates={
        "stage": stage,
        "progress": progress,
        "message": message,
    })

await rag_service.ingest_book(progress_callback=progress_callback)
# 此时所有 progress_callback 已执行完毕
await task_state_service.update(task_id, task_type="upload", updates={"status": "completed"})
# 不会被覆盖！
```

### 3.7 统一 SSE 消息处理协议

**核心原则**：所有任务类型使用统一的 SSE 事件格式，前端只需一套消费逻辑。

#### 频道命名规范

```
{task_type}:{task_id}

示例：
  upload:57865dda-11b7-4310-8a9f-8b66e276b74b
  draft_generation:abc123
  export:def456
  test_run:run-uuid-789
```

#### 统一事件格式

所有 SSE 事件必须包含以下基础字段：

```typescript
interface BaseSseEvent {
  type: 'progress' | 'complete' | 'error' | 'heartbeat';
  task_id: string;
  task_type: string;  // "upload" | "draft_generation" | "export" | "test_run"
  timestamp: string;  // ISO 8601
}
```

**进度事件**：

```json
{
  "type": "progress",
  "task_id": "57865dda-...",
  "task_type": "upload",
  "status": "running",
  "stage": "indexing",
  "progress": 99.0,
  "message": "索引构建完成，正在保存数据",
  "metadata": {},
  "timestamp": "2026-04-20T10:30:00Z"
}
```

**完成事件**：

```json
{
  "type": "complete",
  "task_id": "57865dda-...",
  "task_type": "upload",
  "status": "completed",
  "result": {
    "file_hash": "abc123",
    "document_count": 150
  },
  "timestamp": "2026-04-20T10:30:05Z"
}
```

**错误事件**：

```json
{
  "type": "error",
  "task_id": "57865dda-...",
  "task_type": "upload",
  "status": "failed",
  "error": "解析文件失败：格式不支持",
  "timestamp": "2026-04-20T10:30:03Z"
}
```

#### 后端统一发布器

废弃 `SSEPublisher.publish_progress()` 和 `SSEPublisher.publish_complete()` 等专用方法，统一使用 `SSEPublisher.publish_event()`：

```python
class TaskSsePublisher:
    """统一任务 SSE 发布器"""
    
    @classmethod
    async def publish(cls, task_type: str, task_id: str, event_type: str, data: dict):
        """发布统一格式 SSE 事件
        
        Args:
            task_type: 任务类型（upload/draft_generation/export/test_run）
            task_id: 任务 ID
            event_type: 事件类型（progress/complete/error）
            data: 事件数据（不包含 type/task_id/task_type/timestamp）
        """
        channel = f"{task_type}:{task_id}"
        payload = {
            "type": event_type,
            "task_id": task_id,
            "task_type": task_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        await SSEPublisher.publish(channel, payload)
    
    @classmethod
    async def publish_progress(cls, task_type: str, task_id: str, **kwargs):
        await cls.publish(task_type, task_id, "progress", kwargs)
    
    @classmethod
    async def publish_complete(cls, task_type: str, task_id: str, **kwargs):
        await cls.publish(task_type, task_id, "complete", kwargs)
    
    @classmethod
    async def publish_error(cls, task_type: str, task_id: str, **kwargs):
        await cls.publish(task_type, task_id, "error", kwargs)
```

#### 前端统一消费 Hook

```typescript
// hooks/useTaskProgress.ts
interface UseTaskProgressOptions {
  taskId: string;
  taskType: string;
  pollingInterval?: number;  // 降级轮询间隔，默认 2000ms
  onComplete?: (result: any) => void;
  onError?: (error: string) => void;
}

function useTaskProgress(options: UseTaskProgressOptions): {
  status: TaskStatus;
  progress: number;
  stage: string | null;
  message: string;
  isOffline: boolean;
} {
  const [status, setStatus] = useState<TaskStatus>('pending');
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [isOffline, setIsOffline] = useState(false);
  
  // SSE 重连机制
  const MAX_RECONNECT_ATTEMPTS = 3;
  const RECONNECT_DELAY_MS = 2000;
  let reconnectAttempts = 0;
  
  // 仅缓存必要字段到 localStorage（不存 result，避免配额限制）
  const saveToLocal = (s: TaskStatus, p: number, m: string) => {
    const state = { taskId: options.taskId, status: s, progress: p, message: m, lastUpdated: Date.now() };
    localStorage.setItem(`task:${options.taskId}`, JSON.stringify(state));
  };
  
  // 建立 SSE 连接（带重连）
  useEffect(() => {
    const connectSSE = async () => {
      try {
        const response = await fetch(`/api/v1/tasks/${options.taskType}/${options.taskId}/stream`);
        const reader = response.body?.getReader();
        if (!reader) throw new Error('SSE stream not available');
        
        reconnectAttempts = 0;
        setIsOffline(false);
        
        // 读取 SSE 流...
      } catch (err) {
        if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttempts++;
          setTimeout(connectSSE, RECONNECT_DELAY_MS * reconnectAttempts);
        } else {
          setIsOffline(true);
          // 降级到 Polling 模式
          startPolling();
        }
      }
    };
    
    connectSSE();
    return () => cleanup();
  }, [options.taskId, options.taskType]);
  
  return { status, progress, stage, message, isOffline };
}
```

**工作流程**：

```
1. 组件挂载
   ↓
2. 尝试建立 SSE 连接（最多重连 3 次，指数退避）
   ├── 成功 → 监听 SSE 事件，更新状态
   │         ├── progress 事件 → 更新 progress/stage/message
   │         ├── complete 事件 → 更新 status=completed，停止监听，触发 onComplete
   │         └── error 事件 → 更新 status=failed，停止监听，触发 onError
   └── 失败（3 次重连后）→ 降级到 Polling 模式（2 秒间隔）
   ↓
3. 收到终态事件（complete/error）
   ↓
4. 停止 SSE/Polling，触发回调
   ↓
5. 组件卸载时清理连接
```

**多任务并行管理**：

```typescript
// hooks/useMultipleTasks.ts
// 同时管理多个任务的 SSE 连接
function useMultipleTasks(taskConfigs: Array<{taskId: string, taskType: string}>) {
  // 为每个任务创建独立的 useTaskProgress hook
  const taskStates = taskConfigs.map(config => ({
    ...config,
    ...useTaskProgress(config),
  }));
  
  return taskStates;
}
```

### 3.8 前端统一消费模式

**核心 Hook**：`useTaskProgress`

```typescript
interface UseTaskProgressOptions {
  taskId: string;
  taskType: string;
  pollingInterval?: number;  // 降级轮询间隔，默认 2000ms
  onComplete?: (result: any) => void;
  onError?: (error: string) => void;
}

function useTaskProgress(options: UseTaskProgressOptions): {
  status: TaskStatus;
  progress: number;
  stage: string | null;
  message: string;
}
```

**工作流程**：

```
1. 组件挂载
   ↓
2. 尝试建立 SSE 连接
   ├── 成功 → 监听 SSE 事件，更新状态
   └── 失败 → 降级到 Polling 模式
   ↓
3. 收到终态事件（complete/error）
   ↓
4. 停止 SSE/Polling，触发回调
   ↓
5. 组件卸载时清理连接
```

---

## 四、API 契约

### 4.1 后端 API

#### 创建任务

```
POST /api/v1/tasks/{task_type}
Request: { ... }
Response: {
  "code": 0,
  "data": {
    "task_id": "uuid",
    "status": "pending",
    "created_at": 1776651144.67
  }
}
```

#### 查询任务状态

```
GET /api/v1/tasks/{task_type}/{task_id}
Response: {
  "code": 0,
  "data": {
    "task_id": "uuid",
    "task_type": "upload",
    "status": "running",
    "stage": "indexing",
    "progress": 99.0,
    "message": "索引构建完成，正在保存数据",
    "created_at": 1776651144.67,
    "started_at": 1776651145.12,
    "completed_at": null,
    "metadata": { "filename": "学习之道.epub" }
  }
}
```

#### SSE 监听

```
GET /api/v1/tasks/{task_type}/{task_id}/stream
Content-Type: text/event-stream

event: progress
data: {"type":"progress","status":"running","progress":99.0,...}

event: complete
data: {"type":"complete","status":"completed","result":{...}}
```

#### 取消任务

```
POST /api/v1/tasks/{task_type}/{task_id}/cancel
Response: {
  "code": 0,
  "data": { "status": "cancelled" }
}
```

**取消机制实现**：

```python
class TaskStateService:
    """任务状态服务（含取消信号管理）"""
    
    # 取消信号存储：task_id -> asyncio.Event
    _cancellation_signals: dict[str, asyncio.Event] = {}
    
    async def cancel(self, task_id: str, task_type: str) -> bool:
        """取消任务
        1. 设置取消信号
        2. 更新 Redis 状态为 cancelled
        3. 推送 SSE 取消事件
        """
        # 1. 设置取消信号（业务代码通过 check_cancellation 检查）
        if task_id in self._cancellation_signals:
            self._cancellation_signals[task_id].set()
        
        # 2. 更新 Redis 状态
        success = await self.update(task_id, task_type, {
            "status": "cancelled",
            "completed_at": time.time(),
        })
        
        # 3. 推送 SSE 取消事件
        if success:
            await TaskSsePublisher.publish(
                task_type=task_type,
                task_id=task_id,
                event_type="complete",
                data={"status": "cancelled"},
            )
        
        return success
    
    def get_cancellation_signal(self, task_id: str) -> asyncio.Event:
        """获取任务的取消信号
        业务代码在执行过程中定期检查此信号
        """
        if task_id not in self._cancellation_signals:
            self._cancellation_signals[task_id] = asyncio.Event()
        return self._cancellation_signals[task_id]
    
    async def check_cancellation(self, task_id: str) -> bool:
        """检查任务是否被取消
        业务代码在关键操作前调用此方法
        """
        signal = self._cancellation_signals.get(task_id)
        if signal and signal.is_set():
            return True
        return False
    
    def cleanup_cancellation_signal(self, task_id: str):
        """清理取消信号（任务终态后调用）"""
        self._cancellation_signals.pop(task_id, None)
```

**业务代码使用示例**：

```python
async def ingest_book(file_path: str, task_id: str, progress_callback):
    """文档导入任务（支持取消）"""
    pages = extract_pages(file_path)
    
    for i, page in enumerate(pages):
        # 定期检查取消信号
        if await task_state_service.check_cancellation(task_id):
            logger.info(f"Task {task_id} cancelled at page {i}")
            return  # 优雅退出
        
        process_page(page)
        await progress_callback(i, len(pages), f"处理第 {i+1} 页")
    
    # 任务完成，清理取消信号
    task_state_service.cleanup_cancellation_signal(task_id)
```

**AsyncTaskManager 集成**：

```python
class AsyncTaskManager:
    @classmethod
    async def start_task(cls, task_type, task_func, *args, **kwargs):
        task_id = str(uuid.uuid4())
        
        # 创建取消信号
        cancellation_event = asyncio.Event()
        task_state_service._cancellation_signals[task_id] = cancellation_event
        
        async def wrapped_task():
            try:
                # 将取消信号注入到 kwargs
                kwargs['cancellation_event'] = cancellation_event
                result = await task_func(*args, **kwargs)
                # ... 完成逻辑
            finally:
                task_state_service.cleanup_cancellation_signal(task_id)
        
        # ... 创建任务逻辑
```

#### 删除任务

```
DELETE /api/v1/tasks/{task_type}/{task_id}
Response: { "code": 0, "message": "success" }
```

### 4.2 前端组件接口

#### ProgressList 组件

```typescript
interface ProgressListProps<T extends TaskState> {
  tasks: T[];
  config: ProgressListConfig<T>;
}

interface ProgressListConfig<T> {
  title: string;
  getItemKey: (task: T) => string;
  getItemTitle: (task: T) => string;
  getStageText: (task: T) => string;
  showProgress: boolean;
  showStage: boolean;
  onCancel?: (task: T) => Promise<void>;
  onDelete?: (task: T) => Promise<void>;
  autoRemoveOnSuccess: boolean;
  autoRemoveOnCancel: boolean;
  successKeepSeconds: number;  // 成功后保留时间
  cancelKeepSeconds: number;
  failedKeepSeconds: number;
}
```

---

## 五、迁移策略

### 5.1 分阶段实施（直接替换，无双写）

| 阶段 | 内容 | 风险 | 回滚方案 |
|------|------|------|----------|
| **阶段 1** | 创建 `TaskStateService`（Lua 脚本原子更新）+ `TaskSsePublisher`，不替换旧服务 | 低 | 删除新代码即可 |
| **阶段 2** | 迁移文档上传任务（upload），**直接删除旧服务**，替换为新服务 | 中 | git revert |
| **阶段 3** | 迁移草稿生成任务（draft_generation）+ 导出任务（export），**直接替换** | 中 | git revert |
| **阶段 4** | 迁移 RAG 评估任务（test_run），复用 TestRun.status | 高 | git revert |
| **阶段 5** | 清理旧代码（task_status_service.py, task_state_manager.py），**直接删除** | 低 | git revert |

**零迁移原则**：项目未上线，不存在历史兼容问题。每个阶段完成后**直接删除旧代码**，禁止保留向后兼容层、废弃标记、迁移脚本。

### 5.2 旧代码清理清单

**阶段 2 完成后删除**：
- `backend/src/service/task_status_service.py`（旧 Redis String 服务）
- `backend/src/service/document_ingestion/task_state_manager.py`（旧本地 JSON 文件服务）
- `backend/src/controller/rag_controller.py` 中旧状态枚举（`TASK_STATUS_PENDING` 等）
- `backend/src/controller/rag_controller.py` 中 `process_book_background()` 旧进度回调逻辑

**阶段 3 完成后删除**：
- `backend/src/core/async_task.py` 中旧的 `publish_progress/publish_complete/publish_error` 方法
- `backend/src/service/export_service.py` 中旧的 `_update_task_status/_get_task_status` 方法

**阶段 4 完成后删除**：
- `backend/src/api/sse.py` 中 `publish_progress/publish_complete` 专用方法（保留 `publish/publish_event`）

**阶段 5 完成后删除**：
- 所有旧服务引用和导入语句
- 前端旧状态兼容逻辑（`normalizeStatus` 函数）

### 5.3 ~~前端兼容（仅过渡期）~~

> **已移除**：项目未上线，遵循零迁移原则。每个阶段直接替换为新服务，前端同步更新，不需要兼容旧状态值。

~~```typescript
// 过渡期兼容旧状态值（阶段 2-4 使用，阶段 5 删除）
const normalizeStatus = (status: string): TaskStatus => {
  const map: Record<string, TaskStatus> = {
    'success': 'completed',
    'processing': 'running',
  };
  return map[status] || status as TaskStatus;
};
```~~

### 5.4 Redis 旧 Key 清理

迁移完成后，清理旧服务写入的 Redis Key：

```python
# scripts/cleanup_old_redis_keys.py
async def cleanup_old_keys():
    """清理旧服务写入的 Redis Key"""
    patterns = [
        "upload:*",           # 旧上传任务 Key
        "rag_eval:export:*",  # 旧导出任务 Key
    ]
    
    total_cleaned = 0
    for pattern in patterns:
        count = 0
        async for key in redis_client.scan_iter(match=pattern):
            await redis_client.delete(key)
            count += 1
        logger.info(f"Cleaned up {count} keys matching {pattern}")
        total_cleaned += count
    
    logger.info(f"Total cleaned: {total_cleaned} old Redis keys")
    return total_cleaned
```

### 5.5 ~~配置开关（仅用于灰度发布，非双写）~~

> **已移除**：项目未上线，遵循零迁移原则。每个阶段完成后直接替换为新服务，不需要版本开关。

~~```python
# config/settings.py
class Settings(BaseSettings):
    # 任务状态服务版本（0=旧服务，1=新服务）
    TASK_STATE_SERVICE_VERSION: int = 0  # 阶段 1 完成后改为 1
```~~

---

## 六、风险与应对

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| Redis 宕机 | 任务状态丢失 | 低 | **兜底 1**：本地内存缓存 + Redis 恢复后自动同步 |
| Redis 宕机超过 5 分钟 | 内存缓存过期丢失 | 极低 | **兜底 2**：test_run 任务持久化到 MySQL TestRun 表 |
| 后端服务重启 | 运行中任务中断 | 中 | **兜底 4**：启动时扫描恢复任务 |
| 网络断开 | 前端无法获取状态 | 中 | **兜底 3**：前端 localStorage 缓存 + 离线提示 |
| SSE 连接不稳定 | 进度更新延迟 | 中 | Polling 降级兜底（2 秒间隔） |
| 多实例部署时钟不同步 | 时间戳不准确 | 低 | 使用 NTP 同步 |
| 任务卡住（死循环） | 资源泄漏 | 低 | **看门狗机制**：2 小时超时自动标记失败 |
| Redis 内存溢出 | 新任务无法创建 | 极低 | **强制 TTL**：所有 Key 必须设置过期时间 + 内存监控告警 |
| Lua 脚本加载失败 | 状态更新回退到内存 | 极低 | 启动时预加载脚本，失败则服务启动失败 |

---

## 七、监控与告警

### 7.1 Prometheus 指标

```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge

# 任务状态转换计数
task_status_transitions = Counter(
    'task_status_transitions_total',
    'Task status transitions',
    ['task_type', 'from_status', 'to_status']
)

# 任务执行延迟
task_execution_duration = Histogram(
    'task_execution_duration_seconds',
    'Task execution duration',
    ['task_type'],
    buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600, 7200]
)

# 活跃任务数量
active_tasks_count = Gauge(
    'active_tasks_count',
    'Number of active tasks',
    ['task_type', 'status']
)

# Redis 操作延迟
redis_operation_duration = Histogram(
    'redis_operation_duration_seconds',
    'Redis operation duration',
    ['operation'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

# 兜底触发次数
fallback_activations = Counter(
    'task_state_fallback_activations_total',
    'Task state fallback activations',
    ['fallback_type']  # 'memory_cache', 'mysql', 'local_storage'
)

# 新增指标

# 兜底切换到内存缓存的次数
task_fallback_to_memory_total = Counter(
    'task_fallback_to_memory_total',
    'Number of times task state fell back to memory cache',
    ['task_type']
)

# 服务启动时恢复的任务数
task_recovery_on_startup_total = Counter(
    'task_recovery_on_startup_total',
    'Number of tasks recovered on service startup'
)

# 看门狗检测到的卡住任务数
task_stuck_detected_total = Counter(
    'task_stuck_detected_total',
    'Number of stuck tasks detected by watchdog',
    ['task_type']
)

# Lua 脚本更新失败次数（终态保护拒绝）
task_update_rejected_total = Counter(
    'task_update_rejected_total',
    'Number of task updates rejected (terminal state protection)',
    ['task_type']
)

# SSE 重连次数
sse_reconnect_total = Counter(
    'sse_reconnect_total',
    'Number of SSE reconnection attempts',
    ['task_type']
)

# 一致性校验发现的不一致任务数
task_state_inconsistency_total = Counter(
    'task_state_inconsistency_total',
    'Number of inconsistent task states found during verification'
)
```

### 7.2 告警规则

```yaml
# prometheus/alerts.yml
groups:
  - name: task_state_alerts
    rules:
      # Redis 不可用
      - alert: RedisDown
        expr: redis_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Redis 实例宕机"
          description: "任务状态存储不可用，已降级到内存缓存"
      
      # 活跃任务数量异常
      - alert: TooManyActiveTasks
        expr: active_tasks_count > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "活跃任务数量超过阈值"
          description: "当前活跃任务数：{{ $value }}，可能存在任务堆积"
      
      # 任务执行超时
      - alert: TaskExecutionTimeout
        expr: task_execution_duration_seconds_bucket{le="7200"} > 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "任务执行超过 2 小时"
          description: "任务类型：{{ $labels.task_type }}，可能卡住"
      
      # 兜底频繁触发
      - alert: FallbackFrequentActivation
        expr: rate(fallback_activations_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "兜底机制频繁触发"
          description: "兜底类型：{{ $labels.fallback_type }}，5 分钟内触发 {{ $value }} 次"
      
      # Redis 内存使用过高
      - alert: RedisMemoryHigh
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Redis 内存使用超过 80%"
          description: "当前使用：{{ $value | humanize }}%"
```

### 7.3 日志规范

```python
# 任务状态变更日志
logger.info(
    f"Task {task_id} status changed: {old_status} → {new_status}",
    extra={
        "task_id": task_id,
        "task_type": task_type,
        "from_status": old_status,
        "to_status": new_status,
        "progress": progress,
        "duration": elapsed_time,
    }
)

# 兜底触发日志
logger.warning(
    f"Redis unavailable, fallback to memory cache for task {task_id}",
    extra={
        "task_id": task_id,
        "fallback_type": "memory_cache",
        "reason": str(error),
    }
)

# 任务恢复日志
logger.info(
    f"Recovered {recovered_count} interrupted tasks on startup",
    extra={
        "recovered_count": recovered_count,
        "task_ids": recovered_task_ids,
    }
)
```

---

## 八、验收标准

### 8.1 功能验收

| 测试场景 | 预期结果 | 验证方法 |
|----------|----------|----------|
| 上传文档后等待完成 | 3 秒内显示"上传成功"，文档列表刷新 | 手动测试 + 日志 |
| 上传过程中刷新页面 | 任务状态正确恢复，进度条继续更新 | 手动测试 |
| 取消上传任务 | 状态立即变为"已取消"，3 秒后移除 | 手动测试 |
| 上传失败 | 显示错误信息，保留 1 小时 | 注入异常测试 |
| 并发上传 2 个文档 | 两个任务状态独立更新，不互相覆盖 | 并发测试 |
| 后端重启后查询任务 | 终态任务可查询，运行中任务显示"运行中" | 重启测试 |
| Redis 宕机后任务创建 | 降级到内存缓存，状态正常更新 | 停止 Redis 测试 |
| Redis 恢复后数据同步 | 内存缓存数据自动同步到 Redis | 重启 Redis 测试 |
| 任务运行超过 2 小时 | 自动标记为失败，释放资源 | 模拟超时任务 |
| 网络断开后恢复 | 前端自动从本地状态切换到服务器状态 | 断网测试 |
| 终态保护：已完成任务尝试更新为 running | 更新被拒绝，状态保持 completed | 单元测试 |
| Redis Key 全部带 TTL | 无任何无过期时间的 Key | `redis-cli --scan --pattern "task:*" | xargs redis-cli ttl` |
| 旧代码完全删除 | 无旧服务引用 | 代码搜索 `task_status_service` / `task_state_manager` |

### 8.2 性能验收

| 指标 | 目标值 | 测量方法 |
|------|--------|----------|
| 状态更新延迟 | < 100ms（P99） | Prometheus 指标 |
| SSE 推送延迟 | < 200ms（P99） | 前端时间戳对比 |
| Redis 内存占用 | < 10MB（1000 个活跃任务） | `redis-cli INFO memory` |
| 前端轮询间隔 | 2000ms（默认） | 网络请求监控 |
| 兜底切换延迟 | < 1 秒 | 日志时间戳对比 |
| Lua 脚本执行延迟 | < 5ms（P99） | Redis MONITOR 命令 |

### 8.3 代码质量验收

| 检查项 | 标准 | 工具 |
|--------|------|------|
| 类型检查 | 0 错误 | `npm run typecheck` |
| 代码规范 | 0 警告 | `npm run lint` |
| 测试覆盖率 | > 80%（新代码） | `pytest --cov` |
| 类长度 | < 500 行 | 人工检查 |
| 无重复代码 | 0 重复 | `pylint --duplicates` |

---

## 九、附录

### 10.1 参考方案

- **Celery**: https://docs.celeryq.dev/en/stable/userguide/states.html
- **Bull Queue**: https://github.com/OptimalBits/bull#job-states
- **Airflow**: https://airflow.apache.org/docs/apache-airflow/stable/concepts/states.html

### 10.2 相关文件

| 文件 | 说明 | 状态 |
|------|------|------|
| `backend/src/schemas/task.py` | 统一任务状态模型（TaskState、TaskStatus 枚举、SSE 事件模型） | 新建（阶段 1） |
| `backend/src/service/task_status_service.py` | 旧任务状态服务（Redis String + GET-merge-SET） | **阶段 2 删除** |
| `backend/src/service/document_ingestion/task_state_manager.py` | 本地文件状态管理（JSON 文件） | **阶段 2 删除** |
| `backend/src/service/task_state_service.py` | 新统一任务状态服务（Redis Hash + Lua 脚本 + 强制 TTL + 活跃任务索引） | 新建（阶段 1） |
| `backend/src/service/task_sse_publisher.py` | 统一任务 SSE 发布器 | 新建（阶段 1） |
| `backend/src/service/test_run_task_adapter.py` | test_run 类型的 Redis + MySQL 双写适配器 | 新建（阶段 4） |
| `backend/src/controller/task_controller.py` | 统一任务 API 控制器（承载所有任务类型的 CRUD + SSE + 取消） | 新建（阶段 1） |
| `backend/src/controller/rag_controller.py` | 文档上传控制器（直接替换为新服务） | 修改（阶段 2） |
| `backend/src/core/async_task.py` | 异步任务管理器（删除旧方法，接入新 SSE 发布器 + 取消信号） | 修改（阶段 3） |
| `backend/src/service/export_service.py` | PDF 导出服务（删除旧方法，接入新 SSE 发布器） | 修改（阶段 3） |
| `backend/src/api/sse.py` | SSE 基础设施（删除专用方法，保留通用方法） | 修改（阶段 4） |
| `backend/src/schemas/events.py` | SSE 事件模型（补充统一事件格式） | 修改（阶段 1） |
| `backend/src/core/di_container.py` | 依赖注入容器（注册 TaskStateService、TaskSsePublisher） | 修改（阶段 1） |
| `frontend/src/features/documents/hooks/useDocumentManagement.ts` | 前端任务管理 Hook（直接替换） | 修改（阶段 2） |
| `frontend/src/hooks/useTaskProgress.ts` | 统一任务进度 Hook | 新建（阶段 2） |
| `frontend/src/components/progress/` | 进度组件（复用） | 复用 |
| `scripts/cleanup_old_redis_keys.py` | 旧 Redis Key 清理脚本 | 新建（阶段 5） |

### 10.3 依赖注入注册

`TaskStateService` 和 `TaskSsePublisher` 通过 Injector 容器注册：

```python
# backend/src/core/di_container.py

from src.service.task_state_service import TaskStateService
from src.service.task_sse_publisher import TaskSsePublisher

class TaskModule(Module):
    """任务状态管理模块"""
    
    @provider
    def provide_task_state_service(self, redis_client: RedisClient) -> TaskStateService:
        return TaskStateService(
            redis_client=redis_client,
            multi_instance=settings.MULTI_INSTANCE_DEPLOYMENT,
        )
    
    @provider
    def provide_task_sse_publisher(self) -> TaskSsePublisher:
        return TaskSsePublisher()

# 注册到主容器
injector = Injector([
    # ... 其他模块
    TaskModule(),
])
```

### 10.4 统一任务 API 控制器

新建 `backend/src/controller/task_controller.py` 承载所有任务类型的统一 API：

```python
# backend/src/controller/task_controller.py

from fastapi import APIRouter, Depends
from src.service.task_state_service import TaskStateService
from src.schemas.task import TaskState, TaskStatus

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

@router.post("/{task_type}")
async def create_task(
    task_type: str,
    request: CreateTaskRequest,
    service: TaskStateService = Depends(),
):
    """创建任务"""
    task_id = str(uuid.uuid4())
    state = TaskState(
        task_id=task_id,
        task_type=task_type,
        status=TaskStatus.PENDING,
        created_at=time.time(),
    )
    await service.create(state)
    return APIResponse.success({"task_id": task_id, "status": "pending"})

@router.get("/{task_type}/{task_id}")
async def get_task_status(
    task_type: str,
    task_id: str,
    service: TaskStateService = Depends(),
):
    """查询任务状态"""
    state = await service.get(task_id, task_type)
    if not state:
        raise AppException("任务不存在", code=404)
    return APIResponse.success(state.model_dump())

@router.get("/{task_type}/{task_id}/stream")
async def stream_task_events(
    task_type: str,
    task_id: str,
):
    """SSE 监听"""
    channel = f"{task_type}:{task_id}"
    return sse_response(channel)

@router.post("/{task_type}/{task_id}/cancel")
async def cancel_task(
    task_type: str,
    task_id: str,
    service: TaskStateService = Depends(),
):
    """取消任务"""
    success = await service.cancel(task_id, task_type)
    if not success:
        raise AppException("任务无法取消（可能已完成或不存在）", code=400)
    return APIResponse.success({"status": "cancelled"})

@router.delete("/{task_type}/{task_id}")
async def delete_task(
    task_type: str,
    task_id: str,
    service: TaskStateService = Depends(),
):
    """删除任务"""
    await service.delete(task_id, task_type)
    return APIResponse.success()
```

### 10.5 `retrying` 状态说明

状态机包含 `retrying` 状态，但为可选状态，当前阶段不实现。

**预留设计**（未来需要时启用）：

```
FAILED ──→ RETRYING ──→ RUNNING ──→ ...
```

**触发条件**：
- 任务失败后，用户手动点击"重试"
- 或系统配置了自动重试策略（如网络超时自动重试 3 次）

**退出条件**：
- 重试成功 → COMPLETED
- 重试失败 → FAILED（累计重试次数 +1）
- 用户取消 → CANCELLED

**当前实现**：
- `TaskStatus` 枚举包含 `RETRYING` 值，但业务代码暂不使用
- Lua 脚本的终态保护逻辑不将 `retrying` 视为终态
- 前端不显示"重试"按钮（预留 UI 组件）

### 10.6 术语表

| 术语 | 含义 |
|------|------|
| 终态 | 不可逆的最终状态（completed/failed/cancelled） |
| 活跃任务 | 非终态任务（pending/running/retrying） |
| 原子操作 | 不可分割的操作，要么全部完成，要么全部不执行 |
| 竞态条件 | 多个操作并发执行时，结果依赖于执行顺序 |
| SSE | Server-Sent Events，服务器向客户端推送事件 |
| Polling | 轮询，客户端定期向服务器请求状态 |
