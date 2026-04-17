# 07 - 影响分析引擎 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 07 - 影响分析引擎

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
> **需求点**: 7
> **需求来源**: spec `07c-prompt-impact-analysis.md`

## 目标

实现综合分析代码引用、变量变更、配置依赖的影响分析引擎。

## 方案设计

### 引擎结构

```python
# backend/src/service/prompt_impact_analyzer.py

class PromptImpactAnalyzer:
    """提示词影响分析引擎"""
    
    def __init__(self, session: AsyncSession):
        self._session = session
        self._code_scanner = CodeReferenceScanner()
        self._variable_validator = VariableValidator()
        self._config_detector = ConfigDependencyDetector()
    
    async def analyze(self, prompt_key: str, new_content: str) -> ImpactAnalysisResult:
        """综合分析提示词修改的影响"""
        # 1. 扫描代码引用
        code_refs = await self._code_scanner.scan(prompt_key)
        
        # 2. 校验变量变更
        variable_changes = await self._variable_validator.validate(prompt_key, new_content)
        
        # 3. 检测配置依赖
        config_deps = await self._config_detector.detect(prompt_key, new_content)
        
        return ImpactAnalysisResult(
            code_references=code_refs,
            variable_changes=variable_changes,
            config_dependencies=config_deps,
            affected_files=list(set(ref.file for ref in code_refs)),
            risk_level=self._calculate_risk_level(variable_changes, config_deps)
        )
    
    def _calculate_risk_level(self, variable_changes, config_deps) -> str:
        """计算风险等级"""
        if variable_changes.removed or config_deps.changed:
            return "high"
        if variable_changes.added or variable_changes.modified:
            return "medium"
        return "low"
```

### 分析结果格式

```typescript
interface ImpactAnalysisResult {
  code_references: CodeReference[]
  variable_changes: VariableChanges
  config_dependencies: ConfigDependency[]
  affected_files: string[]
  risk_level: 'low' | 'medium' | 'high'
}

interface VariableChanges {
  added: string[]
  removed: string[]
  modified: string[]
}
```

### 验收标准

- [ ] 综合分析代码引用、变量变更、配置依赖
- [ ] 正确计算风险等级
- [ ] 返回受影响的文件列表
