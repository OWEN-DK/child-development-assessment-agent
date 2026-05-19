"""角色管理控制器

路由前缀：/api/v1/roles
"""
from fastapi import APIRouter, Request

from src.schemas.common import APIResponse
from src.schemas.auth.role import RoleCreate, RoleUpdate
from src.service.auth.role_service import RoleService
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/roles", tags=["角色管理"])


@router.get("")
async def list_roles(request: Request, skip: int = 0, limit: int = 100):
    """列出角色"""
    role_service: RoleService = request.app.state.role_service
    tenant_id = request.state.tenant_id

    result = await role_service.list(tenant_id, skip=skip, limit=limit)
    return APIResponse.success(data=result.model_dump())


@router.post("")
async def create_role(request: Request, data: RoleCreate):
    """创建角色"""
    role_service: RoleService = request.app.state.role_service
    tenant_id = request.state.tenant_id
    actor_id = request.state.user_id
    creator_roles = request.state.roles

    result = await role_service.create(tenant_id, data, creator_roles, actor_id)
    return APIResponse.success(data=result.model_dump())


@router.get("/permissions")
async def get_permissions(request: Request):
    """获取可用权限列表"""
    role_service: RoleService = request.app.state.role_service

    result = role_service.get_permissions()
    return APIResponse.success(data=result.model_dump())


@router.get("/{role_id}")
async def get_role(request: Request, role_id: str):
    """获取角色详情"""
    role_service: RoleService = request.app.state.role_service
    tenant_id = request.state.tenant_id

    result = await role_service.get(role_id, tenant_id)
    return APIResponse.success(data=result.model_dump())


@router.put("/{role_id}")
async def update_role(request: Request, role_id: str, data: RoleUpdate):
    """更新角色"""
    role_service: RoleService = request.app.state.role_service
    tenant_id = request.state.tenant_id
    actor_id = request.state.user_id

    result = await role_service.update(role_id, tenant_id, data, actor_id)
    return APIResponse.success(data=result.model_dump())


@router.delete("/{role_id}")
async def delete_role(request: Request, role_id: str):
    """删除角色"""
    role_service: RoleService = request.app.state.role_service
    tenant_id = request.state.tenant_id
    actor_id = request.state.user_id

    await role_service.delete(role_id, tenant_id, actor_id)
    return APIResponse.success(data=None)
