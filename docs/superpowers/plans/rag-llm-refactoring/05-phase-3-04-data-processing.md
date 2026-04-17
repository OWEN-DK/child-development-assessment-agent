# Phase 3.4: 数据上报与异步处理

> **前置文档:** [03-instrumentation.md](./05-phase-3-03-instrumentation.md)
> **状态:** ⏳ 完全待实现

## 异步队列设计

采用独立队列异步写入追踪数据，不阻塞主流程。

### 队列架构

```
业务层调用 → TraceWriter → 内存队列 (asyncio.Queue) → 后台消费者 → 批量写入 MySQL
                                    ↓
                              队列满时降级
                                    ↓
                              同步写入 + 告警
```

### 采样策略

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `trace_sample_rate` | Float | 1.0 | 采样率（0.0-1.0） |
| `trace_error_sample_rate` | Float | 1.0 | 错误采样率（错误全量保留） |

**采样逻辑**: `random() < sample_rate or is_error` → 写入

---

## 实施任务

### Task 3.4.1: 实现 TraceWriter 异步队列

**Files:**
- Create: `src/core/tracing/writer.py`
- Test: `tests/unit/tracing/test_trace_writer.py`

- [ ] **Step 1: 编写测试用例**
```python
import pytest
from src.core.tracing.writer import TraceWriter

@pytest.mark.asyncio
async def test_writer_enqueue():
    writer = TraceWriter(max_queue_size=100)
    await writer.start()
    
    await writer.record_span(
        trace_id="test-trace-001",
        span_id="span-001",
        parent_span_id=None,
        name="test_node",
        duration_ms=100,
    )
    
    # 验证数据已入队
    assert writer.queue.qsize() == 1
    
    await writer.stop()

@pytest.mark.asyncio
async def test_writer_sampling():
    import random
    writer = TraceWriter(sample_rate=0.0)  # 0% 采样
    await writer.start()
    
    # 非错误调用不应入队
    await writer.record_span(
        trace_id="test-trace-002",
        span_id="span-002",
        parent_span_id=None,
        name="test_node",
        duration_ms=100,
        is_error=False,
    )
    assert writer.queue.qsize() == 0
    
    await writer.stop()

@pytest.mark.asyncio
async def test_writer_error_sampling():
    writer = TraceWriter(sample_rate=0.0, error_sample_rate=1.0)  # 错误全量保留
    await writer.start()
    
    # 错误调用应入队
    await writer.record_span(
        trace_id="test-trace-003",
        span_id="span-003",
        parent_span_id=None,
        name="test_node",
        duration_ms=100,
        is_error=True,
    )
    assert writer.queue.qsize() == 1
    
    await writer.stop()

@pytest.mark.asyncio
async def test_writer_llm_complete_with_parent_span():
    """验证 record_llm_complete 正确传递 parent_span_id"""
    writer = TraceWriter(sample_rate=1.0)
    await writer.start()
    
    await writer.record_llm_complete(
        trace_id="test-trace-004",
        span_id="span-004",
        parent_span_id="parent-span-001",
        completion_message="test response",
        tokens={"input_tokens": 100, "output_tokens": 50},
        ttft=200,
    )
    
    assert writer.queue.qsize() == 1
    item = writer.queue.get_nowait()
    assert item["parent_span_id"] == "parent-span-001"
    
    await writer.stop()
```

- [ ] **Step 2: 实现 TraceWriter**
```python
# src/core/tracing/writer.py
import asyncio
import logging
import random
import time
from typing import Any
from datetime import datetime
from decimal import Decimal

from src.core.tracing.context import get_current_trace_id, get_current_span_id
from src.models.trace import Trace, TraceStatus
from src.models.llm_call_log import LLMCallLog, CallLevel
from src.database import get_session

logger = logging.getLogger(__name__)

# 模块级单例，确保全局共享同一队列和后台任务
_default_writer: "TraceWriter | None" = None

def get_trace_writer() -> "TraceWriter":
    """获取 TraceWriter 单例实例"""
    global _default_writer
    if _default_writer is None:
        _default_writer = TraceWriter()
    return _default_writer

def reset_trace_writer() -> None:
    """重置 TraceWriter 单例 (仅用于测试)"""
    global _default_writer
    _default_writer = None

class TraceWriter:
    def __init__(
        self,
        max_queue_size: int = 10000,
        sample_rate: float = 1.0,
        error_sample_rate: float = 1.0,
        batch_size: int = 100,
        flush_interval: float = 1.0,
    ):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.sample_rate = sample_rate
        self.error_sample_rate = error_sample_rate
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._task: asyncio.Task | None = None
        self._running = False
    
    async def start(self):
        """启动后台消费者"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._consumer())
    
    async def stop(self):
        """停止后台消费者"""
        self._running = False
        if self._task:
            # 等待队列清空
            while not self.queue.empty():
                await asyncio.sleep(0.1)
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    def _should_sample(self, is_error: bool = False) -> bool:
        """采样决策"""
        if is_error:
            return random.random() < self.error_sample_rate
        return random.random() < self.sample_rate
    
    async def record_trace_start(self, trace_id: str, name: str, metadata: dict, start_time: datetime):
        """记录 Trace 开始 (自动由 trace_context 调用)
        
        注意: Trace 记录不受采样率影响，确保工作流完整性可追踪。
        即使 LLM 调用因采样被丢弃，Trace 记录仍会保留，便于统计调用总量。
        """
        try:
            await self.queue.put({
                "type": "trace_start",
                "trace_id": trace_id,
                "name": name,
                "metadata": metadata,
                "start_time": start_time,
                "timestamp": datetime.utcnow(),
            })
        except asyncio.QueueFull:
            logger.warning("Trace queue full, dropping trace_start data")
            # 降级：同步写入 (Trace 记录不应丢失)
            self._write_sync({"type": "trace_start", "trace_id": trace_id, "name": name, "metadata": metadata, "start_time": start_time, "timestamp": datetime.utcnow()})
    
    async def record_trace_end(self, trace_id: str, end_time: datetime):
        """记录 Trace 结束 (自动由 trace_context 调用)
        
        注意: 与 trace_start 一致，不受采样率影响。
        """
        try:
            await self.queue.put({
                "type": "trace_end",
                "trace_id": trace_id,
                "end_time": end_time,
                "timestamp": datetime.utcnow(),
            })
        except asyncio.QueueFull:
            logger.warning("Trace queue full, dropping trace_end data")
            # 降级：同步写入
            self._write_sync({"type": "trace_end", "trace_id": trace_id, "end_time": end_time, "timestamp": datetime.utcnow()})
    
    async def record_span(self, trace_id: str, span_id: str, parent_span_id: str | None, name: str, duration_ms: int, is_error: bool = False):
        """记录 Span 到队列"""
        if not self._should_sample(is_error):
            return
        
        try:
            await self.queue.put({
                "type": "span",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id,
                "name": name,
                "duration_ms": duration_ms,
                "timestamp": datetime.utcnow(),
            })
        except asyncio.QueueFull:
            logger.warning("Trace queue full, dropping span data")
            self._write_sync({"type": "span", "trace_id": trace_id, "span_id": span_id, "parent_span_id": parent_span_id, "name": name, "duration_ms": duration_ms, "timestamp": datetime.utcnow()})
    
    async def record_llm_start(self, trace_id: str, span_id: str, parent_span_id: str | None, prompt_messages: list, call_parameters: dict):
        """记录 LLM 调用开始 (包含采样判断)"""
        if not self._should_sample(is_error=False):
            return
        
        try:
            await self.queue.put({
                "type": "llm_start",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id,
                "prompt_messages": prompt_messages,
                "call_parameters": call_parameters,
                "timestamp": datetime.utcnow(),
            })
        except asyncio.QueueFull:
            logger.warning("Trace queue full, dropping llm_start data")
            self._write_sync({"type": "llm_start", "trace_id": trace_id, "span_id": span_id, "parent_span_id": parent_span_id, "prompt_messages": prompt_messages, "call_parameters": call_parameters, "timestamp": datetime.utcnow()})
    
    async def record_llm_complete(self, trace_id: str, span_id: str, parent_span_id: str | None, completion_message: str, tokens: dict, ttft: int):
        """记录 LLM 调用完成 (包含采样判断)
        
        Args:
            parent_span_id: 父 Span ID (作为 fallback，若 llm_start 被采样丢弃时使用)
        """
        if not self._should_sample(is_error=False):
            return
        
        try:
            await self.queue.put({
                "type": "llm_complete",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id,
                "completion_message": completion_message,
                "tokens": tokens,
                "ttft": ttft,
                "timestamp": datetime.utcnow(),
            })
        except asyncio.QueueFull:
            logger.warning("Trace queue full, dropping llm_complete data")
            self._write_sync({"type": "llm_complete", "trace_id": trace_id, "span_id": span_id, "parent_span_id": parent_span_id, "completion_message": completion_message, "tokens": tokens, "ttft": ttft, "timestamp": datetime.utcnow()})
    
    async def record_llm_error(self, trace_id: str, span_id: str, error: str):
        """记录 LLM 调用错误 (错误全量保留)"""
        if not self._should_sample(is_error=True):
            return
        
        try:
            await self.queue.put({
                "type": "llm_error",
                "trace_id": trace_id,
                "span_id": span_id,
                "error": error,
                "timestamp": datetime.utcnow(),
            })
        except asyncio.QueueFull:
            logger.warning("Trace queue full, dropping llm_error data")
            self._write_sync({"type": "llm_error", "trace_id": trace_id, "span_id": span_id, "error": error, "timestamp": datetime.utcnow()})
    
    async def update_trace(self, trace_id: str, status: str, total_tokens: int = 0, total_cost: Decimal | None = None):
        """更新 Trace 状态"""
        try:
            await self.queue.put({
                "type": "trace_update",
                "trace_id": trace_id,
                "status": status,
                "total_tokens": total_tokens,
                "total_cost": total_cost,
                "timestamp": datetime.utcnow(),
            })
        except asyncio.QueueFull:
            logger.warning("Trace queue full, dropping trace_update data")
            self._write_sync({"type": "trace_update", "trace_id": trace_id, "status": status, "total_tokens": total_tokens, "total_cost": total_cost, "timestamp": datetime.utcnow()})
    
    async def _consumer(self):
        """后台消费者，批量写入数据库"""
        batch = []
        last_flush = time.time()
        
        while self._running:
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                batch.append(item)
            except asyncio.TimeoutError:
                pass
            
            # 批量写入条件：达到批次大小 或 超过刷新间隔
            if len(batch) >= self.batch_size or (batch and time.time() - last_flush >= self.flush_interval):
                await self._flush_batch(batch)
                batch = []
                last_flush = time.time()
    
    async def _flush_batch(self, batch: list[dict]):
        """批量写入数据库"""
        if not batch:
            return
        
        try:
            with get_session() as session:
                # 合并同一 span_id 的 llm_start/llm_complete/llm_error 事件
                merged_spans = {}
                for item in batch:
                    if item["type"] in ("llm_start", "llm_complete", "llm_error"):
                        span_id = item["span_id"]
                        if span_id not in merged_spans:
                            merged_spans[span_id] = {}
                        merged_spans[span_id].update(item)
                
                # 写入合并后的 LLM 调用记录
                for span_id, merged_item in merged_spans.items():
                    self._write_llm_call(session, merged_item)
                
                # 处理各类事件
                for item in batch:
                    if item["type"] == "trace_start":
                        self._create_trace(session, item)
                    elif item["type"] == "trace_end":
                        self._finalize_trace(session, item)
                    elif item["type"] == "span":
                        self._write_span(session, item)
                    elif item["type"] == "trace_update":
                        self._update_trace(session, item)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to flush trace batch: {e}")
    
    def _create_trace(self, session, item: dict):
        """创建 Trace 记录 (由 trace_start 事件触发)"""
        from src.models.trace import Trace, TraceStatus
        
        # 检查是否已存在
        existing = session.query(Trace).filter(Trace.trace_id == item["trace_id"]).first()
        if existing:
            return
        
        trace = Trace(
            trace_id=item["trace_id"],
            name=item["name"],
            metadata=item.get("metadata"),
            start_time=item["start_time"],
            status=TraceStatus.SUCCESS,  # 默认成功，后续可更新
        )
        session.add(trace)
    
    def _finalize_trace(self, session, item: dict):
        """更新 Trace 结束时间 (由 trace_end 事件触发)
        
        注意: start_time 和 end_time 均为 UTC naive datetime (datetime.utcnow())，
        确保时区一致，可安全计算时间差。
        """
        from src.models.trace import Trace
        
        trace = session.query(Trace).filter(Trace.trace_id == item["trace_id"]).first()
        if trace:
            trace.end_time = item["end_time"]
            if trace.start_time:
                trace.total_duration_ms = int((item["end_time"] - trace.start_time).total_seconds() * 1000)
    
    def _write_span(self, session, item: dict):
        """写入 Span 记录 (节点级)"""
        from src.models.llm_call_log import LLMCallLog, CallLevel
        
        # 检查是否已存在 (避免重复写入)
        existing = session.query(LLMCallLog).filter(LLMCallLog.span_id == item["span_id"]).first()
        if existing:
            return
        
        span = LLMCallLog(
            trace_id=item["trace_id"],
            span_id=item["span_id"],
            parent_span_id=item.get("parent_span_id"),
            call_parameters={"scene": item["name"], "duration_ms": item["duration_ms"]},
            completion_start_time_ms=item["duration_ms"],
            level=CallLevel.INFO,
        )
        session.add(span)
    
    def _write_llm_call(self, session, item: dict):
        """写入/更新 LLM 调用记录 (合并 start/complete/error 事件)"""
        from src.models.llm_call_log import LLMCallLog, CallLevel
        from src.core.tracing.cost import calculate_cost
        
        span_id = item.get("span_id")
        if not span_id:
            return
        
        # 查询是否已存在
        log = session.query(LLMCallLog).filter(LLMCallLog.span_id == span_id).first()
        
        if not log:
            log = LLMCallLog(
                trace_id=item.get("trace_id"),
                span_id=span_id,
                parent_span_id=item.get("parent_span_id"),
                prompt_messages=item.get("prompt_messages"),
                level=CallLevel.INFO,
            )
            session.add(log)
        elif not log.parent_span_id and item.get("parent_span_id"):
            # fallback: 若 llm_start 被采样丢弃，从 llm_complete 补充 parent_span_id
            log.parent_span_id = item["parent_span_id"]
        
        # 更新字段
        if "prompt_messages" in item:
            log.prompt_messages = item["prompt_messages"]
        if "completion_message" in item:
            log.completion_message = item["completion_message"]
        if "call_parameters" in item:
            log.call_parameters = item.get("call_parameters", {})
        if "model_parameters" in item:
            log.model_parameters = item["model_parameters"]
        if "tokens" in item:
            tokens = item["tokens"]
            if isinstance(tokens, dict):
                total_tokens = tokens.get("total_tokens", tokens.get("input_tokens", 0) + tokens.get("output_tokens", 0))
                log.tokens = total_tokens
                # 计算成本
                model = item.get("call_parameters", {}).get("model", "unknown")
                input_tokens = tokens.get("input_tokens", 0)
                output_tokens = tokens.get("output_tokens", 0)
                log.cost = calculate_cost(model, input_tokens, output_tokens)
            else:
                log.tokens = tokens
        if "ttft" in item:
            log.completion_start_time_ms = item["ttft"]
        if "error" in item:
            log.level = CallLevel.ERROR
            if log.call_parameters:
                log.call_parameters["error"] = item["error"]
            else:
                log.call_parameters = {"error": item["error"]}
    
    def _update_trace(self, session, item: dict):
        """更新 Trace 状态"""
        from src.models.trace import Trace, TraceStatus
        
        trace = session.query(Trace).filter(Trace.trace_id == item["trace_id"]).first()
        if trace:
            trace.status = TraceStatus(item["status"])
            trace.total_tokens = item.get("total_tokens", 0)
            if item.get("total_cost"):
                trace.total_cost = item["total_cost"]
            trace.end_time = item.get("timestamp")
    
    def _write_sync(self, item: dict):
        """同步写入 (队列满时的降级处理)"""
        try:
            with get_session() as session:
                if item["type"] == "trace_start":
                    self._create_trace(session, item)
                elif item["type"] == "trace_end":
                    self._finalize_trace(session, item)
                elif item["type"] == "span":
                    self._write_span(session, item)
                elif item["type"] == "trace_update":
                    self._update_trace(session, item)
                elif item["type"] in ("llm_start", "llm_complete", "llm_error"):
                    self._write_llm_call(session, item)
                session.commit()
        except Exception as e:
            logger.error(f"Sync trace write failed: {e}")
```

- [ ] **Step 3: 运行测试验证通过**
Run: `pytest tests/unit/tracing/test_trace_writer.py -v`
Expected: PASS

---

### Task 3.4.2: 实现采样策略验证

**Files:**
- Create: `tests/unit/tracing/test_sampling.py`

- [ ] **Step 1: 编写采样率准确性测试**
```python
import pytest
from src.core.tracing.writer import TraceWriter

@pytest.mark.asyncio
async def test_sample_rate_accuracy():
    """验证采样率准确性（允许 ±10% 误差）"""
    writer = TraceWriter(sample_rate=0.1, error_sample_rate=1.0)
    await writer.start()
    
    total_calls = 1000
    sampled = 0
    
    for _ in range(total_calls):
        if writer._should_sample(is_error=False):
            sampled += 1
    
    # 允许 ±10% 误差
    expected = total_calls * 0.1
    assert abs(sampled - expected) <= expected * 0.1
    
    await writer.stop()

@pytest.mark.asyncio
async def test_error_always_sampled():
    """验证错误调用全量保留"""
    writer = TraceWriter(sample_rate=0.0, error_sample_rate=1.0)
    
    for _ in range(100):
        assert writer._should_sample(is_error=True) is True
```

- [ ] **Step 2: 运行测试验证通过**
Run: `pytest tests/unit/tracing/test_sampling.py -v`
Expected: PASS

---

### Task 3.4.3: 队列满降级处理

**Files:**
- Modify: `src/core/tracing/writer.py`
- Test: `tests/unit/tracing/test_queue_overflow.py`

- [ ] **Step 1: 编写队列满测试**
```python
@pytest.mark.asyncio
async def test_queue_full_degradation():
    """验证队列满时降级为同步写入"""
    writer = TraceWriter(max_queue_size=2)
    await writer.start()
    
    # 填满队列
    await writer.queue.put({"type": "test"})
    await writer.queue.put({"type": "test"})
    
    # 再次入队应触发降级
    with pytest.raises(asyncio.QueueFull):
        await asyncio.wait_for(writer.queue.put({"type": "test"}), timeout=0.1)
    
    await writer.stop()
```

- [ ] **Step 2: 实现降级逻辑**
```python
# 在 record_span 等方法中
async def record_span(self, ...):
    try:
        await asyncio.wait_for(self.queue.put(item), timeout=0.5)
    except asyncio.QueueFull:
        logger.warning("Trace queue full, falling back to sync write")
        # 降级：同步写入
        self._write_sync(item)
```

- [ ] **Step 3: 运行测试验证通过**
Run: `pytest tests/unit/tracing/test_queue_overflow.py -v`
Expected: PASS

---

## 验收标准

- [ ] TraceWriter 异步队列正确工作
- [ ] 采样策略生效，采样率准确（±10%）
- [ ] 错误调用全量保留
- [ ] 队列满时降级为同步写入
- [ ] 批量写入正确，不丢失数据

---

**上一阶段:** [03-instrumentation.md](./05-phase-3-03-instrumentation.md)  
**下一阶段:** [05-dashboard.md](./05-phase-3-05-dashboard.md)
