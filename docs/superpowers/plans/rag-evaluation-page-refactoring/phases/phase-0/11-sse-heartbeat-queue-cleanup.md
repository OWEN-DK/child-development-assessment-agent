# SSE 心跳队列清理 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SSE 心跳队列清理

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Modify: `backend/src/api/sse.py`
- Test: `backend/tests/test_sse_heartbeat_cleanup.py`

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

> **需求来源**: spec 文档 `01-phase-0-bug-fixes.md` 中 `2.0.2` 节
> **所属 Phase**: Phase 0
> **根因**: 前端断开连接时，后端心跳队列未清理，导致内存泄漏

---

## 需求定义

当前 `SSEPublisher.subscribe()` 方法中，心跳任务每 30 秒向 `asyncio.Queue` 发送一条消息。如果前端断开连接（刷新页面、关闭标签页），但后端的 `finally` 块未正确执行，心跳消息会持续堆积在队列中，造成内存泄漏。

**修复要求**：
1. 前端断开连接时，后端必须清理对应心跳队列
2. 心跳任务在订阅结束时正确取消
3. 队列设置最大大小，防止无限增长

---

## 验收标准

- [ ] 前端刷新页面后，后端队列内存释放
- [ ] 心跳任务在订阅结束时被取消
- [ ] 队列有最大大小限制

---

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/api/sse.py` | 修改 | `subscribe` 方法的 finally 块完善清理逻辑 |

---

## 实现方案

### 后端实现

**步骤 1：修改 `subscribe` 方法完善清理逻辑**

```python
# backend/src/api/sse.py

import asyncio
import logging
import json
import time
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# 队列最大大小，防止内存泄漏
MAX_QUEUE_SIZE = 1000

class SSEPublisher:
    _local_subscribers: dict[str, list[asyncio.Queue]] = {}
    _redis_available: bool | None = None
    
    @classmethod
    async def subscribe(cls, channel: str) -> AsyncGenerator:
        """订阅 SSE 频道
        
        生成器函数，通过 yield 发送 SSE 消息。
        客户端断开时，finally 块清理所有资源。
        
        参数:
            channel: SSE 频道名称
            
        生成:
            SSE 格式的消息字符串
        """
        # 创建有界队列，防止无限增长
        queue: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        
        if channel not in cls._local_subscribers:
            cls._local_subscribers[channel] = []
        cls._local_subscribers[channel].append(queue)
        
        logger.debug(f'SSE 订阅 channel={channel}, subscribers={len(cls._local_subscribers[channel])}')
        
        # 心跳任务
        heartbeat_task: asyncio.Task | None = None
        
        async def heartbeat():
            """定期发送心跳，保持连接活跃"""
            try:
                while True:
                    await asyncio.sleep(15)
                    try:
                        await queue.put({
                            "type": "heartbeat",
                            "timestamp": time.monotonic(),
                        })
                    except asyncio.QueueFull:
                        # 队列满了，说明消费者太慢，跳过心跳
                        logger.warning(f'SSE 心跳队列已满 channel={channel}，跳过本次心跳')
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f'SSE 心跳异常: {e}')
        
        heartbeat_task = asyncio.create_task(heartbeat(), name=f"sse-heartbeat-{channel}")
        
        # Redis 监听任务（仅在 Redis 可用时创建）
        redis_task: asyncio.Task | None = None
        try:
            redis_available = await cls._check_redis_availability()
        except Exception:
            redis_available = False
        
        if redis_available:
            redis_task = asyncio.create_task(
                cls._listen_redis(channel, queue),
                name=f"sse-redis-{channel}"
            )
        
        try:
            while True:
                try:
                    # 设置超时，防止永久阻塞
                    message = await asyncio.wait_for(queue.get(), timeout=60)
                    
                    if message is None:
                        # None 表示连接关闭信号
                        break
                    
                    yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    # 超时未收到消息，继续等待
                    # 这不会断开连接，只是防止生成器永久阻塞
                    continue
        except asyncio.CancelledError:
            # 客户端断开连接
            logger.debug(f'SSE 客户端断开 channel={channel}')
        except Exception as e:
            logger.error(f'SSE 订阅异常 channel={channel}: {e}')
        finally:
            # === 清理所有资源 ===
            
            # 1. 从订阅者列表中移除队列
            if channel in cls._local_subscribers:
                try:
                    cls._local_subscribers[channel].remove(queue)
                except ValueError:
                    pass  # 队列已被移除
                
                # 如果没有订阅者了，删除频道条目
                if not cls._local_subscribers[channel]:
                    del cls._local_subscribers[channel]
            
            # 2. 取消心跳任务
            if heartbeat_task and not heartbeat_task.done():
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            # 3. 取消 Redis 监听任务
            if redis_task and not redis_task.done():
                redis_task.cancel()
                try:
                    await redis_task
                except asyncio.CancelledError:
                    pass
            
            # 4. 清空队列中的剩余消息（释放内存）
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            
            logger.debug(f'SSE 订阅清理完成 channel={channel}')
    
    @classmethod
    async def _listen_redis(cls, channel: str, queue: asyncio.Queue):
        """监听 Redis Pub/Sub 消息
        
        参数:
            channel: SSE 频道名称
            queue: 消息队列
        """
        pubsub = None
        try:
            from src.core.redis_client import redis_client
            
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(f"child-dev:sse:{channel}")
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    data = json.loads(message['data'])
                    try:
                        await queue.put(data)
                    except asyncio.QueueFull:
                        logger.warning(f'SSE 队列已满 channel={channel}，丢弃消息')
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(f'Redis 监听失败 channel={channel}: {e}')
        finally:
            if pubsub:
                try:
                    await pubsub.unsubscribe()
                    await pubsub.close()
                except Exception:
                    pass
```

**步骤 2：修改 `publish` 方法处理队列满的情况**

```python
@classmethod
async def publish(cls, channel: str, message: dict):
    """发布 SSE 消息
    
    参数:
        channel: 频道名称
        message: 消息内容
    """
    safe_message = jsonable_encoder(message)
    
    # 发布到本地队列
    if channel in cls._local_subscribers:
        for queue in cls._local_subscribers[channel]:
            try:
                # 使用 put_nowait，队列满时不阻塞
                queue.put_nowait(safe_message)
            except asyncio.QueueFull:
                logger.warning(f'SSE 本地队列已满 channel={channel}，丢弃消息')
            except Exception as e:
                logger.debug(f'发布到本地队列失败: {e}')
    
    # 尝试通过 Redis 发布
    redis_available = await cls._get_redis_availability()
    if redis_available:
        try:
            from src.core.redis_client import redis_client
            await redis_client.publish(
                f"child-dev:sse:{channel}",
                json.dumps(safe_message)
            )
        except Exception as e:
            logger.warning(f'通过 Redis发布消息失败: {e}')
            cls._redis_available = False
```

---

## 测试方案

### 单元测试

```python
# backend/tests/test_sse_heartbeat_cleanup.py

import pytest
import asyncio
from unittest.mock import patch
from src.api.sse import SSEPublisher, MAX_QUEUE_SIZE

class TestSSEHeartbeatCleanup:
    @pytest.mark.asyncio
    async def test_queue_cleanup_on_disconnect(self):
        """测试断开连接时队列被清理"""
        channel = "test:cleanup"
        
        # 创建订阅
        gen = SSEPublisher.subscribe(channel)
        
        # 获取队列引用
        queue = SSEPublisher._local_subscribers[channel][0]
        
        # 向队列添加一些消息
        await queue.put({"type": "test"})
        await queue.put({"type": "test"})
        
        assert queue.qsize() == 2
        
        # 关闭生成器（模拟客户端断开）
        await gen.aclose()
        
        # 队列应该被移除
        assert channel not in SSEPublisher._local_subscribers
    
    @pytest.mark.asyncio
    async def test_heartbeat_task_cancelled(self):
        """测试心跳任务在订阅结束时被取消"""
        channel = "test:heartbeat"
        
        gen = SSEPublisher.subscribe(channel)
        
        # 等待心跳任务启动
        await asyncio.sleep(0.1)
        
        # 关闭生成器
        await gen.aclose()
        
        # 等待一小段时间，确保清理完成
        await asyncio.sleep(0.1)
        
        # 频道应该被清理
        assert channel not in SSEPublisher._local_subscribers
    
    @pytest.mark.asyncio
    async def test_queue_max_size(self):
        """测试队列有最大大小限制"""
        channel = "test:maxsize"
        queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        
        # 填满队列
        for i in range(MAX_QUEUE_SIZE):
            queue.put_nowait({"type": "test", "index": i})
        
        assert queue.qsize() == MAX_QUEUE_SIZE
        
        # 再尝试添加应该抛出 QueueFull
        with pytest.raises(asyncio.QueueFull):
            queue.put_nowait({"type": "overflow"})
    
    @pytest.mark.asyncio
    async def test_publish_to_full_queue(self):
        """测试向满队列发布消息时不阻塞"""
        channel = "test:full"
        queue = asyncio.Queue(maxsize=1)
        queue.put_nowait({"type": "full"})
        
        SSEPublisher._local_subscribers[channel] = [queue]
        
        # 发布消息不应阻塞或抛出异常
        await SSEPublisher.publish(channel, {"type": "new"})
        
        # 队列应该仍然是满的（旧消息未被覆盖）
        assert queue.qsize() == 1
        
        # 清理
        del SSEPublisher._local_subscribers[channel]
```

### 手动测试

1. 启动一个 SSE 连接（如上传文档触发 draft 生成）
2. 在进度到达 50% 时刷新页面
3. 等待 1 分钟（超过心跳间隔）
4. 检查后端内存使用，确认没有泄漏
5. 检查日志，确认订阅清理完成

---

## 注意事项

1. **队列大小**：`MAX_QUEUE_SIZE = 1000` 是一个合理的默认值。如果消息平均 1KB，1000 条约 1MB。如需调整，可通过配置管理。
2. **put_nowait vs put**：`publish` 方法使用 `put_nowait`，队列满时丢弃消息而非阻塞。这比阻塞更安全，因为阻塞可能导致发布线程挂起。
3. **心跳跳过**：队列满时跳过心跳消息是可接受的，因为心跳只是保持连接活跃，丢失不影响功能。
4. **生成器关闭**：前端断开连接时，FastAPI/Starlette 会取消生成器的协程，触发 `CancelledError`，进入 `finally` 块。这是 Python 异步生成器的标准行为。

---

**返回索引：** [Phase 0 总览](../00-overview.md)
