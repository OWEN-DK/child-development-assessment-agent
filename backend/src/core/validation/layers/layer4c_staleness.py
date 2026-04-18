"""校验层 - Layer 4c: 文档时效性检查

根据文档类型和上传时间判断源文档是否过期。
"""

import logging
from datetime import datetime, timedelta, UTC
from typing import Any
from collections import defaultdict

from sqlalchemy import select
from src.models.document import SourceDocument

logger = logging.getLogger(__name__)

STALENESS_THRESHOLDS = {
    "政策法规/指南": 3,
    "学术研究/实证": 10,
    "经典理论": None,
    "实操方法/训练方案": 5,
}


class Layer4cDocumentStaleness:
    """Layer 4c: 文档时效性检查"""

    def __init__(self, session_factory, test_run):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        """执行时效性检查"""
        async with self.session_factory() as session:
            source_documents = await self._get_source_documents(session)

        if not source_documents:
            return {"status": "skipped", "data": {"reason": "缺少源文档数据"}}

        now = datetime.now(UTC).replace(tzinfo=None)
        stale_count = 0
        stale_docs = []
        by_type = defaultdict(lambda: {"total": 0, "stale": 0})

        for doc in source_documents:
            doc_type = doc.get("document_type", "学术研究/实证")
            upload_date = doc.get("upload_date")

            if not upload_date:
                continue

            by_type[doc_type]["total"] += 1

            threshold_years = STALENESS_THRESHOLDS.get(doc_type)
            if threshold_years is None:
                continue  # 经典理论不检查

            if isinstance(upload_date, str):
                upload_date = datetime.fromisoformat(
                    upload_date.replace("Z", "+00:00")
                ).replace(tzinfo=None)

            age_years = (now - upload_date).days / 365.25

            if age_years > threshold_years:
                stale_count += 1
                by_type[doc_type]["stale"] += 1
                stale_docs.append(
                    {
                        "doc_id": doc.get("id"),
                        "title": doc.get("title", ""),
                        "doc_type": doc_type,
                        "upload_date": upload_date.isoformat(),
                        "age_years": round(age_years, 1),
                        "threshold_years": threshold_years,
                    }
                )

        total = sum(v["total"] for v in by_type.values())
        stale_ratio = stale_count / total if total > 0 else 0

        warnings = []
        if stale_ratio > 0.20:
            warnings.append(
                {
                    "level": "warning",
                    "message": f"过期文档过多 ({stale_ratio:.1%} > 20%)",
                }
            )

        for doc in stale_docs:
            if doc["doc_type"] == "政策法规/指南" and doc["age_years"] > 5:
                warnings.append(
                    {
                        "level": "critical",
                        "message": f"严重过期文档: {doc['title']} ({doc['age_years']} 年 > 5 年)",
                    }
                )

        return {
            "status": "completed",
            "data": {
                "stale_count": stale_count,
                "stale_ratio": stale_ratio,
                "stale_docs": stale_docs[:10],
                "by_type": dict(by_type),
                "warnings": warnings,
            },
        }

    async def _get_source_documents(self, session) -> list[dict]:
        """通过 test_set.source_document_id 查询源文档列表

        返回: list[dict] with keys: id, title, document_type, upload_date
        """
        from src.models.rag_eval.test_set import RagEvalTestSet

        # 查询 test_set 获取 source_document_id
        result = await session.execute(
            select(RagEvalTestSet.source_document_id).where(
                RagEvalTestSet.id == self.test_run.test_set_id
            )
        )
        source_document_id = result.scalar_one_or_none()

        if not source_document_id:
            return []

        # 查询源文档
        doc_result = await session.execute(
            select(SourceDocument).where(SourceDocument.id == source_document_id)
        )
        doc = doc_result.scalar_one_or_none()

        if not doc:
            return []

        # 使用 file_type 作为 document_type，created_at 作为 upload_date
        documents = []
        if doc.chapter_structure and isinstance(doc.chapter_structure, list):
            for idx, chapter in enumerate(doc.chapter_structure):
                if isinstance(chapter, dict):
                    chapter_title = chapter.get("title", f"章节{idx + 1}")
                else:
                    chapter_title = getattr(chapter, "title", f"章节{idx + 1}")

                documents.append(
                    {
                        "id": f"{doc.id}_ch{idx}",
                        "title": f"{doc.title} - {chapter_title}",
                        "document_type": doc.file_type,
                        "upload_date": doc.created_at,
                    }
                )
        else:
            documents.append(
                {
                    "id": doc.id,
                    "title": doc.title,
                    "document_type": doc.file_type,
                    "upload_date": doc.created_at,
                }
            )

        return documents
