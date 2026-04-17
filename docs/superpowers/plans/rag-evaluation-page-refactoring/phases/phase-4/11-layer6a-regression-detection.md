# 11 - Layer 6a: 回归检测 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 11 - Layer 6a: 回归检测

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/core/validation/layers/layer6a_regression.py`
- Test: `backend/tests/test_placeholder.py`

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

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `5.6.1 校验 6a: 回归检测` 节
> **所属 Phase**: Phase 4

## 需求定义

对比当前运行与上一次运行，检测指标是否退化。下降 > 5% 轻微退化，> 15% 严重退化。

## 验收标准

- [ ] 存在上一次运行时才执行
- [ ] 指标下降 > 5% 时警告
- [ ] 指标下降 > 15% 时严重警告
- [ ] 输出退化指标列表、退化幅度、严重程度

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/validation/layers/layer6a_regression.py` | 新增 | Layer 6a 实现 |

## 实现方案

### 后端实现

```python
# backend/src/core/validation/layers/layer6a_regression.py
import logging
from typing import Any

from sqlalchemy import select
from src.models.test_run import TestRun

logger = logging.getLogger(__name__)

class Layer6aRegressionDetection:
    """Layer 6a: 回归检测"""
    
    def __init__(self, db, test_run):
        self.db = db
        self.test_run = test_run
    
    async def execute(self) -> dict:
        """执行回归检测"""
        previous_run = await self._get_previous_run()
        
        if not previous_run:
            return {"status": "skipped", "data": {"reason": "不存在上一次运行记录"}}
        
        current_metrics = self.test_run.metrics or {}
        previous_metrics = previous_run.metrics or {}
        
        regressed_metrics = []
        
        for key, current_val in current_metrics.items():
            if key in previous_metrics:
                prev_val = previous_metrics[key]
                if prev_val == 0:
                    continue
                
                delta = (current_val - prev_val) / prev_val
                
                if delta < -0.15:
                    severity = "critical"
                elif delta < -0.05:
                    severity = "warning"
                else:
                    continue
                
                regressed_metrics.append({
                    "metric": key,
                    "current_value": current_val,
                    "previous_value": prev_val,
                    "delta_percent": round(delta * 100, 2),
                    "severity": severity,
                })
        
        warnings = []
        for m in regressed_metrics:
            level = "critical" if m["severity"] == "critical" else "warning"
            warnings.append({
                "level": level,
                "message": f"{m['metric']} 退化 {abs(m['delta_percent'])}% ({m['current_value']:.2f} vs {m['previous_value']:.2f})",
            })
        
        return {
            "status": "completed",
            "data": {
                "regressed_metrics": regressed_metrics,
                "previous_run_id": previous_run.id,
                "warnings": warnings,
            },
        }
    
    async def _get_previous_run(self) -> TestRun | None:
        """获取上一次运行记录"""
        stmt = (
            select(TestRun)
            .where(TestRun.test_set_id == self.test_run.test_set_id)
            .where(TestRun.id != self.test_run.id)
            .where(TestRun.status == "completed")
            .order_by(TestRun.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
```

## 测试方案

```python
@pytest.mark.asyncio
async def test_no_previous_run():
    """无上一次运行时跳过"""
    ...

@pytest.mark.asyncio
async def test_metric_regression():
    """指标退化检测正确"""
    ...
```

## 注意事项

- 仅对比同一 test_set_id 的运行
- 退化幅度使用百分比计算
