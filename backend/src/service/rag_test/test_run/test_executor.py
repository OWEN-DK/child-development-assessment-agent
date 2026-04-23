import asyncio
import time
import uuid
from datetime import datetime
from typing import Callable, Dict, List, Optional

from sqlalchemy import and_, select

from src.config import config_manager
from src.core.database import db_session_factory
from src.core.distributed_lock import DistributedLock
from src.models.test_case import TestCase, TestRun, TestRunResult
from src.schemas import TestResult, TestResultItem, TestRunStatus
from src.service.rag_service import rag_service
from src.utils.logger import logger


class TestExecutor:
    """测试执行器，负责执行单个测试用例"""

    def __init__(self):
        self.db_session_factory = db_session_factory

    async def execute_test_case(
        self,
        run_id: str,
        test_case: TestCase,
        progress_callback: Optional[Callable] = None,
    ) -> TestRunResult:
        """
        执行单个测试用例
        
        Args:
            run_id: 测试运行ID
            test_case: 测试用例
            progress_callback: 进度回调函数
            
        Returns:
            测试运行结果
        """
        from src.service.retrieval_service import get_retrieval_service

        retrieval_service = get_retrieval_service()

        async with self.db_session_factory() as session:
            start_time = datetime.now()
            try:
                results = await retrieval_service.retrieve_knowledge(
                    query=test_case.query,
                    age=test_case.age,
                    limit=5,
                )

                matched_count = 0
                actual_knowledge_ids = []

                for result in results:
                    actual_knowledge_ids.append(result.id)
                    if (
                        test_case.expected_knowledge_ids
                        and result.id in test_case.expected_knowledge_ids
                    ):
                        matched_count += 1

                expected_count = (
                    len(test_case.expected_knowledge_ids)
                    if test_case.expected_knowledge_ids
                    else 0
                )
                actual_count = len(actual_knowledge_ids)

                precision = matched_count / actual_count if actual_count > 0 else 0.0
                recall = matched_count / expected_count if expected_count > 0 else 0.0
                f1 = (
                    2 * precision * recall / (precision + recall)
                    if (precision + recall) > 0
                    else 0.0
                )
                passed = recall >= 0.8

                test_result = TestRunResult(
                    run_id=run_id,
                    test_case_id=test_case.id,
                    query=test_case.query,
                    precision=precision,
                    recall=recall,
                    f1=f1,
                    passed=passed,
                    matched_count=matched_count,
                    expected_count=expected_count,
                    actual_count=actual_count,
                    expected_knowledge_ids=test_case.expected_knowledge_ids,
                    actual_knowledge_ids=actual_knowledge_ids,
                    execution_time_ms=int(
                        (datetime.now() - start_time).total_seconds() * 1000
                    ),
                )

                session.add(test_result)
                await session.commit()

                if progress_callback:
                    await progress_callback(test_result)

                return test_result

            except Exception as e:
                logger.error(f"测试用例执行失败：{test_case.id}: {e}")

                test_result = TestRunResult(
                    run_id=run_id,
                    test_case_id=test_case.id,
                    query=test_case.query,
                    passed=False,
                    error_message=str(e),
                    execution_time_ms=int(
                        (datetime.now() - start_time).total_seconds() * 1000
                    ),
                )

                session.add(test_result)
                await session.commit()

                return test_result

    async def run_test_case(self, test_case: TestCase, limit: int = 10) -> TestResult:
        """
        运行单个测试用例并返回详细结果
        
        Args:
            test_case: 测试用例
            limit: 检索数量限制
            
        Returns:
            测试结果
        """
        start_time = time.time()

        results = await rag_service.retrieve_knowledge(
            query=test_case.query, age=test_case.age, limit=limit
        )

        execution_time_ms = int((time.time() - start_time) * 1000)

        test_result_items = []
        relevant_count = 0
        first_relevant_rank = None

        for idx, item in enumerate(results, 1):
            is_expected = False
            if item.id in test_case.expected_knowledge_ids:
                is_expected = True
                relevant_count += 1
                if first_relevant_rank is None:
                    first_relevant_rank = idx
            elif test_case.expected_keywords:
                content_lower = item.content.lower()
                all_keywords_found = all(
                    kw.lower() in content_lower for kw in test_case.expected_keywords
                )
                if all_keywords_found:
                    is_expected = True
                    relevant_count += 1
                    if first_relevant_rank is None:
                        first_relevant_rank = idx

            test_result_items.append(
                TestResultItem(
                    knowledge_id=item.id,
                    content=item.content,
                    score=item.relevance_score,
                    expected=is_expected,
                    rank=idx,
                )
            )

        total_retrieved = len(results)
        total_expected = max(len(test_case.expected_knowledge_ids), 1)

        precision = relevant_count / total_retrieved if total_retrieved > 0 else 0.0
        recall = relevant_count / total_expected if total_expected > 0 else 0.0
        f1_score = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        mrr = 1.0 / first_relevant_rank if first_relevant_rank is not None else 0.0

        ndcg_at_k = self._calculate_ndcg(
            test_result_items, test_case.expected_knowledge_ids
        )

        return TestResult(
            test_case_id=test_case.id,
            query=test_case.query,
            age=test_case.age,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            mrr=mrr,
            ndcg_at_k=ndcg_at_k,
            results=test_result_items,
            execution_time_ms=execution_time_ms,
        )

    def _calculate_ndcg(
        self, results: List[TestResultItem], expected_ids: List[str], k: int = 3
    ) -> float:
        """
        计算NDCG指标
        
        Args:
            results: 测试结果列表
            expected_ids: 期望的知识ID列表
            k: 截断参数
            
        Returns:
            NDCG值
        """
        import math

        if not results or not expected_ids:
            return 0.0

        top_k = results[:k]

        dcg = 0.0
        for i, item in enumerate(top_k):
            rel = 1.0 if item.knowledge_id in expected_ids else 0.0
            dcg += rel / math.log2(i + 2)

        ideal_rels = [1.0] * min(len(expected_ids), k) + [0.0] * max(
            0, k - len(expected_ids)
        )
        idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal_rels[:k]))

        if idcg == 0:
            return 0.0

        return dcg / idcg
