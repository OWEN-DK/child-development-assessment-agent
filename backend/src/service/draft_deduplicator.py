import difflib
from typing import List

from src.schemas import TestCaseDraft
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

        return query_sim
