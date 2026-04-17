# 03 - Layer 2: 历史对比 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 03 - Layer 2: 历史对比

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/core/validation/layers/layer2_history.py`
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

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `5.2 Layer 2: 历史对比` 节
> **所属 Phase**: Phase 4

## 需求定义

从历史运行中匹配相似问题，展示"上次改了什么、效果如何"。2 条规则：配置变更关联 + 相似问题匹配。

## 验收标准

- [ ] 无历史运行时展示基准报告
- [ ] 配置变更→指标变化关联正确
- [ ] 相似问题匹配按失败类型分组
- [ ] 执行延迟 < 100ms

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/validation/layers/layer2_history.py` | 新增 | Layer 2 历史对比实现 |

## 实现方案

### 后端实现

```python
# backend/src/core/validation/layers/layer2_history.py
import logging
from typing import Any

from sqlalchemy import select
from src.models.test_run import TestRun
from src.models.tuning_suggestion_record import TuningSuggestionRecord

logger = logging.getLogger(__name__)

class Layer2HistoryComparison:
    """Layer 2: 历史对比"""
    
    def __init__(self, db, test_run):
        self.db = db
        self.test_run = test_run
    
    async def execute(self) -> dict:
        """执行历史对比"""
        history_runs = await self._get_history_runs()
        
        if not history_runs:
            return {
                "status": "baseline",
                "data": {
                    "message": "运行更多次后可获得历史对比分析",
                    "current_metrics": self.test_run.metrics,
                },
            }
        
        history_refs = []
        
        # 规则 1: 配置变更→指标变化关联
        config_changes = await self._extract_config_changes(history_runs)
        history_refs.append({
            "type": "config_change_correlation",
            "changes": config_changes,
        })
        
        # 规则 2: 相似问题匹配
        bad_cases = self.test_run.bad_cases or []
        similar_matches = await self._match_similar_issues(bad_cases, history_runs)
        history_refs.append({
            "type": "similar_issue_matching",
            "matches": similar_matches,
        })
        
        return {"history_references": history_refs, "total_history_runs": len(history_runs)}
    
    async def _get_history_runs(self) -> list[TestRun]:
        """获取同一 test_set_id 的历史运行"""
        stmt = (
            select(TestRun)
            .where(TestRun.test_set_id == self.test_run.test_set_id)
            .where(TestRun.id != self.test_run.id)
            .where(TestRun.status == "completed")
            .order_by(TestRun.created_at.desc())
            .limit(10)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def _extract_config_changes(self, history_runs: list[TestRun]) -> list:
        """提取配置变更与指标变化"""
        changes = []
        current_config = self.test_run.config_snapshot or {}
        
        for prev_run in history_runs:
            prev_config = prev_run.config_snapshot or {}
            diff = self._json_diff(prev_config, current_config)
            
            if diff:
                metric_delta = self._calc_metric_delta(prev_run.metrics, self.test_run.metrics)
                changes.append({
                    "previous_run_id": prev_run.id,
                    "config_changes": diff,
                    "metric_changes": metric_delta,
                    "created_at": prev_run.created_at.isoformat(),
                })
        
        return changes
    
    def _json_diff(self, old: dict, new: dict, prefix: str = "") -> list:
        """深度对比 JSON 对象，仅输出值发生变化的键值对"""
        changes = []
        all_keys = set(old.keys()) | set(new.keys())
        for key in all_keys:
            full_key = f"{prefix}.{key}" if prefix else key
            old_val = old.get(key)
            new_val = new.get(key)
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                changes.extend(self._json_diff(old_val, new_val, prefix=full_key))
            elif old_val != new_val:
                changes.append({
                    "key": full_key,
                    "old_value": old_val,
                    "new_value": new_val,
                })
        return changes
    
    def _calc_metric_delta(self, old_metrics: dict, new_metrics: dict) -> dict:
        """计算指标变化"""
        deltas = {}
        for key in new_metrics:
            if key in old_metrics:
                deltas[key] = new_metrics[key] - old_metrics[key]
        return deltas
    
    async def _match_similar_issues(self, bad_cases: list, history_runs: list[TestRun]) -> list:
        """基于失败模式标签匹配相似问题"""
        matches = []
        failure_types = [bc.get("failure_type") for bc in bad_cases if bc.get("failure_type")]
        
        for ft in set(failure_types):
            stmt = (
                select(TuningSuggestionRecord)
                .where(TuningSuggestionRecord.source.in_(["rule_engine", "history", "llm"]))
                .where(TuningSuggestionRecord.failure_type == ft)
                .where(TuningSuggestionRecord.test_set_id == self.test_run.test_set_id)
                .limit(5)
            )
            result = await self.db.execute(stmt)
            records = result.scalars().all()
            
            if records:
                matches.append({
                    "failure_type": ft,
                    "resolved_count": len(records),
                    "suggestions": [
                        {
                            "id": r.id,
                            "suggestion": r.suggestion,
                            "source": r.source,
                        }
                        for r in records[:3]
                    ],
                })
        
        return matches
```

## 测试方案

```python
@pytest.mark.asyncio
async def test_no_history_baseline():
    """无历史运行时返回基准报告"""
    ...

@pytest.mark.asyncio
async def test_config_change_correlation():
    """配置变更关联正确"""
    ...

@pytest.mark.asyncio
async def test_similar_issue_matching():
    """相似问题匹配按失败类型分组"""
    ...
```

## 注意事项

- 仅展示变更项和对应指标变化，不做因果推断
- 历史运行限制 10 条，避免查询过慢
