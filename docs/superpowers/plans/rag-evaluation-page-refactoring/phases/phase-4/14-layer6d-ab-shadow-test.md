# 14 - Layer 6d: A/B 影子测试 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 14 - Layer 6d: A/B 影子测试

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/core/validation/layers/layer6d_ab_test.py`
- Create: `backend/src/services/ab_test_service.py`
- Test: `backend/src/services/ab_test_service.py`

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

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `5.6.4 校验 6d: A/B 影子测试` 节
> **所属 Phase**: Phase 4

## 需求定义

同时运行两个配置，逐条对比效果。分层抽样 + 配对 t-test + p-value。生成 3 份报告。

## 验收标准

- [ ] 串行执行：先 A 后 B
- [ ] 抽样策略正确（≤30 全量，31-100 50%，>100 可选 20%/50%）
- [ ] 配对 t-test 输出 p-value 和置信区间
- [ ] 生成 3 份报告（A 常规、B 常规、A/B 对比）
- [ ] 支持取消测试，已完成结果保留

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/validation/layers/layer6d_ab_test.py` | 新增 | Layer 6d 实现 |
| `backend/src/services/ab_test_service.py` | 新增 | A/B 测试服务 |

## 实现方案

### 后端实现

```python
# backend/src/core/validation/layers/layer6d_ab_test.py
import logging
import numpy as np
from typing import Any
from scipy import stats

logger = logging.getLogger(__name__)

class Layer6dABShadowTest:
    """Layer 6d: A/B 影子测试"""
    
    def __init__(self, db, test_run_a, test_run_b, test_set):
        self.db = db
        self.test_run_a = test_run_a
        self.test_run_b = test_run_b
        self.test_set = test_set
    
    async def execute(self) -> dict:
        """执行 A/B 对比"""
        results_a = self.test_run_a.test_run_results or []
        results_b = self.test_run_b.test_run_results or []
        
        paired_metrics = self._pair_results(results_a, results_b)
        
        if not paired_metrics:
            return {"status": "failed", "data": {"reason": "无法配对结果"}}
        
        metric_deltas = self._calc_metric_deltas(paired_metrics)
        
        p_value, confidence_interval = self._paired_t_test(paired_metrics)
        
        # f1_delta = mean(B) - mean(A)，delta > 0 说明 B 更好
        winner = "B" if metric_deltas.get("f1_delta", 0) > 0 else "A"
        if p_value >= 0.05:
            conclusion = "差异不显著，A/B 配置效果相当"
        else:
            conclusion = f"配置 {winner} 胜出 (p={p_value:.3f})"
        
        return {
            "status": "completed",
            "data": {
                "winner": winner if p_value < 0.05 else "tie",
                "conclusion": conclusion,
                "metric_deltas": metric_deltas,
                "p_value": round(p_value, 4),
                "confidence_interval": [round(ci, 4) for ci in confidence_interval],
                "per_case_comparison": paired_metrics[:20],
            },
        }
    
    def _pair_results(self, results_a: list, results_b: list) -> list:
        """配对结果（基于 query）"""
        by_query_a = {getattr(r, "query", ""): r for r in results_a}
        by_query_b = {getattr(r, "query", ""): r for r in results_b}

        paired = []
        for query in by_query_a:
            if not query or query not in by_query_b:
                continue
            ra = by_query_a[query]
            rb = by_query_b[query]
            paired.append({
                "query": query,
                "hit_at_1_a": getattr(ra, "hit_at_1", 0),
                "hit_at_3_a": getattr(ra, "hit_at_3", 0),
                "hit_at_5_a": getattr(ra, "hit_at_5", 0),
                "precision_a": getattr(ra, "precision", 0),
                "recall_a": getattr(ra, "recall", 0),
                "f1_a": getattr(ra, "f1", 0),
                "hit_at_1_b": getattr(rb, "hit_at_1", 0),
                "hit_at_3_b": getattr(rb, "hit_at_3", 0),
                "hit_at_5_b": getattr(rb, "hit_at_5", 0),
                "precision_b": getattr(rb, "precision", 0),
                "recall_b": getattr(rb, "recall", 0),
                "f1_b": getattr(rb, "f1", 0),
            })
        return paired
    
    def _calc_metric_deltas(self, paired: list) -> dict:
        """计算指标差异"""
        if not paired:
            return {}
        
        deltas = {}
        for metric_key in ["hit_at_1", "hit_at_3", "hit_at_5", "precision", "recall", "f1"]:
            values_a = [p.get(f"{metric_key}_a", 0) for p in paired]
            values_b = [p.get(f"{metric_key}_b", 0) for p in paired]
            deltas[f"{metric_key}_delta"] = round(
                float(np.mean(values_b) - np.mean(values_a)), 4
            )
        
        return deltas
    
    def _paired_t_test(self, paired: list) -> tuple:
        """配对 t-test"""
        if len(paired) < 2:
            return 1.0, (0, 0)

        values_a = [p["hit_at_5_a"] for p in paired]
        values_b = [p["hit_at_5_b"] for p in paired]

        t_stat, p_value = stats.ttest_rel(values_b, values_a)

        diff = np.array(values_b) - np.array(values_a)
        sem_val = stats.sem(diff)
        if sem_val == 0:
            # 所有差异相同，置信区间为单点
            ci = (float(np.mean(diff)), float(np.mean(diff)))
        else:
            ci = stats.t.interval(0.95, len(diff) - 1, loc=np.mean(diff), scale=sem_val)

        return p_value, ci
```

### A/B 测试服务

```python
# backend/src/services/ab_test_service.py
import logging
from datetime import datetime, UTC
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ABTestService:
    """A/B 测试服务 — 生成 3 份报告"""

    @staticmethod
    async def create_ab_test_reports(
        db: AsyncSession,
        test_run_a,
        test_run_b,
        ab_comparison_result: dict,
    ) -> tuple:
        """
        生成 3 份报告：
        1. 配置 A 的常规报告 (Layer 1-5)
        2. 配置 B 的常规报告 (Layer 1-5)
        3. A/B 对比报告 (Layer 6d)
        """
        from src.models.rag_eval.test_report import RagEvalTestReport
        from src.models.rag_eval.enums import RagEvalTestReportStatus

        ab_test_id = f"ab-{test_run_a.id[:8]}-{test_run_b.id[:8]}"

        # 报告 1: 配置 A 常规报告
        report_a = RagEvalTestReport(
            run_id=test_run_a.id,
            test_set_id=test_run_a.test_set_id,
            config_version_id=test_run_a.config_version_id,
            validation_results=test_run_a.validation_results or {},
            status=RagEvalTestReportStatus.COMPLETED,
        )
        db.add(report_a)

        # 报告 2: 配置 B 常规报告
        report_b = RagEvalTestReport(
            run_id=test_run_b.id,
            test_set_id=test_run_b.test_set_id,
            config_version_id=test_run_b.config_version_id,
            validation_results=test_run_b.validation_results or {},
            status=RagEvalTestReportStatus.COMPLETED,
        )
        db.add(report_b)

        # 报告 3: A/B 对比报告 (run_id 为 NULL)
        report_ab = RagEvalTestReport(
            run_id=None,
            test_set_id=test_run_a.test_set_id,
            config_version_id=test_run_a.config_version_id,
            validation_results={"layer6d": ab_comparison_result},
            status=RagEvalTestReportStatus.COMPLETED,
        )
        db.add(report_ab)

        await db.commit()
        await db.refresh(report_a)
        await db.refresh(report_b)
        await db.refresh(report_ab)

        return report_a, report_b, report_ab

    @staticmethod
    def determine_sampling_strategy(total_cases: int, user_choice: str = "50%") -> float:
        """确定抽样策略"""
        if total_cases <= 30:
            return 1.0
        elif total_cases <= 100:
            return 0.5
        else:
            return 0.2 if user_choice == "20%" else 0.5

    @staticmethod
    def stratified_sample(test_cases: list, ratio: float) -> list:
        """分层随机抽样"""
        from collections import defaultdict
        import random

        by_stratum = defaultdict(list)
        for tc in test_cases:
            key = (tc.get("domain"), tc.get("age_group"))
            by_stratum[key].append(tc)

        sampled = []
        for cases in by_stratum.values():
            n = max(3, int(len(cases) * ratio))
            sampled.extend(random.sample(cases, min(n, len(cases))))

        return sampled
```

## 测试方案

```python
@pytest.mark.asyncio
async def test_serial_execution():
    """串行执行：先 A 后 B"""
    ...

@pytest.mark.asyncio
async def test_paired_t_test():
    """配对 t-test 输出正确"""
    ...

@pytest.mark.asyncio
async def test_create_three_reports():
    """A/B 测试生成 3 份报告"""
    ...

@pytest.mark.asyncio
async def test_paired_t_test_sem_zero():
    """配对 t-test 当 sem=0 时不报错"""
    ...
```

## 注意事项

- A/B 测试最大并发任务数为 1
- 抽样模式需在报告中标注"抽样结果，仅供参考"
- p < 0.05 表示差异显著
