# 08 - 导出任务并发限制 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 08 - 导出任务并发限制

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

> **Phase**: 6
> **需求点**: 8
> **需求来源**: spec `04-frontend-pages.md` §4.10

## 目标

实现导出任务并发限制：最多 2 个并行 PDF 导出任务，超时 60 秒。

## 方案设计

### 并发控制策略

| 策略 | 说明 |
|------|------|
| **最大并行数** | 2 个 PDF 导出任务同时执行 |
| **队列管理** | 超出任务排队等待，FIFO 顺序 |
| **超时控制** | 单个任务超时 60 秒，标记为 failed |
| **任务状态** | pending → processing → completed/failed |

### 实现方式

使用 `asyncio.Semaphore` 控制并发：

```python
# backend/src/service/export_service.py

class ExportService:
    def __init__(self, redis_client, session_factory):
        self._redis = redis_client
        self._session_factory = session_factory
        self._semaphore = asyncio.Semaphore(2)  # 最多 2 个并行
        self._queue = asyncio.Queue()
        self._timeout = 60  # 60 秒超时
    
    async def _process_queue(self):
        """处理导出队列"""
        async with self._semaphore:
            task_id = await self._queue.get()
            try:
                # 使用 wait_for 实现超时控制
                await asyncio.wait_for(
                    self._generate_pdf(task_id),
                    timeout=self._timeout
                )
            except asyncio.TimeoutError:
                await self._update_task_status(
                    task_id,
                    "failed",
                    error="导出超时 (60s)"
                )
            except Exception as e:
                await self._update_task_status(
                    task_id,
                    "failed",
                    error=str(e)
                )
            finally:
                self._queue.task_done()
```

### 任务状态流转

```
pending ──[获取]──→ processing ──[成功]──→ completed
                         │
                         └──[超时/异常]──→ failed
```

### 监控与日志

```python
# 任务队列状态
- 队列长度: len(self._queue)
- 活跃任务数: 2 - self._semaphore._value
- 已完成任务数: 通过 Redis 统计

# 日志示例
logger.info(f"导出任务 {task_id} 开始处理，队列长度: {self._queue.qsize()}")
logger.info(f"导出任务 {task_id} 完成，耗时: {duration:.2f}s")
logger.warning(f"导出任务 {task_id} 超时")
```

### 验收标准

- [ ] 最多 2 个并行 PDF 导出任务
- [ ] 超出任务排队等待
- [ ] 单个任务超时 60 秒
- [ ] 超时任务标记为 failed
- [ ] 队列任务按 FIFO 顺序处理
