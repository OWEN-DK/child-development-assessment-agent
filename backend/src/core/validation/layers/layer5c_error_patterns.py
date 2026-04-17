"""Layer 5c: 错误模式分组"""

import logging
from typing import Any
from collections import defaultdict
from sqlalchemy import select

from src.models.rag_eval.test_run_result import RagEvalTestRunResult
from src.models.rag_eval.test_case import RagEvalTestCase

logger = logging.getLogger(__name__)

FIX_SOLUTION_MAP = {
    "未召回": "增加 top_k，检查关键词覆盖",
    "排序倒置": "增加 reranker_initial_k，检查重排序模型",
    "误杀": "减小 fusion_threshold，检查同义词扩展",
    "年龄过滤排除": "降低 age_filter_strictness",
    "部分召回": "检查分块粒度，调整 chunk_size",
    "重排序误判": "检查重排序模型适用领域",
}


class Layer5cErrorPatterns:
    """Layer 5c: 错误模式分组"""

    def __init__(self, session_factory, test_run):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        """执行错误模式分组"""
        bad_cases = await self._get_bad_cases()

        if not bad_cases:
            return {"status": "skipped", "data": {"reason": "缺少 Bad Case 列表"}}

        groups = defaultdict(list)

        for bc in bad_cases:
            error_type = bc.get("failure_type", "unknown")
            domain = bc.get("domain", "unknown")
            age_group = bc.get("age_group", "unknown")

            key = f"{error_type}-{domain}-{age_group}"
            groups[key].append(bc)

        error_groups = []
        total_bad_cases = len(bad_cases)

        for group_name, cases in sorted(groups.items(), key=lambda x: -len(x[1])):
            error_type = group_name.split("-")[0]
            fix_solution = FIX_SOLUTION_MAP.get(error_type, "需进一步分析")

            error_groups.append(
                {
                    "group_name": group_name,
                    "count": len(cases),
                    "ratio": len(cases) / total_bad_cases,
                    "example_queries": [c.get("query") for c in cases[:3]],
                    "suggested_fix": fix_solution,
                }
            )

        return {
            "status": "completed",
            "data": {
                "error_groups": error_groups,
                "total_groups": len(error_groups),
                "total_bad_cases": total_bad_cases,
            },
        }

    async def _get_bad_cases(self) -> list:
        """获取 Bad Case 列表 (hit_at_5 = 0)"""
        # 通过 session_factory 查询，关联 RagEvalTestCase 获取 domain 和 age_months
        # 根据 hit_at_1/3/5 计算 failure_type
        try:
            async with self.session_factory() as session:
                stmt = (
                    select(RagEvalTestRunResult, RagEvalTestCase)
                    .join(
                        RagEvalTestCase,
                        RagEvalTestRunResult.case_id == RagEvalTestCase.id,
                    )
                    .where(
                        RagEvalTestRunResult.run_id == self.test_run.id,
                        RagEvalTestRunResult.hit_at_5 == False,
                    )
                )
                result = await session.execute(stmt)
                rows = result.all()

                return [
                    {
                        "query": r[0].query,
                        "failure_type": self._compute_failure_type(
                            r[0].hit_at_1, r[0].hit_at_3, r[0].hit_at_5
                        ),
                        "domain": r[1].domain.value if r[1].domain else "unknown",
                        "age_group": self._age_to_group(r[1].age_months),
                    }
                    for r in rows
                ]
        except Exception:
            return []

    @staticmethod
    def _compute_failure_type(hit_at_1: bool, hit_at_3: bool, hit_at_5: bool) -> str:
        """根据 hit_at 结果计算失败类型"""
        if not hit_at_5:
            if not hit_at_1 and not hit_at_3:
                return "未召回"
            elif not hit_at_1:
                return "排序倒置"
            else:
                return "部分召回"
        return "unknown"

    @staticmethod
    def _age_to_group(age_months: int | None) -> str:
        """将月龄转换为年龄段"""
        if age_months is None:
            return "unknown"
        if age_months <= 12:
            return "0-1岁"
        elif age_months <= 36:
            return "1-3岁"
        elif age_months <= 72:
            return "3-6岁"
        else:
            return "6岁以上"
