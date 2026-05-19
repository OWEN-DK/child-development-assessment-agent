"""知识库控制器

路由前缀：/api/v1/knowledge-bases
"""
from typing import Optional

from fastapi import APIRouter, Query, Request

from src.schemas.common import APIResponse
from src.schemas.knowledge.knowledge_base import (
    CreateKnowledgeBaseReq,
    MigrateBackendReq,
    UpdateChunkStrategyReq,
    UpdateEmbeddingConfigReq,
    UpdateKnowledgeBaseReq,
)
from src.service.knowledge.kb_service import KnowledgeBaseService
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["知识库管理"])


@router.post("")
async def create_knowledge_base(request: Request, data: CreateKnowledgeBaseReq):
    """创建知识库"""
    service: KnowledgeBaseService = request.app.state.kb_service
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id

    result = await service.create(data, tenant_id, user_id)
    return APIResponse.success(data=result.model_dump())


@router.get("")
async def list_knowledge_bases(
    request: Request,
    keyword: Optional[str] = Query(default=None, description="名称搜索"),
    vector_backend: Optional[str] = Query(default=None, description="向量后端筛选"),
    status: Optional[str] = Query(default=None, description="状态筛选"),
    visibility: Optional[str] = Query(default=None, description="可见性筛选"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """列出知识库"""
    service: KnowledgeBaseService = request.app.state.kb_service
    tenant_id = request.state.tenant_id

    result = await service.list(
        tenant_id=tenant_id,
        keyword=keyword,
        vector_backend=vector_backend,
        status=status,
        visibility=visibility,
        skip=skip,
        limit=limit,
    )
    return APIResponse.success(data=result.model_dump())


@router.get("/{kb_id}")
async def get_knowledge_base(request: Request, kb_id: str):
    """获取知识库详情"""
    service: KnowledgeBaseService = request.app.state.kb_service
    tenant_id = request.state.tenant_id

    result = await service.get_detail(kb_id, tenant_id)
    return APIResponse.success(data=result.model_dump())


@router.put("/{kb_id}")
async def update_knowledge_base(request: Request, kb_id: str, data: UpdateKnowledgeBaseReq):
    """更新知识库"""
    service: KnowledgeBaseService = request.app.state.kb_service
    tenant_id = request.state.tenant_id

    result = await service.update(kb_id, data, tenant_id)
    return APIResponse.success(data=result.model_dump())


@router.put("/{kb_id}/chunk-strategy")
async def update_chunk_strategy(request: Request, kb_id: str, data: UpdateChunkStrategyReq):
    """更新分块策略（触发重建）"""
    service: KnowledgeBaseService = request.app.state.kb_service
    tenant_id = request.state.tenant_id

    task_id = await service.update_chunk_strategy(kb_id, data, tenant_id)
    return APIResponse.success(data={"rebuild_task_id": task_id})


@router.put("/{kb_id}/embedding-config")
async def update_embedding_config(request: Request, kb_id: str, data: UpdateEmbeddingConfigReq):
    """更新 Embedding 配置（触发重建）"""
    service: KnowledgeBaseService = request.app.state.kb_service
    tenant_id = request.state.tenant_id

    task_id = await service.update_embedding_config(kb_id, data, tenant_id)
    return APIResponse.success(data={"rebuild_task_id": task_id})


@router.post("/{kb_id}/migrate-backend")
async def migrate_backend(request: Request, kb_id: str, data: MigrateBackendReq):
    """迁移向量后端"""
    service: KnowledgeBaseService = request.app.state.kb_service
    tenant_id = request.state.tenant_id

    result = await service.migrate_backend(kb_id, data.target_backend, tenant_id)
    return APIResponse.success(data=result)


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    request: Request, kb_id: str, force: bool = Query(default=False)
):
    """删除知识库"""
    service: KnowledgeBaseService = request.app.state.kb_service
    tenant_id = request.state.tenant_id

    await service.delete(kb_id, tenant_id, force=force)
    return APIResponse.success(data=None)
