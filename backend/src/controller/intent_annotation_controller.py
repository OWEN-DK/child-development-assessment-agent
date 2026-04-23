"""意图标注 API 控制器"""

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.core.database import db_session_factory
from src.schemas.common import APIResponse
from src.service.intent_annotation_service import IntentAnnotationService
from src.utils.exceptions import ResourceNotFoundException
from src.utils.serializers import create_serializer, safe_isoformat

router = APIRouter(prefix="/api/v1/rag/test", tags=["RAG Eval Intent Annotations"])

intent_annotation_service = IntentAnnotationService()

serialize_annotation = create_serializer(
    object,
    {
        "id": None,
        "case_id": None,
        "intent_type": None,
        "annotated_by": None,
        "annotated_at": safe_isoformat,
    },
)


class CreateAnnotationRequest(BaseModel):
    case_id: str
    intent_type: str
    annotated_by: Optional[str] = None


@router.post("/intent-annotations")
async def create_annotation(request: CreateAnnotationRequest):
    """创建意图标注"""
    async with db_session_factory() as session:
        annotation = await intent_annotation_service.create_annotation(
            session=session,
            case_id=request.case_id,
            intent_type=request.intent_type,
            annotated_by=request.annotated_by,
        )

        return APIResponse.success(data=serialize_annotation(annotation))


@router.get("/intent-annotations")
async def query_annotations(
    intent_type: Optional[str] = Query(None, description="意图类型筛选"),
    annotated_by: Optional[str] = Query(None, description="标注人筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """查询意图标注列表"""
    async with db_session_factory() as session:
        annotations, total = await intent_annotation_service.get_annotations(
            session=session,
            intent_type=intent_type,
            annotated_by=annotated_by,
            page=page,
            page_size=page_size,
        )

        return APIResponse.success(data={
            "items": [serialize_annotation(a) for a in annotations],
            "total": total,
            "page": page,
            "page_size": page_size,
        })


@router.get("/intent-annotations/{annotation_id}")
async def get_annotation(annotation_id: str):
    """获取意图标注详情"""
    async with db_session_factory() as session:
        annotation = await intent_annotation_service.get_annotation_by_id(
            session, annotation_id
        )

        if not annotation:
            raise ResourceNotFoundException(message=f"意图标注不存在: {annotation_id}")

        return APIResponse.success(data=serialize_annotation(annotation))


@router.delete("/intent-annotations/{annotation_id}")
async def delete_annotation(annotation_id: str):
    """删除意图标注"""
    async with db_session_factory() as session:
        success = await intent_annotation_service.delete_annotation(
            session, annotation_id
        )

        if not success:
            raise ResourceNotFoundException(message=f"意图标注不存在: {annotation_id}")

        return APIResponse.success(message="意图标注已删除")
