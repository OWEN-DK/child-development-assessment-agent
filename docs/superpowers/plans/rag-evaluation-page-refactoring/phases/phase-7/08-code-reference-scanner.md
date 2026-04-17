# 08 - 代码引用扫描器 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 08 - 代码引用扫描器

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
> **需求点**: 8
> **需求来源**: spec `07c-prompt-impact-analysis.md`

## 目标

实现扫描代码中 `prompt_manager.get_prompt(key)` 位置的功能。

## 方案设计

### 扫描策略

1. 使用 AST 解析 Python 代码
2. 查找所有 `prompt_manager.get_prompt(key)` 调用
3. 提取文件路径、行号、函数名

### 实现

```python
# backend/src/service/code_reference_scanner.py

import ast
import os
from pathlib import Path

class CodeReferenceScanner:
    def __init__(self, root_dir: str = "backend/src"):
        self._root_dir = root_dir
    
    async def scan(self, prompt_key: str) -> list[CodeReference]:
        """扫描代码中引用指定提示词的位置"""
        references = []
        
        for py_file in Path(self._root_dir).rglob("*.py"):
            refs = await self._scan_file(py_file, prompt_key)
            references.extend(refs)
        
        return references
    
    async def _scan_file(self, file_path: Path, prompt_key: str) -> list[CodeReference]:
        """扫描单个文件"""
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
        except:
            return []
        
        references = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # 检查是否是 prompt_manager.get_prompt() 调用
                if self._is_get_prompt_call(node, prompt_key):
                    func_name = self._get_enclosing_function(tree, node)
                    references.append(CodeReference(
                        file=str(file_path.relative_to(self._root_dir)),
                        line=node.lineno,
                        function=func_name
                    ))
        
        return references
    
    def _is_get_prompt_call(self, node: ast.Call, prompt_key: str) -> bool:
        """检查是否是 get_prompt(prompt_key) 调用"""
        # 简化实现，实际需处理更多 AST 情况
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "get_prompt":
                if node.args and isinstance(node.args[0], ast.Constant):
                    return node.args[0].value == prompt_key
        return False
```

### 验收标准

- [ ] 正确扫描代码中的引用位置
- [ ] 提取文件路径、行号、函数名
- [ ] 支持所有 Python 文件
