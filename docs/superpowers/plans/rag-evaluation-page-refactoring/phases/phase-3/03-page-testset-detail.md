# 03 - 测试集详情页 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 03 - 测试集详情页

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

`/rag-eval/test-sets/{id}`

## 实施文件

`frontend/src/features/rag-eval/pages/TestSetDetailPage.tsx`

## 页面功能

1. 测试集基本信息展示
2. 用例列表（分页、搜索、筛选）
3. 添加用例（手动/从草稿归入）
4. 移除用例
5. 运行测试（选择配置版本后触发）
6. 查看草稿审核入口

## 页面布局

```
┌─────────────────────────────────────────────────────┐
│  ← 返回          测试集名称              [运行测试]    │
│  描述：xxx                                          │
│  来源：BOOK_GENERATED | 用例数：50 | 创建时间：xxx     │
├─────────────────────────────────────────────────────┤
│  [Tab] 用例列表  [Tab] 草稿审核                      │
├─────────────────────────────────────────────────────┤
│  搜索框  [领域筛选] [难度筛选]        [添加用例]       │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │ ID | 查询语句 | 年龄 | 领域 | 难度 | 操作      │  │
│  │ ... 50 rows ...                                │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  分页器                                             │
└─────────────────────────────────────────────────────┘
```

## API 接口

### 获取测试集详情

```
GET /rag/test/test-sets/{id}
```

### 获取用例列表

```
GET /rag/test/test-sets/{id}/cases?page=1&page_size=20&keyword=&domain=&difficulty=
```

响应：
```json
{
  "items": [
    {
      "id": "uuid",
      "query": "3岁儿童大肌肉发展迟缓的表现",
      "age_months": 36,
      "domain": "MOTOR_DEVELOPMENT",
      "difficulty": "MEDIUM",
      "expected_document_ids": ["doc-1", "doc-2"],
      "created_at": "2026-04-10T08:00:00Z"
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20
}
```

### 添加用例

```
POST /rag/test/test-sets/{id}/cases
{
  "query": "查询语句",
  "age_months": 36,
  "domain": "MOTOR_DEVELOPMENT",
  "difficulty": "MEDIUM",
  "expected_document_ids": ["doc-1"]
}
```

### 移除用例

```
DELETE /rag/test/test-sets/{id}/cases/{case_id}
```

### 运行测试

```
POST /api/runs
{
  "test_set_id": "uuid",
  "name": "运行名称（可选）",
  "config_version_id": "uuid（可选，不传则使用最新配置）"
}
```

## 运行测试流程

1. 用户点击"运行测试"按钮
2. 弹出配置选择对话框（选择配置版本，默认最新）
3. 确认后调用运行 API，获取 run_id
4. 跳转到运行详情页 `/rag-eval/runs/{run_id}`，SSE 实时展示进度

## 交互细节

- 用例列表支持按领域、难度筛选
- 搜索支持模糊匹配 query 字段
- 移除用例需二次确认
- 测试集无用例时，"运行测试"按钮禁用并提示"请先添加用例"
- 草稿审核 Tab 显示草稿数量徽标
