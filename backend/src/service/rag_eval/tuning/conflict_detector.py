"""冲突检测器——检测调优建议间的参数/效果/成本冲突"""

from src.schemas.rag_eval.tuning import ConflictPair, TuningSuggestion


class ConflictDetector:
    """检测调优建议间冲突

    检测三类冲突：
    1. parameter：两个建议修改同一参数到不同值
    2. effect：一个建议可能使另一个效果降低
    3. cost：多个建议同时采纳导致成本超预算
    """

    _MUTUALLY_OPPOSING = {
        # (category_a, category_b) 或 sorted pair 表示效果冲突
        ("increase_vector", "decrease_vector"),
        ("increase_top_k", "reduce_top_k"),
        ("tighten_filter", "relax_filter"),
        ("increase_threshold", "decrease_threshold"),
    }

    def detect_conflicts(self, suggestions: list[TuningSuggestion]) -> list[ConflictPair]:
        """检测建议列表中的所有冲突对

        Args:
            suggestions: 调优建议列表

        Returns:
            ConflictPair 列表，每对包含冲突描述和解决建议
        """
        conflicts = []

        for i in range(len(suggestions)):
            for j in range(i + 1, len(suggestions)):
                s1 = suggestions[i]
                s2 = suggestions[j]

                # 检查参数冲突
                param_conflict = self._detect_parameter_conflict(s1, s2)
                if param_conflict:
                    conflicts.append(param_conflict)
                    continue

                # 检查效果冲突
                effect_conflict = self._detect_effect_conflict(s1, s2)
                if effect_conflict:
                    conflicts.append(effect_conflict)
                    continue

                # 检查成本冲突
                cost_conflict = self._detect_cost_conflict(s1, s2)
                if cost_conflict:
                    conflicts.append(cost_conflict)

        return conflicts

    def _detect_parameter_conflict(
        self, s1: TuningSuggestion, s2: TuningSuggestion
    ) -> ConflictPair | None:
        """检测参数冲突：同参不同值"""
        if s1.category != s2.category:
            return None

        val1 = s1.suggested_value if isinstance(s1.suggested_value, dict) else {}
        val2 = s2.suggested_value if isinstance(s2.suggested_value, dict) else {}

        # 检查是否有相同 action 但不同参数
        action1 = val1.get("action", "")
        action2 = val2.get("action", "")
        if action1 and action1 == action2:
            # 检查其他参数是否冲突
            common_keys = set(val1.keys()) & set(val2.keys()) - {"action"}
            for key in common_keys:
                if val1[key] != val2[key]:
                    return ConflictPair(
                        suggestion_id_1=s1.id,
                        suggestion_id_2=s2.id,
                        conflict_type="parameter",
                        description=f"两个建议都涉及 {action1}，但参数 {key} 的值不同：'{val1[key]}' vs '{val2[key]}'",
                        resolution=f"请选择其中一个建议采纳，或手动合并为统一参数值",
                    )

        return None

    def _detect_effect_conflict(
        self, s1: TuningSuggestion, s2: TuningSuggestion
    ) -> ConflictPair | None:
        """检测效果冲突：一个建议的效果可能被另一个削弱"""
        actions = self._extract_actions(s1, s2)
        for a1, a2 in actions:
            pair = (a1, a2)
            if pair in self._MUTUALLY_OPPOSING or (a2, a1) in self._MUTUALLY_OPPOSING:
                return ConflictPair(
                    suggestion_id_1=s1.id,
                    suggestion_id_2=s2.id,
                    conflict_type="effect",
                    description=f"建议「{s1.title}」（{a1}）与建议「{s2.title}」（{a2}）效果互相削弱",
                    resolution=f"请仅采纳其中一个建议，或在更高层面协调",
                )

        return None

    def _detect_cost_conflict(
        self, s1: TuningSuggestion, s2: TuningSuggestion
    ) -> ConflictPair | None:
        """检测成本冲突：两个建议都是成本类且超出预算暗示"""
        if s1.category == "cost" and s2.category == "cost":
            return ConflictPair(
                suggestion_id_1=s1.id,
                suggestion_id_2=s2.id,
                conflict_type="cost",
                description=f"两个成本相关建议同时采纳可能导致预算超支：'{s1.title}' 和 '{s2.title}'",
                resolution=f"建议优先采纳性价比更高的方案，或分批实施",
            )

        return None

    def _extract_actions(self, s1: TuningSuggestion, s2: TuningSuggestion) -> list[tuple[str, str]]:
        """从建议中提取 action 标签"""
        actions = set()
        for s in (s1, s2):
            val = s.suggested_value if isinstance(s.suggested_value, dict) else {}
            if val.get("action"):
                actions.add(val["action"])
            if val.get("direction"):
                actions.add(val["direction"])
        # 如果两个建议都有 action，返回对比对
        if len(actions) >= 2:
            action_list = list(actions)
            return [(action_list[0], action_list[1])]
        return []
