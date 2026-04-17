# 01 - ValidationOrchestrator 编排器 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 01 - ValidationOrchestrator 编排器

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/core/validation/orchestrator.py`
- Modify: `backend/src/core/validation/__init__.py`
- Modify: `backend/src/services/test_report_service.py`
- Test: `backend/tests/test_validation_orchestrator.py`

- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `3.2 分层递进架构` 和 `3.3 校验层定义` 节
> **所属 Phase**: Phase 4

## 需求定义

协调 6 层校验，支持异步/并行/降级执行。总体超时 5 分钟，单层层超时降级，并发限制最多 3 个并行。

**执行策略**（严格按照 spec）：
- Layer 1-2-3-4-5：**全部并行执行**（互不依赖，同时启动）
- Layer 6：**默认不执行**，用户手动触发（读取已完成的 TestReport 数据，不阻塞报告生成）

**超时策略**（从配置中心读取，非硬编码）：
- 总体超时：`rag_validation_timeout_total`（默认 300s）
- 单层层超时：`rag_validation_timeout_per_layer`（Layer 1/2/4/5: 30s, Layer 3: 120s, Layer 6: 60s）
- 并发限制：`rag_validation_max_concurrent`（默认 3），队列上限 `rag_validation_queue_max`（默认 10）

## 验收标准

- [ ] ValidationOrchestrator 协调 Layer 1-5 全部并行执行，Layer 6 用户手动触发
- [ ] Layer 1-2-3-4-5 全部并行启动，无 Phase A/B 串行依赖
- [ ] 总体超时 5 分钟，超时后取消正在执行的层，保留已完成结果
- [ ] 单层层超时正确标记 `status="timeout"`
- [ ] 降级策略正确执行，`status="degraded"`
- [ ] 校验结果写入 TestReport.validation_results (JSON 数组格式)
- [ ] 并发限制：最多 3 个 report 级别并行，队列上限 10
- [ ] 超时配置从数据库/配置中心读取，不硬编码

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/validation/orchestrator.py` | 新增 | ValidationOrchestrator 主类 |
| `backend/src/core/validation/__init__.py` | 修改 | 导出编排器 |
| `backend/src/services/test_report_service.py` | 修改 | 调用编排器生成报告 |

## 实现方案

### 后端实现

```python
# backend/src/core/validation/orchestrator.py
import asyncio
import logging
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
from src.core.config import get_config_value  # 从配置中心读取
from src.models.rag_eval.test_report import RagEvalTestReport
from src.models.rag_eval.test_run import RagEvalTestRun
from src.models.rag_eval.enums import RagEvalTestReportStatus

logger = logging.getLogger(__name__)

# session_factory 类型别名
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


# 并发限制
# 注意：此 Semaphore 控制的是 report 级别的并发（同时最多多少个 TestReport 在校验）
# 单个 TestReport 内部的 Layer 子层并行不受此限制
# Layer 1-5 全部并行执行是允许的


class ValidationOrchestrator:
    """6 层校验编排器"""

    _semaphore: asyncio.Semaphore | None = None
    _init_lock: asyncio.Lock | None = None  # 保护初始化，防止并发重复创建

    @classmethod
    async def init(cls, max_concurrent: int | None = None):
        """初始化编排器，从配置中心读取并发限制
        
        使用 asyncio.Lock 保护初始化，防止多实例场景下重复创建 Semaphore。
        建议在应用启动时显式调用一次：await ValidationOrchestrator.init()
        """
        # 双重检查锁定模式
        if cls._semaphore is not None:
            return
        
        if cls._init_lock is None:
            cls._init_lock = asyncio.Lock()
        
        async with cls._init_lock:
            # 再次检查，防止等待期间其他协程已初始化
            if cls._semaphore is not None:
                return
            
            if max_concurrent is None:
                config = await _get_validation_config()
                max_concurrent = config["max_concurrent"]
            cls._semaphore = asyncio.Semaphore(max_concurrent)
            logger.info(f"ValidationOrchestrator 初始化完成，最大并发: {max_concurrent}")

    async def execute(self, session_factory, test_run: RagEvalTestRun) -> RagEvalTestReport:
        """执行 Layer 1-5 校验，返回 TestReport（Layer 6 用户手动触发）

        注意：接收 session_factory 而非单个 session，因为并行 layer 需要各自独立 session。
        """
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
        self, session_factory, test_run: RagEvalTestRun, config: dict
    ) -> RagEvalTestReport:
        """带总体超时的执行"""
        validation_results: list[dict[str, Any]] = []
        total_timeout = config["total_timeout"]
        try:
            await asyncio.wait_for(
                self._execute_layers(session_factory, test_run, validation_results, config),
                timeout=total_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"校验总体超时 ({total_timeout}s)，保留已完成层")

        return await self._create_report(session_factory, test_run, validation_results)

    async def _execute_layers(
        self, session_factory, test_run: RagEvalTestRun, validation_results: list[dict[str, Any]], config: dict
    ) -> None:
        """执行 Layer 1-5 校验，结果写入列表（按 spec 数组格式）

        执行策略（严格按照 spec）：
        - Layer 1-2-3-4-5：全部并行执行（互不依赖，同时启动）
        - Layer 6：默认不执行，用户手动触发

        注意：每个 layer 使用独立 session（通过 session_factory 创建），
        避免并行协程共享同一 session 导致 SQLAlchemy 异步冲突。
        """
        layer_timeouts = config["layer_timeouts"]

        # Layer 1-5 全部并行执行（无 Phase A/B 串行依赖）
        # 使用 asyncio.Lock 保护并发写入（异步环境必须使用 asyncio.Lock）
        results_lock = asyncio.Lock()
        layer_results: list[dict[str, Any]] = []

        async def run_and_collect(layer_num: int, layer: Any, key: str, timeout_val: int):
            result = await self._run_layer_with_result(layer_num, layer, key, timeout_val)
            async with results_lock:
                layer_results.append(result)

        tasks = [
            asyncio.create_task(run_and_collect(1, Layer1RuleEngine(session_factory, test_run), "layer1", layer_timeouts.get(1, 30))),
            asyncio.create_task(run_and_collect(2, Layer2HistoryComparison(session_factory, test_run), "layer2", layer_timeouts.get(2, 30))),
            asyncio.create_task(run_and_collect(3, Layer3LLMDiagnosis(session_factory, test_run), "layer3", layer_timeouts.get(3, 120))),
            asyncio.create_task(run_and_collect(4, Layer4aGoldenCoverage(session_factory, test_run), "layer4_golden_coverage", layer_timeouts.get(4, 30))),
            asyncio.create_task(run_and_collect(4, Layer4bChunkQuality(session_factory, test_run), "layer4_chunk_quality", layer_timeouts.get(4, 30))),
            asyncio.create_task(run_and_collect(4, Layer4cDocumentStaleness(session_factory, test_run), "layer4_document_staleness", layer_timeouts.get(4, 30))),
            asyncio.create_task(run_and_collect(5, Layer5aEmbeddingQuality(session_factory, test_run), "layer5_embedding_quality", layer_timeouts.get(5, 30))),
            asyncio.create_task(run_and_collect(5, Layer5bIntentAccuracy(session_factory, test_run), "layer5_intent_accuracy", layer_timeouts.get(5, 30))),
            asyncio.create_task(run_and_collect(5, Layer5cErrorPatterns(session_factory, test_run), "layer5_error_patterns", layer_timeouts.get(5, 30))),
        ]
        await asyncio.gather(*tasks)

        # 聚合 Layer 4 和 Layer 5 子层结果到父层
        layer4_data = self._aggregate_sublayers_to_data(
            ["layer4_golden_coverage", "layer4_chunk_quality", "layer4_document_staleness"],
            layer_results,
        )
        layer4_status = self._aggregate_layer_status_from_results(
            ["layer4_golden_coverage", "layer4_chunk_quality", "layer4_document_staleness"],
            layer_results,
        )
        layer_results.append({"layer": 4, "status": layer4_status, "data": layer4_data})

        layer5_data = self._aggregate_sublayers_to_data(
            ["layer5_embedding_quality", "layer5_intent_accuracy", "layer5_error_patterns"],
            layer_results,
        )
        layer5_status = self._aggregate_layer_status_from_results(
            ["layer5_embedding_quality", "layer5_intent_accuracy", "layer5_error_patterns"],
            layer_results,
        )
        layer_results.append({"layer": 5, "status": layer5_status, "data": layer5_data})

        # 过滤掉子层中间结果，只保留 layer 1-5 的父层结果
        parent_keys = {"layer1", "layer2", "layer3"}
        final_results = [r for r in layer_results if r.get("layer") in (1, 2, 3, 4, 5)]

        # Layer 6 默认不执行，用户手动触发
        final_results.append({
            "layer": 6,
            "status": "skipped",
            "data": {"reason": "Layer 6 需用户手动触发"},
        })

        # 按 layer 序号排序后写入 validation_results
        final_results.sort(key=lambda x: x["layer"])
        validation_results.extend(final_results)

    async def _run_layer_with_result(
        self, layer_num: int, layer: Any, key: str, timeout_val: int
    ) -> dict[str, Any]:
        """执行单层校验，返回 {layer, status, data, duration_ms} 格式（spec 数组格式）

        超时值从配置中心读取（layer_timeouts 字典），不硬编码。
        每个 layer 内部通过 session_factory 创建独立 session，避免并行冲突。
        """
        import time
        start = time.monotonic()
        try:
            result = await asyncio.wait_for(layer.execute(), timeout=timeout_val)
            duration_ms = int((time.monotonic() - start) * 1000)
            return {"layer": layer_num, "status": "completed", "data": result.get("data", result), "duration_ms": duration_ms}
        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.warning(f"Layer {key} 超时 ({timeout_val}s)")
            return {"layer": layer_num, "status": "timeout", "data": {"reason": f"超时 ({timeout_val}s)"}, "duration_ms": duration_ms}
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error(f"Layer {key} 异常: {e}")
            return {"layer": layer_num, "status": "degraded", "data": {"reason": str(e)}, "duration_ms": duration_ms}

    @staticmethod
    def _aggregate_sublayers_to_data(
        sub_keys: list, results: list[dict]
    ) -> dict:
        """从结果列表中聚合子层数据到父层 data"""
        data = {}
        for r in results:
            if r.get("data") and any(k in r["data"] for k in sub_keys):
                for k in sub_keys:
                    sub = r["data"].get(k)
                    if sub:
                        clean_key = k.replace("layer4_", "").replace("layer5_", "")
                        data[clean_key] = sub.get("data") if isinstance(sub, dict) else sub
                    else:
                        clean_key = k.replace("layer4_", "").replace("layer5_", "")
                        data[clean_key] = None
        return data

    @staticmethod
    def _aggregate_layer_status_from_results(
        sub_keys: list, results: list[dict]
    ) -> str:
        """从子层结果中聚合父层状态（继承最差状态）
        
        状态优先级（从差到好）：timeout > degraded > skipped > completed
        """
        status_priority = {"timeout": 0, "degraded": 1, "skipped": 2, "completed": 3}
        worst_status = "completed"
        
        for r in results:
            if r.get("data") and any(k in r["data"] for k in sub_keys):
                status = r.get("status", "completed")
                if status_priority.get(status, 3) < status_priority.get(worst_status, 3):
                    worst_status = status
        
        return worst_status

    async def _create_report(
        self, session_factory, test_run: RagEvalTestRun, validation_results: list[dict]
    ) -> RagEvalTestReport:
        """创建 RagEvalTestReport

        注意：使用独立 session 创建报告，避免与并行 layer 的 db session 冲突。
        使用 async with session.begin() 自动管理事务（CLAUDE.md 要求）。
        validation_results 为数组格式：[{layer: 1, status, data, duration_ms}, ...]
        """
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
```

## 测试方案

```python
# backend/tests/test_validation_orchestrator.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.core.validation.orchestrator import ValidationOrchestrator


@pytest.mark.asyncio
async def test_execute_layers_all_parallel():
    """测试 Layer 1-5 全部并行执行（无 Phase A/B 串行）"""
    orchestrator = ValidationOrchestrator()
    orchestrator.init()

    session_factory = AsyncMock()
    test_run = MagicMock(id="test-run-1", test_set_id="ts-1")

    with patch.object(orchestrator, "_run_layer_with_result", new_callable=AsyncMock) as mock_run:
        with patch.object(orchestrator, "_create_report", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock(id="report-1")
            await orchestrator.execute(session_factory, test_run)

            # 验证 _run_layer_with_result 被调用 9 次 (Layer 1-3 + Layer 4a-4c + Layer 5a-5c)
            assert mock_run.call_count == 9


@pytest.mark.asyncio
async def test_validation_results_array_format():
    """测试 validation_results 为数组格式 [{layer, status, data, duration_ms}, ...]"""
    orchestrator = ValidationOrchestrator()
    orchestrator.init()

    session_factory = AsyncMock()
    test_run = MagicMock(id="test-run-1", test_set_id="ts-1")

    with patch.object(orchestrator, "_run_layer_with_result", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"layer": 1, "status": "completed", "data": {"suggestions": []}, "duration_ms": 50}
        with patch.object(orchestrator, "_create_report", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock(id="report-1")
            await orchestrator.execute(session_factory, test_run)

            # 验证 _create_report 接收的 validation_results 是数组
            call_args = mock_create.call_args[0][2]
            assert isinstance(call_args, list)
            if call_args:
                assert "layer" in call_args[0]
                assert "status" in call_args[0]
                assert "duration_ms" in call_args[0]


@pytest.mark.asyncio
async def test_aggregate_sublayers_inherits_worst_status():
    """测试聚合子层状态继承最差"""
    orchestrator = ValidationOrchestrator()
    results = {
        "layer4_golden_coverage": {"status": "completed", "data": {"book_coverage": 0.8}},
        "layer4_chunk_quality": {"status": "timeout", "data": {"reason": "超时 (30s)"}},
        "layer4_document_staleness": {"status": "completed", "data": {"stale_ratio": 0.1}},
    }
    orchestrator._aggregate_sublayers(
        ["layer4_golden_coverage", "layer4_chunk_quality", "layer4_document_staleness"],
        "layer4",
        results,
    )
    assert results["layer4"]["status"] == "timeout"
    assert "golden_coverage" in results["layer4"]["data"]
    assert "chunk_quality" in results["layer4"]["data"]


@pytest.mark.asyncio
async def test_total_timeout_preserves_completed():
    """测试总体超时后保留已完成层"""
    orchestrator = ValidationOrchestrator()
    orchestrator.init()

    session_factory = AsyncMock()
    test_run = MagicMock(id="test-run-1")

    async def slow_execute(*args):
        await asyncio.sleep(999)

    with patch.object(orchestrator, "_execute_layers", side_effect=slow_execute):
        with patch.object(orchestrator, "_create_report", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock(id="report-1")
            await orchestrator.execute(session_factory, test_run)

            # 验证 _create_report 被调用（即使超时）
            mock_create.assert_called_once()
            call_args = mock_create.call_args[0][2]
            assert "validation_results" in str(call_args) or len(call_args) > 0


@pytest.mark.asyncio
async def test_concurrency_limit():
    """测试并发限制"""
    orchestrator = ValidationOrchestrator()
    orchestrator.init(max_concurrent=1)

    session_factory = AsyncMock()
    test_run = MagicMock(id="test-run-1")

    async def slow_task(*args):
        await asyncio.sleep(0.5)

    with patch.object(orchestrator, "_execute_with_timeout", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = slow_task

        # 第一个请求获取信号量
        task1 = asyncio.create_task(orchestrator.execute(session_factory, test_run))
        await asyncio.sleep(0.1)

        # 第二个请求应等待
        task2 = asyncio.create_task(orchestrator.execute(session_factory, test_run))

        # 等待完成
        await asyncio.gather(task1, task2)
```

## 注意事项

- 使用 `asyncio.Semaphore` 控制并发，不使用分布式锁
- 超时使用 `asyncio.wait_for`，异常捕获后标记状态
- 结果通过 `jsonable_encoder` 序列化后写入 JSON 字段
- Layer 4 和 Layer 5 内部子层并行执行，结果聚合到父层 key
- **编排器接收 session_factory 而非单个 session**：每个 layer 通过 factory 创建独立 session，避免并行协程共享 AsyncSession 导致 SQLAlchemy 异步冲突
- **_create_report 使用 `async with session.begin()`**：自动管理事务提交/回滚，不显式调用 `commit()`（CLAUDE.md 要求）
- 超时配置从配置中心读取，禁止硬编码
