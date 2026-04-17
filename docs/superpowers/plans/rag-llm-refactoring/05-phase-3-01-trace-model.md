# Phase 3.1: Trace/Span 数据模型

> **前置文档:** [Overview](./05-phase-3-00-overview.md)
> **状态:** ⏳ 完全待实现

## 数据模型设计

### 1. 新增 `traces` 表

用于表示一次完整的工作流执行（如一次评估请求、一次测试运行），与 `LLMCallLog` 建立一对多关系。

| 字段 | 类型 | 说明 |
|------|------|------|
| `trace_id` | String(64) PK | 唯一追踪 ID (UUID) |
| `name` | String(255) | 追踪名称 (如 "assessment_run", "test_batch_execution") |
| `user_id` | String(64) | 发起用户 ID (可选) |
| `session_id` | String(64) | 会话 ID (可选) |
| `metadata` | JSON | 附加上下文 (结构化字段，见下方 Pydantic 定义) |
| `start_time` | DateTime | 追踪开始时间 |
| `end_time` | DateTime | 追踪结束时间 |
| `total_duration_ms` | Integer | 总耗时 (毫秒) |
| `total_tokens` | Integer | 总 Token 消耗 |
| `total_cost` | DECIMAL(10,4) | 总成本 (估算) |
| `status` | Enum | success/failed/partial |
| `created_at` | DateTime | 创建时间 |

#### metadata 字段结构化定义

为避免随意写入，使用 Pydantic 模型约束 metadata 结构：

```python
# src/core/tracing/schemas.py
from pydantic import BaseModel, Field
from typing import Optional

class TraceMetadata(BaseModel):
    """Trace metadata 结构化模型"""
    child_profile_id: Optional[str] = Field(None, description="儿童档案 ID")
    test_run_id: Optional[str] = Field(None, description="测试运行 ID")
    test_set_id: Optional[str] = Field(None, description="测试集 ID")
    test_case_id: Optional[str] = Field(None, description="测试用例 ID")
    document_id: Optional[str] = Field(None, description="文档 ID")
    model: Optional[str] = Field(None, description="使用的模型名称")
    provider: Optional[str] = Field(None, description="模型提供商")
    extra: Optional[dict] = Field(None, description="其他自定义字段")
```

写入时通过 `metadata.model_dump()` 转为 JSON，确保字段一致性。

### 2. 扩展 `llm_call_logs` 表

将单次 LLM 调用作为 Trace 中的 Span，增加以下关键字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `trace_id` | String(64) | 关联的追踪 ID (外键 → traces.trace_id) |
| `span_id` | String(64) | 当前 Span 唯一 ID (UUID) |
| `parent_span_id` | String(64) | 父 Span ID (用于构建层级树) |
| `prompt_messages` | TEXT | 截断后的输入消息数组 (JSON 格式，默认 ≤8000 字符) |
| `completion_message` | TEXT | 截断后的输出内容 (默认 ≤8000 字符) |
| `full_prompt_path` | String(512) | 完整输入内容的本地文件路径 (可选，截断时生效) |
| `full_completion_path` | String(512) | 完整输出内容的本地文件路径 (可选，截断时生效) |
| `call_parameters` | JSON | 实际调用参数 (provider, temperature, max_tokens, top_p 等) |
| `model_parameters` | JSON | 模型专属参数 |
| `user_id` | String(64) | 发起用户 ID |
| `session_id` | String(64) | 会话 ID |
| `cost` | DECIMAL(10,4) | 单次调用成本 (估算) |
| `tags` | JSON | 分类标签 (如 ["assessment", "qwen-plus"]) |
| `tokens` | Integer | 总 Token 消耗 (input + output) |
| `completion_start_time_ms` | Integer | 首 Token 延迟 (Time to First Token) |
| `level` | Enum | INFO/WARNING/ERROR |

### 3. 索引设计

| 索引名 | 字段 | 类型 | 说明 |
|--------|------|------|------|
| `idx_user_id` | `user_id` | 普通索引 | 加速按用户筛选 |
| `idx_created_at` | `created_at` | 普通索引 | 加速按时间范围查询 |
| `idx_trace_status` | `status`, `created_at` | 复合索引 | 加速状态 + 时间筛选 |
| `idx_span_id` | `span_id` | 唯一索引 | 加速按 Span 查询 |
| `idx_llm_trace_id` | `trace_id` | 普通索引 | 加速按 Trace 查询关联 Span |

---

## 实施任务

### Task 3.1.1: 创建 Trace SQLAlchemy 模型

**Files:**
- Create: `src/models/trace.py`
- Test: `tests/unit/tracing/test_trace_model.py`

- [ ] **Step 1: 编写测试用例**
```python
def test_trace_model_creation():
    from src.models.trace import Trace, TraceStatus
    
    trace = Trace(
        trace_id="test-trace-001",
        name="assessment_run",
        user_id="user-123",
        metadata={"child_profile_id": "cp-456"},
        status=TraceStatus.SUCCESS,
    )
    assert trace.trace_id == "test-trace-001"
    assert trace.status == TraceStatus.SUCCESS
    assert trace.total_tokens == 0  # 默认值
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/unit/tracing/test_trace_model.py::test_trace_model_creation -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.models.trace'"

- [ ] **Step 3: 实现 Trace 模型**
```python
# src/models/trace.py
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Enum, JSON, DECIMAL
from sqlalchemy.orm import declarative_base
from decimal import Decimal

Base = declarative_base()

class TraceStatus(enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"

class Trace(Base):
    __tablename__ = "traces"
    
    trace_id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    user_id = Column(String(64), nullable=True)
    session_id = Column(String(64), nullable=True)
    metadata = Column(JSON, nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    total_duration_ms = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(DECIMAL(10, 4), default=Decimal("0.0000"))
    status = Column(Enum(TraceStatus, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/unit/tracing/test_trace_model.py -v`
Expected: PASS

---

### Task 3.1.2: 扩展 LLMCallLog 模型

**Files:**
- Modify: `src/models/llm_call_log.py` (或现有模型文件)
- Test: `tests/unit/tracing/test_llm_call_log_model.py`

- [ ] **Step 1: 编写测试用例**
```python
def test_llm_call_log_span_fields():
    from src.models.llm_call_log import LLMCallLog, CallLevel
    
    log = LLMCallLog(
        trace_id="test-trace-001",
        span_id="span-001",
        parent_span_id=None,
        prompt_messages=[{"role": "system", "content": "test"}],
        completion_message="test response",
        call_parameters={"provider": "dashscope", "temperature": 0.7},
        level=CallLevel.INFO,
    )
    assert log.trace_id == "test-trace-001"
    assert log.span_id == "span-001"
    assert log.parent_span_id is None
    assert log.level == CallLevel.INFO
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/unit/tracing/test_llm_call_log_model.py::test_llm_call_log_span_fields -v`
Expected: FAIL with 新增字段不存在

- [ ] **Step 3: 扩展 LLMCallLog 模型**
```python
# 在现有 LLMCallLog 模型中新增字段
class CallLevel(enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

class LLMCallLog(Base):
    # ... 现有字段保持不变 ...
    
    # 新增 Trace/Span 字段
    trace_id = Column(String(64), nullable=True)
    span_id = Column(String(64), nullable=True)
    parent_span_id = Column(String(64), nullable=True)
    prompt_messages = Column(JSON, nullable=True)
    completion_message = Column(TEXT, nullable=True)
    call_parameters = Column(JSON, nullable=True)
    model_parameters = Column(JSON, nullable=True)
    cost = Column(DECIMAL(10, 4), nullable=True)
    tags = Column(JSON, nullable=True)
    tokens = Column(Integer, nullable=True)
    completion_start_time_ms = Column(Integer, nullable=True)
    level = Column(Enum(CallLevel, values_callable=lambda obj: [e.value for e in obj]), default=CallLevel.INFO)
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/unit/tracing/test_llm_call_log_model.py -v`
Expected: PASS

---

### Task 3.1.3: 创建 Alembic 迁移脚本

**Files:**
- Create: `alembic/versions/xxxx_add_tracing_tables.py`
- Test: `alembic upgrade head && alembic downgrade -1`

- [ ] **Step 1: 生成迁移脚本**
Run: `cd backend && alembic revision -m "add_tracing_tables"`

- [ ] **Step 2: 编写迁移逻辑**
```python
# alembic/versions/xxxx_add_tracing_tables.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    # 创建 traces 表
    op.create_table(
        "traces",
        sa.Column("trace_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("start_time", sa.DateTime, nullable=False),
        sa.Column("end_time", sa.DateTime, nullable=True),
        sa.Column("total_duration_ms", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("total_tokens", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("total_cost", sa.DECIMAL(10, 4), server_default=sa.text("0.0000"), nullable=False),
        sa.Column("status", sa.Enum("success", "failed", "partial", name="trace_status"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    
    # 创建索引 (注: trace_id 为 PK，MySQL 自动建索引，无需额外创建)
    op.create_index("idx_user_id", "traces", ["user_id"])
    op.create_index("idx_created_at", "traces", ["created_at"])
    op.create_index("idx_trace_status", "traces", ["status", "created_at"])
    
    # 扩展 llm_call_logs 表
    op.add_column("llm_call_logs", sa.Column("trace_id", sa.String(64), nullable=True))
    op.add_column("llm_call_logs", sa.Column("span_id", sa.String(64), nullable=True))
    op.add_column("llm_call_logs", sa.Column("parent_span_id", sa.String(64), nullable=True))
    op.add_column("llm_call_logs", sa.Column("prompt_messages", sa.TEXT, nullable=True))
    op.add_column("llm_call_logs", sa.Column("completion_message", sa.TEXT, nullable=True))
    op.add_column("llm_call_logs", sa.Column("full_prompt_path", sa.String(512), nullable=True))
    op.add_column("llm_call_logs", sa.Column("full_completion_path", sa.String(512), nullable=True))
    op.add_column("llm_call_logs", sa.Column("call_parameters", sa.JSON, nullable=True))
    op.add_column("llm_call_logs", sa.Column("model_parameters", sa.JSON, nullable=True))
    op.add_column("llm_call_logs", sa.Column("cost", sa.DECIMAL(10, 4), nullable=True))
    op.add_column("llm_call_logs", sa.Column("tags", sa.JSON, nullable=True))
    op.add_column("llm_call_logs", sa.Column("tokens", sa.Integer, nullable=True))
    op.add_column("llm_call_logs", sa.Column("completion_start_time_ms", sa.Integer, nullable=True))
    op.add_column("llm_call_logs", sa.Column("level", sa.Enum("INFO", "WARNING", "ERROR", name="call_level"), server_default="INFO"))
    
    # 创建索引
    op.create_index("idx_span_id", "llm_call_logs", ["span_id"], unique=True)
    op.create_index("idx_llm_trace_id", "llm_call_logs", ["trace_id"])

def downgrade():
    # 1. 先删除索引
    op.drop_index("idx_llm_trace_id", "llm_call_logs")
    op.drop_index("idx_span_id", "llm_call_logs")
    op.drop_index("idx_trace_status", "traces")
    op.drop_index("idx_created_at", "traces")
    op.drop_index("idx_user_id", "traces")
    
    # 2. 删除扩展字段 (先删 column，再处理 ENUM 类型)
    op.drop_column("llm_call_logs", "level")
    op.drop_column("llm_call_logs", "tokens")
    op.drop_column("llm_call_logs", "completion_start_time_ms")
    op.drop_column("llm_call_logs", "tags")
    op.drop_column("llm_call_logs", "cost")
    op.drop_column("llm_call_logs", "model_parameters")
    op.drop_column("llm_call_logs", "call_parameters")
    op.drop_column("llm_call_logs", "full_completion_path")
    op.drop_column("llm_call_logs", "full_prompt_path")
    op.drop_column("llm_call_logs", "completion_message")
    op.drop_column("llm_call_logs", "prompt_messages")
    op.drop_column("llm_call_logs", "parent_span_id")
    op.drop_column("llm_call_logs", "span_id")
    op.drop_column("llm_call_logs", "trace_id")
    
    # 3. 删除 traces 表
    op.drop_table("traces")
    
    # 4. 最后删除 MySQL ENUM 类型 (必须在所有引用 column 删除后执行)
    op.execute("DROP TYPE IF EXISTS call_level")
    op.execute("DROP TYPE IF EXISTS trace_status")
```

- [ ] **Step 3: 验证迁移**
Run: `cd backend && alembic upgrade head`
Expected: 无错误，traces 表创建成功，llm_call_logs 表扩展成功

Run: `cd backend && alembic downgrade -1`
Expected: 无错误，traces 表删除成功，llm_call_logs 表恢复原状

---

### Task 3.1.4: 创建模型定价配置

**Files:**
- Modify: `src/config/modules/models/llm.py`
- Test: `tests/unit/tracing/test_cost_calculation.py`

- [ ] **Step 1: 编写测试用例**
```python
def test_cost_calculation():
    from src.core.tracing.cost import calculate_cost
    
    # 已知模型
    cost = calculate_cost(model="qwen-plus", input_tokens=1000, output_tokens=500)
    assert cost > 0
    
    # 未配置模型
    cost = calculate_cost(model="unknown-model", input_tokens=1000, output_tokens=500)
    assert cost is None
```

- [ ] **Step 2: 实现成本计算逻辑**
```python
# src/core/tracing/cost.py
from decimal import Decimal
from typing import Optional

def _get_model_pricing() -> dict:
    """从 ConfigManager 动态加载模型定价表，禁止硬编码"""
    from src.config import get_config
    return get_config("models.llm.model_pricing") or {}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> Optional[Decimal]:
    """计算单次 LLM 调用成本
    
    Args:
        model: 模型名称
        input_tokens: 输入 Token 数
        output_tokens: 输出 Token 数
    
    Returns:
        成本 (Decimal)，未配置定价的模型返回 None
    """
    pricing_table = _get_model_pricing()
    if model not in pricing_table:
        return None
    
    pricing = pricing_table[model]
    input_cost = (input_tokens / 1_000_000) * pricing["input_per_million"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_million"]
    
    return Decimal(str(input_cost + output_cost))
```

- [ ] **Step 3: 运行测试验证通过**
Run: `pytest tests/unit/tracing/test_cost_calculation.py -v`
Expected: PASS

---

## 验收标准

- [ ] Trace 模型字段完整，Enum 映射正确
- [ ] LLMCallLog 扩展字段完整，与现有字段兼容
- [ ] Alembic 迁移可正向/反向执行
- [ ] 索引创建正确，覆盖查询场景
- [ ] 成本计算逻辑正确，未配置模型返回 None

---

**上一阶段:** [Overview](./05-phase-3-00-overview.md)  
**下一阶段:** [02-storage-design.md](./05-phase-3-02-storage-design.md)
