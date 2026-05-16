"""调优建议冲突检测器

检测多条调优建议之间的冲突关系，包括：
1. 参数直接冲突：两条建议指向同一节点的同一参数，值不同
2. 参数间接冲突：同节点的不同参数间有约束关系（如 vector_weight + keyword_weight = 1）
3. 效果对冲：一条提升精度、一条提升召回，方向相反
"""
from typing import Any

from src.utils.logger import logger


class ConflictDetector:
    """调优建议冲突检测器

    分析多条建议之间是否存在冲突，标记冲突类型和被冲突建议 ID。
    conflict_with 字段从单 str 改为 list[str]。
    """

    # 参数约束关系（已知的参数对及其约束）
    KNOWN_CONSTRAINTS = {
        ("vector_weight", "keyword_weight"): {
            "relation": "sum_eq_1",
            "description": "向量权重和关键词权重之和必须为 1",
        },
    }

    def detect(
        self, suggestions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """检测建议列表中的冲突

        Returns:
            更新了 conflict_with 字段的建议列表（原地修改）
        """
        if len(suggestions) <= 1:
            return suggestions

        n = len(suggestions)
        # conflict_with[i] 存储与 suggestions[i] 冲突的建议 ID 列表
        conflict_ids: list[list[str]] = [[] for _ in range(n)]

        for i in range(n):
            for j in range(i + 1, n):
                conflict_type = self._detect_conflict(suggestions[i], suggestions[j])
                if conflict_type:
                    conflict_ids[i].append(suggestions[j]["id"])
                    conflict_ids[j].append(suggestions[i]["id"])
                    suggestions[i]["_conflict_type"] = conflict_type
                    suggestions[j]["_conflict_type"] = conflict_type

        # 更新各条建议的 conflict_with 字段
        for i in range(n):
            if conflict_ids[i]:
                suggestions[i]["conflict_with"] = conflict_ids[i]
            else:
                suggestions[i]["conflict_with"] = None

        total_conflicts = sum(1 for c in conflict_ids if c)
        if total_conflicts:
            logger.info(f"检测到 {total_conflicts} 条建议存在冲突关系")

        return suggestions

    def _detect_conflict(
        self, a: dict[str, Any], b: dict[str, Any]
    ) -> str | None:
        """检测两条建议之间的冲突类型

        Returns:
            冲突类型字符串（direct/indirect/hedging）或 None
        """
        # 1. 参数直接冲突
        if (
            a.get("target_node_id")
            and a["target_node_id"] == b.get("target_node_id")
            and a.get("target_param")
            and a["target_param"] == b.get("target_param")
            and a.get("suggested_value") != b.get("suggested_value")
        ):
            return "direct"

        # 2. 参数间接冲突（同节点不同参数有约束关系）
        if (
            a.get("target_node_id")
            and a["target_node_id"] == b.get("target_node_id")
            and a.get("target_param") != b.get("target_param")
        ):
            param_pair = (a.get("target_param"), b.get("target_param"))
            reverse_pair = (b.get("target_param"), a.get("target_param"))
            if param_pair in self.KNOWN_CONSTRAINTS or reverse_pair in self.KNOWN_CONSTRAINTS:
                return "indirect"

        # 3. 效果对冲（一条提升精度、一条提升召回）
        a_title = (a.get("title") or "").lower()
        b_title = (b.get("title") or "").lower()
        if ("精确" in a_title and "召回" in b_title) or (
            "召回" in a_title and "精确" in b_title
        ):
            return "hedging"

        return None
