# 07 - JSON 导出（前端） Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 07 - JSON 导出（前端）

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

> **Phase**: 6
> **需求点**: 7
> **需求来源**: spec `04-frontend-pages.md` §4.10

## 目标

实现前端直接从报告 API 响应数据下载为 JSON 文件，包含完整报告数据。

## 方案设计

### 实现方式

1. 从报告 API 获取完整数据
2. 直接转换为 JSON 文件
3. 触发浏览器下载

### 前端实现

```typescript
// src/features/rag-eval/utils/export.ts

export async function exportReportToJSON(reportId: string, fileName: string) {
  // 1. 获取完整报告数据
  const response = await fetch(`/api/reports/${reportId}`)
  const reportData = await response.json()
  
  // 2. 生成 JSON 文件
  const json = JSON.stringify(reportData, null, 2)
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  
  // 3. 触发下载
  const link = document.createElement('a')
  link.href = url
  link.download = `${fileName}.json`
  link.click()
  
  URL.revokeObjectURL(url)
}
```

### 导出内容

```json
{
  "report_id": "uuid",
  "test_set_name": "感统训练测试集",
  "config_version": "v2.3",
  "run_time": "2026-04-16T10:30:00Z",
  "metrics": {
    "p_at_5": 0.53,
    "r_at_5": 1.00,
    "f1": 0.69,
    "mrr": 0.72,
    "ndcg": 0.65
  },
  "validation_results": [
    {
      "layer": "layer1_rule_engine",
      "name": "规则引擎",
      "issue_count": 3,
      "suggestion_count": 3,
      "suggestions": [...]
    }
  ],
  "suggestions": [...],
  "case_results": [...]
}
```

### 验收标准

- [ ] 从报告 API 获取完整数据
- [ ] 生成格式化的 JSON 文件
- [ ] 包含所有校验层原始结果
- [ ] 触发浏览器下载
