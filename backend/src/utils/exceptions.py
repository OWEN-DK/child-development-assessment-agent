"""自定义业务异常

应用异常基类及通用/模块异常子类,携带 HTTP 状态码和业务错误码。
"""

from typing import Optional


class AppException(Exception):
    """应用异常基类,携带 HTTP 状态码和业务错误码"""

    def __init__(
        self,
        status_code: int,
        code: int,
        message: str,
        error_code: str = "APP_ERROR",
        details: Optional[dict] = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.error_code = error_code
        self.details = details
        super().__init__(message)


# ==================== 通用异常 (10000-10999) ====================


class TaskCancelledException(AppException):
    """后台任务被用户取消"""

    def __init__(self, message: str = "任务已取消"):
        super().__init__(
            status_code=200,
            code=10010,
            message=message,
            error_code="TASK_CANCELLED",
        )


class InvalidParamsException(AppException):
    """参数校验失败"""

    def __init__(self, message: str = "请求参数校验失败", details: Optional[dict] = None):
        super().__init__(
            status_code=400,
            code=10001,
            message=message,
            error_code="INVALID_PARAMS",
            details=details,
        )


class MissingRequiredFieldException(AppException):
    """缺少必填字段"""

    def __init__(self, field: Optional[str] = None, message: Optional[str] = None):
        msg = message or (f"缺少必填字段: {field}" if field else "缺少必填字段")
        details = {"field": field} if field else None
        super().__init__(
            status_code=400,
            code=10002,
            message=msg,
            error_code="MISSING_REQUIRED_FIELD",
            details=details,
        )


class UnauthorizedException(AppException):
    """未授权"""

    def __init__(self, message: str = "未授权,请先登录"):
        super().__init__(
            status_code=401,
            code=10003,
            message=message,
            error_code="UNAUTHORIZED",
        )


class ForbiddenException(AppException):
    """权限不足"""

    def __init__(self, message: str = "无权限执行此操作"):
        super().__init__(
            status_code=403,
            code=10004,
            message=message,
            error_code="FORBIDDEN",
        )


class ResourceNotFoundException(AppException):
    """资源不存在"""

    def __init__(
        self,
        message: str = "请求的资源不存在",
        error_code: str = "RESOURCE_NOT_FOUND",
        details: Optional[dict] = None,
    ):
        super().__init__(
            status_code=404,
            code=10005,
            message=message,
            error_code=error_code,
            details=details,
        )


class DuplicateResourceException(AppException):
    """资源重复"""

    def __init__(self, message: str = "资源已存在", details: Optional[dict] = None):
        super().__init__(
            status_code=409,
            code=10006,
            message=message,
            error_code="DUPLICATE_RESOURCE",
            details=details,
        )


class InternalServerErrorException(AppException):
    """系统内部异常"""

    def __init__(self, message: str = "系统内部异常,请稍后重试"):
        super().__init__(
            status_code=500,
            code=10007,
            message=message,
            error_code="INTERNAL_ERROR",
        )


class ServiceUnavailableException(AppException):
    """服务不可用"""

    def __init__(self, message: str = "服务暂时不可用"):
        super().__init__(
            status_code=503,
            code=10008,
            message=message,
            error_code="SERVICE_UNAVAILABLE",
        )


class RequestTimeoutException(AppException):
    """请求超时"""

    def __init__(self, message: str = "请求超时"):
        super().__init__(
            status_code=408,
            code=10009,
            message=message,
            error_code="REQUEST_TIMEOUT",
        )


class RateLimitExceededException(AppException):
    """请求频率超限"""

    def __init__(self, message: str = "请求过多,请稍后重试"):
        super().__init__(
            status_code=429,
            code=10009,
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
        )


# ==================== 评估异常 (11000-11999) ====================


class AssessmentFailedException(AppException):
    """评估失败"""

    def __init__(self, message: str = "评估失败", details: Optional[dict] = None):
        super().__init__(
            status_code=500,
            code=11001,
            message=message,
            error_code="ASSESSMENT_FAILED",
            details=details,
        )


class ChildProfileInvalidException(AppException):
    """儿童画像数据无效"""

    def __init__(self, message: str = "儿童画像数据无效", details: Optional[dict] = None):
        super().__init__(
            status_code=400,
            code=11002,
            message=message,
            error_code="CHILD_PROFILE_INVALID",
            details=details,
        )


# ==================== RAG 知识库异常 (12000-12999) ====================


class DocumentNotFoundException(AppException):
    """文档不存在"""

    def __init__(self, document_id: Optional[str] = None):
        details = {"document_id": document_id} if document_id else None
        super().__init__(
            status_code=404,
            code=12001,
            message="文档不存在",
            error_code="DOCUMENT_NOT_FOUND",
            details=details,
        )


class UnsupportedFileTypeException(AppException):
    """不支持的文件类型"""

    def __init__(self, file_type: str):
        super().__init__(
            status_code=400,
            code=12002,
            message=f"不支持的文件类型: {file_type}",
            error_code="UNSUPPORTED_FILE_TYPE",
            details={"file_type": file_type},
        )


class DocumentParseException(AppException):
    """文档解析失败"""

    def __init__(self, message: str = "文档解析失败", details: Optional[dict] = None):
        super().__init__(
            status_code=400,
            code=12003,
            message=message,
            error_code="DOCUMENT_PARSE_FAILED",
            details=details,
        )


class IndexNotAvailableException(AppException):
    """索引未就绪"""

    def __init__(self, message: str = "索引未就绪"):
        super().__init__(
            status_code=503,
            code=12004,
            message=message,
            error_code="INDEX_NOT_AVAILABLE",
        )


class ChunkNotFoundException(AppException):
    """分块不存在"""

    def __init__(self, chunk_id: Optional[str] = None):
        details = {"chunk_id": chunk_id} if chunk_id else None
        super().__init__(
            status_code=404,
            code=12005,
            message="分块不存在",
            error_code="CHUNK_NOT_FOUND",
            details=details,
        )


# ==================== RAG 测试异常 (13000-13999) ====================


class TestCaseNotFoundException(AppException):
    """测试用例不存在"""

    def __init__(self, case_id: Optional[str] = None):
        details = {"case_id": case_id} if case_id else None
        super().__init__(
            status_code=404,
            code=13001,
            message="测试用例不存在",
            error_code="TEST_CASE_NOT_FOUND",
            details=details,
        )


class TestSetNotFoundException(AppException):
    """测试集不存在"""

    def __init__(self, test_set_id: Optional[str] = None):
        details = {"test_set_id": test_set_id} if test_set_id else None
        super().__init__(
            status_code=404,
            code=13002,
            message="测试集不存在",
            error_code="TEST_SET_NOT_FOUND",
            details=details,
        )


class TestRunNotFoundException(AppException):
    """测试运行记录不存在"""

    def __init__(self, run_id: Optional[str] = None):
        details = {"run_id": run_id} if run_id else None
        super().__init__(
            status_code=404,
            code=13003,
            message="测试运行记录不存在",
            error_code="TEST_RUN_NOT_FOUND",
            details=details,
        )


class DraftNotFoundException(AppException):
    """测试草稿不存在"""

    def __init__(self, draft_id: Optional[str] = None):
        details = {"draft_id": draft_id} if draft_id else None
        super().__init__(
            status_code=404,
            code=13004,
            message="测试草稿不存在",
            error_code="DRAFT_NOT_FOUND",
            details=details,
        )


class ReportNotFoundException(AppException):
    """评估报告不存在"""

    def __init__(self, report_id: Optional[str] = None):
        details = {"report_id": report_id} if report_id else None
        super().__init__(
            status_code=404,
            code=13005,
            message="评估报告不存在",
            error_code="REPORT_NOT_FOUND",
            details=details,
        )


class ImportFailedException(AppException):
    """导入失败"""

    def __init__(self, message: str = "导入失败", details: Optional[dict] = None):
        super().__init__(
            status_code=500,
            code=13006,
            message=message,
            error_code="IMPORT_FAILED",
            details=details,
        )


# ==================== 配置管理异常 (14000-14999) ====================


class ConfigValidationFailedException(AppException):
    """配置校验失败"""

    def __init__(self, message: str = "配置校验失败", details: Optional[dict] = None):
        super().__init__(
            status_code=400,
            code=14001,
            message=message,
            error_code="CONFIG_VALIDATION_FAILED",
            details=details,
        )


class ConfigConflictException(AppException):
    """配置冲突"""

    def __init__(self, message: str = "配置冲突", details: Optional[dict] = None):
        super().__init__(
            status_code=409,
            code=14002,
            message=message,
            error_code="CONFIG_CONFLICT",
            details=details,
        )


class RollbackFailedException(AppException):
    """配置回滚失败"""

    def __init__(self, message: str = "配置回滚失败", details: Optional[dict] = None):
        super().__init__(
            status_code=500,
            code=14003,
            message=message,
            error_code="ROLLBACK_FAILED",
            details=details,
        )


# ==================== 提示词管理异常 (15000-15999) ====================


class PromptNotFoundException(AppException):
    """提示词不存在"""

    def __init__(self, prompt_id: Optional[str] = None):
        details = {"prompt_id": prompt_id} if prompt_id else None
        super().__init__(
            status_code=404,
            code=15001,
            message="提示词不存在",
            error_code="PROMPT_NOT_FOUND",
            details=details,
        )


class PromptVersionNotFoundException(AppException):
    """提示词版本不存在"""

    def __init__(self, version_id: Optional[str] = None):
        details = {"version_id": version_id} if version_id else None
        super().__init__(
            status_code=404,
            code=15002,
            message="提示词版本不存在",
            error_code="PROMPT_VERSION_NOT_FOUND",
            details=details,
        )


class PromptTestFailedException(AppException):
    """提示词测试失败"""

    def __init__(self, message: str = "提示词测试失败", details: Optional[dict] = None):
        super().__init__(
            status_code=500,
            code=15003,
            message=message,
            error_code="PROMPT_TEST_FAILED",
            details=details,
        )


class PromptVariableInvalidException(AppException):
    """提示词变量无效"""

    def __init__(self, variable: Optional[str] = None, message: Optional[str] = None):
        msg = message or (f"提示词变量无效: {variable}" if variable else "提示词变量无效")
        details = {"variable": variable} if variable else None
        super().__init__(
            status_code=400,
            code=15004,
            message=msg,
            error_code="PROMPT_VARIABLE_INVALID",
            details=details,
        )


# ==================== 监控异常 (16000-16999) ====================


class TraceNotFoundException(AppException):
    """追踪记录不存在"""

    def __init__(self, trace_id: Optional[str] = None):
        details = {"trace_id": trace_id} if trace_id else None
        super().__init__(
            status_code=404,
            code=16001,
            message="追踪记录不存在",
            error_code="TRACE_NOT_FOUND",
            details=details,
        )


class MetricNotAvailableException(AppException):
    """指标数据不可用"""

    def __init__(self, message: str = "指标数据不可用", details: Optional[dict] = None):
        super().__init__(
            status_code=503,
            code=16002,
            message=message,
            error_code="METRIC_NOT_AVAILABLE",
            details=details,
        )
