# Phase 3.7: API 扩展

> **前置文档:** [06-trace-details.md](./05-phase-3-06-trace-details.md)
> **状态:** ⏳ 完全待实现

## API 接口清单

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/monitoring/traces` | GET | 分页查询追踪列表，支持按场景、模型、状态、用户、时间范围筛选 |
| `/api/v1/monitoring/traces/{trace_id}` | GET | 获取单次追踪的完整数据，包含所有 Span 层级树 |
| `/api/v1/monitoring/traces/{trace_id}/spans/{span_id}` | GET | 获取单个 Span 的详细信息 |
| `/api/v1/monitoring/logs` | GET | 查询原始 LLM 调用日志，支持高级筛选 |
| `/api/v1/monitoring/logs/{request_id}` | GET | 获取单次调用的详细数据 |
| `/api/v1/monitoring/cost` | GET | 成本分析接口，按场景/模型/时间段统计 |
| `/api/v1/monitoring/latency` | GET | 延迟分布接口，返回 P50/P95/P99 延迟 |
| `/api/v1/monitoring/errors` | GET | 错误分析接口，错误分类和趋势 |

---

## 实施任务

### Task 3.7.1: 实现追踪列表查询 API

**Files:**
- Create: `src/controller/monitoring_controller.py` (或扩展现有)
- Create: `src/service/trace_service.py`
- Test: `tests/integration/tracing/test_tracing_api.py`

- [ ] **Step 1: 实现 TraceService**
```python
# src/service/trace_service.py
from typing import Optional
from datetime import datetime
from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from src.models.trace import Trace, TraceStatus
from src.models.llm_call_log import LLMCallLog

class TraceService:
    def list_traces(
        self,
        session: Session,
        page: int = 1,
        page_size: int = 20,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> tuple[list[Trace], int]:
        """分页查询 Trace 列表"""
        query = session.query(Trace)
        
        if start_time:
            query = query.filter(Trace.created_at >= start_time)
        if end_time:
            query = query.filter(Trace.created_at <= end_time)
        if status:
            query = query.filter(Trace.status == status)
        if user_id:
            query = query.filter(Trace.user_id == user_id)
        if trace_id:
            query = query.filter(Trace.trace_id == trace_id)
        
        total = query.count()
        items = query.order_by(Trace.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        return items, total
    
    def get_trace_detail(self, session: Session, trace_id: str) -> Optional[dict]:
        """获取 Trace 详情，包含所有 Span"""
        trace = session.query(Trace).filter(Trace.trace_id == trace_id).first()
        if not trace:
            return None
        
        spans = session.query(LLMCallLog).filter(LLMCallLog.trace_id == trace_id).all()
        
        return {
            "trace_id": trace.trace_id,
            "name": trace.name,
            "user_id": trace.user_id,
            "session_id": trace.session_id,
            "metadata": trace.metadata,
            "start_time": trace.start_time,
            "end_time": trace.end_time,
            "total_duration_ms": trace.total_duration_ms,
            "total_tokens": trace.total_tokens,
            "total_cost": str(trace.total_cost) if trace.total_cost else None,
            "status": trace.status.value,
            "created_at": trace.created_at,
            "spans": [self._span_to_dict(span) for span in spans],
        }
    
    def _span_to_dict(self, span: LLMCallLog) -> dict:
        # 从 call_parameters 中提取节点名称和 duration_ms
        call_params = span.call_parameters or {}
        return {
            "span_id": span.span_id,
            "parent_span_id": span.parent_span_id,
            "name": call_params.get("scene", call_params.get("node_name", "unknown")),
            "duration_ms": call_params.get("duration_ms", span.completion_start_time_ms),
            "tokens": span.tokens,
            "status": "success" if span.level.value == "INFO" else "error",
            "prompt_messages": span.prompt_messages,
            "completion_message": span.completion_message,
            "call_parameters": span.call_parameters,
            "error": call_params.get("error") if span.level.value == "ERROR" else None,
        }
```

- [ ] **Step 2: 实现 Controller**
```python
# src/controller/monitoring_controller.py
from fastapi import APIRouter, Depends, Query
from datetime import datetime
from src.service.trace_service import TraceService
from src.database import get_db

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])

@router.get("/traces")
async def list_traces(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    status: str | None = Query(None),
    user_id: str | None = Query(None),
    trace_id: str | None = Query(None),
    db = Depends(get_db),
):
    service = TraceService()
    items, total = service.list_traces(
        db, page, page_size, start_time, end_time, status, user_id, trace_id
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

@router.get("/traces/{trace_id}")
async def get_trace_detail(
    trace_id: str,
    db = Depends(get_db),
):
    service = TraceService()
    result = service.get_trace_detail(db, trace_id)
    if not result:
        return {"error": "Trace not found"}
    return result
```

- [ ] **Step 3: 运行测试验证通过**
Run: `pytest tests/integration/tracing/test_tracing_api.py -v`
Expected: PASS

---

### Task 3.7.2: 实现成本/延迟/错误分析 API

**Files:**
- Modify: `src/controller/monitoring_controller.py`
- Modify: `src/service/trace_service.py`

- [ ] **Step 1: 实现成本分析 API**
```python
@router.get("/cost")
async def get_cost_analysis(
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    db = Depends(get_db),
):
    service = TraceService()
    return service.get_cost_analysis(db, start_time, end_time)

# 在 TraceService 中
def get_cost_analysis(self, session: Session, start_time: datetime | None, end_time: datetime | None) -> dict:
    query = session.query(LLMCallLog)
    if start_time:
        query = query.filter(LLMCallLog.created_at >= start_time)
    if end_time:
        query = query.filter(LLMCallLog.created_at <= end_time)
    
    logs = query.all()
    
    total_cost = sum(float(log.cost) for log in logs if log.cost)
    total_tokens = sum(log.tokens or 0 for log in logs)
    total_calls = len(logs)
    
    # 按模型统计
    model_stats = {}
    for log in logs:
        model = log.call_parameters.get("model", "unknown") if log.call_parameters else "unknown"
        if model not in model_stats:
            model_stats[model] = {"model": model, "calls": 0, "tokens": 0, "cost": 0}
        model_stats[model]["calls"] += 1
        model_stats[model]["tokens"] += log.tokens or 0
        if log.cost:
            model_stats[model]["cost"] += float(log.cost)
    
    return {
        "total_cost": str(total_cost),
        "total_tokens": total_tokens,
        "total_calls": total_calls,
        "avg_cost_per_call": str(total_cost / total_calls) if total_calls > 0 else "0",
        "model_stats": list(model_stats.values()),
    }
```

- [ ] **Step 2: 实现延迟分析 API**
```python
@router.get("/latency")
async def get_latency_distribution(
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    db = Depends(get_db),
):
    service = TraceService()
    return service.get_latency_distribution(db, start_time, end_time)

# 在 TraceService 中
def get_latency_distribution(self, session: Session, start_time: datetime | None, end_time: datetime | None) -> dict:
    query = session.query(Trace.total_duration_ms).filter(Trace.total_duration_ms.isnot(None))
    if start_time:
        query = query.filter(Trace.created_at >= start_time)
    if end_time:
        query = query.filter(Trace.created_at <= end_time)
    
    durations = [d[0] for d in query.all()]
    if not durations:
        return {"p50": 0, "p95": 0, "p99": 0, "avg": 0}
    
    durations.sort()
    
    def percentile(data, p):
        idx = int(len(data) * p / 100)
        return data[min(idx, len(data) - 1)]
    
    return {
        "p50": percentile(durations, 50),
        "p95": percentile(durations, 95),
        "p99": percentile(durations, 99),
        "avg": sum(durations) / len(durations),
        "min": durations[0],
        "max": durations[-1],
    }
```

- [ ] **Step 3: 实现错误分析 API**
```python
@router.get("/errors")
async def get_error_analysis(
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    db = Depends(get_db),
):
    service = TraceService()
    return service.get_error_analysis(db, start_time, end_time)

# 在 TraceService 中
def get_error_analysis(self, session: Session, start_time: datetime | None, end_time: datetime | None) -> dict:
    from src.models.llm_call_log import CallLevel
    
    query = session.query(LLMCallLog).filter(LLMCallLog.level == CallLevel.ERROR)
    if start_time:
        query = query.filter(LLMCallLog.created_at >= start_time)
    if end_time:
        query = query.filter(LLMCallLog.created_at <= end_time)
    
    errors = query.all()
    
    # 按错误类型分类
    error_types = {}
    for error in errors:
        error_msg = error.call_parameters.get("error", "unknown") if error.call_parameters else "unknown"
        error_type = error_msg.split(":")[0] if ":" in error_msg else error_msg
        if error_type not in error_types:
            error_types[error_type] = {"type": error_type, "count": 0, "examples": []}
        error_types[error_type]["count"] += 1
        if len(error_types[error_type]["examples"]) < 3:
            error_types[error_type]["examples"].append({
                "trace_id": error.trace_id,
                "span_id": error.span_id,
                "message": error_msg,
            })
    
    return {
        "total_errors": len(errors),
        "error_types": list(error_types.values()),
    }
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/integration/tracing/test_tracing_api.py -v`
Expected: PASS

---

### Task 3.7.3: 实现 LLM 调用日志查询 API

**Files:**
- Modify: `src/controller/monitoring_controller.py`
- Modify: `src/service/trace_service.py`

- [ ] **Step 1: 实现日志列表查询**
```python
# 在 TraceService 中新增
def list_llm_call_logs(
    self,
    session: Session,
    page: int = 1,
    page_size: int = 20,
    trace_id: Optional[str] = None,
    model: Optional[str] = None,
    level: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> tuple[list[LLMCallLog], int]:
    """分页查询 LLM 调用日志"""
    query = session.query(LLMCallLog)
    
    if trace_id:
        query = query.filter(LLMCallLog.trace_id == trace_id)
    if model:
        query = query.filter(LLMCallLog.call_parameters["model"].as_string() == model)
    if level:
        query = query.filter(LLMCallLog.level == level)
    if start_time:
        query = query.filter(LLMCallLog.created_at >= start_time)
    if end_time:
        query = query.filter(LLMCallLog.created_at <= end_time)
    
    total = query.count()
    items = query.order_by(LLMCallLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return items, total

def get_llm_call_log_detail(self, session: Session, request_id: str) -> Optional[dict]:
    """获取单次 LLM 调用的详细信息"""
    # request_id 可以是 span_id 或原有的 request_id
    log = (
        session.query(LLMCallLog)
        .filter((LLMCallLog.span_id == request_id) | (LLMCallLog.id == request_id))
        .first()
    )
    if not log:
        return None
    
    return {
        "id": log.id,
        "trace_id": log.trace_id,
        "span_id": log.span_id,
        "parent_span_id": log.parent_span_id,
        "prompt_messages": log.prompt_messages,
        "completion_message": log.completion_message,
        "call_parameters": log.call_parameters,
        "model_parameters": log.model_parameters,
        "tokens": log.tokens,
        "cost": str(log.cost) if log.cost else None,
        "tags": log.tags,
        "completion_start_time_ms": log.completion_start_time_ms,
        "level": log.level.value,
        "created_at": log.created_at,
    }
```

- [ ] **Step 2: 添加 Controller 路由**
```python
# 在 monitoring_controller.py 中添加
@router.get("/logs")
async def list_llm_call_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    trace_id: str | None = Query(None),
    model: str | None = Query(None),
    level: str | None = Query(None),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    db = Depends(get_db),
):
    service = TraceService()
    items, total = service.list_llm_call_logs(
        db, page, page_size, trace_id, model, level, start_time, end_time
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

@router.get("/logs/{request_id}")
async def get_llm_call_log_detail(
    request_id: str,
    db = Depends(get_db),
):
    service = TraceService()
    result = service.get_llm_call_log_detail(db, request_id)
    if not result:
        return {"error": "LLM call log not found"}
    return result
```

- [ ] **Step 3: 运行测试验证通过**
Run: `pytest tests/integration/tracing/test_tracing_api.py::test_list_llm_call_logs -v`
Run: `pytest tests/integration/tracing/test_tracing_api.py::test_get_llm_call_log_detail -v`
Expected: PASS

---

## 验收标准

- [ ] 8 个 API 接口完整实现
- [ ] 分页查询正确，支持所有筛选条件
- [ ] Trace 详情返回完整 Span 层级树
- [ ] 成本分析按模型正确统计
- [ ] 延迟分布计算正确 (P50/P95/P99)
- [ ] 错误分析正确分类

---

**上一阶段:** [06-trace-details.md](./05-phase-3-06-trace-details.md)  
**下一阶段:** [Phase 3 汇总](./05-phase-3-llm-tracing.md)
