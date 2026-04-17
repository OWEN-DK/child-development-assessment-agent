# 15 - 超时与降级策略 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 15 - 超时与降级策略

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Test: `backend/tests/test_timeout_degradation.py`

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

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `3.3 校验层定义` 节
> **所属 Phase**: Phase 4

## 需求定义

总体 5 分钟超时，单层层超时降级标记。降级后报告仍标记为 completed，但 validation_results 中对应层标记 degraded 或 timeout。

> **注意**: 超时核心逻辑已在 `01-validation-orchestrator.md` 中实现，本文档补充策略细节。

## 验收标准

- [ ] 总体超时 5 分钟，超时后取消正在执行的层
- [ ] Layer 1/2/4/5 单层层超时 30s
- [ ] Layer 3 (LLM) 单层层超时 120s（含重试）
- [ ] Layer 6 单层层超时 60s
- [ ] 降级后 TestReport.status 仍为 completed
- [ ] 前端展示降级层显示"⚠️ 部分结果不可用"

## 超时配置汇总

```python
# 定义在 backend/src/core/validation/orchestrator.py
TOTAL_TIMEOUT = 300  # 5 分钟

LAYER_TIMEOUTS = {
    1: 30,   # Layer 1: 30s
    2: 30,   # Layer 2: 30s
    3: 120,  # Layer 3 (LLM): 120s（含重试）
    4: 30,   # Layer 4a/4b/4c 每个子层独立超时 30s（非共享）
    5: 30,   # Layer 5a/5b/5c 每个子层独立超时 30s（非共享）
    6: 60,   # Layer 6: 60s
}
```

> **注意**：Layer 4 和 Layer 5 的超时是**每个子层独立超时**，不是子层共享。
> 即 Layer 4a、4b、4c 各自有 30s 超时窗口，三个子层并行执行时互不影响。
> 总体仍受 TOTAL_TIMEOUT=300s 限制。

## 降级状态处理

### 降级后的 validation_results 结构示例

```json
{
  "layer1": {"status": "completed", "data": {"suggestions": [...]}},
  "layer2": {"status": "timeout", "data": {"reason": "超时 (30s)"}},
  "layer3": {"status": "degraded", "data": {"reason": "LLM 服务不可用，已跳过深度诊断"}},
  "layer4": {"status": "completed", "data": {"golden_coverage": {...}, "chunk_quality": {...}, "document_staleness": {...}}},
  "layer5": {"status": "completed", "data": {"embedding_quality": {...}, "intent_accuracy": {...}, "error_patterns": {...}}},
  "layer6": {"status": "skipped", "data": {"reason": "用户手动触发"}}
}
```

### 状态流转

| 状态 | 触发条件 | 报告 status | 前端展示 |
|------|---------|-------------|---------|
| `completed` | 校验正常完成 | `completed` | ✓ 已完成 |
| `timeout` | 单层层超时 | `completed` | ⏱ 超时 |
| `degraded` | 异常/降级策略触发 | `completed` | ⚠️ 部分结果不可用 |
| `skipped` | 条件不满足/手动跳过 | `completed` | ⏭ 已跳过 |

## 前端降级展示

```tsx
// frontend/src/pages/rag-eval/reports/ReportPage.tsx
const ValidationLayerCard = ({ layer, result }) => {
  const statusConfig = {
    completed: { color: "success", icon: "✓", text: "已完成" },
    timeout: { color: "warning", icon: "⏱", text: "超时" },
    degraded: { color: "warning", icon: "⚠️", text: "部分结果不可用" },
    skipped: { color: "default", icon: "⏭", text: "已跳过" },
  };
  
  const config = statusConfig[result.status] || statusConfig.completed;
  
  return (
    <Card status={config.color}>
      <Title>{layer.name}</Title>
      <Tag color={config.color}>{config.icon} {config.text}</Tag>
      {result.status === "degraded" && (
        <Alert message={result.data.reason} type="warning" />
      )}
      {result.status === "timeout" && (
        <Alert message={result.data.reason} type="warning" />
      )}
      {result.status === "completed" && <LayerContent data={result.data} />}
    </Card>
  );
};
```

## 测试方案

```python
# backend/tests/test_timeout_degradation.py
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.core.validation.orchestrator import ValidationOrchestrator


@pytest.mark.asyncio
async def test_layer_timeout():
    """单层层超时标记 timeout"""
    orchestrator = ValidationOrchestrator()
    orchestrator.init()

    results = {}

    class SlowLayer:
        async def execute(self):
            await asyncio.sleep(999)

    await orchestrator._run_layer(1, SlowLayer(), results, "test_layer")

    assert results["test_layer"]["status"] == "timeout"
    assert "超时" in results["test_layer"]["data"]["reason"]


@pytest.mark.asyncio
async def test_llm_degradation():
    """LLM 异常时标记 degraded"""
    orchestrator = ValidationOrchestrator()
    orchestrator.init()

    results = {}

    class FailingLayer:
        async def execute(self):
            raise ConnectionError("LLM 服务不可用")

    await orchestrator._run_layer(3, FailingLayer(), results, "test_llm_layer")

    assert results["test_llm_layer"]["status"] == "degraded"
    assert "LLM 服务不可用" in results["test_llm_layer"]["data"]["reason"]


@pytest.mark.asyncio
async def test_report_status_after_timeout():
    """超时后报告仍为 completed"""
    orchestrator = ValidationOrchestrator()
    orchestrator.init()

    db = AsyncMock()
    test_run = MagicMock(id="test-run-1", test_set_id="ts-1", config_version_id="cv-1")

    async def slow_execute(*args):
        await asyncio.sleep(999)

    with patch.object(orchestrator, "_execute_layers", side_effect=slow_execute):
        with patch.object(orchestrator, "_create_report", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock(id="report-1", status="completed")
            report = await orchestrator.execute(db, test_run)

            mock_create.assert_called_once()
            # 验证即使超时，_create_report 仍被调用
            assert report.status == "completed"


@pytest.mark.asyncio
async def test_total_timeout_preserves_completed_layers():
    """总体超时后保留已完成层的结果"""
    orchestrator = ValidationOrchestrator()
    orchestrator.init()

    db = AsyncMock()
    test_run = MagicMock(id="test-run-1", test_set_id="ts-1", config_version_id="cv-1")

    call_args = {}

    async def capture_results(db, test_run, results):
        results["layer1"] = {"status": "completed", "data": {"suggestions": []}}
        results["layer2"] = {"status": "completed", "data": {"matches": []}}
        await asyncio.sleep(999)  # layer3 超时

    async def mock_create_report(db, test_run, validation_results):
        call_args["results"] = validation_results
        return MagicMock(id="report-1", status="completed")

    with patch.object(orchestrator, "_execute_layers", side_effect=capture_results):
        with patch.object(orchestrator, "_create_report", side_effect=mock_create_report):
            await orchestrator.execute(db, test_run)

            assert "layer1" in call_args["results"]
            assert call_args["results"]["layer1"]["status"] == "completed"


@pytest.mark.asyncio
async def test_layer_exception_mark_degraded():
    """Layer 异常时标记 degraded 而非失败"""
    orchestrator = ValidationOrchestrator()
    orchestrator.init()

    results = {}

    class ExceptionLayer:
        async def execute(self):
            raise ValueError("数据库连接失败")

    await orchestrator._run_layer(2, ExceptionLayer(), results, "test_exception_layer")

    assert results["test_exception_layer"]["status"] == "degraded"
    assert "数据库连接失败" in results["test_exception_layer"]["data"]["reason"]
```

## 注意事项

- 超时使用 `asyncio.wait_for`，异常捕获后标记状态
- 降级不阻塞报告生成，TestReport.status 仍为 completed
- 前端根据 status 字段展示不同状态
- 核心实现见 `01-validation-orchestrator.md`
