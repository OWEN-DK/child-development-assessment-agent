# Phase 7-4: AppException 层级

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `9.1.2` 节
> **所属 Phase**: Phase 7

## 需求定义

建立完整的业务异常类层级，所有异常继承 `AppException`，禁止直接使用 `HTTPException`。

## 验收标准

- [ ] `AppException` 基类定义完整
- [ ] 通用异常类定义完整（10+ 个）
- [ ] 模块异常类按错误码定义
- [ ] 所有异常类携带 status_code、code、message、error_code

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/utils/exceptions.py` | 修改 | 已有文件，扩展异常类 |

## 实现方案

### 异常类层级结构

```
Exception
└── AppException (基类)
    ├── 通用异常
    │   ├── InvalidParamsException (10001)
    │   ├── MissingRequiredFieldException (10002)
    │   ├── UnauthorizedException (10003)
    │   ├── ForbiddenException (10004)
    │   ├── ResourceNotFoundException (10005)
    │   ├── DuplicateResourceException (10006)
    │   ├── InternalServerErrorException (10007)
    │   ├── ServiceUnavailableException (10008)
    │   ├── RequestTimeoutException (10009)
    │   └── TaskCancelledException (10010)
    │
    ├── RAG 异常
    │   ├── DocumentNotFoundException (12001)
    │   ├── UnsupportedFileTypeException (12002)
    │   ├── DocumentParseException (12003)
    │   ├── IndexNotAvailableException (12004)
    │   └── ChunkNotFoundException (12005)
    │
    ├── RAG 测试异常
    │   ├── TestCaseNotFoundException (13001)
    │   ├── TestSetNotFoundException (13002)
    │   ├── TestRunNotFoundException (13003)
    │   ├── DraftNotFoundException (13004)
    │   ├── ReportNotFoundException (13005)
    │   └── ImportFailedException (13006)
    │
    ├── 配置异常
    │   ├── ConfigValidationFailedException (14001)
    │   ├── ConfigConflictException (14002)
    │   └── RollbackFailedException (14003)
    │
    ├── 提示词异常
    │   ├── PromptNotFoundException (15001)
    │   ├── PromptVersionNotFoundException (15002)
    │   ├── PromptTestFailedException (15003)
    │   └── PromptVariableInvalidException (15004)
    │
    ├── 监控异常
    │   ├── TraceNotFoundException (16001)
    │   └── MetricNotAvailableException (16002)
    │
    └── 评估异常
        ├── AssessmentFailedException (11001)
        └── ChildProfileInvalidException (11002)
```

### 模块异常类示例

```python
# RAG 知识库异常
class DocumentNotFoundException(AppException):
    def __init__(self, document_id: str | None = None):
        details = {"document_id": document_id} if document_id else None
        super().__init__(
            status_code=404,
            code=12001,
            message="文档不存在",
            error_code="DOCUMENT_NOT_FOUND",
            details=details,
        )


class UnsupportedFileTypeException(AppException):
    def __init__(self, file_type: str):
        super().__init__(
            status_code=400,
            code=12002,
            message=f"不支持的文件类型: {file_type}",
            error_code="UNSUPPORTED_FILE_TYPE",
            details={"file_type": file_type},
        )


# RAG 测试异常
class TestCaseNotFoundException(AppException):
    def __init__(self, case_id: str | None = None):
        details = {"case_id": case_id} if case_id else None
        super().__init__(
            status_code=404,
            code=13001,
            message="测试用例不存在",
            error_code="TEST_CASE_NOT_FOUND",
            details=details,
        )
```

## 测试方案

1. 每个异常类实例化后属性正确
2. 异常类可被异常处理器捕获
3. 模块异常类使用对应模块的错误码

## 注意事项

- 所有业务异常必须继承 `AppException`
- 禁止在 Controller/Service 中直接 `raise HTTPException`
- 过渡期保留 `HTTPException` 处理器，最终目标移除
