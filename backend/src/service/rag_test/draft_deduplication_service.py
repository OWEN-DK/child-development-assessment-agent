"""草稿去重服务

与历史草稿比对，阈值 0.85，去重后重新编号 draft_index
"""

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List

from sqlalchemy import select

from src.core.database import db_session_factory
from src.models.test_case import TestCaseDraft, TestDomain


@dataclass
class DraftData:
    """草稿数据载体"""

    query: str
    age: float
    domain: str
    age_stage_label: str
    draft_index: int = 0
    description: str = ""
    expected_keywords: List[str] = None
    answer_points: List[str] = None
    professional_terms: List[str] = None

    def __post_init__(self):
        if self.expected_keywords is None:
            self.expected_keywords = []
        if self.answer_points is None:
            self.answer_points = []
        if self.professional_terms is None:
            self.professional_terms = []


class DraftDeduplicationService:
    """草稿去重服务（与历史草稿比对）"""

    def __init__(self, threshold: float = 0.85):
        """
        Args:
            threshold: 语义相似度阈值，超过此值视为重复
        """
        self.threshold = threshold

    async def deduplicate_drafts(
        self,
        new_drafts: List[DraftData],
        doc_id: str,
        domain: str,
        age_stage_label: str,
    ) -> List[DraftData]:
        """
        将新生成的草稿与历史草稿比对，过滤重复项。

        Returns:
            去重后的草稿列表（未重新编号）
        """
        existing_drafts = await self._get_existing_drafts(doc_id, domain, age_stage_label)
        if not existing_drafts:
            return new_drafts

        filtered = []
        for draft in new_drafts:
            is_dup = await self._is_duplicate(draft, existing_drafts)
            if not is_dup:
                filtered.append(draft)
        return filtered

    def renumber_draft_index(self, drafts: List[DraftData]) -> List[DraftData]:
        """重新编号 draft_index（从 0 开始连续）"""
        for idx, draft in enumerate(drafts):
            draft.draft_index = idx
        return drafts

    async def _get_existing_drafts(
        self,
        doc_id: str,
        domain: str,
        age_stage_label: str,
    ) -> List[TestCaseDraft]:
        """查询同一文档、同一领域、同一年龄段的历史草稿"""
        domain_enum = None
        if domain in [e.value for e in TestDomain]:
            domain_enum = TestDomain(domain)

        async with db_session_factory() as session:
            stmt = select(TestCaseDraft).where(
                TestCaseDraft.source_document_id == doc_id,
                TestCaseDraft.age_stage_label == age_stage_label,
            )
            if domain_enum:
                stmt = stmt.where(TestCaseDraft.domain == domain_enum)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def _is_duplicate(
        self,
        new_draft: DraftData,
        existing_drafts: List[TestCaseDraft],
    ) -> bool:
        """判断新草稿是否与任一历史草稿重复"""
        for existing in existing_drafts:
            similarity = self._calculate_similarity(new_draft, existing)
            if similarity >= self.threshold:
                return True
        return False

    def _calculate_similarity(self, new_draft: DraftData, existing) -> float:
        """
        综合相似度计算：
        - 文本相似度（difflib.SequenceMatcher）: 70%
        - 领域匹配: 固定权重
        - 年龄差距: 衰减因子
        """
        query_sim = SequenceMatcher(None, new_draft.query, existing.query).ratio()
        domain_match = 1.0 if new_draft.domain == existing.domain.value else 0.5
        age_diff = abs(new_draft.age - float(existing.age))
        age_factor = max(0, 1 - age_diff / 24)
        return query_sim * 0.7 * domain_match + age_factor * 0.3
