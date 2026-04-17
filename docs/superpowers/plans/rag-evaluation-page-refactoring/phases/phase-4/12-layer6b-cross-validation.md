# 12 - Layer 6b: 交叉验证 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 12 - Layer 6b: 交叉验证

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/core/validation/layers/layer6b_cross_validation.py`
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

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `5.6.2 校验 6b: 交叉验证` 节
> **所属 Phase**: Phase 4

## 需求定义

检查各领域/年龄组的指标一致性。某领域 F1 < 平均 F1 - 0.1 时警告，一致性评分 < 0.7 时警告。

## 验收标准

- [ ] 按领域/年龄分组计算指标
- [ ] 某领域表现显著低于平均时警告
- [ ] 整体一致性差时警告

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/validation/layers/layer6b_cross_validation.py` | 新增 | Layer 6b 实现 |

## 实现方案

### 后端实现

```python
# backend/src/core/validation/layers/layer6b_cross_validation.py
import logging
import numpy as np
from typing import Any
from collections import defaultdict

logger = logging.getLogger(__name__)

class Layer6bCrossValidation:
    """Layer 6b: 交叉验证"""
    
    def __init__(self, db, test_run):
        self.db = db
        self.test_run = test_run
    
    async def execute(self) -> dict:
        """执行交叉验证"""
        test_results = self.test_run.test_run_results or []
        
        if not test_results:
            return {"status": "skipped", "data": {"reason": "缺少测试结果"}}
        
        by_domain = defaultdict(list)
        by_age_group = defaultdict(list)
        
        for r in test_results:
            domain = r.domain or "unknown"
            age_group = r.age_group or "unknown"
            f1 = r.f1 or 0
            
            by_domain[domain].append(f1)
            by_age_group[age_group].append(f1)
        
        domain_metrics = {k: np.mean(v) for k, v in by_domain.items()}
        age_group_metrics = {k: np.mean(v) for k, v in by_age_group.items()}
        
        avg_f1 = np.mean(list(domain_metrics.values())) if domain_metrics else 0
        
        underperforming_domains = []
        for domain, f1 in domain_metrics.items():
            if f1 < avg_f1 - 0.1:
                underperforming_domains.append({
                    "domain": domain,
                    "f1": f1,
                    "delta_from_avg": round(f1 - avg_f1, 3),
                })
        
        consistency_score = self._calc_consistency_score(domain_metrics, age_group_metrics)
        
        warnings = []
        if underperforming_domains:
            for d in underperforming_domains:
                warnings.append({
                    "level": "warning",
                    "message": f"领域 '{d['domain']}' F1 ({d['f1']:.2f}) 显著低于平均 ({avg_f1:.2f})",
                })
        
        if consistency_score < 0.7:
            warnings.append({
                "level": "warning",
                "message": f"整体一致性差 ({consistency_score:.2f} < 0.7)",
            })
        
        return {
            "status": "completed",
            "data": {
                "domain_metrics": domain_metrics,
                "age_group_metrics": age_group_metrics,
                "avg_f1": avg_f1,
                "underperforming_domains": underperforming_domains,
                "consistency_score": consistency_score,
                "warnings": warnings,
            },
        }
    
    def _calc_consistency_score(self, domain_metrics: dict, age_group_metrics: dict) -> float:
        """计算一致性评分（基于组间方差占比，值域 [0, 1]）"""
        all_metrics = list(domain_metrics.values()) + list(age_group_metrics.values())
        if len(all_metrics) < 2:
            return 1.0
        
        mean = np.mean(all_metrics)
        if mean == 0:
            return 0
        
        std = np.std(all_metrics)
        cv = std / mean
        
        # 使用指数衰减映射，CV 越大一致性越差，但不会直接归零
        import math
        return math.exp(-cv * 2)
```

## 测试方案

```python
@pytest.mark.asyncio
async def test_underperforming_domain():
    """某领域 F1 低于平均时警告"""
    ...

@pytest.mark.asyncio
async def test_consistency_score():
    """一致性评分计算正确"""
    ...
```

## 注意事项

- 一致性评分使用 `exp(-cv * 2)` 指数衰减映射，避免 CV > 1 时直接归零
- 分组基于领域和年龄组
