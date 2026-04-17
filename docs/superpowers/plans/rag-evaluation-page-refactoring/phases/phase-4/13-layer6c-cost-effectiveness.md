# 13 - Layer 6c: 成本效果分析 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 13 - Layer 6c: 成本效果分析

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/core/validation/layers/layer6c_cost_effectiveness.py`
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

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `5.6.3 校验 6c: 成本效果分析` 节
> **所属 Phase**: Phase 4

## 需求定义

分析配置变更带来的指标提升与额外成本的比例。成本效果比 = 指标提升得分 / 额外成本得分。

## 验收标准

- [ ] 成本效果比公式正确实现
- [ ] 零成本场景特殊处理
- [ ] 成本效果比 < 0.1 不建议，0.1-0.5 可考虑，> 0.5 强烈推荐

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/validation/layers/layer6c_cost_effectiveness.py` | 新增 | Layer 6c 实现 |

## 实现方案

### 后端实现

```python
# backend/src/core/validation/layers/layer6c_cost_effectiveness.py
import logging
import math
from typing import Any

from sqlalchemy import select
from src.models.test_run import TestRun

logger = logging.getLogger(__name__)

METRIC_WEIGHTS = {
    "p_at_5": 30,
    "r_at_5": 30,
    "f1": 20,
    "mrr": 10,
    "ndcg": 10,
}

class Layer6cCostEffectiveness:
    """Layer 6c: 成本效果分析"""
    
    def __init__(self, db, test_run):
        self.db = db
        self.test_run = test_run
    
    async def execute(self) -> dict:
        """执行成本效果分析"""
        previous_run = await self._get_previous_run()
        
        if not previous_run:
            return {"status": "skipped", "data": {"reason": "不存在上一次运行记录"}}
        
        config_changed = self.test_run.config_version_id != previous_run.config_version_id
        
        if not config_changed:
            return {"status": "skipped", "data": {"reason": "配置未变更"}}
        
        current_metrics = self.test_run.metrics or {}
        previous_metrics = previous_run.metrics or {}
        
        metric_improvement_score = self._calc_metric_improvement_score(
            previous_metrics, current_metrics
        )
        
        extra_tokens = self._estimate_extra_tokens(previous_run, self.test_run)
        extra_cost_score = self._calc_extra_cost_score(extra_tokens)
        
        if extra_tokens == 0:
            cost_effectiveness_ratio = metric_improvement_score * 10
        else:
            cost_effectiveness_ratio = metric_improvement_score / extra_cost_score if extra_cost_score > 0 else 0
        
        recommendation = self._get_recommendation(cost_effectiveness_ratio)
        
        return {
            "status": "completed",
            "data": {
                "metric_improvement_score": round(metric_improvement_score, 2),
                "extra_tokens": extra_tokens,
                "extra_cost_score": round(extra_cost_score, 2),
                "cost_effectiveness_ratio": round(cost_effectiveness_ratio, 2),
                "recommendation": recommendation,
                "config_changes": self._extract_config_changes(previous_run),
            },
        }
    
    def _calc_metric_improvement_score(self, prev: dict, curr: dict) -> float:
        """指标提升得分"""
        score = 0
        for metric, weight in METRIC_WEIGHTS.items():
            delta = curr.get(metric, 0) - prev.get(metric, 0)
            score += delta * weight
        return max(0, score)
    
    def _estimate_extra_tokens(self, prev_run: TestRun, curr_run: TestRun) -> int:
        """估算额外 token 消耗"""
        prev_tokens = (prev_run.metrics or {}).get("total_tokens", 0)
        curr_tokens = (curr_run.metrics or {}).get("total_tokens", 0)
        return max(0, curr_tokens - prev_tokens)
    
    def _calc_extra_cost_score(self, extra_tokens: int) -> float:
        """额外成本得分"""
        return math.log2(1 + extra_tokens / 1000)
    
    def _get_recommendation(self, ratio: float) -> str:
        """获取建议"""
        if ratio < 0.1:
            return "不建议应用该变更 (成本高，提升小)"
        elif ratio <= 0.5:
            return "可考虑应用 (权衡成本与效果)"
        else:
            return "强烈推荐应用 (成本低，提升大)"
    
    async def _get_previous_run(self) -> TestRun | None:
        """获取上一次运行"""
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
    
    def _extract_config_changes(self, previous_run: TestRun) -> list:
        """提取配置变更"""
        prev_config = previous_run.config_snapshot or {}
        curr_config = self.test_run.config_snapshot or {}
        
        changes = []
        all_keys = set(prev_config.keys()) | set(curr_config.keys())
        for key in all_keys:
            old_val = prev_config.get(key)
            new_val = curr_config.get(key)
            if old_val != new_val:
                changes.append({
                    "key": key,
                    "old_value": old_val,
                    "new_value": new_val,
                })
        return changes
```

## 测试方案

```python
@pytest.mark.asyncio
async def test_zero_cost_scenario():
    """零成本场景特殊处理"""
    ...

@pytest.mark.asyncio
async def test_cost_effectiveness_ratio():
    """成本效果比计算正确"""
    ...
```

## 注意事项

- 使用对数缩放防止 token 数过大时比例趋近于 0
- 零成本优化给予固定权重放大
