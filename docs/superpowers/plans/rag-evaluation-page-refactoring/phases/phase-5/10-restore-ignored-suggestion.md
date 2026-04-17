# 10 - 恢复忽略建议 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 10 - 恢复忽略建议

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
> **需求点**: 10
> **需求来源**: spec `04-frontend-pages.md` §4.2

## 目标

实现恢复忽略建议功能，恢复后重新加入推荐列表。

## 方案设计

### 恢复行为

| 恢复类型 | 行为 |
|---------|------|
| **report 级别** | 该推荐立即重新出现在当前报告的推荐列表中（无需重新运行测试） |
| **test_set 级别** | 该推荐重新出现在该测试集**所有未完成报告**的推荐列表中；对于已完成的报告，需要用户手动重新运行测试 |

### API 端点

```
POST /api/ignored-suggestions/{id}/restore
Response:
{
  "id": "uuid",
  "restored": true,
  "restored_at": "2026-04-16T11:00:00Z",
  "message": "已恢复，推荐将重新出现在推荐列表中"
}
```

### Service 层实现

```python
# backend/src/service/ignored_suggestion_service.py

async def restore_ignored_suggestion(
    suggestion_id: str,
    session: AsyncSession
) -> IgnoredSuggestion:
    """恢复忽略建议"""
    result = await session.execute(
        select(IgnoredSuggestion).where(IgnoredSuggestion.id == suggestion_id)
    )
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        raise ValueError("忽略建议不存在")
    
    suggestion.restored = True
    suggestion.restored_at = datetime.utcnow()
    await session.commit()
    
    return suggestion
```

### 恢复后的推荐展示逻辑

```python
async def get_active_suggestions(
    test_set_id: str,
    report_id: str,
    session: AsyncSession
) -> list[TuningSuggestionRecord]:
    """获取活跃的推荐列表（排除已忽略的）"""
    # 1. 查询所有推荐
    suggestions = await get_all_suggestions(test_set_id, report_id, session)
    
    # 2. 查询应忽略的参数名
    ignored_params = await get_ignored_param_names(test_set_id, report_id, session)
    
    # 3. 过滤已忽略的推荐
    return [
        s for s in suggestions
        if s.param_name not in ignored_params
    ]
```

### 前端交互

1. 用户点击 [恢复] 按钮
2. 调用 POST /api/ignored-suggestions/{id}/restore
3. 恢复成功后：
   - 该条目从已忽略列表中移除
   - 推荐列表中重新出现该推荐
   - 显示成功提示："已恢复推荐"

### 验收标准

- [ ] 恢复操作正确更新数据库记录
- [ ] report 级别恢复后立即出现在推荐列表
- [ ] test_set 级别恢复后影响范围正确
- [ ] 恢复操作不触发自动重新校验
- [ ] 前端展示恢复成功提示
