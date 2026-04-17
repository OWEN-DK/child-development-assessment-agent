# 01 - 推荐模式面板（三种模式） Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 01 - 推荐模式面板（三种模式）

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
> **需求点**: 1
> **需求来源**: spec `04-frontend-pages.md` §4.2

## 目标

实现推荐模式面板的三种模式切换：推荐模式（默认）、向导模式、专家模式。

## 方案设计

### 组件结构

```
src/features/rag-eval/components/RecommendationPanel/
├── index.tsx                    # 入口组件，管理模式状态
├── RecommendationMode.tsx       # 推荐模式（默认）
├── WizardMode.tsx               # 向导模式
├── ExpertMode.tsx               # 专家模式
├── ModeSwitcher.tsx             # 模式切换器
└── types.ts                     # 类型定义
```

### 三种模式定义

| 模式 | 定位 | 展示内容 | 触发场景 |
|------|------|---------|---------|
| **推荐模式** (默认) | 报告驱动，展示诊断发现 | 推荐修改区 + 影响预览 + 原因解释 | 报告页面默认进入 |
| **向导模式** | 按功能域浏览 | 按功能域分组（检索/重排序/年龄过滤/分块），关键参数优先 | 用户主动切换 |
| **专家模式** | 全量控制 | 全部 RAG 配置参数树 + 全部提示词列表 | 高级用户主动切换 |

### 状态管理

使用 Zustand store 管理面板状态：

```typescript
interface RecommendationPanelState {
  mode: 'recommendation' | 'wizard' | 'expert'
  layout: 'fixed' | 'drawer'
  adoptedSuggestions: AdoptedSuggestion[]
  ignoredSuggestions: IgnoredSuggestion[]
  setMode: (mode: ...) => void
  setLayout: (layout: ...) => void
  adoptSuggestion: (suggestion: ...) => void
  ignoreSuggestion: (suggestion: ..., scope: 'report' | 'test_set') => void
  restoreIgnored: (id: string) => void
}
```

### 推荐模式布局

```
┌─────────────────────────────────────────────────────┐
│  🔧 配置与提示词分析 (N 项可优化)                    │
│  面板模式: [推荐] [向导] [专家]  布局: [固定] [抽屉] │
├─────────────────────────────────────────────────────┤
│  ═══ 推荐修改 (N) ═══                               │
│  [推荐项列表 - 每项包含：为什么改/预期影响/风险/操作] │
├─────────────────────────────────────────────────────┤
│  ═══ 其他 RAG 配置 (可手动调整) ▼ ═══               │
│  [按功能域分组的配置项]                              │
├─────────────────────────────────────────────────────┤
│  ═══ 其他提示词 (可手动编辑) ▼ ═══                  │
│  [按分类分组的提示词列表]                            │
├─────────────────────────────────────────────────────┤
│  已采纳的修改 (N): [审查已采纳项 ▶]                  │
│  [查看已忽略 (N)]                                    │
└─────────────────────────────────────────────────────┘
```

### 每个推荐项的数据结构

```typescript
interface TuningSuggestion {
  id: string
  type: 'config' | 'prompt'
  param_name: string              // 参数名或 prompt_key
  name_zh: string                 // 中文名称
  current_value: any              // 当前值
  suggested_value: any            // 建议值
  reason: string                  // 为什么改
  expected_effect: {              // 预期影响
    metric: string
    from: number
    to_range: [number, number]
  }
  risk: string                    // 风险说明
  history_reference?: {           // 历史参考
    version: string
    change: string
    effect: string
  }
}
```

### 验收标准

- [ ] 三种模式可正常切换，展示内容符合定义
- [ ] 推荐模式为默认模式，报告页面进入时自动展示
- [ ] 每个推荐项展示：为什么改、预期影响、风险、历史参考
- [ ] 模式切换器位于面板顶部，状态持久化（sessionStorage）
- [ ] 推荐项支持 [查看对比] [预览影响] [采纳] [忽略] 操作
