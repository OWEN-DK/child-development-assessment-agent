"""复合节点控制器

/api/v1/compound-nodes — 复合节点 CRUD + 导入导出 JSON。
"""
from fastapi import APIRouter, Request

from src.schemas.common import APIResponse
from src.schemas.pipeline.compound import CompoundNodeCreate, CompoundNodeImport
from src.utils.exceptions import AppException
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/compound-nodes", tags=["复合节点"])


def _get_auth(request: Request):
    """提取认证上下文"""
    user_id = getattr(request.state, "user_id", "")
    tenant_id = getattr(request.state, "tenant_id", "")
    if not tenant_id:
        raise AppException(message="缺少租户上下文", code=401, error_code="AUTH_REQUIRED")
    return user_id, tenant_id


@router.get("")
async def list_compound_nodes(request: Request):
    """列出当前租户的所有复合节点"""
    user_id, tenant_id = _get_auth(request)
    service = request.app.state.compound_service
    nodes = await service.list_nodes(tenant_id)
    return APIResponse.success([n.model_dump() for n in nodes])


@router.post("")
async def create_compound_node(data: CompoundNodeCreate, request: Request):
    """创建复合节点"""
    user_id, tenant_id = _get_auth(request)
    service = request.app.state.compound_service
    result = await service.create(data, tenant_id=tenant_id, owner_id=user_id)
    return APIResponse.success(result.model_dump())


@router.get("/{node_id}")
async def get_compound_node(node_id: str, request: Request):
    """获取复合节点详情"""
    user_id, tenant_id = _get_auth(request)
    service = request.app.state.compound_service
    result = await service.get(node_id, tenant_id)
    if not result:
        raise AppException(message="复合节点不存在", code=404, error_code="COMPOUND_NODE_NOT_FOUND")
    return APIResponse.success(result.model_dump())


@router.put("/{node_id}")
async def update_compound_node(node_id: str, data: dict, request: Request):
    """更新复合节点"""
    user_id, tenant_id = _get_auth(request)
    service = request.app.state.compound_service
    result = await service.update(node_id, tenant_id, data)
    if not result:
        raise AppException(message="复合节点不存在", code=404, error_code="COMPOUND_NODE_NOT_FOUND")
    return APIResponse.success(result.model_dump())


@router.delete("/{node_id}")
async def delete_compound_node(node_id: str, request: Request):
    """删除复合节点"""
    user_id, tenant_id = _get_auth(request)
    service = request.app.state.compound_service
    deleted = await service.delete(node_id, tenant_id)
    if not deleted:
        raise AppException(message="复合节点不存在", code=404, error_code="COMPOUND_NODE_NOT_FOUND")
    return APIResponse.success(None)


@router.post("/import")
async def import_compound_node(data: CompoundNodeImport, request: Request):
    """从 JSON 导入复合节点"""
    user_id, tenant_id = _get_auth(request)
    service = request.app.state.compound_service
    result = await service.import_from_json(data, tenant_id=tenant_id, owner_id=user_id)
    return APIResponse.success(result.model_dump())


@router.get("/{node_id}/export")
async def export_compound_node(node_id: str, request: Request):
    """导出复合节点为 JSON"""
    user_id, tenant_id = _get_auth(request)
    service = request.app.state.compound_service
    result = await service.export_to_json(node_id, tenant_id)
    if not result:
        raise AppException(message="复合节点不存在", code=404, error_code="COMPOUND_NODE_NOT_FOUND")
    return APIResponse.success(result)
