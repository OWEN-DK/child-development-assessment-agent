# 05 - 采纳→审查→保存三步流程 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 05 - 采纳→审查→保存三步流程

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
> **需求点**: 5
> **需求来源**: spec `04-frontend-pages.md` §4.2

## 目标

实现"采纳→审查→保存"三步分离流程，不合并为一步。

## 方案设计

### 三步流程定义

| 步骤 | 操作 | 行为 | 状态变化 |
|------|------|------|---------|
| **1. 采纳** | 用户点击推荐项的 [采纳] 按钮 | 将该修改加入"已采纳列表"，不立即生效 | `suggestion.status = 'adopted'` |
| **2. 审查** | 用户点击"审查已采纳项" | 展开抽屉式审查面板，展示所有已采纳修改的完整 diff | 面板展开，无状态变化 |
| **3. 保存** | 用户点击"保存为新版本" | 将所有已采纳的修改保存为新的 ConfigVersion 和 PromptVersion | 创建新版本，清空已采纳列表 |

### 状态机

```
pending ──[采纳]──→ adopted ──[保存]──→ saved
   │                    │
   └──[忽略]──→ ignored ──[恢复]──→ pending
                     │
                     └──[移除]──→ pending
```

### 前端状态管理

```typescript
interface SuggestionState {
  id: string
  status: 'pending' | 'adopted' | 'ignored' | 'saved'
  type: 'config' | 'prompt'
  // ... 其他字段
}

interface PanelState {
  suggestions: SuggestionState[]
  adoptedCount: number
  ignoredCount: number
  
  // Actions
  adopt(id: string): void
  ignore(id: string, scope: 'report' | 'test_set', reason?: string): void
  restoreIgnored(id: string): void
  removeFromAdopted(id: string): void
  saveAll(): Promise<SaveResult>
}
```

### 交互细节

1. **采纳操作**:
   - 点击 [采纳] 按钮
   - 按钮变为 [已采纳]（禁用状态）
   - 底部"已采纳的修改 (N)"计数 +1
   - 不触发任何后端请求

2. **审查操作**:
   - 点击 [审查已采纳项 ▶] 按钮
   - 展开抽屉式审查面板
   - 展示所有已采纳修改的完整信息
   - 支持自定义值、移除单项

3. **保存操作**:
   - 点击 [保存为新版本] 按钮
   - 触发原子保存 API（见 06-atomic-save-transaction.md）
   - 保存成功后：
     - 显示成功提示："已保存为新版本 v2.4"
     - 清空已采纳列表
     - 关闭审查面板
     - 刷新推荐列表
   - 保存失败后：
     - 显示错误提示和具体失败项
     - 保留已采纳列表（用户可重试）

### 验收标准

- [ ] 三步流程严格分离，不合并为一步
- [ ] 采纳操作不触发后端请求，仅前端状态变化
- [ ] 审查面板展示所有已采纳修改
- [ ] 保存操作触发原子保存 API
- [ ] 保存成功后清空已采纳列表并刷新
- [ ] 保存失败后保留已采纳列表并显示错误
