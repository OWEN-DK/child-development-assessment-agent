# 02 - Layer 1: 规则引擎 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 02 - Layer 1: 规则引擎

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/core/validation/layers/layer1_rule_engine.py`
- Test: `backend/tests/test_layer1_rule_engine.py`

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

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `5.1 Layer 1: 规则引擎` 节
> **所属 Phase**: Phase 4

## 需求定义

根据指标短板快速定位问题方向，给出初步参数建议。8 条规则，自适应步长 + 冲突检测。

## 验收标准

- [ ] 8 条规则全部实现（P@5/R@5/F1/MRR/短查询/跨领域/PageIndex/参数安全范围）
- [ ] 自适应步长计算正确
- [ ] 冲突检测与合并正确
- [ ] 参数超出安全范围时修正到边界值
- [ ] 执行延迟 < 50ms

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/validation/layers/layer1_rule_engine.py` | 新增 | Layer 1 规则引擎实现 |

## 实现方案

### 后端实现

```python
# backend/src/core/validation/layers/layer1_rule_engine.py
import logging
from typing import Any

from src.core.config import get_config_value  # 从配置中心读取（禁止硬编码）

logger = logging.getLogger(__name__)

# 参数安全范围默认值（仅作为配置缺失时的降级 fallback，优先从配置中心读取）
_DEFAULT_PARAM_SAFE_RANGES = {
    "bm25_top_k": {"min": 5, "max": 50, "recommended": [10, 20], "step": 5},
    "vector_top_k": {"min": 5, "max": 50, "recommended": [10, 20], "step": 5},
    "fusion_threshold": {"min": 0.1, "max": 0.5, "recommended": [0.2, 0.3], "step": 0.05},
    "reranker_initial_k": {"min": 10, "max": 100, "recommended": [20, 50], "step": 10},
    "reranker_final_k": {"min": 1, "max": 20, "recommended": [3, 10], "step": 2},
    "age_filter_strictness": {"min": 0.0, "max": 1.0, "recommended": [0.3, 0.7], "step": 0.1},
    "chunk_size": {"min": 256, "max": 2048, "recommended": [512, 1024], "step": 128},
}

_DEFAULT_THRESHOLDS = {
    "p_at_5": 0.70,
    "r_at_5": 0.85,
    "f1": 0.75,
    "mrr": 0.70,
    "short_query_failure_rate": 0.30,
    "cross_domain_failure_rate": 0.20,
}


async def _get_layer1_config() -> dict:
    """从配置中心读取 Layer 1 规则引擎配置（禁止硬编码）"""
    return {
        "thresholds": {
            "p_at_5": await get_config_value("rag_validation_threshold_p_at_5", _DEFAULT_THRESHOLDS["p_at_5"]),
            "r_at_5": await get_config_value("rag_validation_threshold_r_at_5", _DEFAULT_THRESHOLDS["r_at_5"]),
            "f1": await get_config_value("rag_validation_threshold_f1", _DEFAULT_THRESHOLDS["f1"]),
            "mrr": await get_config_value("rag_validation_threshold_mrr", _DEFAULT_THRESHOLDS["mrr"]),
            "short_query_failure_rate": await get_config_value(
                "rag_validation_threshold_short_query_failure_rate",
                _DEFAULT_THRESHOLDS["short_query_failure_rate"],
            ),
            "cross_domain_failure_rate": await get_config_value(
                "rag_validation_threshold_cross_domain_failure_rate",
                _DEFAULT_THRESHOLDS["cross_domain_failure_rate"],
            ),
        },
        "param_safe_ranges": {},  # 安全范围从配置中心按 key 读取，降级使用 _DEFAULT_PARAM_SAFE_RANGES
    }


class Layer1RuleEngine:
    """Layer 1: 规则引擎"""

    def __init__(self, session_factory, test_run):
        self.session_factory = session_factory
        self.test_run = test_run
        self.thresholds = {}
        self.safe_ranges = _DEFAULT_PARAM_SAFE_RANGES

    async def execute(self) -> dict:
        """执行规则引擎"""
        config = await _get_layer1_config()
        self.thresholds = config["thresholds"]
        self.safe_ranges = config.get("param_safe_ranges") or _DEFAULT_PARAM_SAFE_RANGES

        async with self.session_factory() as session:
            metrics = await self._get_metrics(session)
            rag_config = await self._get_rag_config(session)

        suggestions = []

        # 规则 1-4: 指标阈值
        suggestions.extend(self._check_metric_rules(metrics, rag_config))

        # 规则 5: 短查询失败率
        if metrics.get("short_query_failure_rate", 0) > self.thresholds["short_query_failure_rate"]:
            if not rag_config.get("query_rewrite_enabled", False):
                suggestions.append({
                    "param": "query_rewrite_enabled",
                    "current": False,
                    "suggested": True,
                    "reason": f"短查询失败率超过 {self.thresholds['short_query_failure_rate']:.0%}，建议开启查询重写",
                    "priority": "function_switch",
                })

        # 规则 6: 跨领域失败率
        if metrics.get("cross_domain_failure_rate", 0) > self.thresholds["cross_domain_failure_rate"]:
            if not rag_config.get("synonym_expansion_enabled", False):
                suggestions.append({
                    "param": "synonym_expansion_enabled",
                    "current": False,
                    "suggested": True,
                    "reason": f"跨领域失败率超过 {self.thresholds['cross_domain_failure_rate']:.0%}，建议开启同义词扩展",
                    "priority": "function_switch",
                })

        # 规则 7: PageIndex 未启用
        if not rag_config.get("pageindex_enabled", False):
            suggestions.append({
                "param": "pageindex_enabled",
                "current": False,
                "suggested": True,
                "reason": "PageIndex 未启用，建议开启以提升检索精度",
                "priority": "function_switch",
            })

        # 规则 8: 参数超出安全范围
        suggestions.extend(self._check_safe_ranges(rag_config))

        # 冲突检测与合并
        suggestions = self._detect_conflicts(suggestions)
        
        # 排序：安全范围修正 > 功能开关 > 参数调优
        priority_order = {"safe_range": 0, "function_switch": 1, "param_tuning": 2}
        suggestions.sort(key=lambda s: priority_order.get(s["priority"], 3))
        
        return {"suggestions": suggestions, "rules_triggered": len(suggestions)}
    
    def _check_metric_rules(self, metrics: dict, config: dict) -> list:
        """检查指标相关规则"""
        suggestions = []
        
        p_at_5 = metrics.get("p_at_5", 1.0)
        r_at_5 = metrics.get("r_at_5", 1.0)
        f1 = metrics.get("f1", 1.0)
        mrr = metrics.get("mrr", 1.0)
        
        # P@5 不达标
        if p_at_5 < self.thresholds["p_at_5"]:
            if r_at_5 >= 0.95:
                pass  # 已饱和，不推荐
            else:
                suggestions.append(self._suggest_param_increase("bm25_top_k", config, "P@5 不达标"))
                suggestions.append(self._suggest_param_increase("vector_top_k", config, "P@5 不达标"))
        
        # R@5 不达标
        if r_at_5 < self.thresholds["r_at_5"]:
            if p_at_5 >= 0.85:
                suggestions.append(self._suggest_param_increase("vector_top_k", config, "R@5 不达标，优先增加 vector_top_k"))
            else:
                suggestions.append(self._suggest_param_increase("bm25_top_k", config, "R@5 不达标"))
        
        # F1 不达标
        if f1 < self.thresholds["f1"]:
            current_ft = config.get("fusion_threshold", 0.25)
            delta = -0.05 if p_at_5 < r_at_5 else 0.05
            suggested = self._clamp_param("fusion_threshold", current_ft + delta)
            suggestions.append({
                "param": "fusion_threshold",
                "current": current_ft,
                "suggested": suggested,
                "reason": f"F1 不达标 ({f1:.2f} < {self.thresholds['f1']})",
                "priority": "param_tuning",
            })
        
        # MRR 不达标
        if mrr < self.thresholds["mrr"]:
            suggestions.append(self._suggest_param_increase("reranker_initial_k", config, "MRR 不达标"))
        
        return suggestions
    
    def _suggest_param_increase(self, param: str, config: dict, reason: str) -> dict:
        """建议增加参数值"""
        safe_range = self.safe_ranges.get(param, {})
        current = config.get(param, safe_range.get("recommended", [10])[0])
        step = self._calc_adaptive_step(param, current)
        suggested = self._clamp_param(param, current + step)
        return {
            "param": param,
            "current": current,
            "suggested": suggested,
            "reason": reason,
            "priority": "param_tuning",
        }
    
    def _calc_adaptive_step(self, param: str, current: float) -> float:
        """自适应步长 = max(1, min(5, int(当前值 × 0.3)))"""
        step = max(1, min(5, int(current * 0.3)))
        return step
    
    def _clamp_param(self, param: str, value: float) -> float:
        """限制参数在安全范围内"""
        safe_range = _DEFAULT_PARAM_SAFE_RANGES.get(param, {})
        if not safe_range:
            return value
        return max(safe_range["min"], min(safe_range["max"], value))
    
    def _check_safe_ranges(self, config: dict) -> list:
        """检查参数是否超出安全范围"""
        suggestions = []
        for param, safe_range in self.safe_ranges.items():
            current = config.get(param)
            if current is not None:
                if current < safe_range["min"] or current > safe_range["max"]:
                    corrected = self._clamp_param(param, current)
                    suggestions.append({
                        "param": param,
                        "current": current,
                        "suggested": corrected,
                        "reason": f"参数超出安全范围 [{safe_range['min']}, {safe_range['max']}]",
                        "priority": "safe_range",
                    })
        return suggestions
    
    async def _get_metrics(self, session) -> dict:
        """从 TestRunResult 聚合获取指标数据
        
        数据来源：
        - P@5/R@5/F1/MRR/NDCG：从 TestRun 表的汇总字段读取
        - short_query_failure_rate：查询长度 < 5 字符的用例失败率
        - cross_domain_failure_rate：跨领域查询的失败率
        
        参数:
            session: SQLAlchemy 异步会话
            
        返回:
            指标字典
        """
        from src.models.rag_eval.test_run import RagEvalTestRun
        from sqlalchemy import select
        
        result = await session.execute(
            select(RagEvalTestRun).where(RagEvalTestRun.id == self.test_run.id)
        )
        run = result.scalar_one_or_none()
        
        if not run:
            return {}
        
        # 从 TestRun 汇总字段读取基础指标
        metrics = {
            "p_at_5": run.overall_precision or 1.0,
            "r_at_5": run.overall_recall or 1.0,
            "f1": run.overall_f1 or 1.0,
            "mrr": run.overall_mrr or 1.0,
            "ndcg": run.overall_ndcg or 1.0,
            "short_query_failure_rate": 0.0,  # 默认值，后续可从 TestRunResult 详细计算
            "cross_domain_failure_rate": 0.0,  # 默认值，后续可从 TestRunResult 详细计算
        }
        
        return metrics
    
    async def _get_rag_config(self, session) -> dict:
        """从 ConfigVersion 获取当前配置快照
        
        数据来源：
        - 从 TestRun.config_version_id 关联 ConfigVersion
        - 读取 config_snapshot JSON 字段
        
        参数:
            session: SQLAlchemy 异步会话
            
        返回:
            配置字典
        """
        from src.models.rag_eval.config_version import RagEvalConfigVersion
        from sqlalchemy import select
        
        if not self.test_run.config_version_id:
            return {}
        
        result = await session.execute(
            select(RagEvalConfigVersion).where(
                RagEvalConfigVersion.id == self.test_run.config_version_id
            )
        )
        config_version = result.scalar_one_or_none()
        
        if not config_version:
            return {}
        
        return config_version.config_snapshot or {}
    
    def _detect_conflicts(self, suggestions: list) -> list:
        """冲突检测与合并"""
        param_suggestions = {}
        for s in suggestions:
            param = s["param"]
            if param in param_suggestions:
                existing = param_suggestions[param]
                if existing["suggested"] != s["suggested"]:
                    existing["conflict"] = True
                    existing["conflict_warning"] = (
                        f"参数冲突: {existing['reason']} 建议 {existing['suggested']}，"
                        f"{s['reason']} 建议 {s['suggested']}，交由用户决策"
                    )
                else:
                    existing["suggested"] = max(existing["suggested"], s["suggested"])
            else:
                param_suggestions[param] = s
        return list(param_suggestions.values())
```

## 测试方案

```python
# backend/tests/test_layer1_rule_engine.py
import pytest
from unittest.mock import MagicMock
from src.core.validation.layers.layer1_rule_engine import Layer1RuleEngine


@pytest.mark.asyncio
async def test_p5_below_threshold():
    """P@5 不达标时建议增加 top_k"""
    test_run = MagicMock()
    test_run.metrics = {"p_at_5": 0.60, "r_at_5": 0.80, "f1": 0.70, "mrr": 0.65}
    test_run.config_snapshot = {"bm25_top_k": 10, "vector_top_k": 10}

    engine = Layer1RuleEngine(db=MagicMock(), test_run=test_run)
    result = await engine.execute()

    suggestions = result["suggestions"]
    param_suggestions = [s for s in suggestions if s["param"] in ("bm25_top_k", "vector_top_k")]
    assert len(param_suggestions) > 0, "P@5 不达标时应建议增加 top_k"


@pytest.mark.asyncio
async def test_adaptive_step():
    """自适应步长计算正确"""
    engine = Layer1RuleEngine(db=MagicMock(), test_run=MagicMock())

    # current=10, step=max(1, min(5, int(10*0.3)))=3
    assert engine._calc_adaptive_step("bm25_top_k", 10) == 3
    # current=20, step=max(1, min(5, int(20*0.3)))=5
    assert engine._calc_adaptive_step("bm25_top_k", 20) == 5
    # current=2, step=max(1, min(5, int(2*0.3)))=1
    assert engine._calc_adaptive_step("bm25_top_k", 2) == 1


@pytest.mark.asyncio
async def test_conflict_detection():
    """冲突检测正确"""
    engine = Layer1RuleEngine(db=MagicMock(), test_run=MagicMock())
    suggestions = [
        {"param": "bm25_top_k", "current": 10, "suggested": 15, "reason": "P@5 不达标", "priority": "param_tuning"},
        {"param": "bm25_top_k", "current": 10, "suggested": 20, "reason": "R@5 不达标", "priority": "param_tuning"},
    ]
    result = engine._detect_conflicts(suggestions)
    assert len(result) == 1
    assert result[0]["suggested"] == 20  # 取较大值


@pytest.mark.asyncio
async def test_conflict_opposite_direction():
    """相反方向冲突标记 conflict=True"""
    engine = Layer1RuleEngine(db=MagicMock(), test_run=MagicMock())
    suggestions = [
        {"param": "fusion_threshold", "current": 0.25, "suggested": 0.30, "reason": "F1 偏低", "priority": "param_tuning"},
        {"param": "fusion_threshold", "current": 0.25, "suggested": 0.20, "reason": "F1 偏高", "priority": "param_tuning"},
    ]
    result = engine._detect_conflicts(suggestions)
    assert len(result) == 1
    assert result[0].get("conflict") is True
    assert "conflict_warning" in result[0]


@pytest.mark.asyncio
async def test_safe_range_clamp():
    """参数超出安全范围时修正到边界值"""
    test_run = MagicMock()
    test_run.metrics = {}
    test_run.config_snapshot = {"bm25_top_k": 100, "fusion_threshold": 0.01}

    engine = Layer1RuleEngine(db=MagicMock(), test_run=test_run)
    result = await engine.execute()

    safe_range_suggestions = [s for s in result["suggestions"] if s["priority"] == "safe_range"]
    assert len(safe_range_suggestions) == 2
    assert safe_range_suggestions[0]["suggested"] == 50  # bm25_top_k 上限
    assert safe_range_suggestions[1]["suggested"] == 0.1  # fusion_threshold 下限


@pytest.mark.asyncio
async def test_priority_ordering():
    """建议排序：安全范围 > 功能开关 > 参数调优"""
    test_run = MagicMock()
    test_run.metrics = {}
    test_run.config_snapshot = {"bm25_top_k": 100, "pageindex_enabled": False}

    engine = Layer1RuleEngine(db=MagicMock(), test_run=test_run)
    result = await engine.execute()

    priorities = [s["priority"] for s in result["suggestions"]]
    assert priorities == sorted(priorities, key=lambda p: {"safe_range": 0, "function_switch": 1, "param_tuning": 2}.get(p, 3))
```

## 注意事项

- 执行延迟 < 50ms，纯内存计算
- 冲突检测只合并同参数，不自动解决相反方向冲突
