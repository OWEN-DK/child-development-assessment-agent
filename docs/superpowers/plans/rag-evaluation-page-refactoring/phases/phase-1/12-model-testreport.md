# 12 - RagEvalTestReport 模型定义 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 12 - RagEvalTestReport 模型定义

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

## 模型说明
评估报告模型，每次运行生成一份报告，包含6层校验结果和调优建议摘要。

## 实施文件
`backend/src/models/rag_eval/test_report.py`

## SQLAlchemy 模型定义
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, Float, JSON, ForeignKey, func, Index, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from src.models.rag_eval.enums import RagEvalTestReportStatus


class RagEvalTestReport(Base):
    __tablename__ = "rag_eval_test_reports"
    __table_args__ = (
        Index("idx_rag_eval_test_report_testset_created", "test_set_id", "created_at"),
        Index("idx_rag_eval_test_report_run_id", "run_id"),
        Index("idx_rag_eval_test_report_config_version", "config_version_id"),
        {"comment": "测试评估报告表"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    test_set_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_eval_test_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    config_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_eval_config_versions.id", ondelete="SET NULL"),
    )

    status: Mapped[RagEvalTestReportStatus] = mapped_column(
        SAEnum(RagEvalTestReportStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=RagEvalTestReportStatus.PROCESSING,
    )
    prompt_version_snapshot: Mapped[dict | None] = mapped_column(JSON, comment="提示词版本快照")

    overall_score: Mapped[float | None] = mapped_column(Float)
    precision: Mapped[float | None] = mapped_column(Float)
    recall: Mapped[float | None] = mapped_column(Float)
    f1: Mapped[float | None] = mapped_column(Float)
    mrr: Mapped[float | None] = mapped_column(Float)
    ndcg: Mapped[float | None] = mapped_column(Float)

    validation_results: Mapped[list | None] = mapped_column(JSON, comment="6层校验结果")
    tuning_suggestion_summary: Mapped[dict | None] = mapped_column(JSON, comment="调优建议摘要")

    created_by: Mapped[str | None] = mapped_column(String(36), comment="生成报告的用户ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    test_run: Mapped["RagEvalTestRun"] = relationship(back_populates="reports")
    test_set: Mapped["RagEvalTestSet"] = relationship(back_populates="reports")
    config_version: Mapped["RagEvalConfigVersion | None"] = relationship(back_populates="reports")
    tuning_suggestions: Mapped[list["RagEvalTuningSuggestionRecord"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    prompt_suggestions: Mapped[list["RagEvalPromptSuggestionRecord"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    ignored_suggestions: Mapped[list["RagEvalIgnoredSuggestion"]] = relationship(back_populates="report", cascade="all, delete-orphan")
```

## 字段说明
| 字段名 | 类型 | 可空 | 说明 |
|--------|------|------|------|
| id | String(36) | 否 | 主键UUID |
| run_id | String(36) | 否 | 测试运行ID，FK→rag_eval_test_runs.id |
| test_set_id | String(36) | 否 | 测试集ID，FK→rag_eval_test_sets.id |
| config_version_id | String(36) | 是 | 配置版本ID，FK→rag_eval_config_versions.id |
| status | VARCHAR(64) | 否 | PROCESSING、COMPLETED、SUPERSEDED |
| prompt_version_snapshot | JSON | 是 | 提示词版本快照 |
| overall_score | FLOAT | 是 | 综合得分 |
| precision | FLOAT | 是 | 精确率 |
| recall | FLOAT | 是 | 召回率 |
| f1 | FLOAT | 是 | F1 |
| mrr | FLOAT | 是 | MRR |
| ndcg | FLOAT | 是 | NDCG |
| validation_results | JSON | 是 | 6层校验结果 |
| tuning_suggestion_summary | JSON | 是 | 调优建议摘要 |
| created_by | String(36) | 是 | 生成报告的用户ID |
| created_at | DATETIME | 否 | 创建时间 |

## 业务规则
- TestReport 在 TestRun 完成后立即创建，初始状态为 processing（无 pending 状态）
- processing: 校验引擎正在执行 6 层校验
- completed: 所有校验完成，报告可展示
- superseded: 用户应用建议并复测后，旧报告标记为被替代
- TestRun.status = completed: 必须生成完整报告
- TestRun.status = failed: 生成部分报告（未完成的层标记 status="skipped"）
- TestRun.status = cancelled: 生成部分报告
- TestRun.status = pending/running: 不生成报告
- prompt_version_snapshot 存储完整内容而非仅引用，防止提示词被修改后无法回溯
- 不再使用 layer1_results ~ layer6_results 六列，改为单列 JSON 数组

## validation_results 中每层的 status 字段枚举值
- "completed": 校验正常完成
- "degraded": 校验降级执行
- "timeout": 校验超时
- "cancelled": 校验被用户手动取消
- "skipped": 校验被跳过

## validation_results JSON Schema 约束

为保证 6 层校验结果的结构一致性，业务层使用以下 Pydantic Schema 验证：

```python
from pydantic import BaseModel, Field
from typing import Literal, Any

class ValidationResultItem(BaseModel):
    """单层校验结果"""
    layer: int = Field(..., ge=1, le=6, description="层序号")
    status: Literal["completed", "timeout", "degraded", "cancelled", "skipped"]
    data: dict = Field(default_factory=dict, description="校验数据")
    duration_ms: int = Field(..., ge=0, description="校验耗时（毫秒）")

class ValidationResultList(BaseModel):
    """完整校验结果列表"""
    __root__: list[ValidationResultItem]
```

**使用方式**：
- 写入数据库前：`ValidationResultList.parse_obj(validation_results)` 验证结构
- 读取数据库后：反序列化为 Pydantic 模型，提供类型安全访问
- 前端 API 响应：使用相同 Schema 保证前后端契约一致

## 关联关系
- 多对1关联RagEvalTestRun
- 多对1关联RagEvalTestSet
- 多对1关联RagEvalConfigVersion
- 1对多关联RagEvalTuningSuggestionRecord
- 1对多关联RagEvalPromptSuggestionRecord
- 1对多关联RagEvalIgnoredSuggestion
