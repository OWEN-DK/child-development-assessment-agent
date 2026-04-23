"""意图标注服务"""

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.rag_eval.intent_annotation import RagEvalIntentAnnotation
from src.utils.logger import logger


class IntentAnnotationService:
    """意图标注服务"""

    async def create_annotation(
        self,
        session: AsyncSession,
        case_id: str,
        intent_type: str,
        annotated_by: Optional[str] = None,
    ) -> RagEvalIntentAnnotation:
        """创建意图标注"""
        from datetime import datetime

        annotation = RagEvalIntentAnnotation(
            case_id=case_id,
            intent_type=intent_type,
            annotated_by=annotated_by,
            annotated_at=datetime.utcnow(),
        )
        session.add(annotation)
        await session.commit()
        await session.refresh(annotation)

        logger.info(
            f"意图标注已创建: case_id={case_id}, intent_type={intent_type}"
        )

        return annotation

    async def get_annotations(
        self,
        session: AsyncSession,
        intent_type: Optional[str] = None,
        annotated_by: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[RagEvalIntentAnnotation], int]:
        """查询意图标注列表"""
        stmt = select(RagEvalIntentAnnotation)

        if intent_type:
            stmt = stmt.where(RagEvalIntentAnnotation.intent_type == intent_type)
        if annotated_by:
            stmt = stmt.where(RagEvalIntentAnnotation.annotated_by == annotated_by)

        # 统计总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await session.execute(count_stmt)
        total = count_result.scalar() or 0

        # 分页查询
        offset = (page - 1) * page_size
        stmt = stmt.order_by(RagEvalIntentAnnotation.annotated_at.desc())
        stmt = stmt.offset(offset).limit(page_size)

        result = await session.execute(stmt)
        annotations = list(result.scalars().all())

        return annotations, total

    async def get_annotation_by_id(
        self, session: AsyncSession, annotation_id: str
    ) -> Optional[RagEvalIntentAnnotation]:
        """根据ID获取意图标注"""
        stmt = select(RagEvalIntentAnnotation).where(
            RagEvalIntentAnnotation.id == annotation_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_annotation(
        self, session: AsyncSession, annotation_id: str
    ) -> bool:
        """删除意图标注"""
        annotation = await self.get_annotation_by_id(session, annotation_id)
        if not annotation:
            return False

        await session.delete(annotation)
        await session.commit()

        logger.info(f"意图标注已删除: annotation_id={annotation_id}")

        return True
