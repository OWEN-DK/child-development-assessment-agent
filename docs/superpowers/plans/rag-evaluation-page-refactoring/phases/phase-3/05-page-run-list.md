# 05 - 运行历史列表页 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 05 - 运行历史列表页

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

`/rag-eval/runs`

## 实施文件

`frontend/src/features/rag-eval/pages/RunListPage.tsx`

## 页面功能

1. 运行记录列表展示
2. 按状态筛选（运行中/已完成/失败）
3. 按测试集筛选
4. 按时间范围筛选
5. 点击进入运行详情
6. 删除运行记录

## 数据表格

| 列名 | 字段 | 宽度 | 说明 |
|------|------|------|------|
| 运行名称 | name | 自适应 | 可点击跳转详情 |
| 测试集 | test_set_name | 200px | 关联测试集名称 |
| 状态 | status | 100px | 标签（运行中/已完成/失败） |
| 用例数 | total_cases | 80px | - |
| 完成数 | completed_cases | 80px | 运行中时显示进度 |
| 配置版本 | config_version_label | 100px | 运行时使用的配置版本 |
| 耗时 | duration | 100px | 运行耗时 |
| 开始时间 | started_at | 160px | - |
| 操作 | - | 80px | 删除 |

## API 接口

### 获取运行列表

```
GET /api/runs?page=1&page_size=20&status=&test_set_id=&date_from=&date_to=
```

响应：
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "3-5岁运动发展测试集-第3次运行",
      "test_set_id": "uuid",
      "test_set_name": "3-5岁运动发展测试集",
      "status": "completed",
      "total_cases": 50,
      "completed_cases": 50,
      "config_version_id": "uuid",
      "config_version_label": "v1.2.0",
      "started_at": "2026-04-17T10:00:00Z",
      "completed_at": "2026-04-17T10:03:00Z",
      "duration_seconds": 180
    }
  ],
  "total": 25,
  "page": 1,
  "page_size": 20
}
```

### 删除运行

```
DELETE /api/runs/{id}
```

## 状态标签

| 状态 | 颜色 | 图标 |
|------|------|------|
| running | blue | LoadingOutlined |
| completed | green | CheckCircleOutlined |
| failed | red | CloseCircleOutlined |

## 交互细节

- 运行中的记录显示实时进度条（通过 SSE 更新）
- 点击运行名称跳转到运行详情页
- 点击测试集名称跳转到测试集详情页
- 删除运行中的记录需确认，并提示"将终止正在运行的测试"
- 空状态："暂无运行记录，请先在测试集中运行测试"
