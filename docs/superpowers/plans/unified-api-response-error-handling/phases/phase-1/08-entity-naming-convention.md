# Phase 1-8: 实体命名规范

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `2.3 分类规则` 节
> **所属 Phase**: Phase 1

## 需求定义

统一所有 Pydantic 实体类的命名规范，确保命名符合分类规则，消除不一致的命名。

## 验收标准

- [ ] 所有 Request DTO 使用 `{Entity}{Action}Request` 格式
- [ ] 所有 Response DTO 使用 `{Entity}Response` 格式
- [ ] 领域模型使用业务实体名
- [ ] 配置模型使用 `{Module}Config` 格式
- [ ] 事件模型使用 `{EventName}Event` 格式
- [ ] 无 Store 后缀的 Pydantic 模型（应使用 Response 或 Request）

## 命名规范

| 类型 | 命名规范 | 示例 | 说明 |
|------|---------|------|------|
| **请求 DTO** | `{Entity}{Action}Request` | `CreateTestCaseRequest` | 接口入参 |
| **响应 DTO** | `{Entity}Response` | `TestCaseResponse` | 接口出参 |
| **领域模型** | 业务实体名 | `ChildState`, `EvaluationResult` | 业务逻辑流转的实体 |
| **配置模型** | `{Module}Config` | `LLMProviderConfig` | 系统配置结构 |
| **事件模型** | `{EventName}Event` | `RunStartedEvent` | SSE 推送事件 |

## 需要重命名的类

### Store 后缀类（应改为 Response 或移除）

| 当前名称 | 建议名称 | 所在文件 |
|---------|---------|---------|
| `TestCaseStore` | 删除或改为 `TestCaseResponse` | `schemas/test_case.py` |
| `SourceDocumentStore` | 删除或改为 `SourceDocumentResponse` | `schemas/test_case.py` |
| `TestCaseDraftStore` | 删除或改为 `TestCaseDraftResponse` | `schemas/test_case.py` |
| `TestSetStore` | 删除或改为 `TestSetResponse` | `schemas/test_case.py` |

### 不一致的命名

| 当前名称 | 建议名称 | 原因 |
|---------|---------|------|
| `GenerationParams` | `TestCaseGenerationParams` | 缺少前缀，易混淆 |
| `TestResultItem` | `TestCaseResultItem` | 缺少上下文 |
| `ValidationError` | `ConfigValidationError` | 与通用错误码冲突 |

## 实现方案

### 重命名步骤

1. 在目标 schemas 文件中定义新名称类
2. 旧名称类添加 `@deprecated` 注释（过渡期）
3. 全局搜索旧名称，更新所有引用
4. 过渡期后删除旧名称类

### 命名检查清单

```python
# ✅ 正确示例
class CreateTestCaseRequest(BaseModel): ...     # Request DTO
class TestCaseResponse(BaseModel): ...          # Response DTO
class ChildState(BaseModel): ...                # 领域模型
class LLMProviderConfig(BaseModel): ...         # 配置模型
class RunStartedEvent(BaseModel): ...           # 事件模型

# ❌ 错误示例
class TestCaseStore(BaseModel): ...             # 不应有 Store 后缀
class GenerationParams(BaseModel): ...          # 缺少前缀
class ValidationError(BaseModel): ...           # 与通用错误码冲突
```

## 测试方案

1. 重命名后所有引用正确
2. API 请求/反序列化正常
3. 前端类型定义同步更新

## 注意事项

- 重命名影响范围大，需全局搜索替换
- Store 后缀类如果是 ORM 模型则不应迁移（保持在 `models/`）
- 前端 TypeScript 类型需同步更新
