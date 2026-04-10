import json
import os
import threading
import shutil
import time
import math
import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from filelock import FileLock
from jsonschema import validate, ValidationError

from src.model.rag_test import (
    TestCase,
    TestCaseStore,
    TestResult,
    TestRun,
    KnowledgeSnapshot,
    TestResultItem,
    SourceDocument,
    SourceDocumentStore,
    DocumentStatus,
    TestCaseDraft,
    TestCaseDraftStore,
    DraftStatus,
    GenerationParams,
    TestSet,
    TestSetStore,
    QualityReport,
    ChapterInfo,
)
from src.service.rag_service import rag_service
from src.config import settings, config_manager
from src.service.document_manager import document_manager
from src.utils.logger import logger
from src.constants.test_case import TEST_CASE_DOMAINS, TEST_CASE_REQUIRED_FIELDS
from src.core.prompts import TEST_CASE_DRAFT_GENERATION_PROMPT
from llama_index.llms.dashscope import DashScope
import asyncio

STORAGE_DIR = settings.rag_storage_dir
TEST_CASE_STORE_PATH = f"{settings.rag_storage_dir}/test_cases.json"
TEST_RUNS_DIR = f"{settings.rag_storage_dir}/test_runs"
SNAPSHOTS_DIR = f"{settings.rag_storage_dir}/snapshots"
SOURCE_DOCUMENTS_DIR = f"{settings.rag_storage_dir}/source_documents"
TEST_CASE_DRAFTS_DIR = f"{settings.rag_storage_dir}/test_case_drafts"
TEST_SETS_DIR = f"{settings.rag_storage_dir}/test_sets"
TEST_CASES_HISTORY_DIR = f"{settings.rag_storage_dir}/test_cases_history"

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
        "additionalProperties": False
    }
}


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
        self._lock = FileLock(TEST_CASE_STORE_PATH + ".lock")
        self.source_document_store = SourceDocumentStore()
        self.test_case_draft_store = TestCaseDraftStore()
        self.test_set_store = TestSetStore()

        # Ensure directories exist
        os.makedirs(self.test_runs_dir, exist_ok=True)
        os.makedirs(self.snapshots_dir, exist_ok=True)
        for dir_path in [
            SOURCE_DOCUMENTS_DIR,
            TEST_CASE_DRAFTS_DIR,
            TEST_SETS_DIR,
            TEST_CASES_HISTORY_DIR,
        ]:
            os.makedirs(dir_path, exist_ok=True)

        self._load_test_cases()
        self._load_source_documents()
        self._load_drafts()
        self._load_test_sets()
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

    def _load_source_documents(self):
        """加载源文档"""
        store_path = os.path.join(SOURCE_DOCUMENTS_DIR, "documents.json")
        if os.path.exists(store_path):
            try:
                with open(store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.source_document_store = SourceDocumentStore(**data)
                logger.info(f"Loaded {len(self.source_document_store.documents)} source documents")
            except Exception as e:
                logger.error(f"Failed to load source documents: {e}")
        else:
            logger.info("No existing source documents found.")

    def _save_source_documents(self):
        """保存源文档"""
        store_path = os.path.join(SOURCE_DOCUMENTS_DIR, "documents.json")
        try:
            tmp_path = store_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(self.source_document_store.model_dump_json(indent=2, ensure_ascii=False))
            os.replace(tmp_path, store_path)
            logger.info("Source documents saved")
        except Exception as e:
            logger.error(f"Failed to save source documents: {e}")

    def _load_drafts(self):
        """加载草稿"""
        store_path = os.path.join(TEST_CASE_DRAFTS_DIR, "drafts.json")
        if os.path.exists(store_path):
            try:
                with open(store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.test_case_draft_store = TestCaseDraftStore(**data)
                logger.info(f"Loaded {len(self.test_case_draft_store.drafts)} drafts")
            except Exception as e:
                logger.error(f"Failed to load drafts: {e}")
        else:
            logger.info("No existing drafts found.")

    def _save_drafts(self):
        """保存草稿"""
        store_path = os.path.join(TEST_CASE_DRAFTS_DIR, "drafts.json")
        try:
            tmp_path = store_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(self.test_case_draft_store.model_dump_json(indent=2, ensure_ascii=False))
            os.replace(tmp_path, store_path)
            logger.info("Drafts saved")
        except Exception as e:
            logger.error(f"Failed to save drafts: {e}")

    def _load_test_sets(self):
        """加载测试集"""
        store_path = os.path.join(TEST_SETS_DIR, "test_sets.json")
        if os.path.exists(store_path):
            try:
                with open(store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.test_set_store = TestSetStore(**data)
                logger.info(f"Loaded {len(self.test_set_store.test_sets)} test sets")
            except Exception as e:
                logger.error(f"Failed to load test sets: {e}")
        else:
            logger.info("No existing test sets found.")

    def _save_test_sets(self):
        """保存测试集"""
        store_path = os.path.join(TEST_SETS_DIR, "test_sets.json")
        try:
            tmp_path = store_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(self.test_set_store.model_dump_json(indent=2, ensure_ascii=False))
            os.replace(tmp_path, store_path)
            logger.info("Test sets saved")
        except Exception as e:
            logger.error(f"Failed to save test sets: {e}")

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
    
    def preview_import_cases(self, import_data: List[dict]) -> Tuple[List[dict], List[dict], List[dict]]:
        """预览导入的测试用例，返回有效/无效/重复数据"""
        valid_cases = []
        invalid_cases = []
        duplicates = []
        
        # 1. Schema校验
        try:
            validate(instance=import_data, schema=TEST_CASE_IMPORT_SCHEMA)
        except ValidationError as e:
            return [], [{"index": 0, "data": import_data[0] if import_data else {}, "error": str(e)}], []
        
        # 2. 业务规则校验和重复检测
        for i, case_data in enumerate(import_data):
            # 校验age范围
            if case_data["age"] < 0 or case_data["age"] > 18:
                invalid_cases.append({
                    "index": i,
                    "data": case_data,
                    "error": f"年龄超出范围: {case_data['age']}，必须在0-18之间"
                })
                continue
            
            # 校验domain
            if case_data.get("domain") and case_data["domain"] not in TEST_CASE_DOMAINS + ["未知"]:
                invalid_cases.append({
                    "index": i,
                    "data": case_data,
                    "error": f"无效的领域: {case_data['domain']}，可选值: {TEST_CASE_DOMAINS}"
                })
                continue
            
            # 检测重复（query + age + domain）
            duplicate_found = False
            for existing_case in self.test_case_store.test_cases.values():
                if (existing_case.query == case_data["query"] and 
                    existing_case.age == case_data["age"] and 
                    existing_case.domain == case_data.get("domain", "未知")):
                    duplicates.append({
                        "index": i,
                        "data": case_data,
                        "existing_id": existing_case.id
                    })
                    duplicate_found = True
                    break
            
            if not duplicate_found:
                valid_cases.append({
                    "index": i,
                    "data": case_data
                })
        
        return valid_cases, invalid_cases, duplicates
    
    def batch_import_cases(self, cases_data: List[dict], test_set_id: Optional[str] = None) -> Dict:
        """批量导入测试用例（事务性操作）"""
        # 阶段1：预校验所有数据
        test_cases = []
        for case_data in cases_data:
            try:
                test_case = TestCase(**case_data)
                test_cases.append(test_case)
            except Exception as e:
                raise ValueError(f"测试用例数据无效: {str(e)}")
        
        # 阶段2：原子写入
        with self._lock:
            # 重新加载数据，避免并发修改
            self._load_test_cases()
            
            # 再次检测重复
            for test_case in test_cases:
                for existing_case in self.test_case_store.test_cases.values():
                    if (existing_case.query == test_case.query and 
                        existing_case.age == test_case.age and 
                        existing_case.domain == test_case.domain):
                        raise ValueError(f"测试用例重复: {test_case.query} (age: {test_case.age}, domain: {test_case.domain})")
            
            # 添加到存储
            imported_ids = []
            for test_case in test_cases:
                self.test_case_store.test_cases[test_case.id] = test_case
                imported_ids.append(test_case.id)
            
            # 保存到文件
            tmp_path = TEST_CASE_STORE_PATH + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(self.test_case_store.model_dump_json(indent=2, ensure_ascii=False))
            os.replace(tmp_path, TEST_CASE_STORE_PATH)
        
        return {
            "imported_count": len(imported_ids),
            "failed_count": 0,
            "test_case_ids": imported_ids,
            "errors": []
        }

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
        ndcg_at_k = self._calculate_ndcg(test_result_items, test_case.expected_knowledge_ids)

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
        test_cases = self.list_test_cases()
        if not test_cases:
            raise ValueError("No test cases available")

        current_version = config_manager.get_active_version()
        config_snapshot = config_manager.get_full_config()

        previous_run = self._get_last_test_run()
        previous_config_version = previous_run.config_version_id if previous_run else None

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
                if hasattr(rag_service.retrieval_service, 'bm25_retriever'):
                    rag_service.retrieval_service.bm25_retriever = None
                if hasattr(rag_service.retrieval_service, 'vector_retriever'):
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
                shutil.move(current_doc_store, os.path.join(backup_dir, "document_store.json"))

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

        avg_v1_precision = sum(r.overall_precision for r in runs_for_v1) / len(runs_for_v1)
        avg_v1_recall = sum(r.overall_recall for r in runs_for_v1) / len(runs_for_v1)
        avg_v1_f1 = sum(r.overall_f1 for r in runs_for_v1) / len(runs_for_v1)
        avg_v1_mrr = sum(r.overall_mrr for r in runs_for_v1) / len(runs_for_v1)

        avg_v2_precision = sum(r.overall_precision for r in runs_for_v2) / len(runs_for_v2)
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

    def _calculate_ndcg(self, results: List[TestResultItem], expected_ids: List[str], k: int = 3) -> float:
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
        ideal_rels = [1.0] * min(len(expected_ids), k) + [0.0] * max(0, k - len(expected_ids))
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

    def upload_source_document(self, file_path: str, title: str, file_type: str) -> SourceDocument:
        """上传源文档"""
        file_hash = self._compute_file_hash(file_path)

        for doc in self.source_document_store.documents.values():
            if doc.file_hash == file_hash:
                logger.info(f"文档已存在，直接复用: {doc.id} - {doc.title}")
                return doc

        dest_path = os.path.join(SOURCE_DOCUMENTS_DIR, f"{file_hash}_{os.path.basename(file_path)}")
        shutil.copy2(file_path, dest_path)

        doc = SourceDocument(
            title=title,
            file_type=file_type,
            file_path=dest_path,
            file_hash=file_hash,
        )

        self.source_document_store.documents[doc.id] = doc
        self._save_source_documents()
        logger.info(f"Source document uploaded: {doc.id} - {title}")
        return doc

    def list_source_documents(self) -> List[SourceDocument]:
        """列出所有源文档"""
        return list(self.source_document_store.documents.values())

    def get_source_document(self, doc_id: str) -> Optional[SourceDocument]:
        """获取单个源文档"""
        return self.source_document_store.documents.get(doc_id)

    def delete_source_document(self, doc_id: str) -> bool:
        """删除源文档"""
        if doc_id not in self.source_document_store.documents:
            return False

        doc = self.source_document_store.documents[doc_id]
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)

        del self.source_document_store.documents[doc_id]
        self._save_source_documents()
        logger.info(f"Source document deleted: {doc_id}")
        return True

    async def generate_test_case_drafts(
        self,
        source_document_id: str,
        params: GenerationParams,
    ) -> List[TestCaseDraft]:
        """根据源文档生成测试用例草稿"""
        doc = self.source_document_store.documents.get(source_document_id)
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
                    logger.info(f"Loaded full document content, length: {len(content_to_use)}")
        except Exception as e:
            logger.warning(f"Failed to load full document content, using summary: {e}")

        # 分批生成，每次生成3个，避免LLM输出截断
        batch_size = 3
        total_needed = params.count
        all_drafts = []
        generated_count = 0

        try:
            if not settings.dashscope_api_key:
                raise ValueError("DASHSCOPE_API_KEY 未配置，无法调用大模型")

            llm = DashScope(
                model=params.llm_model,
                api_key=settings.dashscope_api_key,
                temperature=params.temperature,
            )

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
                logger.info(f"Generating batch {generated_count//batch_size + 1}, count: {current_batch_count}")
                
                prompt = TEST_CASE_DRAFT_GENERATION_PROMPT.format(
                    count=current_batch_count,
                    text=content_to_use,
                    domains=",".join(params.target_domains) if params.target_domains else "通用领域",
                    age_range_min=params.age_range[0],
                    age_range_max=params.age_range[1],
                )

                try:
                    response = await llm.acomplete(prompt)
                    response_text = str(response.text).strip()

                    json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
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
                        logger.warning(f"Standard JSON decode failed, attempting repair: {je}")
                        data = json_repair.loads(json_str)
                        
                    if not isinstance(data, dict):
                        # 如果 json_repair 修复后依然不是 dict，可能是被解析成了字符串或其他类型
                        # 我们尝试重新包装一下
                        if isinstance(data, list):
                            data = {"drafts": data}
                        else:
                            raise ValueError("LLM response did not parse into a JSON object")

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
                        draft = TestCaseDraft(
                            source_document_id=source_document_id,
                            query=item.get("query", ""),
                            age=params.age_range[0],
                            domain=params.target_domains[0] if params.target_domains else "",
                            description=item.get("description", ""),
                            expected_knowledge_ids=[],
                            expected_keywords=ensure_list(item.get("expected_keywords", [])),
                            answer_points=ensure_list(item.get("answer_points", [])),
                            professional_terms=ensure_list(item.get("professional_terms", [])),
                            age_requirement=f"{params.age_range[0]}-{params.age_range[1]}岁",
                            generation_params=params,
                            status=DraftStatus.DRAFT,
                        )
                        all_drafts.append(draft)
                        self.test_case_draft_store.drafts[draft.id] = draft
                        generated_count += 1

                except Exception as batch_e:
                    logger.error(f"Batch generation failed: {batch_e}")
                    # 如果批次生成失败，尝试跳过这个批次，避免完全失败
                    if generated_count == 0:
                        # 如果还没生成任何内容，就抛出错误
                        raise
                    break

            self._save_drafts()
            logger.info(f"Generated {len(all_drafts)} drafts for document {source_document_id}")

            return all_drafts

        except Exception as e:
            logger.error(f"Failed to generate drafts using LLM: {e}")
            raise ValueError(f"生成测试用例草稿失败: {str(e)}")

    def list_drafts(self, source_document_id: Optional[str] = None) -> List[TestCaseDraft]:
        """列出草稿（仅显示待审核状态）"""
        drafts = list(self.test_case_draft_store.drafts.values())
        # 只返回待审核的草稿，已导入的不再显示在草稿列表
        drafts = [d for d in drafts if d.status == DraftStatus.DRAFT]
        if source_document_id:
            drafts = [d for d in drafts if d.source_document_id == source_document_id]
        return drafts

    def get_draft(self, draft_id: str) -> Optional[TestCaseDraft]:
        """获取单个草稿"""
        return self.test_case_draft_store.drafts.get(draft_id)

    def update_draft(self, draft_id: str, updates: Dict) -> Optional[TestCaseDraft]:
        """更新草稿"""
        draft = self.test_case_draft_store.drafts.get(draft_id)
        if not draft:
            return None

        for key, value in updates.items():
            if hasattr(draft, key):
                setattr(draft, key, value)
        draft.updated_at = datetime.now()

        self._save_drafts()
        return draft

    def review_draft(self, draft_id: str, action: str) -> Optional[TestCaseDraft]:
        """审核草稿: action = reviewed/rejected"""
        draft = self.test_case_draft_store.drafts.get(draft_id)
        if not draft:
            return None

        if action == "reviewed":
            draft.status = DraftStatus.REVIEWED
            draft.updated_at = datetime.now()
            # 审核通过后自动导入为正式测试用例
            test_case = TestCase(
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
            self.test_case_store.test_cases[test_case.id] = test_case
            draft.status = DraftStatus.IMPORTED
            self._save_test_cases()
            self._save_drafts()
            logger.info(f"Draft {draft_id} reviewed and imported as test case {test_case.id}")
        elif action == "rejected":
            # 拒绝后自动删除草稿
            deleted_draft = draft.model_copy()
            del self.test_case_draft_store.drafts[draft_id]
            self._save_drafts()
            logger.info(f"Draft {draft_id} rejected and deleted")
            return deleted_draft
        else:
            raise ValueError(f"无效的审核操作: {action}")

        return draft

    def import_reviewed_drafts(self, draft_ids: List[str]) -> Dict:
        """将已审核的草稿导入为正式测试用例"""
        imported_ids = []
        failed_ids = []

        for draft_id in draft_ids:
            draft = self.test_case_draft_store.drafts.get(draft_id)
            if not draft:
                failed_ids.append({"draft_id": draft_id, "error": "草稿不存在"})
                continue

            if draft.status != DraftStatus.REVIEWED:
                failed_ids.append({"draft_id": draft_id, "error": "草稿未通过审核"})
                continue

            test_case = TestCase(
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

            self.test_case_store.test_cases[test_case.id] = test_case
            draft.status = DraftStatus.IMPORTED
            draft.updated_at = datetime.now()
            imported_ids.append(test_case.id)

        self._save_test_cases()
        self._save_drafts()

        return {
            "imported_count": len(imported_ids),
            "failed_count": len(failed_ids),
            "test_case_ids": imported_ids,
            "errors": failed_ids,
        }

    def create_test_set(self, name: str, description: str = "", source_type: str = "manual") -> TestSet:
        """创建测试集"""
        test_set = TestSet(
            name=name,
            description=description,
            source_type=source_type,
        )
        self.test_set_store.test_sets[test_set.id] = test_set
        self._save_test_sets()
        logger.info(f"Test set created: {test_set.id} - {name}")
        return test_set

    def list_test_sets(self) -> List[TestSet]:
        """列出所有测试集"""
        return list(self.test_set_store.test_sets.values())

    def get_test_set(self, test_set_id: str) -> Optional[TestSet]:
        """获取单个测试集"""
        return self.test_set_store.test_sets.get(test_set_id)

    def update_test_set(self, test_set_id: str, updates: Dict) -> Optional[TestSet]:
        """更新测试集"""
        test_set = self.test_set_store.test_sets.get(test_set_id)
        if not test_set:
            return None

        for key, value in updates.items():
            if hasattr(test_set, key):
                setattr(test_set, key, value)
        test_set.updated_at = datetime.now()

        self._save_test_sets()
        return test_set

    def delete_test_set(self, test_set_id: str) -> bool:
        """删除测试集"""
        if test_set_id not in self.test_set_store.test_sets:
            return False

        del self.test_set_store.test_sets[test_set_id]
        self._save_test_sets()
        logger.info(f"Test set deleted: {test_set_id}")
        return True

    def add_test_cases_to_set(self, test_set_id: str, case_ids: List[str]) -> Optional[TestSet]:
        """添加测试用例到测试集"""
        test_set = self.test_set_store.test_sets.get(test_set_id)
        if not test_set:
            return None

        for case_id in case_ids:
            if case_id not in test_set.test_case_ids:
                test_set.test_case_ids.append(case_id)
        test_set.updated_at = datetime.now()

        self._save_test_sets()
        return test_set

    def remove_test_cases_from_set(self, test_set_id: str, case_ids: List[str]) -> Optional[TestSet]:
        """从测试集移除测试用例"""
        test_set = self.test_set_store.test_sets.get(test_set_id)
        if not test_set:
            return None

        test_set.test_case_ids = [cid for cid in test_set.test_case_ids if cid not in case_ids]
        test_set.updated_at = datetime.now()

        self._save_test_sets()
        return test_set

    def export_test_set(self, test_set_id: str) -> Optional[List[Dict]]:
        """导出测试集为JSON"""
        test_set = self.test_set_store.test_sets.get(test_set_id)
        if not test_set:
            return None

        cases = []
        for case_id in test_set.test_case_ids:
            case = self.test_case_store.test_cases.get(case_id)
            if case:
                cases.append(case.model_dump())

        return cases


# 单例实例
rag_test_manager = RagTestManager()
