# 06 - 运行详情页 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 06 - 运行详情页

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

`/rag-eval/runs/{id}`

## 实施文件

`frontend/src/features/rag-eval/pages/RunDetailPage.tsx`

## 页面功能

1. 运行基本信息展示
2. 汇总指标卡片
3. 用例执行结果列表
4. SSE 实时进度展示（运行中时）
5. 生成报告按钮（运行完成后）

## 页面布局

```
┌─────────────────────────────────────────────────────┐
│  ← 返回运行列表    运行名称                           │
│  测试集：xxx | 状态：运行中 | 配置版本：v1.2.0         │
├─────────────────────────────────────────────────────┤
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ 进度     │ │ P@1     │ │ R@5     │ │ MRR     │   │
│  │ 23/50   │ │ 0.84    │ │ 0.86    │ │ 0.71    │   │
│  │ 46%     │ │         │ │         │ │         │   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
│                                                     │
│  进度条 ████████████████░░░░░░░░░░ 46%               │
├─────────────────────────────────────────────────────┤
│  搜索用例结果 [全部] [命中@1] [未命中]                │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │ # | 查询语句 | 状态 | P@1 | R@1 | 耗时 | 得分  │  │
│  │ 1 | ...      | ✓   | 1.0 | 1.0 | 230ms| 0.95 │  │
│  │ 2 | ...      | ✗   | 0.0 | 0.5 | 180ms| 0.32 │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  分页器                               [生成评估报告]  │
└─────────────────────────────────────────────────────┘
```

## SSE 集成

运行中时，连接 SSE 实时更新：

```typescript
const { on } = useTestRunSse(runId);

useEffect(() => {
  on('progress', (event) => {
    setProgress({ current: event.current, total: event.total });
  });

  on('case_result', (event) => {
    setCaseResults(prev => [...prev, event]);
  });

  on('test_completed', (event) => {
    setMetrics(event.metrics);
    setRunStatus('completed');
  });

  on('run_failed', (event) => {
    setError(event.error);
    setRunStatus('failed');
  });
}, [on]);
```

## API 接口

### 获取运行详情

```
GET /api/runs/{id}
```

### 获取用例结果列表

```
GET /api/runs/{id}/results?page=1&page_size=20&status=&hit_at_1=
```

### 生成报告

```
POST /api/runs/{id}/report
```

## 指标卡片

运行完成后展示：

| 指标 | 说明 |
|------|------|
| P@1 | Precision at 1，首位命中率 |
| P@3 | Precision at 3，前3位命中率 |
| P@5 | Precision at 5，前5位命中率 |
| R@1 | Recall at 1 |
| R@5 | Recall at 5 |
| MRR | Mean Reciprocal Rank |
| NDCG@5 | Normalized Discounted Cumulative Gain |
| HR@5 | Hit Rate at 5 |
| 平均延迟 | 平均检索耗时 |

## 交互细节

- 运行中时，进度条和指标卡片实时更新
- 用例结果按执行顺序排列
- 点击用例可查看详细信息（检索到的文档列表、预期文档对比）
- 运行完成后，"生成评估报告"按钮可用
- 运行失败时，显示错误信息和错误码
