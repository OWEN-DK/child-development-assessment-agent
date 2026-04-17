# 02 - 测试集列表页 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 02 - 测试集列表页

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

`/rag-eval/test-sets`

## 实施文件

`frontend/src/features/rag-eval/pages/TestSetListPage.tsx`

## 页面功能

1. 测试集列表展示（表格）
2. 按名称搜索
3. 按来源类型筛选
4. 创建新测试集
5. 删除测试集
6. 点击进入详情页

## 数据表格

| 列名 | 字段 | 宽度 | 说明 |
|------|------|------|------|
| 名称 | name | 自适应 | 可点击跳转详情 |
| 来源类型 | source_type | 120px | 标签展示（BOOK_GENERATED/JSON_IMPORTED/MANUAL） |
| 用例数 | total_cases | 80px | 实时计算 COUNT(test_set_cases) |
| 运行次数 | run_count | 80px | 实时计算 COUNT(test_runs) |
| 最近运行 | last_run_at | 160px | 最新 test_runs.created_at |
| 创建时间 | created_at | 160px | - |
| 操作 | - | 150px | 运行测试、删除 |

## API 接口

### 获取列表

```
GET /rag/test/test-sets?page=1&page_size=20&keyword=&source_type=
```

响应：
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "3-5岁运动发展测试集",
      "source_type": "BOOK_GENERATED",
      "total_cases": 50,
      "run_count": 3,
      "last_run_at": "2026-04-17T10:00:00Z",
      "created_at": "2026-04-10T08:00:00Z"
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 20
}
```

### 创建测试集

```
POST /rag/test/test-sets
{
  "name": "新测试集",
  "description": "描述",
  "source_type": "MANUAL"
}
```

### 删除测试集

```
DELETE /rag/test/test-sets/{id}
```

## 组件结构

```
TestSetListPage
├── PageHeader (标题 + 创建按钮)
├── SearchBar (搜索框 + 来源类型筛选)
├── TestSetTable (数据表格)
│   ├── 名称列 → Link to /rag-eval/test-sets/{id}
│   ├── 来源类型 → Tag 组件
│   ├── 操作列 → [运行测试] [删除]
└── CreateTestSetModal (创建弹窗)
```

## 状态管理

使用 Zustand store：

```typescript
interface TestSetStore {
  testSets: TestSet[];
  loading: boolean;
  total: number;
  page: number;
  pageSize: number;
  keyword: string;
  sourceType: string | null;

  fetchTestSets: () => Promise<void>;
  createTestSet: (data: CreateTestSetInput) => Promise<void>;
  deleteTestSet: (id: string) => Promise<void>;
  setPagination: (page: number, pageSize: number) => void;
  setFilters: (keyword: string, sourceType: string | null) => void;
}
```

## 交互细节

- 删除操作需二次确认（Popconfirm）
- 创建成功后自动刷新列表
- 表格支持按创建时间排序
- 空状态展示引导文案："暂无测试集，点击创建开始"
