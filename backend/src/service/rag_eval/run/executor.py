"""单用例执行器——统一执行路径"""

import asyncio

from src.core.config.cache import ConfigCache
from src.repository.rag_eval.test_run_result_repository import TestRunResultRepository
from src.schemas.rag_eval.test_run import RetrievalMetrics, TestRunResultItem
from src.utils.exceptions import AppException
from src.utils.id_generator import generate_id


class TestCaseExecutor:
    """单用例执行器——统一执行路径

    所有执行（单用例/批量中的单个）都走这个类。
    """

    def __init__(
        self,
        test_run_result_repository: TestRunResultRepository,
        config_cache: ConfigCache | None = None,
    ):
        self._result_repo = test_run_result_repository
        self._config = config_cache or ConfigCache.get_instance()

    async def execute(
        self,
        test_case,
        run_id: str,
        retrieval_fn=None,
        generation_fn=None,
        timeout_ms: int | None = None,
    ) -> TestRunResultItem:
        """执行单个测试用例

        统一执行路径：
        1. 调用 retrieval_fn 获取检索文档
        2. 调用 generation_fn 生成答案
        3. 计算检索指标
        4. 保存结果到 test_run_results
        5. 返回 TestRunResultItem
        """
        if timeout_ms is None:
            timeout_ms = self._get_config_int("rag.eval.run.timeout_ms", 30000)

        result_id = generate_id()
        start_time = asyncio.get_event_loop().time()

        retrieved_ids = []
        actual_answer = None
        error_msg = None
        passed = False

        try:
            # 检索 + 生成，带超时控制
            async def _retrieve_and_generate():
                nonlocal retrieved_ids, actual_answer
                if retrieval_fn:
                    retrieved = await retrieval_fn(test_case.query, test_case.age, test_case.domain)
                    retrieved_ids = [(d.get("id", "") if isinstance(d, dict) else getattr(d, "id", "") or "") for d in (retrieved or [])]
                if generation_fn and retrieved_ids:
                    actual_answer = await generation_fn(test_case.query, retrieved_ids)

            await asyncio.wait_for(
                _retrieve_and_generate(),
                timeout=timeout_ms / 1000.0,
            )
            passed = True
        except asyncio.TimeoutError:
            error_msg = f"单用例执行超时 ({timeout_ms}ms)"
        except AppException:
            raise
        except Exception as e:
            error_msg = str(e)

        end_time = asyncio.get_event_loop().time()
        execution_time_ms = int((end_time - start_time) * 1000)

        # 计算检索指标
        expected_ids = getattr(test_case, "expected_knowledge_ids", None) or []
        metrics = self._calculate_retrieval_metrics(expected_ids, retrieved_ids, len(retrieved_ids))

        # 保存结果
        result_data = {
            "id": result_id,
            "run_id": run_id,
            "test_case_id": test_case.id,
            "query": test_case.query,
            "retrieved_doc_ids": retrieved_ids,
            "relevant_doc_ids": retrieved_ids,
            "expected_knowledge_ids": expected_ids,
            "actual_knowledge_ids": [],
            "matched_count": metrics.matched_count,
            "expected_count": metrics.expected_count,
            "actual_count": metrics.actual_count,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1": metrics.f1,
            "mrr": metrics.mrr,
            "ndcg": metrics.ndcg,
            "hit_rate_1": metrics.hit_rate_1,
            "hit_rate_3": metrics.hit_rate_3,
            "hit_rate_5": metrics.hit_rate_5,
            "actual_answer": actual_answer,
            "passed": passed,
            "error_message": error_msg,
            "execution_time_ms": execution_time_ms,
        }
        await self._result_repo.create(result_data)

        return TestRunResultItem(**result_data)

    def _calculate_retrieval_metrics(
        self,
        expected_ids: list[str],
        actual_ids: list[str],
        total_retrieved: int,
    ) -> RetrievalMetrics:
        """计算 precision, recall, f1, mrr, ndcg, hit_rate_1/3/5"""
        expected_set = set(expected_ids)
        actual_set = set(actual_ids)
        matched = expected_set & actual_set
        matched_count = len(matched)
        expected_count = len(expected_ids)
        actual_count = total_retrieved

        # precision = matched / total_retrieved
        precision = matched_count / actual_count if actual_count > 0 else 0.0
        # recall = matched / len(expected_ids)
        recall = matched_count / expected_count if expected_count > 0 else 0.0
        # f1
        if (precision + recall) > 0:
            f1 = 2 * precision * recall / (precision + recall)
        else:
            f1 = 0.0
        # mrr = 1 / (第一个匹配的排名) or 0
        mrr = 0.0
        for i, aid in enumerate(actual_ids):
            if aid in expected_set:
                mrr = 1.0 / (i + 1)
                break
        # ndcg = DCG / ideal_DCG
        ideal_gains = sorted([1] * expected_count, reverse=True)
        ideal_dcg = sum(g / (1 + i) for i, g in enumerate(ideal_gains[:len(actual_ids)]))
        actual_dcg = sum(
            (1.0 if aid in expected_set else 0.0) / (1 + i)
            for i, aid in enumerate(actual_ids)
        ) if actual_ids else 0.0
        ndcg = actual_dcg / ideal_dcg if ideal_dcg > 0 else 0.0

        # Hit rates
        top_1 = set(actual_ids[:1])
        top_3 = set(actual_ids[:3])
        top_5 = set(actual_ids[:5])
        hit_rate_1 = 1.0 if (expected_set & top_1) else 0.0
        hit_rate_3 = 1.0 if (expected_set & top_3) else 0.0
        hit_rate_5 = 1.0 if (expected_set & top_5) else 0.0

        return RetrievalMetrics(
            precision=precision,
            recall=recall,
            f1=f1,
            mrr=mrr,
            ndcg=ndcg,
            hit_rate_1=hit_rate_1,
            hit_rate_3=hit_rate_3,
            hit_rate_5=hit_rate_5,
            matched_count=matched_count,
            expected_count=expected_count,
            actual_count=actual_count,
        )

    def _get_config_int(self, key: str, default: int) -> int:
        """从 ConfigCache 读取整数配置"""
        try:
            val = self._config.get(key)
            if val is not None:
                return int(val)
        except Exception:
            pass
        return default
