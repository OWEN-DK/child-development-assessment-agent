# Phase 1-6: models 实体迁移

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `2.4 迁移清单` 节
> **所属 Phase**: Phase 1

## 需求定义

将 `backend/src/models/`（复数）目录中定义的 14 个 Pydantic BaseModel 类迁移至 `schemas/` 对应模块文件。

**注意**：`models/`（复数）主要存放 SQLAlchemy ORM 模型，但其中 `sse_events.py` 和 `test_case.py` 混入了 Pydantic BaseModel。

## 验收标准

- [ ] `models/` 中所有 BaseModel 迁移完成
- [ ] SQLAlchemy ORM 模型保留在 `models/` 不受影响
- [ ] 所有引用处 import 更新
- [ ] 功能回归测试通过

## 涉及文件

| 源文件 | BaseModel 数量 | 迁移目标 |
|-------|---------------|---------|
| `models/sse_events.py` | 14 | `schemas/events.py` |
| `models/test_case.py` | 2 | `schemas/test_case.py` |

## 迁移清单

### models/sse_events.py → schemas/events.py

```python
OverallMetrics                 # line 32
ValidationSummaryItem          # line 42
RunStartedEvent                # line 52
ProgressEvent                  # line 63
CaseResultEvent                # line 75
TestCompletedEvent             # line 91
ValidationStartedEvent         # line 102
ValidationCompletedEvent       # line 111
ReportReadyEvent               # line 122
RunFailedEvent                 # line 134
HeartbeatEvent                 # line 145
ExportReadyEvent               # line 153
ExportFailedEvent              # line 164
```

### models/test_case.py → schemas/test_case.py

```python
GenerationParams               # line 70（与 model/rag_test.py 中的重复，需合并）
TestResultItem                 # line 86（与 model/rag_test.py 中的重复，需合并）
```

## 实现方案

### 重复类处理

`GenerationParams` 和 `TestResultItem` 在 `model/rag_test.py` 和 `models/test_case.py` 中都有定义：

1. 对比两个版本的字段差异
2. 合并为单一版本，放在 `schemas/test_case.py`
3. 删除重复定义

### 迁移步骤

1. 在 `schemas/events.py` 中定义所有 SSE 事件模型
2. 在 `schemas/test_case.py` 中合并定义重复类
3. 更新所有引用
4. `models/sse_events.py` 中的 SQLAlchemy ORM 部分保留（如有），删除 Pydantic 部分
5. 运行测试验证

## 测试方案

1. SSE 事件序列化正确
2. SSE Publisher 推送正常
3. 测试用例模型正确

## 注意事项

- `models/sse_events.py` 可能同时包含 SQLAlchemy ORM 和 Pydantic 模型，只迁移 Pydantic 部分
- SSE 事件模型字段必须与 spec 严格一致（ISO 8601 时间格式等）
- 合并重复类时，保留字段更全的版本
