# 06 - 提示词测试沙箱页 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 06 - 提示词测试沙箱页

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

> **Phase**: 7
> **需求点**: 6
> **需求来源**: spec `07b-prompt-frontend-pages.md`

## 目标

实现提示词测试沙箱页，输入变量表单 + 预览 LLM 输出 + 新旧对比。

## 方案设计

### 页面布局

```
┌─────────────────────────────────────────────────────┐
│  测试沙箱: 查询重写提示词                            │
├─────────────────────────────────────────────────────┤
│  输入变量:                                          │
│  ┌───────────────────────────────────────────────┐  │
│  │ query: [什么是感统训练____________]            │  │
│  │ age:   [36_______________________]            │  │
│  │ [运行测试]                                     │  │
│  └───────────────────────────────────────────────┘  │
├───────────────────────────┬─────────────────────────┤
│  当前版本 (v4) 输出        │  上一版本 (v3) 输出      │
│  ┌───────────────────────┐│  ┌─────────────────────┐│
│  │ 感统训练 儿童发展      ││  │ 感统训练 感统失调   ││
│  │ 36个月                 ││  │ 感统训练方法        ││
│  └───────────────────────┘│  └─────────────────────┘│
└───────────────────────────┴─────────────────────────┘
```

### 测试流程

1. 用户填写输入变量表单
2. 点击 [运行测试]
3. 后端使用当前版本和上一版本分别调用 LLM
4. 返回两个版本的输出
5. 前端展示对比结果

### API 端点

```
POST /api/prompts/{prompt_key}/sandbox/test
Request:
{
  "version": "v4",
  "compare_with": "v3",
  "variables": {
    "query": "什么是感统训练",
    "age": 36
  }
}

Response:
{
  "current_output": "感统训练 儿童发展 36个月",
  "compare_output": "感统训练 感统失调 感统训练方法",
  "diff": {
    "added_tokens": ["儿童发展"],
    "removed_tokens": ["感统失调", "感统训练方法"]
  },
  "latency_ms": {
    "current": 245,
    "compare": 230
  }
}
```

### 验收标准

- [ ] 输入变量表单根据 variables_schema 生成
- [ ] 支持预览 LLM 输出
- [ ] 新旧版本输出对比展示
- [ ] 展示差异标记
