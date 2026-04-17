# 09 - 已忽略建议列表 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 09 - 已忽略建议列表

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

> **Phase**: 5
> **需求点**: 9
> **需求来源**: spec `04-frontend-pages.md` §4.2

## 目标

实现已忽略建议列表展示，支持 report/test_set 级别。

## 方案设计

### 数据模型

```python
# backend/src/models/rag_eval.py

class IgnoredSuggestion(Base):
    """忽略建议记录 - 独立表，支持高效跨报告查询"""
    __tablename__ = "ignored_suggestions"
    
    id = Column(CHAR(36), primary_key=True, default=uuid4)
    test_set_id = Column(CHAR(36), ForeignKey("test_sets.id", ondelete="CASCADE"), nullable=False)
    report_id = Column(CHAR(36), ForeignKey("test_reports.id", ondelete="SET NULL"), nullable=True)
    param_name = Column(VARCHAR(255), nullable=False)
    suggestion_type = Column(ENUM("config", "prompt"), nullable=False)
    ignore_scope = Column(ENUM("report", "test_set"), nullable=False, default="report")
    ignored_by = Column(VARCHAR(64), nullable=False)
    ignored_at = Column(DATETIME, nullable=False, default=datetime.utcnow)
    ignore_reason = Column(VARCHAR(500), nullable=True)
    restored = Column(BOOLEAN, nullable=False, default=False)
    restored_at = Column(DATETIME, nullable=True)
    
    # 索引
    __table_args__ = (
        Index("idx_test_set_scope_restored", "test_set_id", "ignore_scope", "restored"),
    )
```

### 前端展示

```
┌─────────────────────────────────────────────────────┐
│  已忽略建议 (N)                         [全部恢复]   │
├─────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────┐  │
│  │ 参数: BM25 TopK                                │  │
│  │ 类型: 配置建议                                  │  │
│  │ 忽略时间: 2026-04-16 10:30                     │  │
│  │ 忽略范围: 仅本次报告                           │  │
│  │ 忽略原因: (可选)                               │  │
│  │ [恢复] [删除]                                  │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │ 提示词: 查询重写 Prompt                        │  │
│  │ 类型: 提示词建议                                │  │
│  │ 忽略时间: 2026-04-16 10:32                     │  │
│  │ 忽略范围: 该测试集的所有运行                    │  │
│  │ 忽略原因: 当前配置已满足需求                    │  │
│  │ [恢复] [删除]                                  │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### API 端点

```
GET /api/ignored-suggestions?test_set_id={id}&report_id={id}
Response:
{
  "items": [
    {
      "id": "uuid",
      "param_name": "bm25_top_k",
      "name_zh": "BM25 TopK",
      "suggestion_type": "config",
      "ignore_scope": "report",
      "ignored_at": "2026-04-16T10:30:00Z",
      "ignored_by": "user_id",
      "ignore_reason": null,
      "restored": false
    }
  ],
  "total": 1
}
```

### 查询逻辑

生成推荐列表时，先查询 `IgnoredSuggestion` 表，过滤 `restored=False` 且 `ignore_scope` 匹配的记录：

```python
async def get_ignored_param_names(test_set_id: str, report_id: str, session: AsyncSession) -> set[str]:
    """获取应忽略的参数名集合"""
    result = await session.execute(
        select(IgnoredSuggestion.param_name)
        .where(
            IgnoredSuggestion.test_set_id == test_set_id,
            IgnoredSuggestion.restored == False,
            or_(
                IgnoredSuggestion.ignore_scope == "test_set",
                and_(
                    IgnoredSuggestion.ignore_scope == "report",
                    IgnoredSuggestion.report_id == report_id
                )
            )
        )
    )
    return set(row[0] for row in result.all())
```

### 验收标准

- [ ] 列表展示忽略记录的完整信息
- [ ] 支持 report 和 test_set 两种级别
- [ ] 忽略原因可选展示
- [ ] [恢复] 按钮可用
- [ ] [删除] 按钮可用（物理删除忽略记录）
