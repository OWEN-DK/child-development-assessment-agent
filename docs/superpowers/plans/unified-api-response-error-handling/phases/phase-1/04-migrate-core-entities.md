# Phase 1-4: Core 实体迁移

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `2.4 迁移清单` 节
> **所属 Phase**: Phase 1

## 需求定义

将 core 目录中定义的 10 个 Pydantic BaseModel 类迁移至 `schemas/` 对应模块文件。

## 验收标准

- [ ] Core 文件中不再有 BaseModel 定义
- [ ] 所有引用处 import 更新为 `from src.schemas import Xxx`
- [ ] 功能回归测试通过

## 涉及文件

| 源文件 | 类数量 | 迁移目标 |
|-------|--------|---------|
| `core/age_filter.py` | 1 | `schemas/config.py` |
| `core/query_router.py` | 1 | `schemas/rag.py` |
| `core/metadata_extractor.py` | 1 | `schemas/rag.py` |
| `core/llm/base.py` | 4 | `schemas/common.py` |
| `core/auth.py` | 1 | `schemas/common.py` |
| `core/tracing/schemas.py` | 1 | `schemas/monitoring.py` |
| `core/llm/adapters/` 等 | 2 | `schemas/common.py` |

## 迁移清单

### core/age_filter.py → schemas/config.py

```python
AgeFilterConfig               # line 27
```

### core/query_router.py → schemas/rag.py

```python
QueryClassification             # line 26
```

### core/metadata_extractor.py → schemas/rag.py

```python
ExtractedMetadata               # line 15
```

### core/llm/base.py → schemas/common.py

```python
Message                         # line 17
LLMMessage                      # line 85
LLMResponse                     # line 92
LLMRequest                      # line 105
```

### core/auth.py → schemas/common.py

```python
User                            # line 9
```

### core/tracing/schemas.py → schemas/monitoring.py

```python
TraceMetadata                   # line 8
```

## 实现方案

### 迁移步骤

1. 在目标 schemas 文件中定义类
2. 在 Core 文件中删除类定义
3. 在 Core 文件顶部添加 import
4. 运行测试验证

## 测试方案

1. Core 模块初始化无错误
2. LLM 请求/响应序列化正确
3. Age filter 配置加载正确

## 注意事项

- `core/llm/base.py` 中的 LLM 模型是基础设施层通用模型，迁移至 `schemas/common.py`
- `core/auth.py` 的 `User` 是认证模型，迁移至 `schemas/common.py`
- 注意 `core/tracing/schemas.py` 文件名与目标目录 `schemas/` 重名，迁移后该文件可删除或重命名
