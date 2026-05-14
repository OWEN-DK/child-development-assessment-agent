"""用户管理控制器

路由前缀：/api/v1/users
"""
from fastapi import APIRouter, Request

from src.api.json_response import APIResponse
from src.schemas.auth.user import UserInvite, UserAcceptInvitation, UserUpdate
from src.service.auth.user_service import UserService
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/users", tags=["用户管理"])


@router.get("/")
async def list_users(request: Request, skip: int = 0, limit: int = 100):
    """列出用户"""
    user_service: UserService = request.app.state.user_service
    tenant_id = request.state.tenant_id

    users = await user_service.list_users(tenant_id, skip=skip, limit=limit)
    return APIResponse.success(data={
        "items": [u.model_dump() for u in users],
        "total": len(users),
    })


@router.post("/invite")
async def invite_user(request: Request, data: UserInvite):
    """邀请用户"""
    user_service: UserService = request.app.state.user_service
    tenant_id = request.state.tenant_id
    actor_id = request.state.user_id

    result = await user_service.invite(tenant_id, data, actor_id)
    return APIResponse.success(data=result)


@router.post("/accept-invitation")
async def accept_invitation(request: Request, data: UserAcceptInvitation):
    """接受邀请"""
    user_service: UserService = request.app.state.user_service

    result = await user_service.accept_invitation(data)
    return APIResponse.success(data=result.model_dump())


@router.get("/{user_id}")
async def get_user(request: Request, user_id: str):
    """获取用户详情"""
    user_service: UserService = request.app.state.user_service
    tenant_id = request.state.tenant_id

    result = await user_service.get_user(user_id, tenant_id)
    return APIResponse.success(data=result.model_dump())


@router.put("/{user_id}")
async def update_user(request: Request, user_id: str, data: UserUpdate):
    """更新用户"""
    user_service: UserService = request.app.state.user_service
    tenant_id = request.state.tenant_id
    actor_id = request.state.user_id

    result = await user_service.update_user(user_id, tenant_id, data, actor_id)
    return APIResponse.success(data=result.model_dump())


@router.delete("/{user_id}")
async def delete_user(request: Request, user_id: str):
    """禁用用户"""
    user_service: UserService = request.app.state.user_service
    tenant_id = request.state.tenant_id
    actor_id = request.state.user_id

    await user_service.disable_user(user_id, tenant_id, actor_id)
    return APIResponse.success(data=None)
