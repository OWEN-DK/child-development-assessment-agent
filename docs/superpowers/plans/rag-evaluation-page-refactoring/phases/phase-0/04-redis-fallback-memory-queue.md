# Redis 降级到内存队列 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redis 降级到内存队列

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Modify: `backend/src/api/sse.py`
- Modify: `backend/src/core/redis_client.py`
- Test: `backend/tests/test_sse_fallback.py`

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

> **需求来源**: spec 文档 `01-phase-0-bug-fixes.md` 中 `2.0.1` 节
> **所属 Phase**: Phase 0
> **根因**: SSE 依赖 Redis Pub/Sub，Redis 未启动时消息丢失

---

## 需求定义

当前 `SSEPublisher.publish()` 方法通过 Redis Pub/Sub 发送消息。如果 Redis 未启动或连接失败，消息将丢失，导致前端无法接收到 SSE 事件。

**修复要求**：
1. 系统启动时检测 Redis 可用性
2. Redis 不可用时，SSE 降级到纯内存队列模式（仅本地队列，无跨实例消息传递）
3. 降级模式不影响 SSE 功能，仅影响多实例部署时的消息路由

---

## 验收标准

- [ ] Redis 未启动时，SSE 推送仍能通过内存队列正常工作
- [ ] Redis 恢复后，自动切换回 Redis Pub/Sub 模式
- [ ] 降级模式在日志中有明确记录

---

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/api/sse.py` | 修改 | `SSEPublisher` 增加 Redis 可用性检测和降级逻辑 |
| `backend/src/core/redis_client.py` | 修改 | 新增 `is_healthy()` 方法 |

---

## 实现方案

### 后端实现

**步骤 1：在 `redis_client.py` 中新增健康检查方法**

```python
# backend/src/core/redis_client.py

class RedisClient:
    # ... 现有代码 ...
    
    async def is_healthy(self) -> bool:
        """检查 Redis 连接是否可用
        
        返回:
            True 如果 Redis 可用，False 否则
        """
        try:
            return await self._client.ping()
        except Exception:
            return False
```

**步骤 2：修改 `SSEPublisher` 支持降级**

```python
# backend/src/api/sse.py

import asyncio
import json
import logging
import time
from typing import Optional

from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)

# 队列最大大小，防止内存泄漏（与需求点 11 一致）
MAX_QUEUE_SIZE = 1000

class SSEPublisher:
    _local_subscribers: dict[str, list[asyncio.Queue]] = {}
    _redis_available: Optional[bool] = None  # 缓存 Redis 可用性状态
    
    @classmethod
    async def _check_redis_availability(cls) -> bool:
        """检查 Redis 是否可用
        
        返回:
            True 如果 Redis 可用，False 否则
        """
        try:
            from src.core.redis_client import redis_client
            return await redis_client.is_healthy()
        except Exception:
            return False
    
    @classmethod
    async def _get_redis_availability(cls) -> bool:
        """获取 Redis 可用性状态（带缓存）
        
        每次发布时检查，但失败时不重试，避免阻塞。
        下次发布时会重新检查。
        
        返回:
            True 如果 Redis 可用，False 否则
        """
        cls._redis_available = await cls._check_redis_availability()
        if not cls._redis_available:
            logger.warning('Redis 不可用，SSE 将降级到内存队列模式')
        return cls._redis_available
    
    @classmethod
    async def publish(cls, channel: str, message: dict):
        """发布 SSE 消息
        
        优先通过 Redis Pub/Sub 发布（支持多实例），
        如果 Redis 不可用，仅发布到本地队列（单实例模式）。
        
        参数:
            channel: 频道名称
            message: 消息内容
        """
        safe_message = jsonable_encoder(message)
        
        # 始终发布到本地队列（同实例订阅者）
        if channel in cls._local_subscribers:
            for queue in cls._local_subscribers[channel]:
                try:
                    # 使用 put_nowait，队列满时不阻塞（与需求点 11 一致）
                    queue.put_nowait(safe_message)
                except asyncio.QueueFull:
                    logger.warning(f'SSE 本地队列已满 channel={channel}，丢弃消息')
                except Exception as e:
                    logger.debug(f'发布到本地队列失败: {e}')
        
        # 尝试通过 Redis Pub/Sub 发布（跨实例）
        redis_available = await cls._get_redis_availability()
        if redis_available:
            try:
                from src.core.redis_client import redis_client
                await redis_client.publish(
                    f"child-dev:sse:{channel}",
                    json.dumps(safe_message)
                )
            except Exception as e:
                logger.warning(f'通过 Redis 发布消息失败: {e}，仅使用本地队列')
                cls._redis_available = False  # 标记为不可用，下次重新检查
```

**步骤 3：修改 `subscribe` 方法处理降级模式**

```python
# backend/src/api/sse.py

class SSEPublisher:
    @classmethod
    async def subscribe(cls, channel: str) -> AsyncGenerator:
        """订阅 SSE 频道
        
        在降级模式下，仅接收本地队列消息。
        
        参数:
            channel: 频道名称
            
        生成:
            SSE 格式的消息字符串
        """
        queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        
        if channel not in cls._local_subscribers:
            cls._local_subscribers[channel] = []
        cls._local_subscribers[channel].append(queue)
        
        # 心跳任务（始终运行）
        heartbeat_task = None
        async def heartbeat():
            try:
                while True:
                    await asyncio.sleep(15)
                    await queue.put({"type": "heartbeat", "channel": channel, "timestamp": time.monotonic()})
            except asyncio.CancelledError:
                return
        
        heartbeat_task = asyncio.create_task(heartbeat())
        
        # Redis 监听任务（仅在 Redis 可用时创建）
        redis_task = None
        redis_available = await cls._check_redis_availability()
        if redis_available:
            redis_task = asyncio.create_task(cls._listen_redis(channel, queue))
        
        try:
            while True:
                message = await queue.get()
                if message is None:
                    break
                yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
        finally:
            # 清理
            if channel in cls._local_subscribers:
                try:
                    cls._local_subscribers[channel].remove(queue)
                except ValueError:
                    pass
                if not cls._local_subscribers[channel]:
                    del cls._local_subscribers[channel]
            
            if heartbeat_task:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            if redis_task:
                redis_task.cancel()
                try:
                    await redis_task
                except asyncio.CancelledError:
                    pass
    
    @classmethod
    async def _listen_redis(cls, channel: str, queue: asyncio.Queue):
        """监听 Redis Pub/Sub 消息
        
        参数:
            channel: 频道名称
            queue: 消息队列
        """
        try:
            from src.core.redis_client import redis_client
            
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(f"child-dev:sse:{channel}")
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    data = json.loads(message['data'])
                    await queue.put(data)
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(f'Redis 监听失败: {e}')
            await queue.put(None)  # 通知订阅者连接断开
        finally:
            try:
                await pubsub.unsubscribe()
                await pubsub.close()
            except Exception:
                pass
```

---

## 测试方案

### 单元测试

```python
# backend/tests/test_sse_fallback.py

import pytest
from unittest.mock import AsyncMock, patch
from src.api.sse import SSEPublisher

class TestSSEFallback:
    @pytest.mark.asyncio
    async def test_publish_without_redis(self):
        """测试 Redis 不可用时仅发布到本地队列"""
        channel = "test:channel"
        message = {"type": "progress", "data": "test"}
        
        # 创建本地订阅者
        queue = asyncio.Queue()
        SSEPublisher._local_subscribers[channel] = [queue]
        
        with patch.object(SSEPublisher, '_check_redis_availability', return_value=False):
            await SSEPublisher.publish(channel, message)
        
        # 消息应该在本地队列中
        result = await asyncio.wait_for(queue.get(), timeout=1)
        assert result["type"] == "progress"
    
    @pytest.mark.asyncio
    async def test_publish_with_redis(self):
        """测试 Redis 可用时同时发布到本地和 Redis"""
        channel = "test:channel"
        message = {"type": "progress", "data": "test"}
        
        queue = asyncio.Queue()
        SSEPublisher._local_subscribers[channel] = [queue]
        
        mock_redis_client = AsyncMock()
        mock_redis_client.is_healthy = AsyncMock(return_value=True)
        
        with patch('src.api.sse.redis_client', mock_redis_client):
            with patch.object(SSEPublisher, '_check_redis_availability', return_value=True):
                await SSEPublisher.publish(channel, message)
        
        # 本地队列应该有消息
        result = await asyncio.wait_for(queue.get(), timeout=1)
        assert result["type"] == "progress"
```

### 手动测试

1. 停止 Redis 服务
2. 重启后端，检查日志是否输出降级警告
3. 触发一个 SSE 事件（如上传文档），确认前端仍能接收进度
4. 启动 Redis，触发另一个 SSE 事件，确认恢复正常

---

## 注意事项

1. **降级范围**：降级仅影响 SSE 消息的跨实例路由。单实例部署时降级无影响。
2. **状态缓存**：`_redis_available` 每次发布时重新检查，避免缓存过期。如果检查失败，标记为不可用，下次重新检查。
3. **内存队列大小**：本地队列有大小限制（`MAX_QUEUE_SIZE=1000`）。队列满时丢弃消息并记录警告，防止内存泄漏。
4. **Redis 恢复检测**：当前方案在每次 `publish` 时重新检查 Redis 可用性，Redis 恢复后自动切换回来。

---

**返回索引：** [Phase 0 总览](../00-overview.md)
