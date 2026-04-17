# Phase 3.3: 调用链路集成与埋点

> **前置文档:** [02-storage-design.md](./05-phase-3-02-storage-design.md)
> **状态:** ⏳ 完全待实现

## TraceContext 实现

使用 `contextvars` 实现 task-local 的 Trace/Span 上下文传递，确保并发安全。

### Trace 创建时机明确化

根 Trace 的创建应在以下入口点进行：

| 场景 | 创建位置 | Trace 名称示例 | metadata 示例 |
|------|---------|---------------|--------------|
| 评估请求 | API Controller 入口 | `"assessment_run"` | `{"child_profile_id": "cp-123", "user_id": "u-456"}` |
| 测试集执行 | `RagTestManager.execute_batch` | `"test_batch_execution"` | `{"test_set_id": "ts-789", "test_run_id": "tr-012"}` |
| 文档导入 | 文档处理入口 | `"document_import"` | `{"document_id": "doc-345"}` |
| 测试用例草稿生成 | 草稿生成入口 | `"draft_generation"` | `{"document_id": "doc-345", "chunk_count": 10}` |

**实现方式**: 在各入口函数的最外层包裹 `async with trace_context(name, metadata) as tid:`，内部所有 LangGraph 节点和 LLM 调用自动成为该 Trace 的子 Span。

### 核心 API

| 函数 | 说明 | 环境 |
|------|------|------|
| `trace_context(name, metadata)` | 创建 Trace 上下文 | async |
| `create_span(name)` | 创建 Span 并维护父子关系栈 | sync |
| `get_current_trace_id()` | 获取当前 Trace ID | sync |
| `get_current_span_id()` | 获取当前 Span ID | sync |
| `get_parent_span_id()` | 获取父 Span ID (栈中倒数第二个) | sync |

### 并发安全说明

- `contextvars` 在 `asyncio` 中是 task-local 的，每个异步任务有独立的上下文副本
- 使用 `asyncio.create_task()` 创建新任务时，子任务会**继承**父任务的上下文快照，但后续修改互不影响
- 在 `asyncio.gather()` 并发场景中，每个并发分支拥有独立的 `trace_id` 和 `span_stack`，不会互相污染
- 若需要在并发分支间共享同一 Trace 但不同 Span，应在 `create_task` 前显式设置 `trace_id.set(parent_trace_id)`

---

## 实施任务

### Task 3.3.1: 实现 TraceContext

**Files:**
- Create: `src/core/tracing/context.py`
- Test: `tests/unit/tracing/test_trace_context.py`

- [ ] **Step 1: 编写测试用例**
```python
import pytest
from src.core.tracing.context import trace_context, create_span, get_current_trace_id, get_current_span_id

@pytest.mark.asyncio
async def test_trace_context_creation():
    async with trace_context("test_trace", {"key": "value"}) as tid:
        assert tid is not None
        assert get_current_trace_id() == tid

@pytest.mark.asyncio
async def test_span_hierarchy():
    async with trace_context("test_trace") as tid:
        with create_span("parent_span") as parent_id:
            assert get_current_span_id() == parent_id
            assert get_parent_span_id() is None  # 根 Span 无父节点
            with create_span("child_span") as child_id:
                assert get_current_span_id() == child_id
                assert get_parent_span_id() == parent_id  # 父节点正确传递
            # 回到 parent_span
            assert get_current_span_id() == parent_id
            assert get_parent_span_id() is None  # 回到根 Span

@pytest.mark.asyncio
async def test_concurrent_isolation():
    import asyncio
    
    results = []
    
    async def run_trace(name):
        async with trace_context(name) as tid:
            await asyncio.sleep(0.01)
            results.append((name, get_current_trace_id()))
    
    await asyncio.gather(run_trace("trace_a"), run_trace("trace_b"))
    
    # 两个 Trace 的 ID 不同
    assert results[0][1] != results[1][1]

@pytest.mark.asyncio
async def test_concurrent_span_isolation():
    """验证并发场景下 Span 栈不互相污染"""
    import asyncio
    
    async def run_with_spans(name, results):
        async with trace_context(name) as tid:
            with create_span(f"{name}_parent") as parent_id:
                await asyncio.sleep(0.01)
                with create_span(f"{name}_child") as child_id:
                    await asyncio.sleep(0.01)
                    # 验证当前 span 是 child
                    assert get_current_span_id() == child_id
                # 退出 child 后，回到 parent
                assert get_current_span_id() == parent_id
                results.append((name, tid, parent_id))
    
    results_a = []
    results_b = []
    await asyncio.gather(
        run_with_spans("trace_a", results_a),
        run_with_spans("trace_b", results_b),
    )
    
    # 验证两个 Trace 的 parent_id 不同
    assert results_a[0][1] != results_b[0][1]
    assert results_a[0][2] != results_b[0][2]

@pytest.mark.asyncio
async def test_shared_trace_across_tasks():
    """验证并发分支间共享同一 Trace 但不同 Span"""
    import asyncio
    
    shared_trace_id = None
    
    async def run_shared_task(index, results):
        nonlocal shared_trace_id
        # 显式设置共享的 trace_id
        from src.core.tracing.context import trace_id
        if shared_trace_id:
            trace_id.set(shared_trace_id)
        
        with create_span(f"shared_span_{index}") as span_id:
            await asyncio.sleep(0.01)
            results.append((index, get_current_trace_id(), span_id))
    
    async with trace_context("shared_trace") as tid:
        shared_trace_id = tid
        results = []
        await asyncio.gather(
            run_shared_task(1, results),
            run_shared_task(2, results),
            run_shared_task(3, results),
        )
    
    # 所有任务共享同一个 trace_id
    for index, trace_id, span_id in results:
        assert trace_id == shared_trace_id
    # 但每个任务有独立的 span_id
    span_ids = [r[2] for r in results]
    assert len(set(span_ids)) == 3
```

- [ ] **Step 2: 实现 TraceContext**
```python
# src/core/tracing/context.py
import uuid
from contextvars import ContextVar
from contextlib import asynccontextmanager, contextmanager
from typing import Generator

trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
span_stack: ContextVar[list[str]] = ContextVar("span_stack", default_factory=list)

def get_current_trace_id() -> str | None:
    return trace_id.get()

def get_current_span_id() -> str | None:
    stack = span_stack.get()
    return stack[-1] if stack else None

def get_parent_span_id() -> str | None:
    """获取父 Span ID (栈中倒数第二个元素)"""
    stack = span_stack.get()
    return stack[-2] if len(stack) >= 2 else None

@asynccontextmanager
async def trace_context(name: str, metadata: dict | None = None):
    """创建 Trace 上下文（async 版本，推荐使用）
    
    自动记录 start_time 和 end_time，并通过 TraceWriter 写入数据库。
    """
    from datetime import datetime
    from src.core.tracing.writer import get_trace_writer
    
    tid = str(uuid.uuid4())
    start_time = datetime.utcnow()
    trace_token = trace_id.set(tid)
    span_token = span_stack.set([])
    
    # 使用全局单例 TraceWriter，确保队列统一
    writer = get_trace_writer()
    writer.record_trace_start(
        trace_id=tid,
        name=name,
        metadata=metadata or {},
        start_time=start_time,
    )
    
    try:
        yield tid
    finally:
        end_time = datetime.utcnow()
        # 自动写入 Trace 结束时间
        writer.record_trace_end(trace_id=tid, end_time=end_time)
        trace_id.reset(trace_token)
        span_stack.reset(span_token)

@contextmanager
def trace_context_sync(name: str, metadata: dict | None = None):
    """创建 Trace 上下文（sync 版本，仅用于同步场景）
    
    自动记录 start_time 和 end_time。
    """
    from datetime import datetime
    from src.core.tracing.writer import get_trace_writer
    
    tid = str(uuid.uuid4())
    start_time = datetime.utcnow()
    trace_token = trace_id.set(tid)
    span_token = span_stack.set([])
    
    writer = get_trace_writer()
    writer.record_trace_start(trace_id=tid, name=name, metadata=metadata or {}, start_time=start_time)
    
    try:
        yield tid
    finally:
        end_time = datetime.utcnow()
        writer.record_trace_end(trace_id=tid, end_time=end_time)
        trace_id.reset(trace_token)
        span_stack.reset(span_token)

@contextmanager
def create_span(name: str) -> Generator[str, None, None]:
    """创建 Span 并维护父子关系栈"""
    span_id = str(uuid.uuid4())
    stack = span_stack.get().copy()
    stack.append(span_id)
    token = span_stack.set(stack)
    try:
        yield span_id
    finally:
        span_stack.reset(token)  # reset 自动恢复到 set 之前的状态
```

- [ ] **Step 3: 运行测试验证通过**
Run: `pytest tests/unit/tracing/test_trace_context.py -v`
Expected: PASS

---

### Task 3.3.2: LangGraph 节点 Span 集成

**Files:**
- Create: `src/core/tracing/langgraph_middleware.py`
- Modify: LangGraph 工作流入口文件
- Test: `tests/integration/tracing/test_langgraph_integration.py`

- [ ] **Step 1: 编写测试用例**
```python
def test_langgraph_node_span_creation():
    """验证 LangGraph 节点执行时自动创建 Span"""
    from src.core.tracing.langgraph_middleware import TracingMiddleware
    from src.core.tracing.context import get_current_trace_id, get_current_span_id
    
    middleware = TracingMiddleware()
    # 模拟节点执行
    with middleware.trace_node("assessment_node"):
        trace_id = get_current_trace_id()
        span_id = get_current_span_id()
        assert trace_id is not None
        assert span_id is not None
```

- [ ] **Step 2: 实现 LangGraph 中间件**
```python
# src/core/tracing/langgraph_middleware.py
import time
from contextlib import contextmanager
from src.core.tracing.context import trace_context, create_span, get_current_trace_id, get_current_span_id, get_parent_span_id
from src.core.tracing.writer import get_trace_writer

class TracingMiddleware:
    def __init__(self, writer=None):
        self.writer = writer or get_trace_writer()
    
    @contextmanager
    def trace_node(self, node_name: str):
        """为 LangGraph 节点创建 Span"""
        span_id = None
        start_time = time.time()
        
        with create_span(node_name) as span_id:
            try:
                yield span_id
            finally:
                duration_ms = int((time.time() - start_time) * 1000)
                # 记录 Span 到异步队列 (包含 parent_span_id)
                self.writer.record_span(
                    trace_id=get_current_trace_id(),
                    span_id=span_id,
                    parent_span_id=get_parent_span_id(),
                    name=node_name,
                    duration_ms=duration_ms,
                )
```

- [ ] **Step 3: 集成到 LangGraph 工作流**
```python
# 在 LangGraph StateGraph 定义中
from src.core.tracing.langgraph_middleware import TracingMiddleware

middleware = TracingMiddleware()

# 每个节点执行前后包裹 tracing
def run_node_with_tracing(node_func, node_name):
    async def wrapper(state):
        with middleware.trace_node(node_name):
            return await node_func(state)
    return wrapper

# 注册节点时使用 wrapper
graph.add_node("assessment", run_node_with_tracing(assessment_node, "assessment"))
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/integration/tracing/test_langgraph_integration.py -v`
Expected: PASS

---

### Task 3.3.3: 测试执行 Trace 集成

**Files:**
- Modify: `src/service/rag_test_manager.py`
- Test: `tests/integration/tracing/test_test_execution_tracing.py`

- [ ] **Step 1: 在 execute_batch 中为每个测试用例创建独立 Trace**
```python
# 在 RagTestManager.execute_batch 中
from src.core.tracing.context import trace_context
from src.core.tracing.writer import get_trace_writer

async def execute_batch(self, test_set_id: str):
    writer = get_trace_writer()
    
    for test_case in test_cases:
        # 为每个测试用例创建独立 Trace
        async with trace_context_async(
            name=f"test_case_execution",
            metadata={"test_case_id": test_case.id, "test_set_id": test_set_id}
        ) as tid:
            # 执行测试用例
            result = await self.run_single_test(test_case)
            
            # 更新 Trace 状态
            writer.update_trace(
                trace_id=tid,
                status="success" if result.passed else "failed",
                total_tokens=result.tokens_used,
            )
```

- [ ] **Step 2: 运行测试验证通过**
Run: `pytest tests/integration/tracing/test_test_execution_tracing.py -v`
Expected: PASS

---

### Task 3.3.4: LLM 调用 Span 集成

**Files:**
- Modify: `src/core/llm/factory.py` (或现有 LLM 调用入口)
- Test: `tests/unit/tracing/test_llm_call_tracing.py`

- [ ] **Step 1: 在 LLM 调用时自动创建 Span**
```python
# 在 LLMServiceFactory.create() 或调用方法中
import time
from src.core.tracing.context import get_current_trace_id, get_current_span_id, get_parent_span_id, create_span
from src.core.tracing.writer import get_trace_writer
from src.core.tracing.truncation import truncate_messages, truncate_content

writer = get_trace_writer()

async def call_llm_with_tracing(self, messages, **kwargs):
    start_time = time.time()
    ttft = None  # Time to First Token
    
    with create_span(f"llm_call_{kwargs.get('model', 'unknown')}") as span_id:
        try:
            # 截断消息
            truncated_messages = truncate_messages(messages)
            
            # 记录调用开始
            writer.record_llm_start(
                trace_id=get_current_trace_id(),
                span_id=span_id,
                parent_span_id=get_parent_span_id(),
                prompt_messages=truncated_messages,
                call_parameters=kwargs,
            )
            
            # 实际调用
            response = await self.llm.ainvoke(messages)
            
            # 计算 TTFT
            ttft = int((time.time() - start_time) * 1000)
            
            # 截断输出
            truncated_completion = truncate_content(response.content)[0]
            
            # 记录调用完成
            writer.record_llm_complete(
                trace_id=get_current_trace_id(),
                span_id=span_id,
                parent_span_id=get_parent_span_id(),
                completion_message=truncated_completion,
                tokens=response.usage_metadata,
                ttft=ttft,
            )
            
            return response
            
        except Exception as e:
            writer.record_llm_error(
                trace_id=get_current_trace_id(),
                span_id=span_id,
                error=str(e),
            )
            raise
```

- [ ] **Step 2: 运行测试验证通过**
Run: `pytest tests/unit/tracing/test_llm_call_tracing.py -v`
Expected: PASS

---

## 验收标准

- [ ] TraceContext 正确创建和传递，父子关系正确
- [ ] 并发场景下上下文隔离，不互相污染
- [ ] LangGraph 节点自动创建 Span
- [ ] 测试执行中每个用例创建独立 Trace
- [ ] LLM 调用自动记录输入、输出、参数、TTFT

---

**上一阶段:** [02-storage-design.md](./05-phase-3-02-storage-design.md)  
**下一阶段:** [04-data-processing.md](./05-phase-3-04-data-processing.md)
