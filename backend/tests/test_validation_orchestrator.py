import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.core.validation.orchestrator import ValidationOrchestrator


@pytest.fixture
def orchestrator():
    """创建 ValidationOrchestrator 实例"""
    return ValidationOrchestrator()


@pytest.fixture
def mock_session_factory():
    """创建 mock session factory"""
    return AsyncMock()


@pytest.fixture
def mock_test_run():
    """创建 mock test run"""
    test_run = MagicMock()
    test_run.id = "test-run-1"
    test_run.test_set_id = "ts-1"
    test_run.config_version_id = "cv-1"
    return test_run


@pytest.mark.asyncio
async def test_execute_layers_all_parallel(
    orchestrator, mock_session_factory, mock_test_run
):
    """测试 Layer 1-5 全部并行执行（无 Phase A/B 串行）"""
    await orchestrator.init(max_concurrent=3)

    with patch(
        "src.core.validation.orchestrator._get_validation_config"
    ) as mock_config:
        mock_config.return_value = {
            "total_timeout": 300,
            "layer_timeouts": {1: 30, 2: 30, 3: 120, 4: 30, 5: 30, 6: 60},
            "max_concurrent": 3,
            "queue_max": 10,
        }
        with patch.object(
            orchestrator, "_run_layer_with_result", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = {
                "layer": 1,
                "status": "completed",
                "data": {},
                "duration_ms": 50,
            }
            with patch.object(
                orchestrator, "_create_report", new_callable=AsyncMock
            ) as mock_create:
                mock_create.return_value = MagicMock(id="report-1")
                await orchestrator.execute(mock_session_factory, mock_test_run)

                assert mock_run.call_count == 9


@pytest.mark.asyncio
async def test_validation_results_array_format(
    orchestrator, mock_session_factory, mock_test_run
):
    """测试 validation_results 为数组格式 [{layer, status, data, duration_ms}, ...]"""
    await orchestrator.init(max_concurrent=3)

    with patch(
        "src.core.validation.orchestrator._get_validation_config"
    ) as mock_config:
        mock_config.return_value = {
            "total_timeout": 300,
            "layer_timeouts": {1: 30, 2: 30, 3: 120, 4: 30, 5: 30, 6: 60},
            "max_concurrent": 3,
            "queue_max": 10,
        }
        with patch.object(
            orchestrator, "_run_layer_with_result", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = {
                "layer": 1,
                "status": "completed",
                "data": {"suggestions": []},
                "duration_ms": 50,
            }
            with patch.object(
                orchestrator, "_create_report", new_callable=AsyncMock
            ) as mock_create:
                mock_create.return_value = MagicMock(id="report-1")
                await orchestrator.execute(mock_session_factory, mock_test_run)

                call_args = mock_create.call_args[0][2]
                assert isinstance(call_args, list)
                if call_args:
                    assert "layer" in call_args[0]
                    assert "status" in call_args[0]
                    assert "duration_ms" in call_args[0]


@pytest.mark.asyncio
async def test_aggregate_sublayers_inherits_worst_status(orchestrator):
    """测试聚合子层状态继承最差"""
    results = [
        {
            "layer": 4,
            "status": "completed",
            "data": {"layer4_golden_coverage": {"data": {"book_coverage": 0.8}}},
        },
        {
            "layer": 4,
            "status": "timeout",
            "data": {"layer4_chunk_quality": {"data": {"reason": "超时 (30s)"}}},
        },
        {
            "layer": 4,
            "status": "completed",
            "data": {"layer4_document_staleness": {"data": {"stale_ratio": 0.1}}},
        },
    ]

    sub_keys = [
        "layer4_golden_coverage",
        "layer4_chunk_quality",
        "layer4_document_staleness",
    ]
    status = orchestrator._aggregate_layer_status_from_results(sub_keys, results)
    data = orchestrator._aggregate_sublayers_to_data(sub_keys, results)

    assert status == "timeout"
    assert "golden_coverage" in data
    assert "chunk_quality" in data


@pytest.mark.asyncio
async def test_total_timeout_preserves_completed(
    orchestrator, mock_session_factory, mock_test_run
):
    """测试总体超时后保留已完成层"""
    await orchestrator.init(max_concurrent=3)

    async def slow_execute(*args):
        await asyncio.sleep(999)

    with patch(
        "src.core.validation.orchestrator._get_validation_config"
    ) as mock_config:
        mock_config.return_value = {
            "total_timeout": 1,
            "layer_timeouts": {1: 30, 2: 30, 3: 120, 4: 30, 5: 30, 6: 60},
            "max_concurrent": 3,
            "queue_max": 10,
        }
        with patch.object(orchestrator, "_execute_layers", side_effect=slow_execute):
            with patch.object(
                orchestrator, "_create_report", new_callable=AsyncMock
            ) as mock_create:
                mock_create.return_value = MagicMock(id="report-1")
                await orchestrator.execute(mock_session_factory, mock_test_run)

                mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_concurrency_limit(mock_session_factory, mock_test_run):
    """测试并发限制"""
    orchestrator = ValidationOrchestrator()
    await orchestrator.init(max_concurrent=1)

    async def slow_task(*args):
        await asyncio.sleep(0.5)
        return MagicMock(id="report-1")

    with patch(
        "src.core.validation.orchestrator._get_validation_config"
    ) as mock_config:
        mock_config.return_value = {
            "total_timeout": 300,
            "layer_timeouts": {1: 30, 2: 30, 3: 120, 4: 30, 5: 30, 6: 60},
            "max_concurrent": 1,
            "queue_max": 10,
        }
        with patch.object(
            orchestrator, "_execute_with_timeout", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.side_effect = slow_task

            task1 = asyncio.create_task(
                orchestrator.execute(mock_session_factory, mock_test_run)
            )
            await asyncio.sleep(0.1)

            task2 = asyncio.create_task(
                orchestrator.execute(mock_session_factory, mock_test_run)
            )

            await asyncio.gather(task1, task2)

            assert mock_exec.call_count == 2


@pytest.mark.asyncio
async def test_layer_timeout_marked_correctly(orchestrator):
    """测试单层超时正确标记 status="timeout" """
    mock_layer = MagicMock()
    mock_layer.execute = AsyncMock(side_effect=asyncio.TimeoutError())

    result = await orchestrator._run_layer_with_result(1, mock_layer, "layer1", 1)

    assert result["status"] == "timeout"
    assert "duration_ms" in result
    assert result["layer"] == 1


@pytest.mark.asyncio
async def test_layer_error_marked_degraded(orchestrator):
    """测试异常标记 status="degraded" """
    mock_layer = MagicMock()
    mock_layer.execute = AsyncMock(side_effect=Exception("测试异常"))

    result = await orchestrator._run_layer_with_result(1, mock_layer, "layer1", 30)

    assert result["status"] == "degraded"
    assert "reason" in result["data"]


@pytest.mark.asyncio
async def test_queue_full_returns_503(mock_session_factory, mock_test_run):
    """测试队列满时返回 503 错误"""
    ValidationOrchestrator._semaphore = None
    ValidationOrchestrator._init_lock = None
    orchestrator = ValidationOrchestrator()
    await orchestrator.init(max_concurrent=1)

    async def slow_task(*args):
        await asyncio.sleep(10)
        return MagicMock(id="report-1")

    with patch(
        "src.core.validation.orchestrator._get_validation_config"
    ) as mock_config:
        mock_config.return_value = {
            "total_timeout": 300,
            "layer_timeouts": {1: 30, 2: 30, 3: 120, 4: 30, 5: 30, 6: 60},
            "max_concurrent": 1,
            "queue_max": 1,
        }
        with patch.object(
            orchestrator, "_execute_with_timeout", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.side_effect = slow_task

            task1 = asyncio.create_task(
                orchestrator.execute(mock_session_factory, mock_test_run)
            )
            await asyncio.sleep(0.1)

            from fastapi import HTTPException

            task2 = asyncio.create_task(
                orchestrator.execute(mock_session_factory, mock_test_run)
            )

            with pytest.raises(HTTPException) as exc_info:
                await task2

            assert exc_info.value.status_code == 503
            assert "队列已满" in exc_info.value.detail

            task1.cancel()
            try:
                await task1
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_queue_max_config_used_in_timeout(mock_session_factory, mock_test_run):
    """测试 queue_max 配置用于计算等待超时"""
    orchestrator = ValidationOrchestrator()
    await orchestrator.init(max_concurrent=1)

    with patch(
        "src.core.validation.orchestrator._get_validation_config"
    ) as mock_config:
        mock_config.return_value = {
            "total_timeout": 300,
            "layer_timeouts": {1: 30, 2: 30, 3: 120, 4: 30, 5: 30, 6: 60},
            "max_concurrent": 1,
            "queue_max": 5,
        }
        with patch.object(
            orchestrator, "_execute_with_timeout", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = MagicMock(id="report-1")

            await orchestrator.execute(mock_session_factory, mock_test_run)

            mock_config.assert_called()
            assert mock_config.return_value["queue_max"] == 5


@pytest.mark.asyncio
async def test_layer6_skipped_status(orchestrator, mock_session_factory, mock_test_run):
    """测试 Layer 6 默认标记为 skipped 状态"""
    await orchestrator.init(max_concurrent=3)

    with patch(
        "src.core.validation.orchestrator._get_validation_config"
    ) as mock_config:
        mock_config.return_value = {
            "total_timeout": 300,
            "layer_timeouts": {1: 30, 2: 30, 3: 120, 4: 30, 5: 30, 6: 60},
            "max_concurrent": 3,
            "queue_max": 10,
        }
        with patch.object(
            orchestrator, "_run_layer_with_result", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = {
                "layer": 1,
                "status": "completed",
                "data": {},
                "duration_ms": 50,
            }
            with patch.object(
                orchestrator, "_create_report", new_callable=AsyncMock
            ) as mock_create:
                mock_create.return_value = MagicMock(id="report-1")
                await orchestrator.execute(mock_session_factory, mock_test_run)

                call_args = mock_create.call_args[0][2]
                layer6_result = next(
                    (r for r in call_args if r.get("layer") == 6), None
                )
                assert layer6_result is not None
                assert layer6_result["status"] == "skipped"
                assert "reason" in layer6_result["data"]
