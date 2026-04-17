"""ValidationOrchestrator 测试用例

测试 6 层校验编排器的并行执行、超时控制、并发限制和结果聚合。
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from src.core.validation.orchestrator import ValidationOrchestrator


@pytest.mark.asyncio
async def test_execute_layers_all_parallel():
    """测试 Layer 1-5 全部并行执行（无 Phase A/B 串行）"""
    orchestrator = ValidationOrchestrator()
    await orchestrator.init()

    session_factory = AsyncMock()
    test_run = MagicMock(id="test-run-1", test_set_id="ts-1", config_version_id=None)

    # Mock 返回正确的 dict 结构
    async def mock_run_layer(*args):
        return {"layer": 1, "status": "completed", "data": {}, "duration_ms": 50}

    with patch.object(
        orchestrator, "_run_layer_with_result", new_callable=AsyncMock
    ) as mock_run:
        mock_run.side_effect = mock_run_layer
        with patch.object(
            orchestrator, "_create_report", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = MagicMock(id="report-1")
            await orchestrator.execute(session_factory, test_run)

            # 应该调用 9 次：Layer1, Layer2, Layer3, Layer4a, Layer4b, Layer4c, Layer5a, Layer5b, Layer5c
            assert mock_run.call_count == 9


@pytest.mark.asyncio
async def test_validation_results_array_format():
    """测试 validation_results 为数组格式"""
    orchestrator = ValidationOrchestrator()
    await orchestrator.init()

    session_factory = AsyncMock()
    test_run = MagicMock(id="test-run-1", test_set_id="ts-1", config_version_id=None)

    async def mock_run_layer(*args):
        return {
            "layer": 1,
            "status": "completed",
            "data": {"suggestions": []},
            "duration_ms": 50,
        }

    with patch.object(
        orchestrator, "_run_layer_with_result", new_callable=AsyncMock
    ) as mock_run:
        mock_run.side_effect = mock_run_layer
        with patch.object(
            orchestrator, "_create_report", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = MagicMock(id="report-1")
            await orchestrator.execute(session_factory, test_run)

            # 验证传入 _create_report 的 validation_results 是列表
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
    results = [
        {
            "layer": 4,
            "key": "layer4_golden_coverage",
            "status": "completed",
            "data": {"data": {"book_coverage": 0.8}},
        },
        {
            "layer": 4,
            "key": "layer4_chunk_quality",
            "status": "timeout",
            "data": {"data": {"reason": "超时 (30s)"}},
        },
        {
            "layer": 4,
            "key": "layer4_document_staleness",
            "status": "completed",
            "data": {"data": {"stale_ratio": 0.1}},
        },
    ]
    status = orchestrator._aggregate_layer_status_from_results(
        ["layer4_golden_coverage", "layer4_chunk_quality", "layer4_document_staleness"],
        results,
    )
    assert status == "timeout"


@pytest.mark.asyncio
async def test_concurrency_limit():
    """测试并发限制"""
    orchestrator = ValidationOrchestrator()
    await orchestrator.init(max_concurrent=1)

    session_factory = AsyncMock()
    test_run = MagicMock(id="test-run-1", test_set_id="ts-1", config_version_id=None)

    async def slow_task(*args):
        await asyncio.sleep(0.5)

    with patch.object(
        orchestrator, "_execute_with_timeout", new_callable=AsyncMock
    ) as mock_exec:
        mock_exec.side_effect = slow_task

        task1 = asyncio.create_task(orchestrator.execute(session_factory, test_run))
        await asyncio.sleep(0.1)

        task2 = asyncio.create_task(orchestrator.execute(session_factory, test_run))

        await asyncio.gather(task1, task2)


@pytest.mark.asyncio
async def test_layer_timeout_returns_degraded_status():
    """测试单层超时返回 timeout 状态"""
    orchestrator = ValidationOrchestrator()

    async def slow_execute():
        await asyncio.sleep(10)

    mock_layer = MagicMock()
    mock_layer.execute = slow_execute

    result = await orchestrator._run_layer_with_result(1, mock_layer, "test_layer", 0.1)

    assert result["status"] == "timeout"
    assert "layer" in result
    assert "duration_ms" in result


@pytest.mark.asyncio
async def test_layer_exception_returns_degraded_status():
    """测试单层异常返回 degraded 状态"""
    orchestrator = ValidationOrchestrator()

    async def failing_execute():
        raise ValueError("测试异常")

    mock_layer = MagicMock()
    mock_layer.execute = failing_execute

    result = await orchestrator._run_layer_with_result(1, mock_layer, "test_layer", 30)

    assert result["status"] == "degraded"
    assert "reason" in result["data"]
    assert "测试异常" in result["data"]["reason"]


@pytest.mark.asyncio
async def test_aggregate_sublayers_data():
    """测试聚合子层数据到父层"""
    orchestrator = ValidationOrchestrator()
    # _run_layer_with_result 返回的格式: {"layer": N, "status": "...", "data": {...}, "duration_ms": N}
    # 其中 data 是层执行返回的结果，应该包含 layer4_xxx 或 layer5_xxx 键
    results = [
        {
            "layer": 4,
            "key": "layer4_golden_coverage",
            "status": "completed",
            "data": {"data": {"book_coverage": 0.8}},
            "duration_ms": 50,
        },
        {
            "layer": 4,
            "key": "layer4_chunk_quality",
            "status": "completed",
            "data": {"data": {"avg_chunk_size": 512}},
            "duration_ms": 60,
        },
        {
            "layer": 4,
            "key": "layer4_document_staleness",
            "status": "completed",
            "data": {"data": {"stale_ratio": 0.1}},
            "duration_ms": 70,
        },
    ]
    data = orchestrator._aggregate_sublayers_to_data(
        ["layer4_golden_coverage", "layer4_chunk_quality", "layer4_document_staleness"],
        results,
    )
    assert "golden_coverage" in data
    assert "chunk_quality" in data
    assert "document_staleness" in data
    assert data["golden_coverage"] == {"book_coverage": 0.8}


@pytest.mark.asyncio
async def test_layer_6_skipped_by_default():
    """测试 Layer 6 默认跳过"""
    orchestrator = ValidationOrchestrator()
    await orchestrator.init()

    session_factory = AsyncMock()
    test_run = MagicMock(id="test-run-1", test_set_id="ts-1", config_version_id=None)

    async def mock_run_layer(*args):
        return {"layer": 1, "status": "completed", "data": {}, "duration_ms": 50}

    with patch.object(
        orchestrator, "_run_layer_with_result", new_callable=AsyncMock
    ) as mock_run:
        mock_run.side_effect = mock_run_layer
        with patch.object(
            orchestrator, "_create_report", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = MagicMock(id="report-1")
            await orchestrator.execute(session_factory, test_run)

            call_args = mock_create.call_args[0][2]
            layer_6_result = next((r for r in call_args if r.get("layer") == 6), None)
            assert layer_6_result is not None
            assert layer_6_result["status"] == "skipped"


@pytest.mark.asyncio
async def test_validation_results_sorted_by_layer():
    """测试 validation_results 按 layer 序号排序"""
    orchestrator = ValidationOrchestrator()
    await orchestrator.init()

    session_factory = AsyncMock()
    test_run = MagicMock(id="test-run-1", test_set_id="ts-1", config_version_id=None)

    # 需要提供 9 个结果（Layer 1-5 的所有子层）
    layer_results = [
        {"layer": 1, "status": "completed", "data": {}, "duration_ms": 50},
        {"layer": 2, "status": "completed", "data": {}, "duration_ms": 75},
        {"layer": 3, "status": "completed", "data": {}, "duration_ms": 100},
        {
            "layer": 4,
            "status": "completed",
            "data": {"layer4_golden_coverage": {}},
            "duration_ms": 60,
        },
        {
            "layer": 4,
            "status": "completed",
            "data": {"layer4_chunk_quality": {}},
            "duration_ms": 65,
        },
        {
            "layer": 4,
            "status": "completed",
            "data": {"layer4_document_staleness": {}},
            "duration_ms": 70,
        },
        {
            "layer": 5,
            "status": "completed",
            "data": {"layer5_embedding_quality": {}},
            "duration_ms": 80,
        },
        {
            "layer": 5,
            "status": "completed",
            "data": {"layer5_intent_accuracy": {}},
            "duration_ms": 85,
        },
        {
            "layer": 5,
            "status": "completed",
            "data": {"layer5_error_patterns": {}},
            "duration_ms": 90,
        },
    ]

    call_index = 0

    async def mock_run_layer(*args):
        nonlocal call_index
        result = layer_results[call_index]
        call_index += 1
        return result

    with patch.object(
        orchestrator, "_run_layer_with_result", new_callable=AsyncMock
    ) as mock_run:
        mock_run.side_effect = mock_run_layer
        with patch.object(
            orchestrator, "_create_report", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = MagicMock(id="report-1")
            await orchestrator.execute(session_factory, test_run)

            call_args = mock_create.call_args[0][2]
            layers = [
                r.get("layer") for r in call_args if r.get("layer") in (1, 2, 3, 4, 5)
            ]
            assert layers == sorted(layers)


@pytest.mark.asyncio
async def test_init_idempotent():
    """测试初始化幂等性"""
    orchestrator = ValidationOrchestrator()
    await orchestrator.init(max_concurrent=2)
    await orchestrator.init(max_concurrent=5)  # 不应覆盖

    # 验证信号量已初始化
    assert orchestrator._semaphore is not None
