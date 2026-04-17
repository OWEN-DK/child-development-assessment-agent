# 06 - CSV 导出（前端） Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 06 - CSV 导出（前端）

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
> **需求点**: 6
> **需求来源**: spec `04-frontend-pages.md` §4.10

## 目标

实现前端使用 papaparse 生成 CSV 导出文件，包含用例执行明细。

## 方案设计

### 实现方式

1. 从 API 获取用例明细数据
2. 使用 papaparse 转换为 CSV
3. 触发浏览器下载

### 前端实现

```typescript
// src/features/rag-eval/utils/export.ts

import Papa from 'papaparse'

interface CaseResult {
  query: string
  age: number
  domain: string
  hit_at_1: number
  hit_at_3: number
  hit_at_5: number
  status: 'pass' | 'fail'
}

export async function exportCasesToCSV(runId: string, fileName: string) {
  // 1. 获取用例明细数据
  const response = await fetch(`/api/runs/${runId}/results`)
  const data = await response.json()
  const cases: CaseResult[] = data.items
  
  // 2. 转换为 CSV 格式
  const csvData = cases.map(c => ({
    '查询': c.query,
    '年龄': c.age,
    '领域': c.domain,
    'hit@1': c.hit_at_1,
    'hit@3': c.hit_at_3,
    'hit@5': c.hit_at_5,
    '状态': c.status === 'pass' ? '通过' : '失败'
  }))
  
  // 3. 生成并下载 CSV
  const csv = Papa.unparse(csvData)
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  
  const link = document.createElement('a')
  link.href = url
  link.download = `${fileName}.csv`
  link.click()
  
  URL.revokeObjectURL(url)
}
```

### 交互流程

1. 用户点击 [导出] → [CSV]
2. 前端获取用例明细数据
3. 使用 papaparse 生成 CSV
4. 触发浏览器下载

### 验收标准

- [ ] 使用 papaparse 生成 CSV
- [ ] 包含用例执行明细
- [ ] 中文列名
- [ ] UTF-8 编码（含 BOM）
- [ ] 触发浏览器下载
