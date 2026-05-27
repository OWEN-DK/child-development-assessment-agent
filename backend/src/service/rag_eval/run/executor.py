"""单用例执行器——统一执行路径"""

import asyncio

from src.repository.rag_eval.test_run_result_repository import TestRunResultRepository
from src.schemas.rag_eval.test_run import RetrievalMetrics, TestRunResultItem
from src.utils.exceptions import AppException
from src.utils.id_generator import generate_id
from src.utils.logger import logger


class TestCaseExecutor:
    """单用例执行器——统一执行路径

    所有执行（单用例/批量中的单个）都走这个类。
    """

    def __init__(
        self,
        test_run_result_repository: TestRunResultRepository,
    ):
        self._result_repo = test_run_result_repository

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

        Args:
            timeout_ms: 超时时间（毫秒），默认 300000ms（300秒）
        """
        result_id = generate_id()
        start_time = asyncio.get_event_loop().time()
        timeout_sec = (timeout_ms or 300_000) / 1000.0

        retrieved_ids = []
        retrieved_contexts = []
        actual_answer = None
        error_msg = None
        passed = False
        failure_stage = None
        retrieval_raw_count = 0

        try:
            # 检索 + 生成（RAG 流水线内部已有步骤级超时保护，外层仅保留安全网）
            async def _retrieve_and_generate():
                nonlocal retrieved_ids, retrieved_contexts, actual_answer, failure_stage, retrieval_raw_count
                if retrieval_fn:
                    case_book_ids = getattr(test_case, "book_ids", None) or None
                    retrieved = await retrieval_fn(test_case.query, book_ids=case_book_ids)
                    retrieval_raw_count = len(retrieved or [])
                    retrieved_ids = [
                        (d.get("id", "") if isinstance(d, dict) else getattr(d, "id", "") or "")
                        for d in (retrieved or [])
                        if (d.get("id", "") if isinstance(d, dict) else getattr(d, "id", "") or "")
                    ]
                    # 捕获检索上下文文本，用于 L2 指标评分
                    retrieved_contexts = [
                        (d.get("content", "") if isinstance(d, dict) else getattr(d, "content", "") or "")
                        for d in (retrieved or [])
                    ]
                    if not retrieved_ids:
                        failure_stage = "retrieval_empty"
                        logger.warning(
                            f"[RAG-EVAL] 用例 {test_case.id} 检索返回空结果 "
                            f"(原始结果数={retrieval_raw_count}), query='{test_case.query[:80]}'"
                        )
                        return
                if generation_fn and retrieved_ids:
                    actual_answer = await generation_fn(test_case.query, retrieved_ids)
                    if not actual_answer:
                        failure_stage = "generation_empty"
                        logger.warning(
                            f"[RAG-EVAL] 用例 {test_case.id} 生成返回空答案 "
                            f"(检索到 {len(retrieved_ids)} 个片段), query='{test_case.query[:80]}'"
                        )
                elif not retrieved_ids:
                    failure_stage = "no_retrieval_fn_or_empty"

            # 安全网超时，防止协程泄漏；正常执行由子系统自行管理超时
            await asyncio.wait_for(
                _retrieve_and_generate(),
                timeout=timeout_sec,
            )
            passed = actual_answer is not None
        except asyncio.TimeoutError:
            error_msg = f"单用例执行超时 ({timeout_ms or 300_000}ms)"
            failure_stage = "timeout"
        except AppException:
            raise
        except Exception as e:
            error_msg = str(e)
            failure_stage = "exception"

        if failure_stage:
            logger.info(
                f"[RAG-EVAL] 用例 {test_case.id} 执行失败: "
                f"stage={failure_stage}, retrieved={len(retrieved_ids)}, "
                f"expected={getattr(test_case, 'expected_knowledge_ids', []) or []}"
            )
            if not error_msg:
                error_msg = f"pipeline_failure:{failure_stage}"

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
            "retrieved_contexts": retrieved_contexts,
            "relevant_doc_ids": retrieved_ids,
            "expected_knowledge_ids": expected_ids,
            "actual_knowledge_ids": retrieved_ids,
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

