# Phase 7-3: 模块错误码

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `8.3` 节
> **所属 Phase**: Phase 7

## 需求定义

定义各模块专属错误码，按分段分配到对应范围。

## 验收标准

- [ ] RAG 知识库模块错误码 (12000-12999) 定义完整
- [ ] RAG 测试模块错误码 (13000-13999) 定义完整
- [ ] 配置管理模块错误码 (14000-14999) 定义完整
- [ ] 提示词管理模块错误码 (15000-15999) 定义完整
- [ ] 监控模块错误码 (16000-16999) 定义完整
- [ ] 评估模块错误码 (11000-11999) 定义完整

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/utils/error_codes.py` | 修改 | 添加模块错误码常量 |

## 实现方案

### RAG 知识库模块 (12000-12999)

| 错误码 | error_code | message |
|--------|-----------|---------|
| `12001` | `DOCUMENT_NOT_FOUND` | 文档不存在 |
| `12002` | `UNSUPPORTED_FILE_TYPE` | 不支持的文件类型 |
| `12003` | `DOCUMENT_PARSE_FAILED` | 文档解析失败 |
| `12004` | `INDEX_NOT_AVAILABLE` | 索引未就绪 |
| `12005` | `CHUNK_NOT_FOUND` | 分块不存在 |

### RAG 测试模块 (13000-13999)

| 错误码 | error_code | message |
|--------|-----------|---------|
| `13001` | `TEST_CASE_NOT_FOUND` | 测试用例不存在 |
| `13002` | `TEST_SET_NOT_FOUND` | 测试集不存在 |
| `13003` | `TEST_RUN_NOT_FOUND` | 测试运行记录不存在 |
| `13004` | `DRAFT_NOT_FOUND` | 测试草稿不存在 |
| `13005` | `REPORT_NOT_FOUND` | 评估报告不存在 |
| `13006` | `IMPORT_FAILED` | 导入失败 |

### 配置管理模块 (14000-14999)

| 错误码 | error_code | message |
|--------|-----------|---------|
| `14001` | `CONFIG_VALIDATION_FAILED` | 配置校验失败 |
| `14002` | `CONFIG_CONFLICT` | 配置冲突 |
| `14003` | `ROLLBACK_FAILED` | 配置回滚失败 |

### 提示词管理模块 (15000-15999)

| 错误码 | error_code | message |
|--------|-----------|---------|
| `15001` | `PROMPT_NOT_FOUND` | 提示词不存在 |
| `15002` | `PROMPT_VERSION_NOT_FOUND` | 提示词版本不存在 |
| `15003` | `PROMPT_TEST_FAILED` | 提示词测试失败 |
| `15004` | `PROMPT_VARIABLE_INVALID` | 提示词变量无效 |

### 监控模块 (16000-16999)

| 错误码 | error_code | message |
|--------|-----------|---------|
| `16001` | `TRACE_NOT_FOUND` | 追踪记录不存在 |
| `16002` | `METRIC_NOT_AVAILABLE` | 指标数据不可用 |

### 评估模块 (11000-11999)

| 错误码 | error_code | message |
|--------|-----------|---------|
| `11001` | `ASSESSMENT_FAILED` | 评估失败 |
| `11002` | `CHILD_PROFILE_INVALID` | 儿童画像数据无效 |

### 常量定义

```python
# RAG 知识库模块 (12000-12999)
RAG_DOCUMENT_NOT_FOUND = 12001
RAG_UNSUPPORTED_FILE_TYPE = 12002
RAG_DOCUMENT_PARSE_FAILED = 12003
RAG_INDEX_NOT_AVAILABLE = 12004
RAG_CHUNK_NOT_FOUND = 12005

# RAG 测试模块 (13000-13999)
RAG_TEST_CASE_NOT_FOUND = 13001
RAG_TEST_SET_NOT_FOUND = 13002
RAG_TEST_RUN_NOT_FOUND = 13003
RAG_DRAFT_NOT_FOUND = 13004
RAG_REPORT_NOT_FOUND = 13005
RAG_IMPORT_FAILED = 13006

# 配置管理模块 (14000-14999)
CONFIG_VALIDATION_FAILED = 14001
CONFIG_CONFLICT = 14002
CONFIG_ROLLBACK_FAILED = 14003

# 提示词管理模块 (15000-15999)
PROMPT_NOT_FOUND = 15001
PROMPT_VERSION_NOT_FOUND = 15002
PROMPT_TEST_FAILED = 15003
PROMPT_VARIABLE_INVALID = 15004

# 监控模块 (16000-16999)
MONITORING_TRACE_NOT_FOUND = 16001
MONITORING_METRIC_NOT_AVAILABLE = 16002

# 评估模块 (11000-11999)
ASSESSMENT_FAILED = 11001
ASSESSMENT_CHILD_PROFILE_INVALID = 11002
```

## 测试方案

1. 每个模块错误码在对应范围内
2. 无重复错误码
3. error_code 唯一

## 注意事项

- 模块错误码由该模块的异常类使用
- 新增错误码时按顺序递增，预留中间值方便插入
