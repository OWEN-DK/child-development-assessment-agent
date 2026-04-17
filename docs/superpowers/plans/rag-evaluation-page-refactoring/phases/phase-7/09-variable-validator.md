# 09 - 变量校验器 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 09 - 变量校验器

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
> **需求点**: 9
> **需求来源**: spec `07c-prompt-impact-analysis.md`

## 目标

实现校验提示词变量新增/删除/修改的功能。

## 方案设计

### 校验逻辑

```python
# backend/src/service/variable_validator.py

import re

class VariableValidator:
    async def validate(self, prompt_key: str, new_content: str) -> VariableChanges:
        """校验提示词变量变更"""
        # 1. 获取当前版本的变量列表
        current_vars = await self._get_current_variables(prompt_key)
        
        # 2. 提取新内容中的变量
        new_vars = set(re.findall(r'\{(\w+)\}', new_content))
        
        # 3. 计算差异
        added = list(new_vars - current_vars)
        removed = list(current_vars - new_vars)
        modified = []  # 变量名相同但类型/必填变化的情况
        
        return VariableChanges(
            added=added,
            removed=removed,
            modified=modified
        )
    
    async def _get_current_variables(self, prompt_key: str) -> set[str]:
        """获取当前版本的变量列表"""
        # 从 PromptVersion.variables_extracted 或 PromptMetadata.variables_schema 获取
        pass
```

### 验收标准

- [ ] 正确检测变量新增
- [ ] 正确检测变量删除
- [ ] 正确检测变量修改
