"""文档管理控制器

路由前缀：/api/v1/knowledge-bases/{kb_id}/documents
"""
from typing import Optional

from fastapi import APIRouter, File, Query, Request, UploadFile

from src.api.json_response import APIResponse
from src.schemas.knowledge.document import UpdateDocAclReq
from src.service.knowledge.document_service import DocumentService
from src.utils.logger import logger

router = APIRouter(
    prefix="/api/v1/knowledge-bases/{kb_id}/documents",
    tags=["文档管理"],
)


@router.post("/")
async def upload_documents(
    request: Request,
    kb_id: str,
    files: list[UploadFile] = File(..., description="上传文件（支持批量）"),
):
    """批量上传文档"""
    service: DocumentService = request.app.state.document_service
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id

    # 读取文件内容
    file_list = []
    for f in files:
        content = await f.read()
        file_list.append((f.filename, content))

    result = await service.upload(kb_id, tenant_id, user_id, file_list)
    return APIResponse.success(data=result.model_dump())


@router.get("/")
async def list_documents(
    request: Request,
    kb_id: str,
    parse_status: Optional[str] = Query(default=None, description="解析状态筛选"),
    file_type: Optional[str] = Query(default=None, description="文件类型筛选"),
    keyword: Optional[str] = Query(default=None, description="文件名搜索"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """列出文档"""
    service: DocumentService = request.app.state.document_service
    tenant_id = request.state.tenant_id

    result = await service.list_documents(
        kb_id=kb_id,
        tenant_id=tenant_id,
        parse_status=parse_status,
        file_type=file_type,
        keyword=keyword,
        skip=skip,
        limit=limit,
    )
    return APIResponse.success(data=result.model_dump())


@router.get("/{doc_id}")
async def get_document(request: Request, kb_id: str, doc_id: str):
    """获取文档详情（含分块预览）"""
    service: DocumentService = request.app.state.document_service
    tenant_id = request.state.tenant_id

    result = await service.get_detail(doc_id, kb_id, tenant_id)
    return APIResponse.success(data=result.model_dump())


@router.delete("/{doc_id}")
async def delete_document(request: Request, kb_id: str, doc_id: str):
    """删除文档"""
    service: DocumentService = request.app.state.document_service
    tenant_id = request.state.tenant_id

    await service.delete(doc_id, kb_id, tenant_id)
    return APIResponse.success(data=None)


@router.put("/{doc_id}/acl")
async def update_document_acl(
    request: Request, kb_id: str, doc_id: str, data: UpdateDocAclReq
):
    """更新文档 ACL"""
    # TODO: 实现 ACL 更新
    return APIResponse.success(data={"message": "功能待实现"})
