# Phase 1-3: Service 实体迁移

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `2.4 迁移清单` 节
> **所属 Phase**: Phase 1

## 需求定义

将 4 个 Service 文件中定义的 7 个 Pydantic BaseModel 类迁移至 `schemas/` 对应模块文件。

## 验收标准

- [ ] Service 文件中不再有 BaseModel 定义
- [ ] 所有引用处 import 更新为 `from src.schemas import Xxx`
- [ ] 功能回归测试通过

## 涉及文件

| 源文件 | 类数量 | 迁移目标 |
|-------|--------|---------|
| `service/config_conflict_detector.py` | 1 | `schemas/config.py` |
| `service/config_validation_engine.py` | 1 | `schemas/config.py` |
| `service/prompt_impact_analyzer.py` | 4 | `schemas/prompt.py` |
| `service/retrieval_service.py` | 1 | `schemas/rag.py` |

## 迁移清单

### service/config_conflict_detector.py → schemas/config.py

```python
Conflict                       # line 6
```

### service/config_validation_engine.py → schemas/config.py

```python
ValidationResult               # line 7
```

### service/prompt_impact_analyzer.py → schemas/prompt.py

```python
CodeReference                  # line 10
VariableChanges                # line 18
ConfigDependency               # line 26
ImpactAnalysisResult           # line 35
```

### service/retrieval_service.py → schemas/rag.py

```python
SynonymExpansionResult         # line 31
```

## 实现方案

### 迁移步骤

1. 在目标 schemas 文件中定义类
2. 在 Service 文件中删除类定义
3. 在 Service 文件顶部添加 import
4. 运行测试验证

## 测试方案

1. Service 初始化无错误
2. 类实例化正确
3. Pydantic 验证正常

## 注意事项

- `Conflict` 和 `ValidationResult` 是配置模块的核心领域模型，迁移至 `schemas/config.py`
- `ImpactAnalysisResult` 及其依赖类迁移至 `schemas/prompt.py`
