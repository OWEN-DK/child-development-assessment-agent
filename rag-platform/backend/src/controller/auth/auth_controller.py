"""认证控制器

路由前缀：/api/v1/auth
"""
from fastapi import APIRouter, Request

from src.schemas.common import APIResponse
from src.schemas.auth.auth import LoginRequest, LoginResponse, TokenRefresh, TokenRefreshResponse, SwitchRoleRequest
from src.core.auth.password import verify_password
from src.core.auth.jwt_service import JWTService
from src.repository.auth.user_repo import UserRepository
from src.repository.auth.role_repo import RoleRepository
from src.repository.auth.user_repo import UserRoleRepository
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


@router.post("/login")
async def login(request: Request, data: LoginRequest):
    """用户登录"""
    # 获取依赖（实际应通过 DI 注入）
    jwt_service: JWTService = request.app.state.jwt_service
    user_repo: UserRepository = request.app.state.user_repo
    user_role_repo: UserRoleRepository = request.app.state.user_role_repo
    role_repo: RoleRepository = request.app.state.role_repo

    # 查找用户（先尝试超管，再尝试租户用户）
    user = await user_repo.find_superadmin(data.username)
    is_superadmin = user is not None and user.tenant_id is None

    if user is None:
        # TODO: 需要从请求上下文获取 tenant_id
        # 暂时从数据库查询所有匹配的用户
        user = await user_repo.find_by_email(data.username)

    if user is None:
        return APIResponse.error(code=401, message="用户名或密码错误", error_code="AUTHENTICATION_ERROR")

    # 验证密码
    if not verify_password(data.password, user.password_hash):
        return APIResponse.error(code=401, message="用户名或密码错误", error_code="AUTHENTICATION_ERROR")

    # 获取用户角色
    role_ids = await user_role_repo.get_roles_by_user(user.id)
    roles = []
    role_slugs = []
    for role_id in role_ids:
        role = await role_repo.get_by_id(role_id)
        if role:
            roles.extend(role.permissions)
            role_slugs.append(role.slug)

    # 签发令牌
    access_token = jwt_service.issue_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        roles=roles,
        is_superadmin=is_superadmin,
        role_slugs=role_slugs,
    )
    refresh_token = jwt_service.issue_refresh_token(user_id=user.id)

    return APIResponse.success(data={
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "status": user.status,
            "roles": roles,
        },
    })


@router.post("/refresh")
async def refresh_token(request: Request, data: TokenRefresh):
    """刷新令牌"""
    jwt_service: JWTService = request.app.state.jwt_service
    user_repo: UserRepository = request.app.state.user_repo
    user_role_repo: UserRoleRepository = request.app.state.user_role_repo
    role_repo: RoleRepository = request.app.state.role_repo

    try:
        payload = jwt_service.decode(data.refresh_token)
        if payload.get("type") != "refresh":
            return APIResponse.error(code=400, message="非刷新令牌", error_code="AUTHENTICATION_ERROR")

        user = await user_repo.get_by_id(payload["sub"])
        if user is None:
            return APIResponse.error(code=404, message="用户不存在", error_code="USER_NOT_FOUND")

        # 获取用户角色权限
        role_ids = await user_role_repo.get_roles_by_user(user.id)
        roles = []
        role_slugs = []
        for role_id in role_ids:
            role = await role_repo.get_by_id(role_id)
            if role:
                roles.extend(role.permissions)
                role_slugs.append(role.slug)

        new_access, new_refresh = jwt_service.refresh_with_user_info(
            refresh_token=data.refresh_token,
            user_id=user.id,
            tenant_id=user.tenant_id,
            roles=roles,
            is_superadmin=user.tenant_id is None,
            role_slugs=role_slugs,
        )

        return APIResponse.success(data={
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
        })
    except Exception as e:
        return APIResponse.error(code=401, message=str(e), error_code="AUTHENTICATION_ERROR")


@router.post("/switch-role")
async def switch_role(request: Request, data: SwitchRoleRequest):
    """切换角色视角（仅管理员可用）"""
    # TODO: 实现角色视角切换
    return APIResponse.success(data={"message": "功能待实现"})
