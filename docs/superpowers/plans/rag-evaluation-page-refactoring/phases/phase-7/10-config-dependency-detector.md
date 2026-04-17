# 10 - 配置参数依赖检测器 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 10 - 配置参数依赖检测器

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
> **需求点**: 10
> **需求来源**: spec `07c-prompt-impact-analysis.md`

## 目标

实现检测提示词中引用的配置参数的功能。

## 方案设计

### 检测逻辑

```python
# backend/src/service/config_dependency_detector.py

import re

class ConfigDependencyDetector:
    async def detect(self, prompt_key: str, new_content: str) -> list[ConfigDependency]:
        """检测提示词中引用的配置参数"""
        # 1. 获取所有配置参数列表
        all_configs = await self._get_all_config_params()
        
        # 2. 扫描内容中的配置参数引用
        dependencies = []
        for param in all_configs:
            pattern = r'\{' + re.escape(param.key) + r'\}'
            if re.search(pattern, new_content):
                dependencies.append(ConfigDependency(
                    param=param.key,
                    category=param.category,
                    description=param.description_zh,
                    current_value=param.current_value
                ))
        
        return dependencies
    
    async def _get_all_config_params(self) -> list[ConfigParam]:
        """获取所有配置参数"""
        # 从 ConfigMetadata 表获取
        pass
```

### 验收标准

- [ ] 正确检测提示词中的配置参数引用
- [ ] 返回参数名、分类、说明、当前值
