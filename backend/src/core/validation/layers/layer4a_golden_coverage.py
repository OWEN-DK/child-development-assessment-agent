"""Layer 4a: Golden 覆盖度分析

检查测试用例是否覆盖足够的源文档和章节。
"""

import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import select

from src.models.document import SourceDocument
from src.models.rag_eval.test_case import RagEvalTestCase
from src.models.rag_eval.test_set_case import RagEvalTestSetCase

logger = logging.getLogger(__name__)


class Layer4aGoldenCoverage:
    """Layer 4a: 黄金覆盖度分析"""

    def __init__(self, session_factory, test_run):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        """执行覆盖度分析"""
        async with self.session_factory() as session:
            test_cases = await self._get_test_cases(session)
            source_documents = await self._get_source_documents(session)

        if not test_cases or not source_documents:
            return {"status": "skipped", "data": {"reason": "缺少测试用例或源文档"}}

        # 构建 doc_id → doc 索引（O(1) 查找）
        doc_index = {d["id"]: d for d in source_documents if d.get("id")}

        # 计算覆盖率
        covered_books = set()
        covered_chapters = set()
        domain_coverage = defaultdict(set)

        for tc in test_cases:
            doc_id = tc.get("source_document_id")
            if doc_id and doc_id in doc_index:
                doc = doc_index[doc_id]
                covered_books.add(doc.get("book_id"))
                covered_chapters.add(doc.get("chapter_id"))
                domain_coverage[doc.get("domain", "unknown")].add(doc_id)

        total_books = set(
            d.get("book_id") for d in source_documents if d.get("book_id")
        )
        total_chapters = set(
            d.get("chapter_id") for d in source_documents if d.get("chapter_id")
        )

        book_coverage = len(covered_books) / len(total_books) if total_books else 0
        chapter_coverage = (
            len(covered_chapters) / len(total_chapters) if total_chapters else 0
        )

        # 生成警告
        warnings = []
        if book_coverage < 0.60:
            warnings.append(
                {
                    "level": "warning",
                    "message": f"书籍覆盖率低 ({book_coverage:.1%} < 60%)",
                }
            )
        if chapter_coverage < 0.40:
            warnings.append(
                {
                    "level": "warning",
                    "message": f"章节覆盖率低 ({chapter_coverage:.1%} < 40%)",
                }
            )

        all_domains = set(d.get("domain") for d in source_documents if d.get("domain"))
        uncovered_domains = all_domains - set(domain_coverage.keys())
        for domain in uncovered_domains:
            warnings.append({"level": "critical", "message": f"领域 '{domain}' 无覆盖"})

        return {
            "status": "completed",
            "data": {
                "book_coverage": book_coverage,
                "chapter_coverage": chapter_coverage,
                "domain_coverage": {k: len(v) for k, v in domain_coverage.items()},
                "warnings": warnings,
            },
        }

    async def _get_test_cases(self, session) -> list[dict]:
        """通过 test_set_id 查询测试用例列表

        数据路径: RagEvalTestRun → test_set_id → RagEvalTestSetCase → RagEvalTestCase
        返回: list[dict] with keys: source_document_id (from expected_document_ids), domain
        """
        result = await session.execute(
            select(RagEvalTestCase)
            .join(
                RagEvalTestSetCase,
                RagEvalTestCase.id == RagEvalTestSetCase.case_id,
            )
            .where(RagEvalTestSetCase.test_set_id == self.test_run.test_set_id)
        )
        cases = result.scalars().all()

        test_cases = []
        for case in cases:
            # 从 expected_document_ids 提取第一个文档 ID 作为 source_document_id
            source_doc_id = None
            if case.expected_document_ids and len(case.expected_document_ids) > 0:
                source_doc_id = case.expected_document_ids[0]

            test_cases.append(
                {
                    "source_document_id": source_doc_id,
                    "domain": case.domain.value
                    if hasattr(case.domain, "value")
                    else str(case.domain),
                }
            )

        return test_cases

    async def _get_source_documents(self, session) -> list[dict]:
        """通过 test_set.source_document_id 查询源文档列表

        返回: list[dict] with keys: id, book_id, chapter_id, domain
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

        # 从 quality_report 中提取建议的领域
        domains = []
        if doc.quality_report and isinstance(doc.quality_report, dict):
            domains = doc.quality_report.get("suggested_domains", [])

        # 从 chapter_structure 中提取章节信息
        documents = []
        if doc.chapter_structure and isinstance(doc.chapter_structure, list):
            for idx, chapter in enumerate(doc.chapter_structure):
                # chapter 可能是 dict 或 ChapterInfo 对象
                if isinstance(chapter, dict):
                    chapter_title = chapter.get("title", f"章节{idx + 1}")
                else:
                    chapter_title = getattr(chapter, "title", f"章节{idx + 1}")

                # 使用文档 ID 作为 book_id，章节标题作为 chapter_id
                documents.append(
                    {
                        "id": f"{doc.id}_ch{idx}",
                        "book_id": doc.id,
                        "chapter_id": chapter_title,
                        "domain": domains[0] if domains else None,
                    }
                )
        else:
            # 如果没有章节结构，将整个文档作为一个单元
            documents.append(
                {
                    "id": doc.id,
                    "book_id": doc.id,
                    "chapter_id": None,
                    "domain": domains[0] if domains else None,
                }
            )

        return documents
