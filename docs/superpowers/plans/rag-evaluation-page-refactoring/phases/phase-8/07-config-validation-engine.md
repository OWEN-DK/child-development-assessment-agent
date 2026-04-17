# 07 - 配置校验引擎 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 07 - 配置校验引擎

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
> **需求点**: 7
> **需求来源**: spec `08c-config-validation.md`

## 目标

实现类型校验 + 范围校验 + 推荐范围警告的配置校验引擎。

## 方案设计

### 校验流程

```
用户输入配置值
     ↓
类型校验 (ERROR)
     ↓
取值范围校验 (ERROR)
     ↓
推荐范围校验 (WARNING)
     ↓
冲突检测 (ERROR/WARNING)
     ↓
返回校验结果
```

### 校验引擎实现

```python
# backend/src/service/config_validation_engine.py

class ConfigValidationEngine:
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def validate(self, config_updates: dict) -> ValidationResult:
        """校验配置更新"""
        errors = []
        warnings = []
        
        for key, value in config_updates.items():
            metadata = await self._get_metadata(key)
            if not metadata:
                errors.append(f"配置项 {key} 不存在")
                continue
            
            # 1. 类型校验
            type_error = self._validate_type(value, metadata.value_type)
            if type_error:
                errors.append(f"{metadata.name_zh}: {type_error}")
                continue
            
            # 2. 取值范围校验
            range_error = self._validate_range(value, metadata)
            if range_error:
                errors.append(f"{metadata.name_zh}: {range_error}")
                continue
            
            # 3. 推荐范围校验
            rec_warning = self._validate_recommended_range(value, metadata)
            if rec_warning:
                warnings.append(f"{metadata.name_zh}: {rec_warning}")
        
        # 4. 冲突检测
        conflict_errors, conflict_warnings = await self._detect_conflicts(config_updates)
        errors.extend(conflict_errors)
        warnings.extend(conflict_warnings)
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _validate_type(self, value: any, value_type: str) -> str | None:
        """类型校验"""
        if value_type == "number":
            if not isinstance(value, (int, float)):
                return "值必须为数字"
        elif value_type == "boolean":
            if not isinstance(value, bool):
                return "值必须为布尔类型"
        elif value_type == "json":
            if not isinstance(value, (dict, list)):
                return "值必须为 JSON 对象"
        return None
    
    def _validate_range(self, value: any, metadata: ConfigMetadata) -> str | None:
        """取值范围校验"""
        if metadata.min_value is not None and value < metadata.min_value:
            return f"值不能小于 {metadata.min_value}"
        if metadata.max_value is not None and value > metadata.max_value:
            return f"值不能大于 {metadata.max_value}"
        return None
    
    def _validate_recommended_range(self, value: any, metadata: ConfigMetadata) -> str | None:
        """推荐范围校验"""
        warnings = []
        if metadata.recommended_min is not None and value < metadata.recommended_min:
            warnings.append(f"推荐值不低于 {metadata.recommended_min}")
        if metadata.recommended_max is not None and value > metadata.recommended_max:
            warnings.append(f"推荐值不超过 {metadata.recommended_max}")
        return " ".join(warnings) if warnings else None
```

### 验收标准

- [ ] 类型校验正确执行
- [ ] 取值范围校验正确执行
- [ ] 推荐范围警告正确展示
- [ ] 校验结果返回错误和警告列表
