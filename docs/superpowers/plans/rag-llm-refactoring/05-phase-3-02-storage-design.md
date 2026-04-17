# Phase 3.2: 存储设计与优化

> **前置文档:** [01-trace-model.md](./05-phase-3-01-trace-model.md)
> **状态:** ⏳ 完全待实现

## 存储优化策略

### 1. 截断存储

`prompt_messages` 和 `completion_message` 默认截断至前 8000 字符（可配置 `trace_truncate_length`），完整内容存储于可选的本地文件。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `trace_truncate_length` | Integer | 8000 | 截断长度（字符数） |
| `trace_full_content_enabled` | Boolean | false | 是否存储完整内容到文件 |
| `trace_full_content_dir` | String | `storage/traces` | 完整内容存储目录 |

### 2. TTL 自动清理

支持按时间自动清理过期追踪数据（默认保留 30 天）。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `trace_ttl_days` | Integer | 30 | 数据保留天数 |
| `trace_cleanup_batch_size` | Integer | 1000 | 单次清理批次大小 |
| `trace_cleanup_schedule` | String | `0 2 * * *` | APScheduler 定时表达式（每天凌晨 2 点） |

### 3. 采样策略

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `trace_sample_rate` | Float | 1.0 | 采样率（0.0-1.0） |
| `trace_error_sample_rate` | Float | 1.0 | 错误采样率（错误全量保留） |

---

## 实施任务

### Task 3.2.1: 实现截断存储策略

**Files:**
- Create: `src/core/tracing/truncation.py`
- Test: `tests/unit/tracing/test_truncation.py`

- [ ] **Step 1: 编写测试用例**
```python
def test_truncate_short_content():
    from src.core.tracing.truncation import truncate_content
    
    content = "short content"
    result, truncated = truncate_content(content, max_length=8000)
    assert result == content
    assert truncated is False

def test_truncate_long_content():
    from src.core.tracing.truncation import truncate_content
    
    content = "a" * 10000
    result, truncated = truncate_content(content, max_length=8000)
    assert len(result) == 8000
    assert truncated is True

def test_truncate_json_messages():
    from src.core.tracing.truncation import truncate_messages
    
    messages = [{"role": "user", "content": "a" * 10000}]
    result = truncate_messages(messages, max_length=8000)
    assert len(result[0]["content"]) == 8000
```

- [ ] **Step 2: 实现截断逻辑**
```python
# src/core/tracing/truncation.py
import json
import os
import uuid
from typing import Any, Tuple

DEFAULT_TRUNCATE_LENGTH = 8000
FULL_CONTENT_DIR = "storage/traces"

def truncate_content(content: str, max_length: int = DEFAULT_TRUNCATE_LENGTH) -> Tuple[str, bool]:
    """截断文本内容，返回 (截断后内容, 是否被截断)"""
    if len(content) <= max_length:
        return content, False
    return content[:max_length], True

def truncate_messages(messages: list[dict], max_length: int = DEFAULT_TRUNCATE_LENGTH) -> list[dict]:
    """截断消息数组中每个消息的 content 字段"""
    result = []
    for msg in messages:
        truncated_msg = msg.copy()
        if "content" in truncated_msg and isinstance(truncated_msg["content"], str):
            truncated_msg["content"], _ = truncate_content(truncated_msg["content"], max_length)
        result.append(truncated_msg)
    return result

def save_full_content(content: str, trace_id: str, span_id: str, field_name: str) -> str:
    """保存完整内容到本地文件，返回文件路径
    
    Args:
        content: 完整内容
        trace_id: 追踪 ID
        span_id: Span ID
        field_name: 字段名 ("prompt" 或 "completion")
    
    Returns:
        文件绝对路径，用于写入 full_prompt_path 或 full_completion_path
    """
    os.makedirs(FULL_CONTENT_DIR, exist_ok=True)
    filename = f"{trace_id}_{span_id}_{field_name}.json"
    filepath = os.path.join(FULL_CONTENT_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"trace_id": trace_id, "span_id": span_id, "field": field_name, "content": content}, f)
    
    return filepath
```

- [ ] **Step 3: 运行测试验证通过**
Run: `pytest tests/unit/tracing/test_truncation.py -v`
Expected: PASS

---

### Task 3.2.2: 实现 TTL 清理任务

**Files:**
- Create: `src/core/tracing/cleanup.py`
- Test: `tests/unit/tracing/test_cleanup.py`

- [ ] **Step 1: 编写测试用例**
```python
def test_cleanup_expired_traces():
    from src.core.tracing.cleanup import cleanup_expired_traces
    from datetime import datetime, timedelta
    
    # 创建过期数据（31 天前）
    expired_date = datetime.utcnow() - timedelta(days=31)
    # ... 插入测试数据 ...
    
    deleted_count = cleanup_expired_traces(retention_days=30, batch_size=100)
    assert deleted_count >= 1

def test_cleanup_dry_run():
    from src.core.tracing.cleanup import cleanup_expired_traces
    
    deleted_count = cleanup_expired_traces(retention_days=30, dry_run=True)
    assert deleted_count == 0  # dry_run 不删除
```

- [ ] **Step 2: 实现清理逻辑**
```python
# src/core/tracing/cleanup.py
from datetime import datetime, timedelta
from sqlalchemy import delete
from src.models.trace import Trace
from src.models.llm_call_log import LLMCallLog
from src.database import get_session

def cleanup_expired_traces(
    retention_days: int = 30,
    batch_size: int = 1000,
    dry_run: bool = False,
) -> int:
    """清理过期 Trace 数据
    
    Args:
        retention_days: 保留天数
        batch_size: 单次处理批次大小
        dry_run: 是否仅模拟执行
    
    Returns:
        删除的记录数
    """
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    total_deleted = 0
    
    with get_session() as session:
        # 查询过期的 trace_id
        expired_traces = (
            session.query(Trace.trace_id)
            .filter(Trace.created_at < cutoff_date)
            .limit(batch_size)
            .all()
        )
        
        if not expired_traces:
            return 0
        
        expired_ids = [t.trace_id for t in expired_traces]
        
        if not dry_run:
            # 删除关联的 LLMCallLog
            session.execute(
                delete(LLMCallLog).where(LLMCallLog.trace_id.in_(expired_ids))
            )
            # 删除 Trace
            session.execute(
                delete(Trace).where(Trace.trace_id.in_(expired_ids))
            )
            session.commit()
        
        total_deleted = len(expired_ids)
    
    return total_deleted
```

- [ ] **Step 3: 注册 APScheduler 定时任务**
```python
# 在 APScheduler 配置中添加
from apscheduler.schedulers.background import BackgroundScheduler
from src.core.tracing.cleanup import cleanup_expired_traces

scheduler = BackgroundScheduler()
scheduler.add_job(
    cleanup_expired_traces,
    "cron",
    hour=2,
    minute=0,
    kwargs={"retention_days": 30, "batch_size": 1000},
    max_instances=1,  # 防止并发执行
)
scheduler.start()
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/unit/tracing/test_cleanup.py -v`
Expected: PASS

---

### Task 3.2.3: 配置项集中化

**Files:**
- Modify: `src/config/modules/monitoring.py` (新建或现有模块)
- Test: `tests/config/test_monitoring_config.py`

- [ ] **Step 1: 定义配置模型**
```python
# src/config/modules/monitoring.py
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class TracingConfig(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")
    
    enabled: bool = Field(default=True, description="是否启用追踪")
    sample_rate: float = Field(default=1.0, ge=0.0, le=1.0, description="采样率")
    error_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0, description="错误采样率")
    truncate_length: int = Field(default=8000, gt=0, description="截断长度")
    full_content_enabled: bool = Field(default=False, description="是否存储完整内容")
    full_content_dir: str = Field(default="storage/traces", description="完整内容存储目录")
    ttl_days: int = Field(default=30, gt=0, description="数据保留天数")
    cleanup_batch_size: int = Field(default=1000, gt=0, description="清理批次大小")
```

- [ ] **Step 2: 运行测试验证通过**
Run: `pytest tests/config/test_monitoring_config.py -v`
Expected: PASS

---

## 验收标准

- [ ] 截断策略正确执行，超长内容被截断
- [ ] 完整内容可选存储到本地文件
- [ ] TTL 清理任务定时执行，过期数据被删除
- [ ] dry_run 模式不删除数据
- [ ] 配置项可通过 ConfigManager 热更新

---

**上一阶段:** [01-trace-model.md](./05-phase-3-01-trace-model.md)  
**下一阶段:** [03-instrumentation.md](./05-phase-3-03-instrumentation.md)
