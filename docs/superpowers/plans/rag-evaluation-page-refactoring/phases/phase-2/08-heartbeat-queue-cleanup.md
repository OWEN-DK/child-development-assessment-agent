# 08 - 心跳队列清理 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 08 - 心跳队列清理

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

## 问题描述

现有 `SSEPublisher.subscribe()` 方法中，每个客户端连接会创建一个 `asyncio.Queue` 和一个心跳任务。如果客户端异常断开（如关闭浏览器标签页），队列和心跳任务可能未被正确清理，导致内存泄漏。

## 根因分析

```
客户端连接 → 创建 Queue + heartbeat_task
     ↓
客户端断开 → finally 块执行
     ↓
问题：queue.put(None) 可能阻塞（队列已满）
     → finally 块无法完成
     → Queue 和 heartbeat_task 残留
```

## 修复方案

### 1. 使用 `put_nowait` 替代 `put`

```python
finally:
    # 使用 put_nowait 避免阻塞
    try:
        queue.put_nowait(None)  # 非阻塞发送停止信号
    except asyncio.QueueFull:
        pass  # 队列已满说明消费者还在处理，无需担心
    except Exception:
        pass

    if channel in cls._local_subscribers:
        try:
            cls._local_subscribers[channel].remove(queue)
        except ValueError:
            pass  # 队列已被移除
        if not cls._local_subscribers[channel]:
            del cls._local_subscribers[channel]

    # 取消后台任务并等待完成
    redis_task.cancel()
    heartbeat_task.cancel()
    for task in (redis_task, heartbeat_task):
        try:
            await task
        except asyncio.CancelledError:
            pass
```

### 2. 心跳任务使用 `wait_for` 替代 `sleep`

现有实现使用 `asyncio.sleep(30)`，无法快速响应取消：

```python
# 修改前
async def heartbeat():
    while True:
        await asyncio.sleep(30)
        await queue.put({...})

# 修改后
async def heartbeat():
    while True:
        try:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            queue.put_nowait({
                "type": "heartbeat",
                "channel": channel,
                "timestamp": asyncio.get_event_loop().time()
            })
        except asyncio.CancelledError:
            break  # 快速退出
```

### 3. 队列大小限制

防止队列无限增长：

```python
queue = asyncio.Queue(maxsize=100)  # 限制最多100条未消费消息
```

当队列满时，新消息会被丢弃（`put_nowait` 抛 `QueueFull`），这是可接受的——客户端消费慢时，丢弃旧事件比内存泄漏更好。

### 4. 主动清理接口

新增管理接口，用于诊断和手动清理：

```python
@classmethod
def get_subscriber_stats(cls) -> dict:
    """获取订阅者统计信息（用于诊断）"""
    stats = {}
    for channel, queues in cls._local_subscribers.items():
        stats[channel] = {
            "subscriber_count": len(queues),
            "queue_sizes": [q.qsize() for q in queues]
        }
    return stats
```

## 验收标准

- [ ] 客户端断开后，对应 Queue 在 1 秒内被移除
- [ ] 心跳任务在取消后 100ms 内退出
- [ ] 队列大小限制为 100，不会无限增长
- [ ] 24 小时运行后，`_local_subscribers` 中无僵尸队列
- [ ] `get_subscriber_stats()` 返回正确的统计信息
