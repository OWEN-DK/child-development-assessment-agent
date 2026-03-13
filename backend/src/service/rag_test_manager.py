import json
import os
import threading
import shutil
import time
from typing import Dict, List, Optional
from datetime import datetime

from src.model.rag_test import (
    TestCase,
    TestCaseStore,
    TestResult,
    TestRun,
    KnowledgeSnapshot,
    TestResultItem,
)
from src.service.rag_service import rag_service, STORAGE_DIR
from src.service.document_manager import document_manager
from src.utils.logger import logger

TEST_CASE_STORE_PATH = "./storage/test_cases.json"
TEST_RUNS_DIR = "./storage/test_runs"
SNAPSHOTS_DIR = "./storage/snapshots"


class RagTestManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(RagTestManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.test_case_store_path = TEST_CASE_STORE_PATH
        self.test_runs_dir = TEST_RUNS_DIR
        self.snapshots_dir = SNAPSHOTS_DIR
        self.test_case_store = TestCaseStore()

        # Ensure directories exist
        os.makedirs(self.test_runs_dir, exist_ok=True)
        os.makedirs(self.snapshots_dir, exist_ok=True)

        self._load_test_cases()
        self._initialized = True

    def _load_test_cases(self):
        """加载测试用例"""
        if os.path.exists(self.test_case_store_path):
            try:
                with open(self.test_case_store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.test_case_store = TestCaseStore(**data)
                logger.info(f"Loaded {len(self.test_case_store.test_cases)} test cases")
            except Exception as e:
                logger.error(f"Failed to load test cases: {e}")
        else:
            logger.info("No existing test cases found. Starting fresh.")

    def _save_test_cases(self):
        """保存测试用例"""
        try:
            os.makedirs(os.path.dirname(self.test_case_store_path), exist_ok=True)
            with open(self.test_case_store_path, "w", encoding="utf-8") as f:
                f.write(self.test_case_store.model_dump_json(indent=2))
            logger.info("Test cases saved")
        except Exception as e:
            logger.error(f"Failed to save test cases: {e}")

    def add_test_case(self, test_case: TestCase) -> TestCase:
        """添加测试用例"""
        with self._lock:
            self.test_case_store.test_cases[test_case.id] = test_case
            self._save_test_cases()
            return test_case

    def update_test_case(
        self, test_case_id: str, test_case: TestCase
    ) -> Optional[TestCase]:
        """更新测试用例"""
        with self._lock:
            if test_case_id not in self.test_case_store.test_cases:
                return None
            test_case.updated_at = datetime.now()
            self.test_case_store.test_cases[test_case_id] = test_case
            self._save_test_cases()
            return test_case

    def delete_test_case(self, test_case_id: str) -> bool:
        """删除测试用例"""
        with self._lock:
            if test_case_id in self.test_case_store.test_cases:
                del self.test_case_store.test_cases[test_case_id]
                self._save_test_cases()
                return True
            return False

    def get_test_case(self, test_case_id: str) -> Optional[TestCase]:
        """获取单个测试用例"""
        return self.test_case_store.test_cases.get(test_case_id)

    def list_test_cases(self) -> List[TestCase]:
        """列出所有测试用例"""
        return list(self.test_case_store.test_cases.values())

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

        return TestResult(
            test_case_id=test_case.id,
            query=test_case.query,
            age=test_case.age,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            mrr=mrr,
            results=test_result_items,
            execution_time_ms=execution_time_ms,
        )

    async def run_all_tests(
        self, name: str = "", description: str = "", limit: int = 10
    ) -> TestRun:
        """执行所有测试用例"""
        test_cases = self.list_test_cases()
        if not test_cases:
            raise ValueError("No test cases available")

        test_run = TestRun(
            name=name or f"Test Run {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            description=description,
            total_test_cases=len(test_cases),
            status="running",
        )

        test_results = []
        passed_count = 0
        total_precision = 0.0
        total_recall = 0.0
        total_f1 = 0.0
        total_mrr = 0.0

        for test_case in test_cases:
            try:
                result = await self.run_test_case(test_case, limit)
                test_results.append(result)

                total_precision += result.precision
                total_recall += result.recall
                total_f1 += result.f1_score
                total_mrr += result.mrr

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

        # 复制当前索引到快照目录
        if os.path.exists(STORAGE_DIR):
            shutil.copytree(
                STORAGE_DIR, os.path.join(snapshot_dir, "storage"), dirs_exist_ok=True
            )

        # 复制文档存储
        doc_store_path = "./storage/document_store.json"
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
            if rag_service.index:
                rag_service.index = None
                rag_service.bm25_retriever = None
                rag_service.vector_retriever = None

            # 备份当前状态
            backup_dir = (
                f"{STORAGE_DIR}_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            if os.path.exists(STORAGE_DIR):
                shutil.move(STORAGE_DIR, backup_dir)

            # 恢复快照
            snapshot_storage = os.path.join(snapshot.storage_path, "storage")
            if os.path.exists(snapshot_storage):
                shutil.copytree(snapshot_storage, STORAGE_DIR)

            # 恢复文档存储
            snapshot_doc_store = os.path.join(
                snapshot.storage_path, "document_store.json"
            )
            if os.path.exists(snapshot_doc_store):
                shutil.copy2(snapshot_doc_store, "./storage/document_store.json")
                # 重新加载文档管理器
                document_manager._load_store()

            # 重新初始化索引
            rag_service._initialize_index()

            logger.info(f"Successfully restored snapshot {snapshot_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore snapshot {snapshot_id}: {e}")
            # 恢复备份
            if "backup_dir" in locals() and os.path.exists(backup_dir):
                if os.path.exists(STORAGE_DIR):
                    shutil.rmtree(STORAGE_DIR)
                shutil.move(backup_dir, STORAGE_DIR)
                rag_service._initialize_index()
                document_manager._load_store()
            return False

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


# 单例实例
rag_test_manager = RagTestManager()
