"""冲突检测器:过滤矛盾的调参建议"""

from typing import List, Tuple
from src.model.tuning import TuningSuggestion
from src.utils.logger import logger


CONFLICT_PAIRS = {
    ("increase", "decrease"),
    ("enable", "disable"),
    ("switch", "switch"),
}

PRIORITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}

SOURCE_WEIGHT = {"rule_engine": 3, "history": 2, "llm": 1}


class ConflictDetector:
    """冲突检测器:按参数名分组,检测并过滤矛盾建议"""

    def detect(
        self, suggestions: List[TuningSuggestion]
    ) -> Tuple[List[TuningSuggestion], int]:
        """检测并过滤冲突建议"""
        param_groups = {}
        for s in suggestions:
            if s.param_name not in param_groups:
                param_groups[s.param_name] = []
            param_groups[s.param_name].append(s)

        filtered = []
        conflict_count = 0

        for param_name, group in param_groups.items():
            if len(group) == 1:
                filtered.extend(group)
                continue

            has_conflict = False
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    if self._is_conflict(group[i], group[j]):
                        has_conflict = True
                        break
                if has_conflict:
                    break

            if has_conflict:
                group.sort(
                    key=lambda s: (
                        PRIORITY_WEIGHT.get(s.priority, 0),
                        SOURCE_WEIGHT.get(s.source, 0),
                    ),
                    reverse=True,
                )
                filtered.append(group[0])
                conflict_count += len(group) - 1
                logger.info(
                    f"冲突检测: 参数 {param_name} 过滤 {len(group) - 1} 条冲突建议"
                )
            else:
                filtered.extend(group)

        logger.info(
            f"冲突检测完成: 过滤 {conflict_count} 条冲突建议,保留 {len(filtered)} 条"
        )
        return filtered, conflict_count

    def _is_conflict(self, s1: TuningSuggestion, s2: TuningSuggestion) -> bool:
        """判断两条建议是否冲突"""
        pair = (s1.action, s2.action)
        return pair in CONFLICT_PAIRS or (s2.action, s1.action) in CONFLICT_PAIRS
