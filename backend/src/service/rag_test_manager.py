import json
import os
import shutil
import time
import math
import hashlib
from typing import Dict, List, Optional, Tuple, Callable, Awaitable
from datetime import datetime
from jsonschema import validate, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
import uuid

from src.models.test_case import (
    TestCase,
    TestRun,
    KnowledgeSnapshot,
    TestResultItem,
    SourceDocument,
    DocumentStatus,
    TestCaseDraft,
    DraftStatus,
    GenerationParams,
    TestSet,
    TestSetCase,
    TestRunResult,
    TestRunStatus,
    TestDomain,
    DifficultyLevel,
)
from src.models.document import SourceDocument, DocumentStatus
from src.model.rag_test import TestResult
from src.service.rag_service import rag_service
from src.config import settings, config_manager
from src.service.document_manager import document_manager
from src.utils.logger import logger
from src.constants.test_case import TEST_CASE_DOMAINS, TEST_CASE_REQUIRED_FIELDS
from src.core.prompts_fallback import TEST_CASE_DRAFT_GENERATION_PROMPT
from src.core.llm.factory import LLMServiceFactory, LLMFramework
from src.core.llm.base import LLMRequest, LLMMessage
from src.core.database import db_session_factory
from src.core.distributed_lock import DistributedLock
import asyncio

STORAGE_DIR = settings.rag_storage_dir
SNAPSHOTS_DIR = f"{settings.rag_storage_dir}/snapshots"
SOURCE_DOCUMENTS_DIR = f"{settings.rag_storage_dir}/source_documents"
TEST_RUNS_DIR = f"{settings.rag_storage_dir}/test_runs"

# JSON导入Schema
TEST_CASE_IMPORT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": TEST_CASE_REQUIRED_FIELDS,
        "properties": {
            "query": {"type": "string", "minLength": 1},
            "age": {"type": "integer", "minimum": 0, "maximum": 18},
            "domain": {"type": "string", "enum": TEST_CASE_DOMAINS + ["未知"]},
            "expected_knowledge_ids": {"type": "array", "items": {"type": "string"}},
            "expected_keywords": {"type": "array", "items": {"type": "string"}},
            "description": {"type": "string"},
            "answer_points": {"type": "array", "items": {"type": "string"}},
            "professional_terms": {"type": "array", "items": {"type": "string"}},
            "age_requirement": {"type": "string"},
        },
        "additionalProperties": False,
    },
}


class RagTestManager:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RagTestManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.snapshots_dir = SNAPSHOTS_DIR
        self.test_runs_dir = TEST_RUNS_DIR
        self.db_session_factory = db_session_factory

        # Ensure directories exist
        os.makedirs(self.snapshots_dir, exist_ok=True)
        os.makedirs(SOURCE_DOCUMENTS_DIR, exist_ok=True)
        os.makedirs(self.test_runs_dir, exist_ok=True)

        self._initialized = True

    async def create_test_run(
        self,
        name: str,
        description: str = None,
        test_case_ids: list[str] = None,
        test_set_id: str = None,
    ) -> str:
        """创建测试运行"""
        async with self.db_session_factory() as session:
            run_id = str(uuid.uuid4())

            # 获取测试用例列表
            if test_case_ids:
                stmt = select(TestCase).where(TestCase.id.in_(test_case_ids))
                result = await session.execute(stmt)
                test_cases = result.scalars().all()
            elif test_set_id:
                # 从测试集获取
                stmt = (
                    select(TestCase)
                    .join(TestSetCase)
                    .where(TestSetCase.test_set_id == test_set_id)
                    .options(selectinload(TestSetCase.test_case))
                )
                result = await session.execute(stmt)
                test_cases = result.scalars().all()
            else:
                # 默认所有测试用例
                stmt = select(TestCase)
                result = await session.execute(stmt)
                test_cases = result.scalars().all()

            # 创建测试运行
            test_run = TestRun(
                id=run_id,
                name=name,
                description=description,
                total_test_cases=len(test_cases),
                passed_test_cases=0,
                status=TestRunStatus.RUNNING,
            )

            session.add(test_run)
            await session.commit()

            logger.info(f"测试运行已创建：{run_id}, 共 {len(test_cases)} 个用例")
            return run_id

    async def add_test_case(self, test_case: TestCase) -> TestCase:
        """添加测试用例"""
        from src.repository import TestCaseRepository

        repo = TestCaseRepository(self.db_session_factory)
        case_data = {
            "id": test_case.id or str(uuid.uuid4()),
            "query": test_case.query,
            "age": test_case.age,
            "domain": test_case.domain,
            "description": test_case.description,
            "expected_knowledge_count": test_case.expected_knowledge_count,
            "answer_points_summary": test_case.answer_points_summary,
            "min_age_requirement": test_case.min_age_requirement,
            "max_age_requirement": test_case.max_age_requirement,
            "difficulty_level": test_case.difficulty_level,
            "expected_knowledge_ids": test_case.expected_knowledge_ids,
            "expected_keywords": test_case.expected_keywords,
            "professional_terms": test_case.professional_terms,
            "relevance_scores": test_case.relevance_scores,
            "source_document_id": test_case.source_document_id,
            "version": test_case.version,
        }
        created = await repo.create(case_data)
        logger.info(f"Test case added: {created.id}")
        return created

    async def execute_test_case(
        self,
        run_id: str,
        test_case: TestCase,
        progress_callback: Optional[Callable] = None,
    ) -> TestRunResult:
        """执行单个测试用例"""
        async with self.db_session_factory() as session:
            # 执行检索
            from src.service.retrieval_service import RetrievalService

            retrieval_service = RetrievalService()

            start_time = datetime.now()
            try:
                results = await retrieval_service.search(
                    query=test_case.query,
                    age=test_case.age,
                    limit=5,
                )

                # 计算指标
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
                passed = recall >= 0.8  # 召回率 >= 80% 视为通过

                # 创建结果
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

                # 进度回调
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

    async def complete_test_run(self, run_id: str):
        """完成测试运行，计算聚合指标"""
        async with self.db_session_factory() as session:
            # 获取所有结果
            stmt = select(TestRunResult).where(TestRunResult.run_id == run_id)
            result = await session.execute(stmt)
            test_results = result.scalars().all()

            # 计算聚合指标
            total = len(test_results)
            passed = sum(1 for r in test_results if r.passed)

            avg_precision = (
                sum(r.precision for r in test_results if r.precision is not None)
                / total
                if total > 0
                else 0.0
            )
            avg_recall = (
                sum(r.recall for r in test_results if r.recall is not None) / total
                if total > 0
                else 0.0
            )
            avg_f1 = (
                sum(r.f1 for r in test_results if r.f1 is not None) / total
                if total > 0
                else 0.0
            )

            # 更新测试运行
            stmt = select(TestRun).where(TestRun.id == run_id)
            result = await session.execute(stmt)
            test_run = result.scalar_one()

            test_run.status = TestRunStatus.COMPLETED
            test_run.completed_at = datetime.now()
            test_run.passed_test_cases = passed
            test_run.overall_precision = avg_precision
            test_run.overall_recall = avg_recall
            test_run.overall_f1 = avg_f1

            await session.commit()

            logger.info(
                f"测试运行已完成：{run_id}, 通过率={passed}/{total}={passed / total:.2%}"
            )

    async def execute_batch(
        self,
        run_id: str,
        concurrency: int = 5,
        progress_callback: Optional[Callable] = None,
    ) -> list:
        """批量执行测试用例（带分布式锁）"""

        lock_name = f"rag:test_run:{run_id}"

        async def _execute_with_lock():
            """在分布式锁保护下执行"""
            async with self.db_session_factory() as session:
                # 获取测试用例
                stmt = select(TestRun).where(TestRun.id == run_id)
                result = await session.execute(stmt)
                test_run = result.scalar_one()

                # 获取未执行的测试用例
                stmt = (
                    select(TestCase)
                    .outerjoin(
                        TestRunResult,
                        and_(
                            TestCase.id == TestRunResult.test_case_id,
                            TestRunResult.run_id == run_id,
                        ),
                    )
                    .where(TestRunResult.id.is_(None))  # 未执行的
                )
                result = await session.execute(stmt)
                test_cases = result.scalars().all()

            # 并发执行
            semaphore = asyncio.Semaphore(concurrency)

            async def execute_single(test_case):
                async with semaphore:
                    return await self.execute_test_case(
                        run_id, test_case, progress_callback
                    )

            tasks = [execute_single(tc) for tc in test_cases]
            results = await asyncio.gather(*tasks)

            # 完成运行
            await self.complete_test_run(run_id)

            return results

        # 使用分布式锁执行
        results = await DistributedLock.execute_with_lock(
            lock_name,
            _execute_with_lock,
            timeout=3600,  # 1 小时超时
        )

        return results

    async def update_test_case(
        self, test_case_id: str, test_case: TestCase
    ) -> Optional[TestCase]:
        """更新测试用例"""
        from src.repository import TestCaseRepository

        repo = TestCaseRepository(self.db_session_factory)
        existing = await repo.get_by_id(test_case_id)
        if not existing:
            return None

        update_data = {}
        for key, value in test_case.model_dump(exclude_unset=True).items():
            if hasattr(existing, key):
                update_data[key] = value
        update_data["updated_at"] = datetime.now()

        updated = await repo.update(test_case_id, update_data)
        logger.info(f"Test case updated: {test_case_id}")
        return updated

    async def delete_test_case(self, test_case_id: str) -> bool:
        """删除测试用例"""
        from src.repository import TestCaseRepository

        repo = TestCaseRepository(self.db_session_factory)
        existing = await repo.get_by_id(test_case_id)
        if not existing:
            return False
        result = await repo.delete(test_case_id)
        if result:
            logger.info(f"Test case deleted: {test_case_id}")
        return result

    async def batch_delete_test_cases(self, case_ids: List[str]) -> int:
        """批量删除测试用例"""
        from src.repository import TestCaseRepository
        
        repo = TestCaseRepository(self.db_session_factory)
        deleted_count = 0
        for case_id in case_ids:
            if await repo.delete(case_id):
                deleted_count += 1
                logger.info(f"Test case deleted: {case_id}")
        return deleted_count

    async def batch_delete_test_runs(self, run_ids: List[str]) -> int:
        """批量删除测试运行（评估报告）"""
        from src.repository import TestRunRepository
        
        repo = TestRunRepository(self.db_session_factory)
        deleted_count = 0
        for run_id in run_ids:
            if await repo.delete(run_id):
                deleted_count += 1
                # 删除本地存储的测试运行文件
                run_dir = f"{self.test_runs_dir}/{run_id}"
                if os.path.exists(run_dir):
                    shutil.rmtree(run_dir)
                logger.info(f"Test run deleted: {run_id}")
        return deleted_count

    async def delete_draft(self, draft_id: str) -> bool:
        """删除草稿"""
        from src.repository import TestCaseDraftRepository
        
        repo = TestCaseDraftRepository(self.db_session_factory)
        existing = await repo.get_by_id(draft_id)
        if not existing:
            return False
        result = await repo.delete(draft_id)
        if result:
            logger.info(f"Draft deleted: {draft_id}")
        return result

    async def batch_delete_drafts(self, draft_ids: List[str]) -> int:
        """批量删除草稿"""
        from src.repository import TestCaseDraftRepository
        
        repo = TestCaseDraftRepository(self.db_session_factory)
        deleted_count = 0
        for draft_id in draft_ids:
            if await repo.delete(draft_id):
                deleted_count += 1
                logger.info(f"Draft deleted: {draft_id}")
        return deleted_count

    async def get_test_case(self, test_case_id: str) -> Optional[TestCase]:
        """获取单个测试用例"""
        from src.repository import TestCaseRepository

        repo = TestCaseRepository(self.db_session_factory)
        return await repo.get_by_id(test_case_id)

    async def list_test_cases(self) -> List[TestCase]:
        """列出所有测试用例"""
        from src.repository import TestCaseRepository

        repo = TestCaseRepository(self.db_session_factory)
        return await repo.get_all(limit=10000)

    async def analyze_test_run(self, run_id: str) -> dict:
        """分析测试运行结果"""
        async with self.db_session_factory() as session:
            # 获取运行信息
            stmt = select(TestRun).where(TestRun.id == run_id)
            result = await session.execute(stmt)
            test_run = result.scalar_one()

            # 获取结果
            stmt = select(TestRunResult).where(TestRunResult.run_id == run_id)
            result = await session.execute(stmt)
            test_results = result.scalars().all()

            # 按领域分析
            domain_stats = {}
            for test_result in test_results:
                test_case = await session.get(TestCase, test_result.test_case_id)
                domain = test_case.domain.value

                if domain not in domain_stats:
                    domain_stats[domain] = {
                        "total": 0,
                        "passed": 0,
                        "precision_sum": 0.0,
                        "recall_sum": 0.0,
                    }

                domain_stats[domain]["total"] += 1
                if test_result.passed:
                    domain_stats[domain]["passed"] += 1
                if test_result.precision:
                    domain_stats[domain]["precision_sum"] += test_result.precision
                if test_result.recall:
                    domain_stats[domain]["recall_sum"] += test_result.recall

            # 计算平均值
            for domain in domain_stats:
                total = domain_stats[domain]["total"]
                domain_stats[domain]["avg_precision"] = (
                    domain_stats[domain]["precision_sum"] / total
                )
                domain_stats[domain]["avg_recall"] = (
                    domain_stats[domain]["recall_sum"] / total
                )
                domain_stats[domain]["pass_rate"] = (
                    domain_stats[domain]["passed"] / total
                )

            return {
                "run_id": run_id,
                "name": test_run.name,
                "status": test_run.status,
                "total": test_run.total_test_cases,
                "passed": test_run.passed_test_cases,
                "overall_precision": test_run.overall_precision,
                "overall_recall": test_run.overall_recall,
                "overall_f1": test_run.overall_f1,
                "domain_stats": domain_stats,
            }

    async def compare_test_runs(self, run_id_1: str, run_id_2: str) -> dict:
        """对比两个测试运行"""
        stats_1 = await self.analyze_test_run(run_id_1)
        stats_2 = await self.analyze_test_run(run_id_2)

        return {
            "run_1": stats_1,
            "run_2": stats_2,
            "comparison": {
                "precision_diff": stats_2["overall_precision"]
                - stats_1["overall_precision"],
                "recall_diff": stats_2["overall_recall"] - stats_1["overall_recall"],
                "f1_diff": stats_2["overall_f1"] - stats_1["overall_f1"],
                "pass_rate_diff": (stats_2["passed"] / stats_2["total"])
                - (stats_1["passed"] / stats_1["total"]),
            },
        }

    async def recalculate_aggregate_scores(self):
        """全量重新计算聚合评分（放入 BackgroundTasks 异步执行）"""
        async with self.db_session_factory() as session:
            # 获取所有已完成的运行
            stmt = select(TestRun).where(TestRun.status == TestRunStatus.COMPLETED)
            result = await session.execute(stmt)
            runs = result.scalars().all()

            for run in runs:
                # 重新计算该运行的聚合指标
                results_stmt = select(TestRunResult).where(
                    TestRunResult.run_id == run.id
                )
                results_result = await session.execute(results_stmt)
                results = results_result.scalars().all()

                if not results:
                    continue

                total = len(results)
                passed = sum(1 for r in results if r.passed)
                run.passed_test_cases = passed
                run.overall_precision = (
                    sum(r.precision for r in results if r.precision) / total
                )
                run.overall_recall = sum(r.recall for r in results if r.recall) / total
                run.overall_f1 = sum(r.f1 for r in results if r.f1) / total

            await session.commit()
            logger.info(f"聚合评分已重算：{len(runs)} 个运行")

    async def preview_import_cases(
        self, import_data: List[dict]
    ) -> Tuple[List[dict], List[dict], List[dict]]:
        """预览导入的测试用例，返回有效/无效/重复数据"""
        valid_cases = []
        invalid_cases = []
        duplicates = []

        # 1. Schema校验
        try:
            validate(instance=import_data, schema=TEST_CASE_IMPORT_SCHEMA)
        except ValidationError as e:
            return (
                [],
                [
                    {
                        "index": 0,
                        "data": import_data[0] if import_data else {},
                        "error": str(e),
                    }
                ],
                [],
            )

        # Get all existing test cases for duplicate check
        async def _get_existing():
            async with self.db_session_factory() as session:
                stmt = select(TestCase)
                result = await session.execute(stmt)
                return list(result.scalars().all())

        existing_cases = await _get_existing()

        # 2. 业务规则校验和重复检测
        for i, case_data in enumerate(import_data):
            # 校验age范围
            if case_data["age"] < 0 or case_data["age"] > 18:
                invalid_cases.append(
                    {
                        "index": i,
                        "data": case_data,
                        "error": f"年龄超出范围: {case_data['age']}，必须在0-18之间",
                    }
                )
                continue

            # 校验domain
            domain = case_data.get("domain", "未知")
            if domain not in [d.value for d in TestDomain] + ["未知"]:
                invalid_cases.append(
                    {
                        "index": i,
                        "data": case_data,
                        "error": f"无效的领域: {domain}，可选值: {[d.value for d in TestDomain]}",
                    }
                )
                continue

            # 检测重复（query + age + domain）
            duplicate_found = False
            for existing_case in existing_cases:
                if (
                    existing_case.query == case_data["query"]
                    and existing_case.age == case_data["age"]
                    and existing_case.domain.value == domain
                ):
                    duplicates.append(
                        {"index": i, "data": case_data, "existing_id": existing_case.id}
                    )
                    duplicate_found = True
                    break

            if not duplicate_found:
                valid_cases.append({"index": i, "data": case_data})

        return valid_cases, invalid_cases, duplicates

    async def batch_import_cases(
        self, cases_data: List[dict], test_set_id: Optional[str] = None
    ) -> Dict:
        """批量导入测试用例（事务性操作）"""
        # 阶段1：预校验所有数据
        test_cases = []
        for case_data in cases_data:
            try:
                # Convert domain string to enum
                if "domain" in case_data and isinstance(case_data["domain"], str):
                    if case_data["domain"] == "未知":
                        case_data["domain"] = (
                            TestDomain.SENSORY_INTEGRATION
                        )  # Default value for unknown
                    else:
                        case_data["domain"] = TestDomain(case_data["domain"])

                test_case = TestCase(**case_data)
                if not test_case.id:
                    test_case.id = str(uuid.uuid4())
                test_cases.append(test_case)
            except Exception as e:
                raise ValueError(f"测试用例数据无效: {str(e)}")

        # 阶段2：原子写入到数据库
        async def _import():
            async with self.db_session_factory() as session:
                imported_ids = []
                try:
                    # 再次检测重复
                    for test_case in test_cases:
                        stmt = select(TestCase).where(
                            TestCase.query == test_case.query,
                            TestCase.age == test_case.age,
                            TestCase.domain == test_case.domain,
                        )
                        result = await session.execute(stmt)
                        if result.scalar_one_or_none():
                            raise ValueError(
                                f"测试用例重复: {test_case.query} (age: {test_case.age}, domain: {test_case.domain.value})"
                            )

                    # Add all test cases
                    for test_case in test_cases:
                        session.add(test_case)
                        imported_ids.append(test_case.id)

                    # If test set ID is provided, add all cases to the test set
                    if test_set_id:
                        test_set = await session.get(TestSet, test_set_id)
                        if test_set:
                            # Get existing case IDs
                            stmt = select(TestSetCase.test_case_id).where(
                                TestSetCase.test_set_id == test_set_id
                            )
                            result = await session.execute(stmt)
                            existing_ids = [row[0] for row in result.all()]

                            # Add new cases
                            for case_id in imported_ids:
                                if case_id not in existing_ids:
                                    ts_case = TestSetCase(
                                        test_set_id=test_set_id, test_case_id=case_id
                                    )
                                    session.add(ts_case)

                    await session.commit()
                    return imported_ids
                except Exception as e:
                    await session.rollback()
                    raise e

        try:
            imported_ids = await _import()

            return {
                "imported_count": len(imported_ids),
                "failed_count": 0,
                "test_case_ids": imported_ids,
                "errors": [],
            }
        except Exception as e:
            raise e

    async def run_test_case(self, test_case: TestCase, limit: int = 10) -> TestResult:
        """执行单个测试用例"""
        start_time = time.time()

        # 执行检索
        results = await rag_service.retrieve_knowledge(
            query=test_case.query, age=test_case.age, limit=limit
        )

        execution_time_ms = int((time.time() - start_time) * 1000)

        # 处理结果
        test_result_items = []
        relevant_count = 0
        first_relevant_rank = None

        for idx, item in enumerate(results, 1):
            # 判断是否是预期结果：ID匹配或包含所有预期关键词
            is_expected = False
            if item.id in test_case.expected_knowledge_ids:
                is_expected = True
                relevant_count += 1
                if first_relevant_rank is None:
                    first_relevant_rank = idx
            elif test_case.expected_keywords:
                # 检查是否包含所有关键词
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

        # 计算指标
        total_retrieved = len(results)
        total_expected = max(len(test_case.expected_knowledge_ids), 1)  # 避免除以0

        precision = relevant_count / total_retrieved if total_retrieved > 0 else 0.0
        recall = relevant_count / total_expected if total_expected > 0 else 0.0
        f1_score = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        mrr = 1.0 / first_relevant_rank if first_relevant_rank is not None else 0.0

        # 计算 NDCG@K
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

    async def run_all_tests(
        self, name: str = "", description: str = "", limit: int = 10
    ) -> TestRun:
        """执行所有测试用例"""
        test_cases = await self.list_test_cases()
        if not test_cases:
            raise ValueError("No test cases available")

        current_version = config_manager.get_active_version()
        config_snapshot = config_manager.get_full_config()

        previous_run = self._get_last_test_run()
        previous_config_version = (
            previous_run.config_version_id if previous_run else None
        )

        test_run = TestRun(
            name=name or f"Test Run {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            description=description,
            total_test_cases=len(test_cases),
            status="running",
            config_version_id=current_version,
            config_snapshot=config_snapshot,
            previous_config_version_id=previous_config_version,
        )

        test_results = []
        passed_count = 0
        total_precision = 0.0
        total_recall = 0.0
        total_f1 = 0.0
        total_mrr = 0.0
        total_ndcg = 0.0

        for test_case in test_cases:
            try:
                result = await self.run_test_case(test_case, limit)
                test_results.append(result)

                total_precision += result.precision
                total_recall += result.recall
                total_f1 += result.f1_score
                total_mrr += result.mrr
                total_ndcg += result.ndcg_at_k

                # 认为F1 > 0.7为通过
                if result.f1_score >= 0.7:
                    passed_count += 1

            except Exception as e:
                logger.error(f"Failed to run test case {test_case.id}: {e}")
                continue

        # 计算整体指标
        test_count = len(test_results)
        if test_count > 0:
            test_run.overall_precision = total_precision / test_count
            test_run.overall_recall = total_recall / test_count
            test_run.overall_f1 = total_f1 / test_count
            test_run.overall_mrr = total_mrr / test_count
            test_run.overall_ndcg = total_ndcg / test_count

        test_run.test_results = test_results
        test_run.passed_test_cases = passed_count
        test_run.status = "completed"
        test_run.completed_at = datetime.now()

        # 保存测试运行结果
        self._save_test_run(test_run)

        return test_run

    def _save_test_run(self, test_run: TestRun):
        """保存测试运行结果"""
        try:
            file_path = os.path.join(self.test_runs_dir, f"{test_run.id}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(test_run.model_dump_json(indent=2))
            logger.info(f"Test run saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save test run: {e}")

    def list_test_runs(self) -> List[TestRun]:
        """列出所有测试运行"""
        test_runs = []
        try:
            for filename in os.listdir(self.test_runs_dir):
                if filename.endswith(".json"):
                    file_path = os.path.join(self.test_runs_dir, filename)
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        test_runs.append(TestRun(**data))
            # 按创建时间倒序排列
            test_runs.sort(key=lambda x: x.created_at, reverse=True)
        except Exception as e:
            logger.error(f"Failed to list test runs: {e}")
        return test_runs

    def get_test_run(self, run_id: str) -> Optional[TestRun]:
        """获取单个测试运行结果"""
        try:
            file_path = os.path.join(self.test_runs_dir, f"{run_id}.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return TestRun(**data)
        except Exception as e:
            logger.error(f"Failed to get test run {run_id}: {e}")
        return None

    def create_snapshot(
        self, name: str = "", description: str = ""
    ) -> KnowledgeSnapshot:
        """创建知识库快照"""
        # 获取当前文档列表
        docs = document_manager.list_documents()
        document_hashes = [doc.file_hash for doc in docs]

        # 计算索引大小
        index_size = 0
        if os.path.exists(STORAGE_DIR):
            for root, dirs, files in os.walk(STORAGE_DIR):
                for file in files:
                    file_path = os.path.join(root, file)
                    index_size += os.path.getsize(file_path)

        snapshot = KnowledgeSnapshot(
            name=name or f"Snapshot {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            description=description,
            document_count=len(docs),
            document_hashes=document_hashes,
            index_size_bytes=index_size,
        )

        # 创建快照目录
        snapshot_dir = os.path.join(self.snapshots_dir, snapshot.id)
        os.makedirs(snapshot_dir, exist_ok=True)

        # 仅复制索引目录
        index_dir = os.path.join(STORAGE_DIR, "index")
        snapshot_index_dir = os.path.join(snapshot_dir, "index")
        if os.path.exists(index_dir):
            shutil.copytree(index_dir, snapshot_index_dir, dirs_exist_ok=True)

        # 复制文档存储
        doc_store_path = os.path.join(STORAGE_DIR, "document_store.json")
        if os.path.exists(doc_store_path):
            shutil.copy2(
                doc_store_path, os.path.join(snapshot_dir, "document_store.json")
            )

        snapshot.storage_path = snapshot_dir

        # 保存快照元数据
        self._save_snapshot(snapshot)

        logger.info(f"Snapshot created: {snapshot.id}")
        return snapshot

    def _save_snapshot(self, snapshot: KnowledgeSnapshot):
        """保存快照元数据"""
        try:
            file_path = os.path.join(snapshot.storage_path, "snapshot.json")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(snapshot.model_dump_json(indent=2))
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")

    def list_snapshots(self) -> List[KnowledgeSnapshot]:
        """列出所有快照"""
        snapshots = []
        try:
            for snapshot_id in os.listdir(self.snapshots_dir):
                snapshot_dir = os.path.join(self.snapshots_dir, snapshot_id)
                if os.path.isdir(snapshot_dir):
                    meta_path = os.path.join(snapshot_dir, "snapshot.json")
                    if os.path.exists(meta_path):
                        with open(meta_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            snapshots.append(KnowledgeSnapshot(**data))
            # 按创建时间倒序排列
            snapshots.sort(key=lambda x: x.created_at, reverse=True)
        except Exception as e:
            logger.error(f"Failed to list snapshots: {e}")
        return snapshots

    def get_snapshot(self, snapshot_id: str) -> Optional[KnowledgeSnapshot]:
        """获取单个快照"""
        try:
            snapshot_dir = os.path.join(self.snapshots_dir, snapshot_id)
            meta_path = os.path.join(snapshot_dir, "snapshot.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return KnowledgeSnapshot(**data)
        except Exception as e:
            logger.error(f"Failed to get snapshot {snapshot_id}: {e}")
        return None

    def restore_snapshot(self, snapshot_id: str) -> bool:
        """恢复到指定快照"""
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            logger.error(f"Snapshot {snapshot_id} not found")
            return False

        try:
            # 停止当前服务
            if rag_service.index_manager.is_index_available():
                rag_service.index_manager.index = None
                if hasattr(rag_service.retrieval_service, "bm25_retriever"):
                    rag_service.retrieval_service.bm25_retriever = None
                if hasattr(rag_service.retrieval_service, "vector_retriever"):
                    rag_service.retrieval_service.vector_retriever = None

            # 备份当前状态（仅备份 index 目录和 document_store.json，不移动整个 STORAGE_DIR 以免丢失测试用例等）
            backup_dir = (
                f"{STORAGE_DIR}_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            os.makedirs(backup_dir, exist_ok=True)

            current_index_dir = os.path.join(STORAGE_DIR, "index")
            if os.path.exists(current_index_dir):
                shutil.move(current_index_dir, os.path.join(backup_dir, "index"))

            current_doc_store = os.path.join(STORAGE_DIR, "document_store.json")
            if os.path.exists(current_doc_store):
                shutil.move(
                    current_doc_store, os.path.join(backup_dir, "document_store.json")
                )

            # 恢复快照中的 index
            snapshot_index_dir = os.path.join(snapshot.storage_path, "index")

            if os.path.exists(snapshot_index_dir):
                shutil.copytree(snapshot_index_dir, current_index_dir)

            # 恢复文档存储
            snapshot_doc_store = os.path.join(
                snapshot.storage_path, "document_store.json"
            )

            if os.path.exists(snapshot_doc_store):
                shutil.copy2(snapshot_doc_store, current_doc_store)

            # 重新加载文档管理器
            document_manager._load_store()

            # 重新初始化索引
            rag_service.index_manager._initialize_index()

            logger.info(f"Successfully restored snapshot {snapshot_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore snapshot {snapshot_id}: {e}")
            # 恢复备份
            if "backup_dir" in locals() and os.path.exists(backup_dir):
                backup_index = os.path.join(backup_dir, "index")
                if os.path.exists(backup_index):
                    if os.path.exists(current_index_dir):
                        shutil.rmtree(current_index_dir)
                    shutil.move(backup_index, current_index_dir)

                backup_doc = os.path.join(backup_dir, "document_store.json")
                if os.path.exists(backup_doc):
                    if os.path.exists(current_doc_store):
                        os.remove(current_doc_store)
                    shutil.move(backup_doc, current_doc_store)

                rag_service.index_manager._initialize_index()
                document_manager._load_store()
            return False

    def _get_last_test_run(self) -> Optional[TestRun]:
        """获取上一次测试运行"""
        runs = self.list_test_runs()
        if runs:
            return runs[0]
        return None

    def compare_config_versions(self, version_id1: str, version_id2: str) -> Dict:
        """对比两个配置版本的测试结果"""
        runs = self.list_test_runs()
        runs_for_v1 = [r for r in runs if r.config_version_id == version_id1]
        runs_for_v2 = [r for r in runs if r.config_version_id == version_id2]

        if not runs_for_v1:
            raise ValueError(f"No test runs found for config version {version_id1}")
        if not runs_for_v2:
            raise ValueError(f"No test runs found for config version {version_id2}")

        avg_v1_precision = sum(r.overall_precision for r in runs_for_v1) / len(
            runs_for_v1
        )
        avg_v1_recall = sum(r.overall_recall for r in runs_for_v1) / len(runs_for_v1)
        avg_v1_f1 = sum(r.overall_f1 for r in runs_for_v1) / len(runs_for_v1)
        avg_v1_mrr = sum(r.overall_mrr for r in runs_for_v1) / len(runs_for_v1)

        avg_v2_precision = sum(r.overall_precision for r in runs_for_v2) / len(
            runs_for_v2
        )
        avg_v2_recall = sum(r.overall_recall for r in runs_for_v2) / len(runs_for_v2)
        avg_v2_f1 = sum(r.overall_f1 for r in runs_for_v2) / len(runs_for_v2)
        avg_v2_mrr = sum(r.overall_mrr for r in runs_for_v2) / len(runs_for_v2)

        return {
            "version1": {
                "version_id": version_id1,
                "run_count": len(runs_for_v1),
                "avg_precision": avg_v1_precision,
                "avg_recall": avg_v1_recall,
                "avg_f1": avg_v1_f1,
                "avg_mrr": avg_v1_mrr,
            },
            "version2": {
                "version_id": version_id2,
                "run_count": len(runs_for_v2),
                "avg_precision": avg_v2_precision,
                "avg_recall": avg_v2_recall,
                "avg_f1": avg_v2_f1,
                "avg_mrr": avg_v2_mrr,
            },
            "differences": {
                "precision_change": avg_v2_precision - avg_v1_precision,
                "recall_change": avg_v2_recall - avg_v1_recall,
                "f1_change": avg_v2_f1 - avg_v1_f1,
                "mrr_change": avg_v2_mrr - avg_v1_mrr,
            },
        }

    def _calculate_ndcg(
        self, results: List[TestResultItem], expected_ids: List[str], k: int = 3
    ) -> float:
        """计算 NDCG@K

        Args:
            results: 检索结果列表
            expected_ids: 预期知识ID列表
            k: 截断位置

        Returns:
            NDCG@K 值（0-1 之间）
        """
        if not results or not expected_ids:
            return 0.0

        # 取前 k 个结果
        top_k = results[:k]

        # 计算 DCG
        dcg = 0.0
        for i, item in enumerate(top_k):
            # 相关性：预期结果得分为 1，否则为 0
            rel = 1.0 if item.knowledge_id in expected_ids else 0.0
            dcg += rel / math.log2(i + 2)  # i+2 因为排名从 1 开始

        # 计算理想 DCG (IDCG)
        ideal_rels = [1.0] * min(len(expected_ids), k) + [0.0] * max(
            0, k - len(expected_ids)
        )
        idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal_rels[:k]))

        if idcg == 0:
            return 0.0

        return dcg / idcg

    def compare_test_runs(self, run_id1: str, run_id2: str) -> Dict:
        """比较两个测试运行的结果"""
        run1 = self.get_test_run(run_id1)
        run2 = self.get_test_run(run_id2)

        if not run1 or not run2:
            raise ValueError("One or both test runs not found")

        return {
            "run1": {
                "id": run1.id,
                "name": run1.name,
                "created_at": run1.created_at.isoformat(),
                "overall_precision": run1.overall_precision,
                "overall_recall": run1.overall_recall,
                "overall_f1": run1.overall_f1,
                "overall_mrr": run1.overall_mrr,
                "passed_count": run1.passed_test_cases,
                "total_count": run1.total_test_cases,
            },
            "run2": {
                "id": run2.id,
                "name": run2.name,
                "created_at": run2.created_at.isoformat(),
                "overall_precision": run2.overall_precision,
                "overall_recall": run2.overall_recall,
                "overall_f1": run2.overall_f1,
                "overall_mrr": run2.overall_mrr,
                "passed_count": run2.passed_test_cases,
                "total_count": run2.total_test_cases,
            },
            "differences": {
                "precision_change": run2.overall_precision - run1.overall_precision,
                "recall_change": run2.overall_recall - run1.overall_recall,
                "f1_change": run2.overall_f1 - run1.overall_f1,
                "mrr_change": run2.overall_mrr - run1.overall_mrr,
                "passed_count_change": run2.passed_test_cases - run1.passed_test_cases,
            },
        }

    def _compute_file_hash(self, file_path: str) -> str:
        """计算文件SHA256哈希"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def upload_source_document(
        self, file_path: str, title: str, file_type: str
    ) -> SourceDocument:
        """上传源文档"""
        file_hash = self._compute_file_hash(file_path)

        # Check if document already exists in database
        async def _check_existing():
            async with self.db_session_factory() as session:
                stmt = select(SourceDocument).where(
                    SourceDocument.file_hash == file_hash
                )
                result = await session.execute(stmt)
                return result.scalar_one_or_none()

        existing_doc = await _check_existing()
        if existing_doc:
            logger.info(
                f"文档已存在，直接复用: {existing_doc.id} - {existing_doc.title}"
            )
            return existing_doc

        dest_path = os.path.join(
            SOURCE_DOCUMENTS_DIR, f"{file_hash}_{os.path.basename(file_path)}"
        )
        shutil.copy2(file_path, dest_path)

        doc = SourceDocument(
            id=str(uuid.uuid4()),
            title=title,
            file_type=file_type,
            file_path=dest_path,
            file_hash=file_hash,
            status=DocumentStatus.UPLOADED,
        )

        # Save to database
        async def _save_doc():
            async with self.db_session_factory() as session:
                session.add(doc)
                await session.commit()
                await session.refresh(doc)
                return doc

        saved_doc = await _save_doc()

        logger.info(f"Source document uploaded: {saved_doc.id} - {title}")
        return saved_doc

    async def list_source_documents(self) -> List[SourceDocument]:
        """列出所有源文档"""

        async def _get_all():
            async with self.db_session_factory() as session:
                stmt = select(SourceDocument).order_by(SourceDocument.created_at.desc())
                result = await session.execute(stmt)
                return list(result.scalars().all())

        docs = await _get_all()
        return docs

    async def get_source_document(self, doc_id: str) -> Optional[SourceDocument]:
        """获取单个源文档"""

        async def _get_one():
            async with self.db_session_factory() as session:
                return await session.get(SourceDocument, doc_id)

        doc = await _get_one()
        return doc

    async def delete_source_document(self, doc_id: str) -> bool:
        """删除源文档"""

        async def _delete():
            async with self.db_session_factory() as session:
                doc = await session.get(SourceDocument, doc_id)
                if not doc:
                    return False

                # Delete file
                if os.path.exists(doc.file_path):
                    os.remove(doc.file_path)

                # Delete from database
                await session.delete(doc)
                await session.commit()
                return True

        success = await _delete()

        if success:
            logger.info(f"Source document deleted: {doc_id}")
        return success

    async def generate_test_case_drafts(
        self,
        source_document_id: str,
        params: GenerationParams,
        progress_callback: Optional[Callable[[int, int, str], Awaitable[None]]] = None,
    ) -> List[TestCaseDraft]:
        """根据源文档生成测试用例草稿"""
        async with self.db_session_factory() as session:
            stmt = select(SourceDocument).where(SourceDocument.id == source_document_id)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()
        if not doc:
            raise ValueError(f"源文档不存在: {source_document_id}")

        # 尝试读取完整文档内容而不是只使用摘要
        content_to_use = doc.content_summary or "暂无摘要内容"
        try:
            if os.path.exists(doc.file_path):
                with open(doc.file_path, "r", encoding="utf-8", errors="ignore") as f:
                    full_content = f.read()
                    # 如果内容太长，取前4000字符
                    if len(full_content) > 4000:
                        content_to_use = full_content[:4000] + "..."
                    else:
                        content_to_use = full_content
                    logger.info(
                f"Loaded full document content, length: {len(content_to_use)}"
            )
        except Exception as e:
            logger.warning(f"Failed to load full document content, using summary: {e}")

        # 通知前端：文档加载完成，开始生成
        if progress_callback:
            await progress_callback(0, params.count, "已加载文档内容，开始生成测试用例")

        # 分批生成，每次生成3个，避免LLM输出截断
        batch_size = 3
        total_needed = params.count
        all_drafts = []
        generated_count = 0

        try:
            if not settings.dashscope_api_key:
                raise ValueError("DASHSCOPE_API_KEY 未配置，无法调用大模型")

            import re
            import json_repair

            # 确保即使模型返回的是字符串也能被容错为列表
            def ensure_list(val):
                if isinstance(val, list):
                    return val
                if isinstance(val, str):
                    return [val] if val else []
                return []

            while generated_count < total_needed:
                current_batch_count = min(batch_size, total_needed - generated_count)
                batch_num = generated_count // batch_size + 1
                total_batch = (total_needed + batch_size - 1) // batch_size
                logger.info(
                    f"Generating batch {batch_num}/{total_batch}, count: {current_batch_count}"
                )
                # 通知前端：开始生成当前批次
                if progress_callback:
                    await progress_callback(
                        generated_count,
                        params.count,
                        f"正在生成第 {batch_num}/{total_batch} 批测试用例"
                    )

                prompt = TEST_CASE_DRAFT_GENERATION_PROMPT.format(
                    count=current_batch_count,
                    text=content_to_use,
                    domains=",".join(params.target_domains)
                    if params.target_domains
                    else "通用领域",
                    age_range_min=params.age_range[0],
                    age_range_max=params.age_range[1],
                )

                try:
                    # 使用工厂创建 LLM 实例
                    llm = LLMServiceFactory.create(
                        framework=LLMFramework.LLAMAINDEX,
                        model_name=params.llm_model,
                        scenario="test_case_generation",
                        temperature=params.temperature,
                    )

                    # 构建提示词
                    messages = [
                        LLMMessage(
                            role="system",
                            content="你是一个专业的测试用例生成专家，根据文档内容生成相关的测试用例。",
                        ),
                        LLMMessage(role="user", content=prompt),
                    ]

                    # 调用 LLM
                    response = await llm.chat(
                        LLMRequest(
                            messages=messages,
                            model_name=params.llm_model,
                            temperature=params.temperature,
                            max_tokens=4096,
                            scenario="test_case_generation",
                            prompt_key="test_case_draft_generation",
                        )
                    )
                    response_text = response.content.strip()

                    json_match = re.search(
                        r"```json\s*(.*?)\s*```", response_text, re.DOTALL
                    )
                    if json_match:
                        json_str = json_match.group(1)
                    else:
                        start = response_text.find("{")
                        end = response_text.rfind("}")
                        if start != -1 and end != -1:
                            json_str = response_text[start : end + 1]
                        else:
                            json_str = response_text

                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError as je:
                        logger.warning(
                            f"Standard JSON decode failed, attempting repair: {je}"
                        )
                        data = json_repair.loads(json_str)

                    if not isinstance(data, dict):
                        # 如果 json_repair 修复后依然不是 dict，可能是被解析成了字符串或其他类型
                        # 我们尝试重新包装一下
                        if isinstance(data, list):
                            data = {"drafts": data}
                        else:
                            raise ValueError(
                                "LLM response did not parse into a JSON object"
                            )

                    draft_list = data.get("drafts", [])
                    if not isinstance(draft_list, list):
                        # 某些情况下，大模型可能直接返回了草稿列表而没有包裹在 drafts 里
                        if isinstance(data, list):
                            draft_list = data
                        else:
                            raise ValueError("'drafts' field is missing or not a list")

                    for item in draft_list:
                        if generated_count >= total_needed:
                            break
                        
                        # map domain from prompt target_domains to TestDomain enum
                        # Default to sensory_integration if not matching
                        domain_mapping = {
                            "粗大动作": TestDomain.GROSS_MOTOR,
                            "精细动作": TestDomain.FINE_MOTOR,
                            "语言发展": TestDomain.LANGUAGE,
                            "认知能力": TestDomain.COGNITIVE,
                            "社交情感": TestDomain.SOCIAL_EMOTIONAL,
                            "感觉统合": TestDomain.SENSORY_INTEGRATION,
                        }
                        
                        try:
                            target_domain_str = params.target_domains[0] if params.target_domains else "感觉统合"
                            test_domain = domain_mapping.get(target_domain_str, TestDomain.SENSORY_INTEGRATION)
                        except Exception:
                            test_domain = TestDomain.SENSORY_INTEGRATION
                            
                        draft = TestCaseDraft(
                            id=str(uuid.uuid4()),
                            source_document_id=source_document_id,
                            query=item.get("query", ""),
                            age=params.age_range[0],
                            domain=test_domain,
                            description=item.get("description", ""),
                            expected_knowledge_ids=[],
                            expected_keywords=ensure_list(
                                item.get("expected_keywords", [])
                            ),
                            answer_points=ensure_list(item.get("answer_points", [])),
                            professional_terms=ensure_list(
                                item.get("professional_terms", [])
                            ),
                            age_requirement=f"{params.age_range[0]}-{params.age_range[1]}岁",
                            generation_params=params.model_dump(mode="json", exclude_unset=True)
                            if hasattr(params, "model_dump")
                            else {k: str(v) for k, v in params.__dict__.items() if not k.startswith("_")},
                            status=DraftStatus.DRAFT,
                        )
                        all_drafts.append(draft)
                        generated_count += 1
                        # 通知前端：当前批次生成完成
                        if progress_callback:
                            await progress_callback(
                                generated_count,
                                params.count,
                                f"已生成 {generated_count}/{params.count} 个测试用例"
                            )

                except Exception as batch_e:
                    logger.error(f"Batch generation failed: {batch_e}")
                    # 如果批次生成失败，尝试跳过这个批次，避免完全失败
                    if generated_count == 0:
                        # 如果还没生成任何内容，就抛出错误
                        raise
                    break

            logger.info(
                f"Generated {len(all_drafts)} drafts for document {source_document_id}"
            )

            # Save drafts to database
            async with self.db_session_factory() as session:
                try:
                    for draft in all_drafts:
                        session.add(draft)
                    await session.commit()
                    # Refresh to get IDs
                    for draft in all_drafts:
                        await session.refresh(draft)
                except Exception as e:
                    logger.error(f"Failed to save test case drafts: {str(e)}", exc_info=True)
                    await session.rollback()
                    raise

            return all_drafts

        except Exception as e:
            logger.error(f"Failed to generate drafts using LLM: {e}", exc_info=True)
            raise ValueError(f"生成测试用例草稿失败: {str(e)}")

    async def list_drafts(
        self, source_document_id: Optional[str] = None
    ) -> List[TestCaseDraft]:
        """列出草稿（仅显示待审核状态）"""
        async with self.db_session_factory() as session:
            stmt = select(TestCaseDraft).where(
                TestCaseDraft.status == DraftStatus.DRAFT
            )
            if source_document_id:
                stmt = stmt.where(
                    TestCaseDraft.source_document_id == source_document_id
                )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_draft(self, draft_id: str) -> Optional[TestCaseDraft]:
        """获取单个草稿"""
        async with self.db_session_factory() as session:
            return await session.get(TestCaseDraft, draft_id)

    async def update_draft(
        self, draft_id: str, updates: Dict
    ) -> Optional[TestCaseDraft]:
        """更新草稿"""
        async with self.db_session_factory() as session:
            draft = await session.get(TestCaseDraft, draft_id)
            if not draft:
                return None

            for key, value in updates.items():
                if hasattr(draft, key):
                    setattr(draft, key, value)
            draft.updated_at = datetime.now()
            await session.commit()
            await session.refresh(draft)
            return draft

    async def review_draft(self, draft_id: str, action: str) -> Optional[TestCaseDraft]:
        """审核草稿: action = reviewed/rejected"""
        async with self.db_session_factory() as session:
            try:
                draft = await session.get(TestCaseDraft, draft_id)
                if not draft:
                    return None

                if action == "reviewed":
                    draft.status = DraftStatus.REVIEWED
                    draft.updated_at = datetime.now()
                    # 审核通过后自动导入为正式测试用例
                    test_case = TestCase(
                        id=str(uuid.uuid4()),
                        query=draft.query,
                        age=draft.age,
                        domain=draft.domain,
                        expected_knowledge_ids=draft.expected_knowledge_ids,
                        expected_keywords=draft.expected_keywords,
                        description=draft.description,
                        professional_terms=draft.professional_terms,
                        source_document_id=draft.source_document_id,
                        # 补充默认值，避免必填字段缺失
                        expected_knowledge_count=len(draft.expected_knowledge_ids) if draft.expected_knowledge_ids else 0,
                        answer_points_summary=draft.answer_points[0] if draft.answer_points and len(draft.answer_points) > 0 else "",
                        min_age_requirement=draft.age,
                        max_age_requirement=draft.age + 1,
                        difficulty_level=DifficultyLevel.MEDIUM
                    )
                    session.add(test_case)
                    draft.status = DraftStatus.IMPORTED
                    await session.commit()
                    await session.refresh(draft)
                    logger.info(
                        f"Draft {draft_id} reviewed and imported as test case {test_case.id}"
                    )
                elif action == "rejected":
                    # 拒绝后自动删除草稿
                    deleted_draft = draft.model_copy()
                    await session.delete(draft)
                    await session.commit()
                    logger.info(f"Draft {draft_id} rejected and deleted")
                    return deleted_draft
                else:
                    raise ValueError(f"无效的审核操作: {action}")

                return draft
            except Exception as e:
                logger.error(f"审核草稿失败: {str(e)}", exc_info=True)
                await session.rollback()
                raise ValueError(f"审核草稿失败: {str(e)}")

    async def import_reviewed_drafts(self, draft_ids: List[str]) -> Dict:
        """将已审核的草稿导入为正式测试用例"""
        imported_ids = []
        failed_ids = []

        async with self.db_session_factory() as session:
            # 单次查询获取所有草稿，避免N+1问题
            stmt = select(TestCaseDraft).where(TestCaseDraft.id.in_(draft_ids))
            result = await session.execute(stmt)
            drafts = result.scalars().all()
            
            # 创建id到draft的映射，方便查找
            draft_map = {draft.id: draft for draft in drafts}
            
            for draft_id in draft_ids:
                draft = draft_map.get(draft_id)
                if not draft:
                    failed_ids.append({"draft_id": draft_id, "error": "草稿不存在"})
                    continue

                if draft.status != DraftStatus.REVIEWED:
                    failed_ids.append({"draft_id": draft_id, "error": "草稿未通过审核"})
                    continue

                test_case = TestCase(
                    id=str(uuid.uuid4()),
                    query=draft.query,
                    age=draft.age,
                    domain=draft.domain,
                    expected_knowledge_ids=draft.expected_knowledge_ids,
                    expected_keywords=draft.expected_keywords,
                    description=draft.description,
                    answer_points=draft.answer_points,
                    professional_terms=draft.professional_terms,
                    age_requirement=draft.age_requirement,
                    source_document_id=draft.source_document_id,
                )

                session.add(test_case)
                draft.status = DraftStatus.IMPORTED
                draft.updated_at = datetime.now()
                imported_ids.append(test_case.id)

            await session.commit()

        return {
            "imported_count": len(imported_ids),
            "failed_count": len(failed_ids),
            "test_case_ids": imported_ids,
            "errors": failed_ids,
        }

    async def create_test_set(
        self, name: str, description: str = "", source_type: str = "manual"
    ) -> TestSet:
        """创建测试集"""
        async with self.db_session_factory() as session:
            test_set = TestSet(
                id=str(uuid.uuid4()),
                name=name,
                description=description,
                source_type=TestSourceType(source_type),
            )
            session.add(test_set)
            await session.commit()
            await session.refresh(test_set)
            logger.info(f"Test set created: {test_set.id} - {name}")
            return test_set

    async def list_test_sets(self) -> List[TestSet]:
        """列出所有测试集"""
        async with self.db_session_factory() as session:
            stmt = select(TestSet).order_by(TestSet.created_at.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_test_set(self, test_set_id: str) -> Optional[TestSet]:
        """获取单个测试集"""
        async with self.db_session_factory() as session:
            test_set = await session.get(TestSet, test_set_id)
            if test_set:
                # Get associated test case IDs
                stmt = select(TestSetCase.test_case_id).where(
                    TestSetCase.test_set_id == test_set_id
                )
                result = await session.execute(stmt)
                test_set.test_case_ids = [row[0] for row in result.all()]
            return test_set

    async def update_test_set(self, test_set_id: str, updates: Dict) -> Optional[TestSet]:
        """更新测试集"""
        async with self.db_session_factory() as session:
            test_set = await session.get(TestSet, test_set_id)
            if not test_set:
                return None

            for key, value in updates.items():
                if hasattr(test_set, key):
                    setattr(test_set, key, value)
            test_set.updated_at = datetime.now()

            await session.commit()
            await session.refresh(test_set)

            # Get associated test case IDs
            stmt = select(TestSetCase.test_case_id).where(
                TestSetCase.test_set_id == test_set_id
            )
            result = await session.execute(stmt)
            test_set.test_case_ids = [row[0] for row in result.all()]

            return test_set

    async def delete_test_set(self, test_set_id: str) -> bool:
        """删除测试集"""
        async with self.db_session_factory() as session:
            test_set = await session.get(TestSet, test_set_id)
            if not test_set:
                return False

            await session.delete(test_set)
            await session.commit()
            logger.info(f"Test set deleted: {test_set_id}")
            return True

    async def add_test_cases_to_set(
        self, test_set_id: str, case_ids: List[str]
    ) -> Optional[TestSet]:
        """添加测试用例到测试集"""
        async with self.db_session_factory() as session:
            test_set = await session.get(TestSet, test_set_id)
            if not test_set:
                return None

            # Get existing case IDs
            stmt = select(TestSetCase.test_case_id).where(
                TestSetCase.test_set_id == test_set_id
            )
            result = await session.execute(stmt)
            existing_ids = [row[0] for row in result.all()]

            # Add new cases
            for case_id in case_ids:
                if case_id not in existing_ids:
                    ts_case = TestSetCase(
                        test_set_id=test_set_id, test_case_id=case_id
                    )
                    session.add(ts_case)

            await session.commit()
            await session.refresh(test_set)

            # Get updated case IDs
            stmt = select(TestSetCase.test_case_id).where(
                TestSetCase.test_set_id == test_set_id
            )
            result = await session.execute(stmt)
            test_set.test_case_ids = [row[0] for row in result.all()]

            return test_set

    async def remove_test_cases_from_set(
        self, test_set_id: str, case_ids: List[str]
    ) -> Optional[TestSet]:
        """从测试集移除测试用例"""
        async with self.db_session_factory() as session:
            test_set = await session.get(TestSet, test_set_id)
            if not test_set:
                return None

            # Delete specified cases
            stmt = select(TestSetCase).where(
                TestSetCase.test_set_id == test_set_id,
                TestSetCase.test_case_id.in_(case_ids),
            )
            result = await session.execute(stmt)
            for ts_case in result.scalars().all():
                await session.delete(ts_case)

            await session.commit()
            await session.refresh(test_set)

            # Get updated case IDs
            stmt = select(TestSetCase.test_case_id).where(
                TestSetCase.test_set_id == test_set_id
            )
            result = await session.execute(stmt)
            test_set.test_case_ids = [row[0] for row in result.all()]

            return test_set

    async def export_test_set(self, test_set_id: str) -> Optional[List[Dict]]:
        """导出测试集为JSON"""
        async with self.db_session_factory() as session:
            # Get test set
            test_set = await session.get(TestSet, test_set_id)
            if not test_set:
                return None

            # Get test case IDs
            stmt = select(TestSetCase.test_case_id).where(
                TestSetCase.test_set_id == test_set_id
            )
            result = await session.execute(stmt)
            case_ids = [row[0] for row in result.all()]

            # Get test cases
            cases = []
            for case_id in case_ids:
                case = await session.get(TestCase, case_id)
                if case:
                    cases.append(case.model_dump())

            return cases


# 单例实例
rag_test_manager = RagTestManager()
