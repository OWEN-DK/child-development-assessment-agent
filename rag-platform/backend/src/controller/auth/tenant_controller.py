"""租户管理控制器（超管专用）

路由前缀：/api/v1/admin/tenants
"""
from fastapi import APIRouter, Request

from src.api.json_response import APIResponse
from src.schemas.auth.tenant import TenantCreate, TenantUpdate
from src.schemas.auth.god_mode import GodModeEnter, GodModeExtend
from src.service.auth.tenant_service import TenantService
from src.service.auth.god_mode_service import GodModeService
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/admin/tenants", tags=["租户管理"])


@router.post("/")
async def create_tenant(request: Request, data: TenantCreate):
    """创建租户"""
    tenant_service: TenantService = request.app.state.tenant_service
    actor_id = request.state.user_id

    result = await tenant_service.create(data, actor_id)
    return APIResponse.success(data=result.model_dump())


@router.get("/")
async def list_tenants(request: Request, skip: int = 0, limit: int = 100):
    """列出所有租户"""
    tenant_service: TenantService = request.app.state.tenant_service

    result = await tenant_service.list(skip=skip, limit=limit)
    return APIResponse.success(data=result.model_dump())


@router.get("/{tenant_id}")
async def get_tenant(request: Request, tenant_id: str):
    """获取租户详情"""
    tenant_service: TenantService = request.app.state.tenant_service

    result = await tenant_service.get(tenant_id)
    return APIResponse.success(data=result.model_dump())


@router.put("/{tenant_id}")
async def update_tenant(request: Request, tenant_id: str, data: TenantUpdate):
    """更新租户"""
    tenant_service: TenantService = request.app.state.tenant_service
    actor_id = request.state.user_id

    result = await tenant_service.update(tenant_id, data, actor_id)
    return APIResponse.success(data=result.model_dump())


@router.put("/{tenant_id}/archive")
async def archive_tenant(request: Request, tenant_id: str):
    """归档租户"""
    tenant_service: TenantService = request.app.state.tenant_service
    actor_id = request.state.user_id

    result = await tenant_service.archive(tenant_id, actor_id)
    return APIResponse.success(data=result.model_dump())


@router.put("/{tenant_id}/restore")
async def restore_tenant(request: Request, tenant_id: str):
    """恢复租户"""
    tenant_service: TenantService = request.app.state.tenant_service
    actor_id = request.state.user_id

    result = await tenant_service.restore(tenant_id, actor_id)
    return APIResponse.success(data=result.model_dump())


@router.delete("/{tenant_id}")
async def delete_tenant(request: Request, tenant_id: str):
    """软删除租户"""
    tenant_service: TenantService = request.app.state.tenant_service
    actor_id = request.state.user_id

    await tenant_service.soft_delete(tenant_id, actor_id)
    return APIResponse.success(data=None)


@router.post("/{tenant_id}/impersonate")
async def enter_god_mode(request: Request, tenant_id: str):
    """进入 God Mode"""
    god_mode_service: GodModeService = request.app.state.god_mode_service
    actor_id = request.state.user_id

    result = await god_mode_service.enter(tenant_id, actor_id)
    return APIResponse.success(data=result.model_dump())


@router.delete("/{tenant_id}/impersonate")
async def exit_god_mode(request: Request, tenant_id: str):
    """退出 God Mode"""
    god_mode_service: GodModeService = request.app.state.god_mode_service
    actor_id = request.state.user_id

    await god_mode_service.exit(tenant_id, actor_id)
    return APIResponse.success(data=None)


@router.post("/{tenant_id}/impersonate/extend")
async def extend_god_mode(request: Request, tenant_id: str, data: GodModeExtend):
    """延长 God Mode"""
    god_mode_service: GodModeService = request.app.state.god_mode_service
    actor_id = request.state.user_id

    result = await god_mode_service.extend(tenant_id, actor_id, data.extend_minutes)
    return APIResponse.success(data=result.model_dump())


@router.get("/{tenant_id}/god-mode-log")
async def get_god_mode_logs(request: Request, tenant_id: str, skip: int = 0, limit: int = 100):
    """获取 God Mode 审计日志"""
    from src.repository.auth.audit_repo import AuditRepository

    audit_repo: AuditRepository = request.app.state.audit_repo
    logs = await audit_repo.get_god_mode_logs(tenant_id, skip=skip, limit=limit)
    total = await audit_repo.count_god_mode_logs(tenant_id)

    return APIResponse.success(data={
        "items": [
            {
                "id": log.id,
                "tenant_id": log.tenant_id,
                "actor_id": log.actor_id,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "details": log.details,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "total": total,
    })
