# 04 - 实时校验 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 04 - 实时校验

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
> **需求点**: 4
> **需求来源**: spec `08b-config-frontend-pages.md`

## 目标

实现输入时校验取值范围和推荐范围。

## 方案设计

### 校验规则

| 规则 | 级别 | 说明 |
|------|------|------|
| 取值范围 | ERROR | 超出 min_value ~ max_value 时阻止保存 |
| 推荐范围 | WARNING | 超出 recommended_min ~ recommended_max 时警告但允许保存 |
| 类型校验 | ERROR | 值类型不匹配时阻止保存 |

### 前端校验

```typescript
const validateConfigValue = (
  value: any,
  metadata: ConfigMetadata
): ValidationResult => {
  const errors: string[] = []
  const warnings: string[] = []
  
  // 类型校验
  if (metadata.value_type === 'number' && isNaN(Number(value))) {
    errors.push('值必须为数字')
  }
  
  // 取值范围
  if (metadata.min_value !== null && value < metadata.min_value) {
    errors.push(`值不能小于 ${metadata.min_value}`)
  }
  if (metadata.max_value !== null && value > metadata.max_value) {
    errors.push(`值不能大于 ${metadata.max_value}`)
  }
  
  // 推荐范围
  if (metadata.recommended_min !== null && value < metadata.recommended_min) {
    warnings.push(`推荐值不低于 ${metadata.recommended_min}`)
  }
  if (metadata.recommended_max !== null && value > metadata.recommended_max) {
    warnings.push(`推荐值不超过 ${metadata.recommended_max}`)
  }
  
  return { errors, warnings, valid: errors.length === 0 }
}
```

### 后端校验

```python
# backend/src/service/config_validation_service.py

async def validate_config_value(
    config_key: str,
    value: any,
    session: AsyncSession
) -> ValidationResult:
    """校验配置值"""
    metadata = await get_config_metadata(config_key, session)
    
    errors = []
    warnings = []
    
    # 类型校验
    if metadata.value_type == "number":
        try:
            value = float(value)
        except (ValueError, TypeError):
            errors.append("值必须为数字")
    
    # 取值范围
    if metadata.min_value is not None and value < metadata.min_value:
        errors.append(f"值不能小于 {metadata.min_value}")
    if metadata.max_value is not None and value > metadata.max_value:
        errors.append(f"值不能大于 {metadata.max_value}")
    
    # 推荐范围
    if metadata.recommended_min is not None and value < metadata.recommended_min:
        warnings.append(f"推荐值不低于 {metadata.recommended_min}")
    if metadata.recommended_max is not None and value > metadata.recommended_max:
        warnings.append(f"推荐值不超过 {metadata.recommended_max}")
    
    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )
```

### 验收标准

- [ ] 输入时实时校验取值范围
- [ ] 超出取值范围时阻止保存并显示错误
- [ ] 超出推荐范围时显示警告但允许保存
- [ ] 前后端双重校验
