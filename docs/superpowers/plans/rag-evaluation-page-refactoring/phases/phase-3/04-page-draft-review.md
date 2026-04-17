# 04 - 草稿审核页 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 04 - 草稿审核页

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

## 路由

`/rag-eval/test-sets/{id}/drafts`

## 实施文件

`frontend/src/features/rag-eval/pages/DraftReviewPage.tsx`

## 页面功能

1. 草稿列表展示（按状态筛选）
2. 单条预览（查询语句、年龄、领域、来源文档）
3. 通过/拒绝操作
4. 批量归入测试集
5. 批量拒绝

## 页面布局

```
┌─────────────────────────────────────────────────────┐
│  ← 返回测试集详情    草稿审核                         │
│  来源文档：xxx.pdf | 草稿总数：30 | 待审核：15         │
├─────────────────────────────────────────────────────┤
│  [全部] [待审核] [已通过] [已拒绝]    [批量归入] [批量拒绝]│
├─────────────────────────────────────────────────────┤
│  ┌───┐ ┌───────────────────────────────────────┐    │
│  │ ☐ │ │ 查询：3岁儿童平衡能力发展里程碑           │    │
│  │   │ │ 年龄：36个月 | 领域：MOTOR_DEVELOPMENT   │    │
│  │   │ │ 来源：第3章 第2节                        │    │
│  │   │ │                        [通过] [拒绝]     │    │
│  ├───┤ ├───────────────────────────────────────┤    │
│  │ ☐ │ │ ...                                    │    │
│  └───┘ └───────────────────────────────────────┘    │
│                                                     │
│  分页器                                             │
└─────────────────────────────────────────────────────┘
```

## API 接口

### 获取草稿列表

```
GET /rag/test/test-sets/{id}/drafts?page=1&page_size=20&status=PENDING
```

### 通过草稿

```
POST /rag/test/drafts/{draft_id}/approve
{
  "test_set_id": "uuid"
}
```

### 拒绝草稿

```
POST /rag/test/drafts/{draft_id}/reject
{
  "reason": "拒绝原因（可选）"
}
```

### 批量归入

```
POST /rag/test/drafts/batch-approve
{
  "draft_ids": ["uuid1", "uuid2"],
  "test_set_id": "uuid"
}
```

### 批量拒绝

```
POST /rag/test/drafts/batch-reject
{
  "draft_ids": ["uuid1", "uuid2"],
  "reason": "原因（可选）"
}
```

## 状态定义

| 状态 | 值 | 说明 |
|------|-----|------|
| 待审核 | PENDING | 刚生成，等待人工审核 |
| 已通过 | APPROVED | 已归入测试集，成为正式用例 |
| 已拒绝 | REJECTED | 被拒绝，不纳入测试集 |

## 交互细节

- 支持多选批量操作
- 通过操作将草稿转为正式用例并关联到测试集
- 拒绝操作可选填写原因
- 已通过/已拒绝的草稿仍可切换查看，但不可再次操作
- 空状态：当无草稿时展示"暂无草稿，请先从书籍生成"
