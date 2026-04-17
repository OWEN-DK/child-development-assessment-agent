# 17 - Layer 6 手动触发 API 端点 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 17 - Layer 6 手动触发 API 端点

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/core/validation/layers/layer6_runner.py`
- Modify: `backend/src/controller/rag_test_controller.py`
- Modify: `backend/src/service/test_report_service.py`
- Test: `backend/src/service/test_report_service.py`

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

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `5.6 验证保障层` 节
> **所属 Phase**: Phase 4
> **补充说明**: 编排器中 Layer 6 默认跳过，需通过独立 API 手动触发

## 需求定义

Layer 6（回归检测、交叉验证、成本效果分析、A/B 影子测试）计算成本高，默认不执行。
用户需在评估报告页手动触发，触发后异步执行，通过 SSE 推送结果。

## 验收标准

- [ ] `POST /rag/test/reports/{report_id}/validate-layer6` 端点可用
- [ ] 触发后返回 `task_id`，前端通过 SSE 监听进度
- [ ] Layer 6 结果写入对应 TestReport.validation_results["layer6"]
- [ ] 重复触发时提示"Layer 6 已在执行中"

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/controller/rag_test_controller.py` | 修改 | 新增 Layer 6 触发端点 |
| `backend/src/service/test_report_service.py` | 修改 | 新增 `trigger_layer6_validation` 方法 |
| `backend/src/core/validation/layers/layer6_runner.py` | 新增 | Layer 6 四子层执行器 |

## 实现方案

### 后端实现

```python
# backend/src/core/validation/layers/layer6_runner.py
import asyncio
import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.validation.layers.layer6a_regression import Layer6aRegressionDetection
from src.core.validation.layers.layer6b_cross_validation import Layer6bCrossValidation
from src.core.validation.layers.layer6c_cost_effectiveness import Layer6cCostEffectiveness
from src.core.validation.layers.layer6d_ab_shadow import Layer6dABShadowTest

logger = logging.getLogger(__name__)


class Layer6Runner:
    """Layer 6 四子层执行器（用户手动触发）"""

    def __init__(self, db: AsyncSession, test_run, report):
        self.db = db
        self.test_run = test_run
        self.report = report

    async def execute(self) -> dict:
        """执行 Layer 6 全部四子层，返回聚合结果"""
        layer6_results = {}

        # 四个子层依次执行（Layer 6 不并行，因为子层之间有数据依赖）
        sublayers = [
            ("regression", Layer6aRegressionDetection(self.db, self.test_run)),
            ("cross_validation", Layer6bCrossValidation(self.db, self.test_run)),
            ("cost_effectiveness", Layer6cCostEffectiveness(self.db, self.test_run)),
            ("ab_shadow_test", Layer6dABShadowTest(self.db, self.test_run)),
        ]

        for key, layer in sublayers:
            try:
                result = await asyncio.wait_for(layer.execute(), timeout=60)
                layer6_results[key] = result
            except asyncio.TimeoutError:
                logger.warning(f"Layer 6 {key} 超时 (60s)")
                layer6_results[key] = {
                    "status": "timeout",
                    "data": {"reason": "超时 (60s)"},
                }
            except Exception as e:
                logger.error(f"Layer 6 {key} 异常: {e}")
                layer6_results[key] = {
                    "status": "degraded",
                    "data": {"reason": str(e)},
                }

        # 聚合 Layer 6 状态
        statuses = [r.get("status", "completed") for r in layer6_results.values() if isinstance(r, dict)]
        priority = {"degraded": 0, "timeout": 1, "completed": 2}
        worst = min(statuses, key=lambda s: priority.get(s, 2)) if statuses else "completed"

        return {
            "status": worst,
            "data": layer6_results,
        }
```

```python
# backend/src/service/test_report_service.py 新增方法

async def trigger_layer6_validation(
    self,
    report_id: str,
    sse_publisher,
) -> dict:
    """触发 Layer 6 校验（异步）

    参数:
        report_id: 评估报告 ID
        sse_publisher: SSE 发布器

    返回:
        {"task_id": "...", "message": "Layer 6 校验已触发"}

    异常:
        ValueError: 报告不存在或 Layer 6 已在执行中
    """
    # 查询报告
    report = await self._get_report_by_id(report_id)
    if not report:
        raise ValueError(f"报告 {report_id} 不存在")

    # 检查 Layer 6 是否已在执行
    validation_results = report.validation_results or {}
    layer6 = validation_results.get("layer6", {})
    if layer6.get("status") == "running":
        raise ValueError("Layer 6 校验已在执行中")

    # 标记为 running
    validation_results["layer6"] = {
        "status": "running",
        "data": {"reason": "正在执行 Layer 6 校验"},
    }
    await self._update_report_validation_results(report_id, validation_results)

    # 异步执行 Layer 6
    from src.core.validation.layers.layer6_runner import Layer6Runner

    async def _run_layer6():
        try:
            runner = Layer6Runner(self.db_session, report.test_run, report)
            result = await runner.execute()

            # 更新报告
            validation_results["layer6"] = result
            await self._update_report_validation_results(report_id, validation_results)

            # SSE 推送
            await sse_publisher.publish(
                channel=f"test_run:{report.run_id}",
                event_type="layer6_completed",
                data={"report_id": report_id, "result": result},
            )
        except Exception as e:
            logger.error(f"Layer 6 执行异常: {e}")
            validation_results["layer6"] = {
                "status": "degraded",
                "data": {"reason": str(e)},
            }
            await self._update_report_validation_results(report_id, validation_results)

            await sse_publisher.publish(
                channel=f"test_run:{report.run_id}",
                event_type="layer6_failed",
                data={"report_id": report_id, "error": str(e)},
            )

    task_id = f"layer6-{report_id}"
    asyncio.create_task(_run_layer6())

    return {"task_id": task_id, "message": "Layer 6 校验已触发"}
```

```python
# backend/src/controller/rag_test_controller.py 新增端点

@router.post("/reports/{report_id}/validate-layer6")
async def trigger_layer6_validation(
    report_id: str,
    # 依赖注入: sse_publisher, test_report_service
):
    """手动触发 Layer 6 校验

    Layer 6 包含：回归检测、交叉验证、成本效果分析、A/B 影子测试。
    触发后异步执行，通过 SSE 推送结果。
    """
    try:
        result = await test_report_service.trigger_layer6_validation(
            report_id=report_id,
            sse_publisher=sse_publisher,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"触发 Layer 6 校验异常: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")
```

## 前端 SSE 事件补充

需在 `01-sse-event-definitions.md` 中新增两种事件：

```json
// layer6_completed
{
  "type": "layer6_completed",
  "report_id": "uuid-string",
  "result": {
    "status": "completed",
    "data": {
      "regression": {...},
      "cross_validation": {...},
      "cost_effectiveness": {...},
      "ab_shadow_test": {...}
    }
  },
  "timestamp": "2026-04-17T10:10:00Z"
}

// layer6_failed
{
  "type": "layer6_failed",
  "report_id": "uuid-string",
  "error": "数据库连接失败",
  "timestamp": "2026-04-17T10:10:00Z"
}
```

## 测试方案

```python
# backend/tests/test_layer6_trigger.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.asyncio
async def test_trigger_layer6_success():
    """成功触发 Layer 6 校验"""
    service = MagicMock()
    service._get_report_by_id = AsyncMock(return_value=MagicMock(
        id="report-1",
        run_id="run-1",
        validation_results={"layer1": {"status": "completed"}},
    ))
    service._update_report_validation_results = AsyncMock()

    with patch("asyncio.create_task") as mock_create_task:
        result = await service.trigger_layer6_validation("report-1", MagicMock())
        assert "task_id" in result
        assert mock_create_task.called


@pytest.mark.asyncio
async def test_trigger_layer6_already_running():
    """Layer 6 已在执行中时抛出 ValueError"""
    service = MagicMock()
    service._get_report_by_id = AsyncMock(return_value=MagicMock(
        id="report-1",
        validation_results={"layer6": {"status": "running"}},
    ))

    with pytest.raises(ValueError, match="已在执行中"):
        await service.trigger_layer6_validation("report-1", MagicMock())


@pytest.mark.asyncio
async def test_trigger_layer6_report_not_found():
    """报告不存在时抛出 ValueError"""
    service = MagicMock()
    service._get_report_by_id = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="不存在"):
        await service.trigger_layer6_validation("non-existent", MagicMock())
```

## 注意事项

1. **Layer 6 子层依次执行**，不并行，因为回归检测需要交叉验证的结果作为参考
2. **重复触发保护**：通过 `status="running"` 标记防止重复触发
3. **SSE 推送**：完成后推送 `layer6_completed` 或 `layer6_failed` 事件
4. **前端展示**：评估报告页新增"执行 Layer 6 校验"按钮，点击后显示加载状态
