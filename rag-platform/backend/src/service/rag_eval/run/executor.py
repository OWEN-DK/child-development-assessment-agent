"""测试用例执行器

通过 PipelineCompiler 执行管道搜索，替代原来的直调检索服务模式。
每个测试用例独立执行一次管道搜索，记录检索结果和性能数据。
"""
import time
import uuid
from typing import Any, Optional

from src.core.pipeline.compiled_pipeline import CompiledPipeline, PipelineState
from src.core.pipeline.compiler import PipelineCompiler
from src.core.pipeline.node_context import AuthContext
from src.core.pipeline.node_result import NodeResult
from src.models.rag_eval.test_case import TestCase
from src.models.rag_eval.test_run import TestRun, TestRunResult
from src.repository.rag_eval.test_run_repo import TestRunResultRepository
from src.utils.logger import logger


class TestCaseExecutor:
    """测试用例执行器

    通过 PipelineCompiler 执行管道搜索，替代原来的直调检索服务。
    记录每个用例的执行结果、检索到的文档、耗时和域贡献。
    """

    def __init__(
        self,
        pipeline_compiler: PipelineCompiler,
        result_repo: TestRunResultRepository,
    ):
        self._compiler = pipeline_compiler
        self._result_repo = result_repo

    async def execute(
        self,
        test_case: TestCase,
        run: TestRun,
        pipeline_config: dict[str, Any],
        auth_context: AuthContext,
        search_params: Optional[dict[str, Any]] = None,
        timeout_ms: Optional[int] = None,
    ) -> TestRunResult:
        """执行单个测试用例

        用 PipelineCompiler 编译并执行管道搜索，收集检索结果、域信息和耗时。

        Args:
            test_case: 测试用例（含 query、expected_knowledge_ids 等）
            run: 所属测试运行
            pipeline_config: 管道 JSON 配置
            auth_context: 权限上下文（含用户角色，影响检索结果）
            search_params: 搜索参数覆盖（如 top_k）
            timeout_ms: 单用例超时（毫秒），超时后记录失败但不抛异常

        Returns:
            写入数据库的 TestRunResult 实例
        """
        start_time = time.monotonic()
        result_id = str(uuid.uuid4())

        params = {"top_k": search_params.get("top_k", 5) if search_params else 5}

        try:
            # 编译并执行管道
            compiled = self._compiler.compile(pipeline_config)

            # 构造初始状态
            state = PipelineState(
                query=test_case.query,
                params=params,
                auth=auth_context,
            )

            # 驱动执行（带超时）
            if timeout_ms:
                import asyncio

                state = await asyncio.wait_for(
                    self._compiler.drive(compiled, state),
                    timeout=timeout_ms / 1000.0,
                )
            else:
                state = await self._compiler.drive(compiled, state)

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            # 提取检索结果
            retrieved_docs = state.sources or []
            retrieved_ids = [d.get("id", "") for d in retrieved_docs if d.get("id")]
            retrieved_contexts = [
                d.get("content", "") for d in retrieved_docs if d.get("content")
            ]

            # 提取域结果
            domain_results = self._extract_domain_results(state)

            # 计算 L1 指标（precision/recall/F1/MRR/NDCG）
            l1_metrics = self._calculate_l1_metrics(
                test_case=test_case,
                retrieved_ids=retrieved_ids,
            )

            # 判断是否通过（至少召回一个期望文档）
            expected_ids = test_case.expected_knowledge_ids or []
            passed = (
                1
                if not expected_ids
                else (1 if any(eid in retrieved_ids for eid in expected_ids) else 0)
            )

            result_data = {
                "id": result_id,
                "run_id": run.id,
                "test_case_id": test_case.id,
                "tenant_id": run.tenant_id,
                "query": test_case.query,
                "retrieved_doc_ids": retrieved_ids,
                "retrieved_contexts": retrieved_contexts,
                "expected_knowledge_ids": expected_ids,
                "actual_knowledge_ids": retrieved_ids,
                "precision": l1_metrics.get("precision"),
                "recall": l1_metrics.get("recall"),
                "f1": l1_metrics.get("f1"),
                "mrr": l1_metrics.get("mrr"),
                "ndcg": l1_metrics.get("ndcg"),
                "actual_answer": state.answer,
                "domain_results_json": domain_results,
                "l1_metrics_json": l1_metrics,
                "passed": passed,
                "execution_time_ms": elapsed_ms,
            }

            result = await self._result_repo.create_result(result_data)
            logger.debug(
                f"用例 {test_case.id} 执行完成: elapsed={elapsed_ms}ms, passed={passed}"
            )
            return result

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"用例 {test_case.id} 执行失败: {exc}")

            result_data = {
                "id": result_id,
                "run_id": run.id,
                "test_case_id": test_case.id,
                "tenant_id": run.tenant_id,
                "query": test_case.query,
                "retrieved_doc_ids": [],
                "retrieved_contexts": [],
                "expected_knowledge_ids": test_case.expected_knowledge_ids or [],
                "actual_knowledge_ids": [],
                "passed": None,
                "error_message": str(exc),
                "execution_time_ms": elapsed_ms,
            }
            result = await self._result_repo.create_result(result_data)
            return result

    def _extract_domain_results(self, state: PipelineState) -> dict[str, Any]:
        """从管道执行状态中提取域贡献结果

        各域返回格式: {domain_id: {activated: bool, contribution: float, top_chunks: [...]}}
        """
        domain_outputs: dict[str, Any] = {}
        for dr in state.domain_results:
            domain_id = dr.get("domain_id", "")
            if not domain_id:
                continue
            domain_outputs[domain_id] = {
                "activated": dr.get("activated", True),
                "contribution": dr.get("contribution", 0.0),
                "top_chunks": dr.get("top_chunks", []),
                "hit_count": len(dr.get("top_chunks", [])),
            }
        return domain_outputs

    def _calculate_l1_metrics(
        self,
        test_case: TestCase,
        retrieved_ids: list[str],
    ) -> dict[str, Any]:
        """计算 L1 检索层指标

        在运行阶段计算 precision/recall/F1/MRR/NDCG，
        避免评估后处理重复计算。
        """
        expected_ids = test_case.expected_knowledge_ids or []
        expected_set = set(expected_ids)
        retrieved_set = set(retrieved_ids)

        # Precision
        intersection = expected_set & retrieved_set
        precision = (
            len(intersection) / len(retrieved_set) if retrieved_set else 0.0
        )

        # Recall
        recall = len(intersection) / len(expected_set) if expected_set else 0.0

        # F1
        f1_sum = precision + recall
        f1 = (2 * precision * recall / f1_sum) if f1_sum > 0 else 0.0

        # MRR（倒数排名）
        mrr = 0.0
        for i, rid in enumerate(retrieved_ids):
            if rid in expected_set:
                mrr = 1.0 / (i + 1)
                break

        # NDCG@K（K=检索结果数，理想排序：期望文档在前）
        import math

        ndcg = 0.0
        if expected_set and retrieved_ids:
            dcg = 0.0
            for i, rid in enumerate(retrieved_ids):
                if rid in expected_set:
                    dcg += 1.0 / math.log2(i + 2)
            idcg = 0.0
            for i in range(min(len(expected_set), len(retrieved_ids))):
                idcg += 1.0 / math.log2(i + 2)
            ndcg = dcg / idcg if idcg > 0 else 0.0

        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "mrr": round(mrr, 4),
            "ndcg": round(ndcg, 4),
            "intersection_count": len(intersection),
        }
