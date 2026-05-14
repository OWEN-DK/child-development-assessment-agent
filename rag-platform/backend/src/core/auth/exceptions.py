"""认证授权异常类

全部继承 AppException，统一错误码。
"""
from src.utils.exceptions import AppException


class AuthenticationError(AppException):
    """认证失败（401）"""
    code = 401
    error_code = "AUTHENTICATION_ERROR"


class AuthorizationError(AppException):
    """授权失败（403）"""
    code = 403
    error_code = "AUTHORIZATION_ERROR"


class TenantSuspendedError(AppException):
    """租户已停用（403）"""
    code = 403
    error_code = "TENANT_SUSPENDED"


class TenantNotFoundError(AppException):
    """租户不存在（404）"""
    code = 404
    error_code = "TENANT_NOT_FOUND"


class UserNotFoundError(AppException):
    """用户不存在（404）"""
    code = 404
    error_code = "USER_NOT_FOUND"


class RoleNotFoundError(AppException):
    """角色不存在（404）"""
    code = 404
    error_code = "ROLE_NOT_FOUND"


class InvitationExpiredError(AppException):
    """邀请已过期（410）"""
    code = 410
    error_code = "INVITATION_EXPIRED"


class InvitationInvalidError(AppException):
    """邀请无效（400）"""
    code = 400
    error_code = "INVITATION_INVALID"


class QuotaExceededError(AppException):
    """配额超限（429）"""
    code = 429
    error_code = "QUOTA_EXCEEDED"


class MissingTenantContextError(AppException):
    """缺少租户上下文（500）"""
    code = 500
    error_code = "MISSING_TENANT_CONTEXT"


class GodModeConflictError(AppException):
    """God Mode 冲突（409）"""
    code = 409
    error_code = "GOD_MODE_CONFLICT"
