"""结果聚合与运行对比"""

from src.repository.rag_eval.test_run_repository import TestRunRepository
from src.repository.rag_eval.test_run_result_repository import TestRunResultRepository
from src.schemas.rag_eval.test_run import RunComparison, TestRunRead, TestRunResultItem
from src.utils.exceptions import (
    AppException,
    TestRunNotFoundException,
)
from src.utils.orm_mapper import OrmMapper


class ResultProcessor:
    """结果聚合与运行对比"""

    def __init__(
        self,
        test_run_repository: TestRunRepository,
        test_run_result_repository: TestRunResultRepository,
        orm_mapper: OrmMapper,
    ):
        self._run_repo = test_run_repository
        self._result_repo = test_run_result_repository
        self._mapper = orm_mapper

    async def aggregate(self, run_id: str) -> int:
        """汇总单次运行结果，更新 test_runs 扁平指标字段

        Returns:
            通过的用例数
        """
        results = await self._result_repo.get_by_run_id(run_id)
        if not results:
            return 0

        passed = sum(1 for r in results if r.passed)
        total = len(results)

        precision_vals = [r.precision for r in results if r.precision is not None]
        recall_vals = [r.recall for r in results if r.recall is not None]
        f1_vals = [r.f1 for r in results if r.f1 is not None]
        mrr_vals = [r.mrr for r in results if r.mrr is not None]
        ndcg_vals = [r.ndcg for r in results if r.ndcg is not None]

        update_data = {
            "passed_test_cases": passed,
            "total_test_cases": total,
        }
        if precision_vals:
            update_data["overall_precision"] = sum(precision_vals) / len(precision_vals)
        if recall_vals:
            update_data["overall_recall"] = sum(recall_vals) / len(recall_vals)
        if f1_vals:
            update_data["overall_f1"] = sum(f1_vals) / len(f1_vals)
        if mrr_vals:
            update_data["overall_mrr"] = sum(mrr_vals) / len(mrr_vals)
        if ndcg_vals:
            update_data["overall_ndcg"] = sum(ndcg_vals) / len(ndcg_vals)

        await self._run_repo.update(run_id, update_data)
        return passed

    async def compare(self, run_id_1: str, run_id_2: str) -> RunComparison:
        """比较两个测试运行，返回 RunComparison"""
        run_1 = await self._run_repo.get_by_id(run_id_1)
        run_2 = await self._run_repo.get_by_id(run_id_2)
        if not run_1:
            raise TestRunNotFoundException(run_id_1)
        if not run_2:
            raise TestRunNotFoundException(run_id_2)

        run_1_read = self._mapper.to_read(run_1, TestRunRead)
        run_2_read = self._mapper.to_read(run_2, TestRunRead)

        # 计算指标 delta
        metric_keys = ["overall_precision", "overall_recall", "overall_f1", "overall_mrr", "overall_ndcg"]
        metric_deltas = {}
        improved = []
        degraded = []
        for key in metric_keys:
            v1 = getattr(run_1, key, None) or 0
            v2 = getattr(run_2, key, None) or 0
            delta = v2 - v1
            metric_deltas[key.replace("overall_", "")] = round(float(delta), 4)
            if delta > 0:
                improved.append(key.replace("overall_", ""))
            elif delta < 0:
                degraded.append(key.replace("overall_", ""))

        # 获取两轮运行的未通过用例 ID
        bad_1 = await self._get_bad_case_ids(run_id_1)
        bad_2 = await self._get_bad_case_ids(run_id_2)

        set_1 = set(bad_1)
        set_2 = set(bad_2)

        return RunComparison(
            run_1=run_1_read,
            run_2=run_2_read,
            metric_deltas=metric_deltas,
            improved=improved,
            degraded=degraded,
            common_bad_cases=list(set_1 & set_2),
            new_bad_cases=list(set_2 - set_1),
            fixed_bad_cases=list(set_1 - set_2),
        )

    async def get_bad_cases(self, run_id: str) -> list[TestRunResultItem]:
        """获取坏案列表（passed=false 的用例）"""
        results = await self._result_repo.get_failed_results_by_run(run_id)
        return self._mapper.to_read_list(results, TestRunResultItem)

    async def _get_bad_case_ids(self, run_id: str) -> list[str]:
        """获取未通过的用例 ID 列表"""
        results = await self._result_repo.get_failed_results_by_run(run_id)
        return [r.test_case_id for r in results]
