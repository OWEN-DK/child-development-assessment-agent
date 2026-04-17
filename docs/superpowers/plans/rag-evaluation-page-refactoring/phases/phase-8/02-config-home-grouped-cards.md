# 02 - 配置主页（分组卡片） Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 02 - 配置主页（分组卡片）

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

> **Phase**: 8
> **需求点**: 2
> **需求来源**: spec `08b-config-frontend-pages.md`

## 目标

实现配置主页按功能域分组展示：RAG 检索/分块/LLM/数据库/Redis/日志/业务规则。

## 方案设计

### 页面布局

```
┌─────────────────────────────────────────────────────┐
│  配置管理                                            │
├─────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │ 🔍 RAG 检索  │ │ 📄 RAG 分块 │ │ 🧠 LLM 模型 │   │
│  │ 6 项配置     │ │ 3 项配置     │ │ 3 项配置     │   │
│  │ [进入]      │ │ [进入]      │ │ [进入]      │   │
│  └─────────────┘ └─────────────┘ └─────────────┘   │
│                                                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │ 💾 数据库    │ │ ⚡ Redis    │ │ 📊 日志     │   │
│  │ 2 项配置     │ │ 2 项配置     │ │ 2 项配置     │   │
│  │ [进入]      │ │ [进入]      │ │ [进入]      │   │
│  └─────────────┘ └─────────────┘ └─────────────┘   │
│                                                     │
│  ┌─────────────┐                                    │
│  │ 📐 业务规则  │                                    │
│  │ 3 项配置     │                                    │
│  │ [进入]      │                                    │
│  └─────────────┘                                    │
└─────────────────────────────────────────────────────┘
```

### 分组卡片组件

```typescript
interface ConfigGroup {
  key: string
  name_zh: string
  icon: string
  description: string
  config_count: number
  configs: ConfigItem[]
}
```

### API 端点

```
GET /api/config/groups
Response:
{
  "groups": [
    {
      "key": "rag_retrieval",
      "name_zh": "RAG 检索配置",
      "icon": "search",
      "config_count": 6,
      "configs": [
        {"key": "bm25_top_k", "name_zh": "BM25 TopK", "current_value": 10}
      ]
    }
  ]
}
```

### 验收标准

- [ ] 配置主页按功能域分组展示
- [ ] 每个分组显示配置数量
- [ ] 卡片可点击进入分类配置页
- [ ] 展示配置项摘要信息
