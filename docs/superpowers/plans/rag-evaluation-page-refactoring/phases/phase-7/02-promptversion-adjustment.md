# 02 - PromptVersion 调整 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 02 - PromptVersion 调整

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
> **需求点**: 2
> **需求来源**: spec `07a-prompt-data-model.md` §2.2

## 目标

调整 PromptVersion 模型，新增 variables_extracted 和 change_impact 字段。

## 方案设计

### 字段变更

| 字段 | 类型 | 变更 | 说明 |
|------|------|------|------|
| id | CHAR(36) | 改为 UUID | 原为 string 格式 "{prompt_key}_{version}" |
| version_label | VARCHAR(64) | 重命名 | 原字段名 `version`，改为 `version_label` 与 ConfigVersion 统一 |
| variables_extracted | JSON | 新增 | 自动提取的变量列表（保存时从 content 中提取） |
| change_impact | JSON | 新增 | 变更影响分析 |

### 保留字段

prompt_key, content, content_hash, description, created_by, created_at

### 删除字段

- `variables` - 删除，使用 variables_extracted 替代
- `tags` - 删除
- `fallback` - 删除，降级逻辑由 prompts_fallback.py 独立处理

### change_impact 格式

```json
{
  "variables_added": ["new_var"],
  "variables_removed": ["old_var"],
  "variables_modified": ["modified_var"],
  "config_dependencies_changed": true,
  "affected_code_files": ["src/service/retrieval_service.py"]
}
```

### 变量自动提取

```python
# backend/src/service/prompt_service.py

import re

def extract_variables(content: str) -> list[str]:
    """从提示词内容中提取变量 {variable}"""
    pattern = r'\{(\w+)\}'
    return list(set(re.findall(pattern, content)))
```

### 代码修改清单

| 变更 | 修改方式 | 涉及文件 |
|------|---------|---------|
| `PromptVersion.id` 格式变更 | 所有通过 ID 查询的代码改为 UUID 查询 | `backend/src/core/prompt/manager.py` |
| `PromptVersion.version` 重命名 | 全局替换为 `version_label` | 所有引用 `.version` 属性的代码 |
| `PromptVersion.variables` | 删除该字段，所有读取改为 `variables_extracted` | `backend/src/core/prompt/manager.py` |
| `PromptVersion.fallback` | 删除该字段，降级逻辑由 prompts_fallback.py 处理 | `backend/src/core/prompt/models.py` |
| `PromptVersion.tags` | 删除该字段 | `backend/src/core/prompt/models.py` |

### 验收标准

- [ ] id 字段类型改为 CHAR(36) UUID
- [ ] version 字段重命名为 version_label
- [ ] variables_extracted 字段新增，保存时自动提取
- [ ] change_impact 字段新增
- [ ] variables/tags/fallback 字段删除
- [ ] 所有引用旧字段的代码已更新
