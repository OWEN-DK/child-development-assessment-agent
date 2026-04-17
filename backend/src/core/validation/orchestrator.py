"""6 层校验编排器

负责协调 Layer 1-5 的并行执行，Layer 6 由用户手动触发。
"""

import asyncio
import logging
import time
from datetime import datetime, UTC
from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.validation.layers.layer1_rule_engine import Layer1RuleEngine
from src.core.validation.layers.layer2_history import Layer2HistoryComparison
from src.core.validation.layers.layer3_llm import Layer3LLMDiagnosis
from src.core.validation.layers.layer4a_golden_coverage import Layer4aGoldenCoverage
from src.core.validation.layers.layer4b_chunk_quality import Layer4bChunkQuality
from src.core.validation.layers.layer4c_staleness import Layer4cDocumentStaleness
from src.core.validation.layers.layer5a_embedding import Layer5aEmbeddingQuality
from src.core.validation.layers.layer5b_intent import Layer5bIntentAccuracy
from src.core.validation.layers.layer5c_error_patterns import Layer5cErrorPatterns
from src.core.validation.config import get_config_value
from src.models.rag_eval.test_report import RagEvalTestReport
from src.models.rag_eval.test_run import RagEvalTestRun
from src.models.rag_eval.enums import RagEvalTestReportStatus

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AsyncSession]


async def _get_validation_config() -> dict:
    """从配置中心读取校验配置（禁止硬编码）"""
    return {
        "total_timeout": await get_config_value("rag_validation_timeout_total", 300),
        "layer_timeouts": {
            1: await get_config_value("rag_validation_timeout_per_layer_1", 30),
            2: await get_config_value("rag_validation_timeout_per_layer_2", 30),
            3: await get_config_value("rag_validation_timeout_per_layer_3", 120),
            4: await get_config_value("rag_validation_timeout_per_layer_4", 30),
            5: await get_config_value("rag_validation_timeout_per_layer_5", 30),
            6: await get_config_value("rag_validation_timeout_per_layer_6", 60),
        },
        "max_concurrent": await get_config_value("rag_validation_max_concurrent", 3),
        "queue_max": await get_config_value("rag_validation_queue_max", 10),
    }


class ValidationOrchestrator:
    """6 层校验编排器"""

    _semaphore: asyncio.Semaphore | None = None
    _init_lock: asyncio.Lock | None = None

    @classmethod
    async def init(cls, max_concurrent: int | None = None):
        """初始化编排器，从配置中心读取并发限制"""
        if cls._semaphore is not None:
            return

        if cls._init_lock is None:
            cls._init_lock = asyncio.Lock()

        async with cls._init_lock:
            if cls._semaphore is not None:
                return

            if max_concurrent is None:
                config = await _get_validation_config()
                max_concurrent = config["max_concurrent"]
            cls._semaphore = asyncio.Semaphore(max_concurrent)
            logger.info(
                f"ValidationOrchestrator 初始化完成，最大并发: {max_concurrent}"
            )

    async def execute(
        self, session_factory: SessionFactory, test_run: RagEvalTestRun
    ) -> RagEvalTestReport:
        """执行 Layer 1-5 校验，返回 TestReport（Layer 6 用户手动触发）"""
        if not self._semaphore:
            await self.init()

        config = await _get_validation_config()
        queue_max = config["queue_max"]

        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=5)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=503, detail="校验队列已满，请稍后重试")

        try:
            return await self._execute_with_timeout(session_factory, test_run, config)
        finally:
            self._semaphore.release()

    async def _execute_with_timeout(
        self, session_factory: SessionFactory, test_run: RagEvalTestRun, config: dict
    ) -> RagEvalTestReport:
        """带总体超时的执行"""
        validation_results: list[dict[str, Any]] = []
        total_timeout = config["total_timeout"]
        try:
            await asyncio.wait_for(
                self._execute_layers(
                    session_factory, test_run, validation_results, config
                ),
                timeout=total_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"校验总体超时 ({total_timeout}s)，保留已完成结果")

        return await self._create_report(session_factory, test_run, validation_results)

    async def _execute_layers(
        self,
        session_factory: SessionFactory,
        test_run: RagEvalTestRun,
        validation_results: list[dict[str, Any]],
        config: dict,
    ) -> None:
        """执行 Layer 1-5 校验，结果写入列表"""
        layer_timeouts = config["layer_timeouts"]

        results_lock = asyncio.Lock()
        layer_results: list[dict[str, Any]] = []

        async def run_and_collect(
            layer_num: int, layer: Any, key: str, timeout_val: int
        ):
            result = await self._run_layer_with_result(
                layer_num, layer, key, timeout_val
            )
            async with results_lock:
                layer_results.append(result)

        tasks = [
            asyncio.create_task(
                run_and_collect(
                    1,
                    Layer1RuleEngine(session_factory, test_run),
                    "layer1",
                    layer_timeouts.get(1, 30),
                )
            ),
            asyncio.create_task(
                run_and_collect(
                    2,
                    Layer2HistoryComparison(session_factory, test_run),
                    "layer2",
                    layer_timeouts.get(2, 30),
                )
            ),
            asyncio.create_task(
                run_and_collect(
                    3,
                    Layer3LLMDiagnosis(session_factory, test_run),
                    "layer3",
                    layer_timeouts.get(3, 120),
                )
            ),
            asyncio.create_task(
                run_and_collect(
                    4,
                    Layer4aGoldenCoverage(session_factory, test_run),
                    "layer4_golden_coverage",
                    layer_timeouts.get(4, 30),
                )
            ),
            asyncio.create_task(
                run_and_collect(
                    4,
                    Layer4bChunkQuality(session_factory, test_run),
                    "layer4_chunk_quality",
                    layer_timeouts.get(4, 30),
                )
            ),
            asyncio.create_task(
                run_and_collect(
                    4,
                    Layer4cDocumentStaleness(session_factory, test_run),
                    "layer4_document_staleness",
                    layer_timeouts.get(4, 30),
                )
            ),
            asyncio.create_task(
                run_and_collect(
                    5,
                    Layer5aEmbeddingQuality(session_factory, test_run),
                    "layer5_embedding_quality",
                    layer_timeouts.get(5, 30),
                )
            ),
            asyncio.create_task(
                run_and_collect(
                    5,
                    Layer5bIntentAccuracy(session_factory, test_run),
                    "layer5_intent_accuracy",
                    layer_timeouts.get(5, 30),
                )
            ),
            asyncio.create_task(
                run_and_collect(
                    5,
                    Layer5cErrorPatterns(session_factory, test_run),
                    "layer5_error_patterns",
                    layer_timeouts.get(5, 30),
                )
            ),
        ]
        await asyncio.gather(*tasks)

        # 聚合 Layer 4 和 Layer 5 子层结果到父层
        layer4_data = self._aggregate_sublayers_to_data(
            [
                "layer4_golden_coverage",
                "layer4_chunk_quality",
                "layer4_document_staleness",
            ],
            layer_results,
        )
        layer4_status = self._aggregate_layer_status_from_results(
            [
                "layer4_golden_coverage",
                "layer4_chunk_quality",
                "layer4_document_staleness",
            ],
            layer_results,
        )
        layer_results.append({"layer": 4, "status": layer4_status, "data": layer4_data})

        layer5_data = self._aggregate_sublayers_to_data(
            [
                "layer5_embedding_quality",
                "layer5_intent_accuracy",
                "layer5_error_patterns",
            ],
            layer_results,
        )
        layer5_status = self._aggregate_layer_status_from_results(
            [
                "layer5_embedding_quality",
                "layer5_intent_accuracy",
                "layer5_error_patterns",
            ],
            layer_results,
        )
        layer_results.append({"layer": 5, "status": layer5_status, "data": layer5_data})

        # 过滤掉子层中间结果，只保留 layer 1-5 的父层结果
        final_results = [r for r in layer_results if r.get("layer") in (1, 2, 3, 4, 5)]

        # Layer 6 默认不执行，用户手动触发
        final_results.append(
            {
                "layer": 6,
                "status": "skipped",
                "data": {"reason": "Layer 6 需用户手动触发"},
            }
        )

        # 按 layer 序号排序后写入 validation_results
        final_results.sort(key=lambda x: x["layer"])
        validation_results.extend(final_results)

    async def _run_layer_with_result(
        self, layer_num: int, layer: Any, key: str, timeout_val: int
    ) -> dict[str, Any]:
        """执行单层校验，返回 {layer, key, status, data, duration_ms} 格式"""
        start = time.monotonic()
        try:
            result = await asyncio.wait_for(layer.execute(), timeout=timeout_val)
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                "layer": layer_num,
                "key": key,
                "status": "completed",
                "data": result.get("data", result),
                "duration_ms": duration_ms,
            }
        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.warning(f"Layer {key} 超时 ({timeout_val}s)")
            return {
                "layer": layer_num,
                "key": key,
                "status": "timeout",
                "data": {"reason": f"超时 ({timeout_val}s)"},
                "duration_ms": duration_ms,
            }
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error(f"Layer {key} 异常: {e}")
            return {
                "layer": layer_num,
                "key": key,
                "status": "degraded",
                "data": {"reason": str(e)},
                "duration_ms": duration_ms,
            }

    @staticmethod
    def _aggregate_sublayers_to_data(sub_keys: list, results: list[dict]) -> dict:
        """从结果列表中聚合子层数据到父层 data"""
        data = {}
        # 初始化所有子键为 None
        for k in sub_keys:
            clean_key = k.replace("layer4_", "").replace("layer5_", "")
            data[clean_key] = None

        # 遍历结果，通过 key 字段匹配子层
        for r in results:
            r_key = r.get("key")
            if r_key not in sub_keys:
                continue

            clean_key = r_key.replace("layer4_", "").replace("layer5_", "")
            r_data = r.get("data")
            # 如果子层结果是 dict 且有 "data" 键，提取其 data；否则直接使用整个值
            data[clean_key] = (
                r_data.get("data")
                if isinstance(r_data, dict) and "data" in r_data
                else r_data
            )

        return data

    @staticmethod
    def _aggregate_layer_status_from_results(
        sub_keys: list, results: list[dict]
    ) -> str:
        """从子层结果中聚合父层状态（继承最差状态）"""
        status_priority = {"timeout": 0, "degraded": 1, "skipped": 2, "completed": 3}
        worst_status = "completed"

        for r in results:
            if r.get("key") in sub_keys:
                status = r.get("status", "completed")
                if status_priority.get(status, 3) < status_priority.get(
                    worst_status, 3
                ):
                    worst_status = status

        return worst_status

    async def _create_report(
        self,
        session_factory: SessionFactory,
        test_run: RagEvalTestRun,
        validation_results: list[dict],
    ) -> RagEvalTestReport:
        """创建 RagEvalTestReport"""
        async with session_factory() as session:
            async with session.begin():
                report = RagEvalTestReport(
                    run_id=test_run.id,
                    test_set_id=test_run.test_set_id,
                    config_version_id=test_run.config_version_id,
                    validation_results=validation_results,
                    status=RagEvalTestReportStatus.COMPLETED,
                )
                session.add(report)
                await session.flush()
                await session.refresh(report)
                return report
