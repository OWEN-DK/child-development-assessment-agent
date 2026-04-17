# 03 - SSEPublisher 增强实现 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 03 - SSEPublisher 增强实现

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

## 现状分析

现有 `SSEPublisher` 位于 `backend/src/api/sse.py`，已具备：
- Redis Pub/Sub 发布/订阅机制，支持多实例
- 本地队列优化（同实例直连）
- 30 秒心跳保活（防止反向代理超时）
- `jsonable_encoder` 序列化保护

## 需要增强的内容

1. 心跳间隔从 30 秒调整为 15 秒（匹配前端 45 秒超时阈值）
2. 心跳格式对齐 spec：`{run_id, timestamp(ISO 8601)}`，不含 `channel` 字段
3. 心跳队列需要清理机制（前端断开时释放内存）
4. 新增 `publish_event` 统一发布入口

## 增强方案

### 修改 `backend/src/api/sse.py`

在现有 `SSEPublisher` 类中做以下增强：

```python
import re
from datetime import datetime, timezone

# 1. 心跳间隔改为可配置参数（默认15秒）
HEARTBEAT_INTERVAL = 15  # 秒

# 2. 从频道名中提取run_id的正则（匹配 test_run:{uuid} 格式）
_RUN_ID_PATTERN = re.compile(r"^test_run:(.+)$")

def _extract_run_id(channel: str) -> Optional[str]:
    """从频道名中提取run_id，仅适用于test_run:{run_id}格式"""
    match = _RUN_ID_PATTERN.match(channel)
    return match.group(1) if match else None

# 3. subscribe() 方法中的心跳循环修改为：
async def heartbeat():
    run_id = _extract_run_id(channel)
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        heartbeat_data = {
            "type": "heartbeat",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if run_id:
            heartbeat_data["run_id"] = run_id
        queue.put_nowait(heartbeat_data)

# 4. 新增心跳队列清理方法
@classmethod
async def cleanup_subscriber(cls, channel: str, queue: asyncio.Queue):
    """清理指定订阅者的队列
    当客户端断开连接时调用，防止内存泄漏
    """
    if channel in cls._local_subscribers:
        if queue in cls._local_subscribers[channel]:
            cls._local_subscribers[channel].remove(queue)
            # 发送停止信号，让yield循环退出
            await queue.put(None)
        if not cls._local_subscribers[channel]:
            del cls._local_subscribers[channel]

# 5. 新增统一事件发布入口
@classmethod
async def publish_event(cls, channel: str, event_type: str, data: dict):
    """统一事件发布入口
    Args:
        channel: SSE频道名，如 test_run:{run_id}
        event_type: 事件类型，如 run_started, progress, case_result 等
        data: 事件数据（不含type字段）
    """
    payload = {"type": event_type, **data}
    await cls.publish(channel, payload)
```

**心跳格式说明**：
- spec 定义心跳格式为 `{run_id, timestamp(ISO 8601)}`
- `subscribe()` 是通用方法，不知道 `run_id`，因此通过正则从频道名 `test_run:{run_id}` 中提取
- 非 `test_run:` 频道（如 `exports:{user_id}`）的心跳不包含 `run_id` 字段
- `timestamp` 使用 UTC ISO 8601 格式，非 `time.monotonic()`
- 使用 `put_nowait` 替代 `await queue.put()`，避免阻塞

### 内存泄漏防护

**问题根因**：现有 `subscribe()` 的 `finally` 块只做队列移除，但如果 `queue.put(None)` 在 `finally` 之前没有被消费，队列对象会一直驻留在内存中。

**修复方案**：
1. `finally` 块中先使用 `put_nowait(None)` 发送停止信号，再移除队列引用
2. 心跳任务先取消，再取消 redis 任务

```python
finally:
    # 先发送停止信号，让yield循环退出
    try:
        queue.put_nowait(None)
    except asyncio.QueueFull:
        pass  # 队列已满说明消费者还在处理
    except Exception:
        pass

    # 再移除队列引用
    if channel in cls._local_subscribers:
        try:
            cls._local_subscribers[channel].remove(queue)
        except ValueError:
            pass  # 队列已被移除
        if not cls._local_subscribers[channel]:
            del cls._local_subscribers[channel]

    # 最后取消后台任务
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
```

## 验收标准

- [ ] 心跳间隔为 15 秒
- [ ] 前端断开后，对应队列在 1 秒内被清理
- [ ] 长时间运行（24 小时）无内存增长
- [ ] 多实例部署下，Redis Pub/Sub 消息不丢失
- [ ] 所有发布方法使用 `jsonable_encoder` 处理
