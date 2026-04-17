# 07 - 配置热重载 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 07 - 配置热重载

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Test: `tests/test_placeholder.py`

- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

> **Phase**: 5
> **需求点**: 7
> **需求来源**: spec `04-frontend-pages.md` §4.2

## 目标

实现 Redis Pub/Sub 发布 config_changed 事件，多实例同步配置。

## 方案设计

### 热重载机制

| 机制 | 说明 | 实现方式 |
|------|------|---------|
| **生效时机** | 配置保存后立即生效，下次 TestRun 使用新配置 | 当前正在运行的 TestRun 继续使用保存前的配置快照 |
| **多实例同步** | 多实例部署时，所有实例必须同步更新 | 通过 Redis Pub/Sub 发布 `config_changed` 事件 |
| **配置缓存** | 配置数据缓存在内存，避免每次查询数据库 | 使用 `ConfigCache` 单例 |
| **缓存失效策略** | 配置变更后失效旧版本缓存，加载新版本 | `reload()` 查询最新 ConfigVersion，替换缓存字典 |
| **冲突处理** | 运行中的 TestRun 不受配置变更影响 | TestRun 创建时快照 `config_version_id` |
| **回滚生效** | 配置回滚同样触发热重载 | 回滚操作创建新的 ConfigChangeSet，发布事件 |

### Redis Pub/Sub 事件格式

```json
{
  "event": "config_changed",
  "change_set_id": "uuid",
  "timestamp": "2026-04-16T10:30:00Z",
  "changed_by": "user_id"
}
```

### 实例端处理逻辑

```python
# backend/src/core/config/cache.py

import asyncio
import json
import redis.asyncio as redis
from datetime import datetime

class ConfigCache:
    """配置缓存单例"""
    _instance = None
    _cache: dict[str, dict] = {}
    _loaded_at: datetime | None = None
    
    @classmethod
    async def initialize(cls, redis_client: redis.Redis):
        """初始化并订阅配置变更事件"""
        cls._redis = redis_client
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("config_changed")
        
        # 启动后台任务监听事件
        asyncio.create_task(cls._listen_config_changes(pubsub))
        
        # 初始加载配置
        await cls.reload()
    
    @classmethod
    async def _listen_config_changes(cls, pubsub: redis.client.PubSub):
        """监听配置变更事件"""
        async for message in pubsub.listen():
            if message["type"] == "message":
                event = json.loads(message["data"])
                await cls.reload()
    
    @classmethod
    async def reload(cls):
        """从数据库重新加载最新配置"""
        from sqlalchemy import select
        from src.models import ConfigVersion
        
        async with get_async_session() as session:
            result = await session.execute(
                select(ConfigVersion)
                .order_by(ConfigVersion.created_at.desc())
                .limit(1)
            )
            latest = result.scalar_one_or_none()
            if latest:
                # 清理超过 5 分钟的旧版本条目
                cutoff = datetime.utcnow() - timedelta(minutes=5)
                stale_keys = [k for k, v in cls._cache.items() 
                             if v.get("loaded_at") and v["loaded_at"] < cutoff]
                for k in stale_keys:
                    del cls._cache[k]
                
                cls._cache[str(latest.id)] = {
                    "config_snapshot": latest.config_snapshot,
                    "loaded_at": datetime.utcnow()
                }
                cls._loaded_at = datetime.utcnow()
    
    @classmethod
    def get_config(cls, config_version_id: str) -> dict | None:
        """获取配置快照"""
        entry = cls._cache.get(config_version_id)
        if entry:
            return entry["config_snapshot"]
        return None
```

### 多实例配置生效延迟

- 事务提交后，Redis Pub/Sub 事件几乎瞬时到达（< 10ms）
- 各实例收到事件后刷新本地缓存，刷新耗时 < 50ms
- **可接受延迟**: 配置变更后，所有实例在 **100ms 内** 生效
- **短暂窗口处理**: 在 100ms 窗口内，部分实例可能使用旧配置。由于 TestRun 创建时快照 `config_version_id`，运行中的测试不受影响

### 验收标准

- [ ] Redis Pub/Sub 正确发布 config_changed 事件
- [ ] 实例订阅事件后自动刷新本地缓存
- [ ] 配置变更后 100ms 内所有实例生效
- [ ] 运行中的 TestRun 不受配置变更影响
- [ ] 配置回滚同样触发热重载
