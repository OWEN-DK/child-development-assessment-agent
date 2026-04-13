# Phase 5: LLM 监控系统实现

> 本文档是 MySQL + Redis 集成重构实施方案的一部分
> 
> **返回索引：** [README.md](./README.md) | [项目概览](./00-overview.md)

---

## Phase 5: LLM 监控系统实现（周期：2 天）

### 目标
实现 LLM 调用日志采集和存储，开发监控统计 API 和前端展示页面，可视化调用量、Token 消耗、错误率等指标。

### 架构设计

```
┌─────────────────────────────────────────────────┐
│           前端监控仪表板                          │
│    - 调用量趋势图                                │
│    - Token 消耗统计                               │
│    - 错误率监控                                  │
│    - 模型使用分布                                │
└─────────────────────────────────────────────────┘
                      ↓ API
┌─────────────────────────────────────────────────┐
│         监控服务 (MonitoringService)             │
│    - 日志采集                                    │
│    - 指标聚合                                    │
│    - 统计分析                                    │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│         MySQL 数据库                             │
│    - llm_call_logs                               │
│    - ab_test_metrics                             │
└─────────────────────────────────────────────────┘
```

---

### Task 5.1: 实现 LLM 调用日志采集

**Files:**
- Create: `backend/src/service/monitoring_service.py`

- [ ] **Step 1: 创建监控服务**

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, extract
from sqlalchemy.orm import aliased
from datetime import datetime, timedelta
from typing import Optional
from src.core.database import db_session_factory
from src.models.monitor import LLMCallLog, LLMCallStatus, ABTestMetrics
from src.utils.logger import logger

class MonitoringService:
    """LLM 监控服务"""
    
    def __init__(self):
        self.db_session_factory = db_session_factory
    
    async def log_llm_call(
        self,
        request_id: str,
        model_name: str,
        prompt_key: str = None,
        prompt_version: str = None,
        scenario: str = None,
        input_tokens: int = None,
        output_tokens: int = None,
        total_tokens: int = None,
        duration_ms: int = None,
        status: str = "success",
        error_message: str = None,
    ):
        """记录 LLM 调用日志"""
        async with self.db_session_factory() as session:
            log_entry = LLMCallLog(
                request_id=request_id,
                prompt_key=prompt_key,
                prompt_version=prompt_version,
                scenario=scenario,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                status=status,
                error_message=error_message,
            )
            
            session.add(log_entry)
            await session.commit()
            
            logger.debug(f"LLM 调用日志已记录：{request_id}")
    
    async def get_call_statistics(
        self,
        start_time: datetime,
        end_time: datetime,
        model_name: str = None,
        scenario: str = None,
    ) -> dict:
        """获取调用统计"""
        async with self.db_session_factory() as session:
            # 基础查询
            base_query = select(LLMCallLog).where(
                and_(
                    LLMCallLog.created_at >= start_time,
                    LLMCallLog.created_at <= end_time,
                )
            )
            
            if model_name:
                base_query = base_query.where(LLMCallLog.model_name == model_name)
            
            if scenario:
                base_query = base_query.where(LLMCallLog.scenario == scenario)
            
            # 总调用次数
            stmt = select(func.count()).select_from(base_query.subquery())
            result = await session.execute(stmt)
            total_calls = result.scalar()
            
            # 成功/失败次数
            stmt = select(
                LLMCallLog.status,
                func.count().label('count')
            ).where(
                and_(
                    LLMCallLog.created_at >= start_time,
                    LLMCallLog.created_at <= end_time,
                )
            ).group_by(LLMCallLog.status)
            
            result = await session.execute(stmt)
            status_counts = {row[0]: row[1] for row in result.all()}
            
            # Token 统计
            stmt = select(
                func.sum(LLMCallLog.input_tokens).label('input_tokens'),
                func.sum(LLMCallLog.output_tokens).label('output_tokens'),
                func.sum(LLMCallLog.total_tokens).label('total_tokens'),
            ).where(
                and_(
                    LLMCallLog.created_at >= start_time,
                    LLMCallLog.created_at <= end_time,
                )
            )
            
            result = await session.execute(stmt)
            token_stats = result.one()
            
            # 平均耗时
            stmt = select(
                func.avg(LLMCallLog.duration_ms).label('avg_duration'),
                func.max(LLMCallLog.duration_ms).label('max_duration'),
                func.min(LLMCallLog.duration_ms).label('min_duration'),
            ).where(
                and_(
                    LLMCallLog.created_at >= start_time,
                    LLMCallLog.created_at <= end_time,
                )
            )
            
            result = await session.execute(stmt)
            duration_stats = result.one()
            
            return {
                "total_calls": total_calls,
                "success_count": status_counts.get("success", 0),
                "failed_count": status_counts.get("failed", 0),
                "timeout_count": status_counts.get("timeout", 0),
                "error_rate": (status_counts.get("failed", 0) + status_counts.get("timeout", 0)) / total_calls if total_calls > 0 else 0,
                "input_tokens": token_stats.input_tokens or 0,
                "output_tokens": token_stats.output_tokens or 0,
                "total_tokens": token_stats.total_tokens or 0,
                "avg_duration_ms": duration_stats.avg_duration or 0,
                "max_duration_ms": duration_stats.max_duration or 0,
                "min_duration_ms": duration_stats.min_duration or 0,
            }
    
    async def get_hourly_trend(
        self,
        start_time: datetime,
        end_time: datetime,
        metric: str = "calls",
    ) -> list[dict]:
        """获取小时级趋势"""
        async with self.db_session_factory() as session:
            if metric == "calls":
                stmt = select(
                    extract('hour', LLMCallLog.created_at).label('hour'),
                    func.count().label('value'),
                ).where(
                    and_(
                        LLMCallLog.created_at >= start_time,
                        LLMCallLog.created_at <= end_time,
                    )
                ).group_by(
                    extract('hour', LLMCallLog.created_at)
                ).order_by(
                    extract('hour', LLMCallLog.created_at)
                )
            elif metric == "tokens":
                stmt = select(
                    extract('hour', LLMCallLog.created_at).label('hour'),
                    func.sum(LLMCallLog.total_tokens).label('value'),
                ).where(
                    and_(
                        LLMCallLog.created_at >= start_time,
                        LLMCallLog.created_at <= end_time,
                    )
                ).group_by(
                    extract('hour', LLMCallLog.created_at)
                ).order_by(
                    extract('hour', LLMCallLog.created_at)
                )
            elif metric == "duration":
                stmt = select(
                    extract('hour', LLMCallLog.created_at).label('hour'),
                    func.avg(LLMCallLog.duration_ms).label('value'),
                ).where(
                    and_(
                        LLMCallLog.created_at >= start_time,
                        LLMCallLog.created_at <= end_time,
                    )
                ).group_by(
                    extract('hour', LLMCallLog.created_at)
                ).order_by(
                    extract('hour', LLMCallLog.created_at)
                )
            
            result = await session.execute(stmt)
            return [{"hour": row[0], "value": row[1]} for row in result.all()]
    
    async def get_model_distribution(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict]:
        """获取模型使用分布"""
        async with self.db_session_factory() as session:
            stmt = select(
                LLMCallLog.model_name,
                func.count().label('count'),
                func.sum(LLMCallLog.total_tokens).label('total_tokens'),
            ).where(
                and_(
                    LLMCallLog.created_at >= start_time,
                    LLMCallLog.created_at <= end_time,
                )
            ).group_by(
                LLMCallLog.model_name
            ).order_by(
                func.count().desc()
            )
            
            result = await session.execute(stmt)
            return [
                {
                    "model_name": row[0],
                    "count": row[1],
                    "total_tokens": row[2],
                }
                for row in result.all()
            ]
    
    async def get_scenario_statistics(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict]:
        """获取场景统计"""
        async with self.db_session_factory() as session:
            stmt = select(
                LLMCallLog.scenario,
                func.count().label('count'),
                func.avg(LLMCallLog.duration_ms).label('avg_duration'),
                func.sum(LLMCallLog.total_tokens).label('total_tokens'),
            ).where(
                and_(
                    LLMCallLog.created_at >= start_time,
                    LLMCallLog.created_at <= end_time,
                )
            ).group_by(
                LLMCallLog.scenario
            ).order_by(
                func.count().desc()
            )
            
            result = await session.execute(stmt)
            return [
                {
                    "scenario": row[0],
                    "count": row[1],
                    "avg_duration_ms": row[2],
                    "total_tokens": row[3],
                }
                for row in result.all()
            ]
```

---

### Task 5.2: 创建监控 API 端点

**Files:**
- Modify: `backend/src/controller/monitoring_controller.py`

- [ ] **Step 1: 创建监控控制器**

```python
from fastapi import APIRouter, Query
from datetime import datetime, timedelta
from src.service.monitoring_service import MonitoringService

router = APIRouter()

@router.get("/monitoring/statistics")
async def get_statistics(
    days: int = Query(default=7, ge=1, le=30),
    model_name: str = None,
    scenario: str = None,
):
    """获取调用统计"""
    service = MonitoringService()
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    stats = await service.get_call_statistics(
        start_time=start_time,
        end_time=end_time,
        model_name=model_name,
        scenario=scenario,
    )
    
    return stats

@router.get("/monitoring/trend")
async def get_trend(
    days: int = Query(default=7, ge=1, le=30),
    metric: str = Query(default="calls", enum=["calls", "tokens", "duration"]),
):
    """获取趋势数据"""
    service = MonitoringService()
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    trend = await service.get_hourly_trend(
        start_time=start_time,
        end_time=end_time,
        metric=metric,
    )
    
    return {"trend": trend, "metric": metric}

@router.get("/monitoring/models")
async def get_model_distribution(
    days: int = Query(default=7, ge=1, le=30),
):
    """获取模型分布"""
    service = MonitoringService()
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    distribution = await service.get_model_distribution(
        start_time=start_time,
        end_time=end_time,
    )
    
    return {"distribution": distribution}

@router.get("/monitoring/scenarios")
async def get_scenario_statistics(
    days: int = Query(default=7, ge=1, le=30),
):
    """获取场景统计"""
    service = MonitoringService()
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    stats = await service.get_scenario_statistics(
        start_time=start_time,
        end_time=end_time,
    )
    
    return {"scenarios": stats}
```

---

### Task 5.3: 集成 LLM 调用日志采集

**Files:**
- Modify: `backend/src/core/llm/base.py`
- Modify: `backend/src/core/llm/adapters/langchain.py`
- Modify: `backend/src/core/llm/adapters/llamaindex.py`

- [ ] **Step 1: 在 LLM 适配器中添加日志采集**

```python
# 在 LangChainLLMAdapter.chat 方法中添加
from src.service.monitoring_service import MonitoringService
import uuid

async def chat(self, request: LLMRequest) -> LLMResponse:
    """聊天接口实现"""
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    try:
        # ... 现有调用逻辑 ...
        response = await self.llm.ainvoke(lc_messages)
        
        # 计算耗时
        duration_ms = int((time.time() - start_time) * 1000)
        
        # 估算 Token
        input_tokens = sum(len(msg.content) for msg in request.messages) // 4
        output_tokens = len(response.content) // 4
        
        llm_response = LLMResponse(
            content=response.content,
            model_name=self._model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            duration_ms=duration_ms,
        )
        
        # 记录成功日志
        monitoring = MonitoringService()
        asyncio.create_task(
            monitoring.log_llm_call(
                request_id=request_id,
                model_name=self._model_name,
                prompt_key=request.prompt_key,
                scenario=request.scenario,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                duration_ms=duration_ms,
                status="success",
            )
        )
        
        return llm_response
        
    except Exception as e:
        # 记录失败日志
        monitoring = MonitoringService()
        asyncio.create_task(
            monitoring.log_llm_call(
                request_id=request_id,
                model_name=self._model_name,
                prompt_key=request.prompt_key,
                scenario=request.scenario,
                status="failed",
                error_message=str(e),
            )
        )
        raise
```

---

### Task 5.4: 实现 Prometheus 指标输出

**Files:**
- Create: `backend/src/core/prometheus_metrics.py`
- Modify: `backend/src/service/monitoring_service.py`
- Modify: `backend/src/server.py`

- [ ] **Step 1: 定义 Prometheus 指标**

```python
# backend/src/core/prometheus_metrics.py
"""Prometheus 监控指标定义"""
from prometheus_client import Counter, Histogram, Gauge

# LLM 调用次数
LLM_CALLS_TOTAL = Counter(
    'llm_calls_total',
    'Total LLM calls',
    ['model', 'scenario', 'status']  # status: success/failed/timeout
)

# LLM 调用耗时
LLM_CALL_DURATION = Histogram(
    'llm_call_duration_seconds',
    'LLM call duration',
    ['model', 'scenario'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]  # 秒
)

# Token 消耗
LLM_TOKENS_TOTAL = Counter(
    'llm_tokens_total',
    'Total tokens consumed',
    ['model', 'scenario', 'type']  # type: input/output/total
)

# 活跃连接数
ACTIVE_CONNECTIONS = Gauge(
    'llm_active_connections',
    'Active LLM connections',
    ['model']
)

# 缓存命中率
CACHE_HIT_RATE = Gauge(
    'cache_hit_rate',
    'Cache hit rate',
    ['cache_type']  # type: memory/redis
)
```

- [ ] **Step 2: 在监控服务中埋点**

```python
# backend/src/service/monitoring_service.py
from src.core.prometheus_metrics import (
    LLM_CALLS_TOTAL,
    LLM_CALL_DURATION,
    LLM_TOKENS_TOTAL,
)

class MonitoringService:
    async def log_llm_call(self, ...):
        """记录 LLM 调用日志"""
        # ... 现有 MySQL 写入逻辑 ...
        
        # 记录 Prometheus 指标
        LLM_CALLS_TOTAL.labels(
            model=model_name,
            scenario=scenario,
            status=status
        ).inc()
        
        if duration_ms:
            LLM_CALL_DURATION.labels(
                model=model_name,
                scenario=scenario
            ).observe(duration_ms / 1000.0)
        
        if input_tokens:
            LLM_TOKENS_TOTAL.labels(
                model=model_name,
                scenario=scenario,
                type='input'
            ).inc(input_tokens)
        
        if output_tokens:
            LLM_TOKENS_TOTAL.labels(
                model=model_name,
                scenario=scenario,
                type='output'
            ).inc(output_tokens)
```

- [ ] **Step 3: 暴露 /metrics 端点**

```python
# backend/src/server.py
from prometheus_client import make_asgi_app

# 创建 Prometheus metrics 应用
metrics_app = make_asgi_app()

# 挂载到 FastAPI
app.mount("/metrics", metrics_app)
```

- [ ] **Step 4: 验证指标输出**

访问 `http://localhost:8000/metrics`，确认指标正常输出：
```bash
curl http://localhost:8000/metrics
```

Expected Output:
```
# HELP llm_calls_total Total LLM calls
# TYPE llm_calls_total counter
llm_calls_total{model="qwen-plus",scenario="assessment",status="success"} 100.0
llm_calls_total{model="qwen-turbo",scenario="validation",status="success"} 50.0
# HELP llm_call_duration_seconds LLM call duration
# TYPE llm_call_duration_seconds histogram
llm_call_duration_seconds_bucket{model="qwen-plus",scenario="assessment",le="0.5"} 80.0
```

---

### Task 5.4: 异常告警规则配置
**Files:**
- Create: `backend/src/service/alert_service.py`

- [ ] **Step 1: 创建告警规则配置**
```python
# backend/src/service/alert_service.py
from dataclasses import dataclass
from typing import Callable
from src.utils.logger import logger

@dataclass
class AlertRule:
    name: str
    condition: Callable[[dict], bool]
    message: str
    severity: str = "warning"  # warning / critical

class AlertService:
    """LLM 监控告警服务"""
    
    _rules: list[AlertRule] = []
    
    @classmethod
    def add_rule(cls, rule: AlertRule):
        cls._rules.append(rule)
    
    @classmethod
    def check_alerts(cls, metrics: dict) -> list[AlertRule]:
        """检查是否触发告警"""
        triggered = []
        for rule in cls._rules:
            if rule.condition(metrics):
                triggered.append(rule)
                logger.warning(f"[{rule.severity.upper()}] 告警触发: {rule.name} - {rule.message}")
        return triggered

# 默认告警规则
AlertService.add_rule(AlertRule(
    name="high_error_rate",
    condition=lambda m: m.get("error_rate", 0) > 0.1,
    message="LLM 调用错误率超过 10%",
    severity="critical",
))

AlertService.add_rule(AlertRule(
    name="slow_response",
    condition=lambda m: m.get("avg_duration_ms", 0) > 10000,
    message="LLM 平均响应时间超过 10 秒",
    severity="warning",
))

AlertService.add_rule(AlertRule(
    name="token_spike",
    condition=lambda m: m.get("total_tokens", 0) > 1000000,
    message="Token 消耗突增超过 100 万",
    severity="warning",
))
```

### Task 5.5: A/B 测试 variant 对比 API
**Files:**
- Modify: `backend/src/controller/monitoring_controller.py`

- [ ] **Step 1: 添加 variant 对比接口**
```python
@router.get("/monitoring/ab-comparison")
async def get_ab_comparison(
    test_name: str,
    days: int = Query(default=7, ge=1, le=30),
):
    """A/B 测试 variant 对比"""
    service = MonitoringService()
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    # 获取各 variant 的指标
    variants = await service.get_ab_variant_stats(test_name, start_time, end_time)
    
    # 计算差异
    comparison = {}
    if len(variants) >= 2:
        variant_a = variants[0]
        variant_b = variants[1]
        comparison = {
            "precision_diff": variant_b["precision"] - variant_a["precision"],
            "recall_diff": variant_b["recall"] - variant_a["recall"],
            "f1_diff": variant_b["f1"] - variant_a["f1"],
            "avg_duration_diff": variant_b["avg_duration"] - variant_a["avg_duration"],
        }
    
    return {
        "test_name": test_name,
        "variants": variants,
        "comparison": comparison,
    }
```

### Task 5.6: 修复 LLM 日志采集的 asyncio.create_task 数据丢失
**Files:**
- Modify: `backend/src/core/llm/adapters/langchain.py`
- Modify: `backend/src/core/llm/adapters/llamaindex.py`

- [ ] **Step 1: 使用队列替代 asyncio.create_task**
```python
# backend/src/core/llm/log_collector.py
import asyncio
from src.service.monitoring_service import MonitoringService
from src.utils.logger import logger

class LLMLogCollector:
    """LLM 调用日志采集器（使用队列防止关闭时数据丢失）"""
    
    _queue: asyncio.Queue = None
    _worker_task: asyncio.Task = None
    _monitoring: MonitoringService = None
    
    @classmethod
    def start(cls):
        """启动采集器（应用启动时调用）"""
        cls._queue = asyncio.Queue(maxsize=10000)
        cls._monitoring = MonitoringService()
        cls._worker_task = asyncio.create_task(cls._worker())
        logger.info("LLM 日志采集器已启动")
    
    @classmethod
    async def stop(cls):
        """停止采集器（应用关闭时调用，确保数据全部写入）"""
        if cls._worker_task:
            await cls._queue.put(None)  # 停止信号
            await cls._worker_task
            logger.info("LLM 日志采集器已停止")
    
    @classmethod
    async def submit(cls, log_data: dict):
        """提交日志到队列"""
        try:
            await cls._queue.put(log_data)
        except asyncio.QueueFull:
            logger.warning("LLM 日志队列已满，丢弃日志")
    
    @classmethod
    async def _worker(cls):
        """后台工作协程"""
        while True:
            log_data = await cls._queue.get()
            if log_data is None:  # 停止信号
                break
            
            try:
                await cls._monitoring.log_llm_call(**log_data)
            except Exception as e:
                logger.error(f"LLM 日志写入失败: {e}")

# 在适配器中使用
# 替换 asyncio.create_task(monitoring.log_llm_call(...))
# 改为 await LLMLogCollector.submit(log_data)
```

### Phase 5 完成验证

- [ ] 运行单元测试，验证日志采集功能正常
- [ ] 测试监控 API，确认统计数据准确
- [ ] 验证前端仪表板展示
- [ ] 检查日志记录完整性
- [ ] 压力测试：高并发调用下日志采集正常

---

**返回索引：** [README.md](./README.md)
