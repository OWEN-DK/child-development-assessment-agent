import difflib
from typing import List
from src.models.test_case import TestCaseDraft
from src.utils.logger import logger


class DraftDeduplicator:
    """基于相似度的草稿去重器"""

    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold

    def deduplicate(self, drafts: List[TestCaseDraft]) -> List[TestCaseDraft]:
        """去除重复草稿"""
        if not drafts:
            return []

        unique_drafts = []
        for draft in drafts:
            is_duplicate = False
            for existing in unique_drafts:
                similarity = self._calculate_similarity(draft, existing)
                if similarity > self.similarity_threshold:
                    is_duplicate = True
                    logger.debug(
                        f"草稿 {draft.id} 与 {existing.id} 相似度过高: {similarity:.2f}"
                    )
                    break

            if not is_duplicate:
                unique_drafts.append(draft)

        removed_count = len(drafts) - len(unique_drafts)
        if removed_count > 0:
            logger.info(
                f"草稿去重完成：{len(drafts)} → {len(unique_drafts)}（移除 {removed_count} 条）"
            )

        return unique_drafts

    def _calculate_similarity(
        self, draft1: TestCaseDraft, draft2: TestCaseDraft
    ) -> float:
        """计算两个草稿的相似度"""
        # 基于 query 的文本相似度
        query_sim = difflib.SequenceMatcher(None, draft1.query, draft2.query).ratio()

        # 如果领域不同，直接判定不相似
        if draft1.domain != draft2.domain:
            return query_sim * 0.5

        # 如果年龄相差超过 6 个月，降低相似度
        age_diff = abs(float(draft1.age) - float(draft2.age))
        age_factor = max(0, 1 - age_diff / 12)

        return query_sim * 0.7 + age_factor * 0.3
