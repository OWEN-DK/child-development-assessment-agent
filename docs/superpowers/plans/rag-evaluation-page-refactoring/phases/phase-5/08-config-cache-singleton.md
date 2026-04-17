# 08 - ConfigCache 单例 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 08 - ConfigCache 单例

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
> **需求点**: 8
> **需求来源**: spec `04-frontend-pages.md` §4.2

## 目标

实现配置缓存单例，订阅 Redis 事件后刷新。

## 方案设计

### 缓存结构

```python
ConfigCache._cache = {
    "config_version_id": {
        "config_snapshot": { ... },    # 完整配置快照
        "loaded_at": datetime          # 加载时间
    }
}
```

### 缓存策略

| 策略 | 说明 |
|------|------|
| **加载时机** | 应用启动时加载最新配置版本 |
| **失效策略** | 收到 Redis config_changed 事件后刷新 |
| **TTL** | 旧版本条目在 5 分钟 TTL 后自动清理 |
| **并发安全** | 使用 asyncio.Lock 防止并发刷新 |

### 完整实现

```python
# backend/src/core/config/cache.py

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import ConfigVersion
from src.database import get_async_session

class ConfigCache:
    """配置缓存单例，支持 Redis Pub/Sub 热更新"""
    
    _instance: 'ConfigCache | None' = None
    _initialized: bool = False
    
    def __init__(self):
        self._cache: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._redis: redis.Redis | None = None
        self._cleanup_task: asyncio.Task | None = None
    
    @classmethod
    async def get_instance(cls) -> 'ConfigCache':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def initialize(self, redis_client: redis.Redis):
        """初始化缓存并订阅配置变更事件"""
        if self._initialized:
            return
        
        self._redis = redis_client
        
        # 初始加载配置
        await self.reload()
        
        # 启动后台清理任务
        self._cleanup_task = asyncio.create_task(self._cleanup_expired())
        
        # 订阅配置变更事件
        pubsub = self._redis.pubsub()
        await pubsub.subscribe("config_changed")
        asyncio.create_task(self._listen_config_changes(pubsub))
        
        self._initialized = True
    
    async def reload(self):
        """从数据库重新加载最新配置"""
        async with self._lock:
            async with get_async_session() as session:
                result = await session.execute(
                    select(ConfigVersion)
                    .order_by(ConfigVersion.created_at.desc())
                    .limit(1)
                )
                latest = result.scalar_one_or_none()
                if latest:
                    version_id = str(latest.id)
                    self._cache[version_id] = {
                        "config_snapshot": latest.config_snapshot,
                        "loaded_at": datetime.utcnow(),
                        "expires_at": datetime.utcnow() + timedelta(minutes=5)
                    }
    
    async def _listen_config_changes(self, pubsub: redis.client.PubSub):
        """监听配置变更事件"""
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    event = json.loads(message["data"])
                    await self.reload()
        except asyncio.CancelledError:
            pass
    
    async def _cleanup_expired(self):
        """定期清理过期缓存条目"""
        while True:
            await asyncio.sleep(60)  # 每分钟清理一次
            now = datetime.utcnow()
            expired_keys = [
                k for k, v in self._cache.items()
                if v.get("expires_at") and now > v["expires_at"]
            ]
            for key in expired_keys:
                del self._cache[key]
    
    def get_config(self, config_version_id: str) -> dict[str, Any] | None:
        """获取配置快照"""
        entry = self._cache.get(config_version_id)
        if entry:
            return entry.get("config_snapshot")
        return None
    
    def get_latest_config(self) -> dict[str, Any] | None:
        """获取最新配置快照"""
        if not self._cache:
            return None
        # 返回最后加载的配置
        latest_version_id = list(self._cache.keys())[-1]
        return self.get_config(latest_version_id)
```

### 使用方式

```python
# 在 TestRun 创建时获取配置
cache = await ConfigCache.get_instance()
config = cache.get_config(run.config_version_id)
if config is None:
    # 缓存未命中，从数据库查询
    config = await load_config_from_db(run.config_version_id)
```

### 验收标准

- [ ] 单例模式正确实现
- [ ] 应用启动时加载最新配置
- [ ] 收到 Redis 事件后刷新缓存
- [ ] 旧版本条目 5 分钟后自动清理
- [ ] 并发刷新安全（使用 asyncio.Lock）
- [ ] 缓存未命中时回退到数据库查询
