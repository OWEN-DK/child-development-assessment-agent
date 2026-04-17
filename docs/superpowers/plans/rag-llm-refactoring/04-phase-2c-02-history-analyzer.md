# Phase 2C.2: 历史对比分析

> **前置文档:** [Overview](./04-phase-2c-00-overview.md)
> **状态:** ⏳ 完全待实现
> **预计工期:** 1 人天

## 目标

实现历史对比分析模块，从历史 TestRun 中提取参数变更与指标变化的关联关系，展示"上次改了什么、效果如何"。

---

### Task 2C.2.1: 数据关联链路实现

**Files:**
- Create: `src/core/tuning/history_analyzer.py`
- Test: `tests/unit/tuning/test_history_analyzer.py`

- [ ] **Step 1: 扩展 Pydantic 模型**

```python
# src/model/tuning.py (追加)
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel

class HistoryReference(BaseModel):
    """历史参考"""
    run_id: str                        # 历史运行ID
    date: str                          # 运行日期
    changed_params: Dict[str, Dict[str, Any]]  # 变更参数 {"参数名": {"from": 旧值, "to": 新值}}
    metric_changes: Dict[str, Dict[str, Any]]  # 指标变化 {"指标名": {"from": 旧值, "to": 新值, "delta": "+0.16"}}
    conclusion: str                    # 结论总结
```

- [ ] **Step 2: 编写测试用例**

```python
async def test_diff_configs_extracts_changed_params():
    """配置快照对比应正确提取变更参数"""
    from src.core.tuning.history_analyzer import HistoryAnalyzer
    
    old_snapshot = {"rag_hybrid_bm25_top_k": 10, "rag_reranker_final_k": 5}
    new_snapshot = {"rag_hybrid_bm25_top_k": 15, "rag_reranker_final_k": 5}
    
    analyzer = HistoryAnalyzer(None, None)  # 此测试不需要 mock
    diff = analyzer._diff_configs(old_snapshot, new_snapshot)
    
    assert "rag_hybrid_bm25_top_k" in diff
    assert diff["rag_hybrid_bm25_top_k"]["from"] == 10
    assert diff["rag_hybrid_bm25_top_k"]["to"] == 15
    assert "rag_reranker_final_k" not in diff  # 未变更

async def test_analyze_returns_empty_when_less_than_2_history_runs(mock_test_run_repo):
    """历史运行 < 2 次时应返回空列表"""
    from src.core.tuning.history_analyzer import HistoryAnalyzer
    
    # Mock 仅 1 次历史运行
    mock_run = MagicMock(id="run_1")
    mock_test_run_repo.get_completed_runs = AsyncMock(return_value=[mock_run])
    
    analyzer = HistoryAnalyzer(mock_test_run_repo, None)
    references = await analyzer.analyze(
        current_metrics={"overall_recall": 0.65},
        current_run_id="current_run",
    )
    
    assert len(references) == 0

async def test_analyze_extracts_metric_changes_between_runs(mock_test_run_repo, mock_config_manager):
    """应正确提取两次历史运行之间的指标变化（参数变更前 vs 变更后）"""
    from src.core.tuning.history_analyzer import HistoryAnalyzer
    
    # Mock 2 次历史运行，run_1 使用新配置，run_2 使用旧配置
    mock_run_1 = MagicMock(
        id="run_1", config_version_id="v2", previous_config_version_id="v1",
        overall_recall=0.78, overall_precision=0.81,
        created_at=MagicMock(strftime=MagicMock(return_value="2026-04-10")),
    )
    mock_run_2 = MagicMock(
        id="run_2", config_version_id="v1", previous_config_version_id=None,
        overall_recall=0.62, overall_precision=0.85,
        created_at=MagicMock(strftime=MagicMock(return_value="2026-04-05")),
    )
    mock_test_run_repo.get_completed_runs = AsyncMock(return_value=[mock_run_1, mock_run_2])
    mock_config_manager.get_version_config = AsyncMock(side_effect=lambda vid: {
        "v1": {"rag_hybrid_bm25_top_k": 10},
        "v2": {"rag_hybrid_bm25_top_k": 15},
    }.get(vid))
    
    analyzer = HistoryAnalyzer(mock_test_run_repo, mock_config_manager)
    references = await analyzer.analyze(
        current_metrics={"overall_recall": 0.65},
        current_run_id="current_run",
    )
    
    assert len(references) > 0
    # 验证对比的是 run_2 → run_1 的指标变化
    assert "overall_recall" in references[0].metric_changes
    assert references[0].metric_changes["overall_recall"]["from"] == 0.62
    assert references[0].metric_changes["overall_recall"]["to"] == 0.78
```

- [ ] **Step 3: 运行测试验证失败**
Run: `pytest tests/unit/tuning/test_history_analyzer.py -v`
Expected: FAIL - 模块不存在

- [ ] **Step 4: 实现历史分析器**

```python
# src/core/tuning/history_analyzer.py
"""历史对比分析：从历史运行中提取参数变更效果"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from src.model.tuning import HistoryReference
from src.utils.logger import logger


class HistoryAnalyzer:
    """历史对比分析：参数变更效果追踪"""
    
    # 关注的指标列表
    METRICS_OF_INTEREST = [
        "overall_precision", "overall_recall", "overall_f1",
        "overall_mrr", "overall_ndcg",
    ]
    
    def __init__(self, test_run_repo=None, config_mgr=None):
        """初始化历史分析器"""
        self.test_run_repo = test_run_repo
        self.config_mgr = config_mgr
    
    async def analyze(
        self,
        current_metrics: Dict[str, float],
        current_run_id: str,
    ) -> List[HistoryReference]:
        """分析历史运行，返回参考建议"""
        # 获取所有已完成的历史运行 (排除当前)，按时间倒序
        history_runs = await self.test_run_repo.get_completed_runs(
            exclude_run_id=current_run_id,
            limit=20,  # 仅分析最近 20 次
            order_by="created_at DESC",
        )
        
        if len(history_runs) < 2:
            logger.info("历史运行不足 2 次，跳过历史对比分析")
            return []
        
        # 构建相邻运行对的参数变更→指标变化映射
        # 核心逻辑：对比 run[i] 和 run[i+1] 的配置快照差异，以及对应的指标变化
        references = []
        for i in range(len(history_runs) - 1):
            current_run = history_runs[i]
            previous_run = history_runs[i + 1]  # 时间上更早的一次运行
            
            ref = await self._build_reference(current_run, previous_run)
            if ref:
                references.append(ref)
        
        # 额外补充：最近一次历史运行与当前运行的对比（用于展示当前短板与历史的差异）
        if history_runs:
            latest_ref = await self._build_reference(
                history_runs[0],
                None,  # 无前置运行，仅展示当前运行的配置快照
                current_metrics=current_metrics,
            )
            if latest_ref:
                references.insert(0, latest_ref)
        
        logger.info(f"历史对比分析完成: 找到 {len(references)} 条历史参考")
        return references
    
    async def _build_reference(
        self,
        run: Any,
        previous_run: Optional[Any],
        current_metrics: Optional[Dict[str, float]] = None,
    ) -> Optional[HistoryReference]:
        """构建单条历史参考
        
        Args:
            run: 当前运行记录
            previous_run: 前一次运行记录（用于对比参数变更→指标变化效果）
            current_metrics: 可选，当前运行的指标（仅在不提供 previous_run 时使用）
        """
        # 获取配置快照
        new_snapshot = await self._get_config_snapshot(run.config_version_id)
        if not new_snapshot:
            return None
        
        if previous_run:
            # 有前置运行：对比两次运行之间的配置变更和指标变化
            old_snapshot = await self._get_config_snapshot(previous_run.config_version_id)
            if not old_snapshot:
                return None
            
            changed_params = self._diff_configs(old_snapshot, new_snapshot)
            if not changed_params:
                return None  # 无参数变更，跳过
            
            # 对比指标变化：previous_run 的指标 → run 的指标
            metric_changes = self._diff_metrics_between_runs(previous_run, run)
        else:
            # 无前置运行：仅展示当前运行与当前指标的对比（无参数变更，仅指标对比）
            if not current_metrics:
                return None
            changed_params = {}
            metric_changes = self._diff_metrics_against_current(run, current_metrics)
        
        # 生成结论
        conclusion = self._generate_conclusion(changed_params, metric_changes, has_config_change=(previous_run is not None))
        
        return HistoryReference(
            run_id=run.id,
            date=run.created_at.strftime("%Y-%m-%d") if run.created_at else "未知",
            changed_params=changed_params,
            metric_changes=metric_changes,
            conclusion=conclusion,
        )
    
    def _diff_configs(self, old_snapshot: Dict, new_snapshot: Dict) -> Dict[str, Dict[str, Any]]:
        """对比两个配置快照，提取变更参数"""
        changed = {}
        all_keys = set(list(old_snapshot.keys()) + list(new_snapshot.keys()))
        
        for key in all_keys:
            old_val = old_snapshot.get(key)
            new_val = new_snapshot.get(key)
            
            if old_val != new_val:
                changed[key] = {"from": old_val, "to": new_val}
        
        return changed
    
    def _diff_metrics_between_runs(self, old_run: Any, new_run: Any) -> Dict[str, Dict[str, Any]]:
        """对比两次运行之间的指标变化（参数变更前 vs 变更后）"""
        changes = {}
        
        for metric in self.METRICS_OF_INTEREST:
            old_val = getattr(old_run, metric, None)
            new_val = getattr(new_run, metric, None)
            
            if old_val is not None and new_val is not None:
                delta = new_val - old_val
                changes[metric] = {
                    "from": round(old_val, 4),
                    "to": round(new_val, 4),
                    "delta": f"{delta:+.4f}",
                }
        
        return changes
    
    def _diff_metrics_against_current(self, run: Any, current_metrics: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
        """对比历史运行与当前运行的指标差异（用于展示当前短板与历史的差异）"""
        changes = {}
        
        for metric in self.METRICS_OF_INTEREST:
            old_val = getattr(run, metric, None)
            new_val = current_metrics.get(metric)
            
            if old_val is not None and new_val is not None:
                delta = new_val - old_val
                changes[metric] = {
                    "from": round(old_val, 4),
                    "to": round(new_val, 4),
                    "delta": f"{delta:+.4f}",
                }
        
        return changes
    
    async def _get_config_snapshot(self, version_id: str) -> Optional[Dict]:
        """获取配置版本快照"""
        if not version_id:
            return None
        full_config = await self.config_mgr.get_version_config(version_id)
        return full_config
    
    def _generate_conclusion(
        self,
        changed_params: Dict[str, Dict[str, Any]],
        metric_changes: Dict[str, Dict[str, Any]],
        has_config_change: bool = True,
    ) -> str:
        """生成结论总结
        
        Args:
            changed_params: 变更的参数
            metric_changes: 指标变化
            has_config_change: 是否有配置变更（False 表示仅指标对比）
        """
        if not has_config_change:
            # 无配置变更，仅展示指标对比
            parts = []
            for metric, delta in metric_changes.items():
                parts.append(f"{metric}: {delta['from']} → {delta['to']} ({delta['delta']})")
            return "；".join(parts) if parts else "指标数据无显著变化"
        
        # 有配置变更，展示参数变更→指标变化的因果关系
        parts = []
        for param, change in changed_params.items():
            param_short = param.split("_")[-1]  # 简化参数名
            for metric, delta in metric_changes.items():
                parts.append(
                    f"修改 {param_short} 从 {change['from']} 到 {change['to']} 后，"
                    f"{metric} 变化了 {delta['delta']}"
                )
        
        return "；".join(parts) if parts else "参数有变更，但指标变化不明显"
```

- [ ] **Step 5: 运行测试验证通过**
Run: `pytest tests/unit/tuning/test_history_analyzer.py -v`
Expected: PASS

---

### Task 2C.2.2: 相似问题匹配

**Files:**
- Modify: `src/core/tuning/history_analyzer.py`
- Test: `tests/unit/tuning/test_history_analyzer.py`

- [ ] **Step 1: 编写测试用例**

```python
async def test_find_similar_runs_matches_recall_issue():
    """召回率不足的历史运行应被匹配"""
    from src.core.tuning.history_analyzer import HistoryAnalyzer
    
    current_metrics = {"overall_recall": 0.60, "overall_precision": 0.85}
    history_runs = [
        MagicMock(overall_recall=0.62, overall_precision=0.83, overall_mrr=0.7, overall_ndcg=0.8),  # 相似
        MagicMock(overall_recall=0.90, overall_precision=0.60, overall_mrr=0.7, overall_ndcg=0.8),  # 不相似
    ]
    
    analyzer = HistoryAnalyzer(None, None)
    similar = analyzer._find_similar_runs(current_metrics, history_runs)
    
    assert len(similar) == 1
    assert similar[0].overall_recall < 0.7
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/unit/tuning/test_history_analyzer.py::test_find_similar_runs_matches_recall_issue -v`
Expected: FAIL - 方法未实现

- [ ] **Step 3: 实现相似匹配**

```python
# src/core/tuning/history_analyzer.py (追加方法)

# 指标短板阈值
WEAKNESS_THRESHOLDS = {
    "overall_recall": 0.7,
    "overall_precision": 0.75,
    "overall_mrr": 0.65,
    "overall_ndcg": 0.75,
}

def _find_similar_runs(
    self,
    current_metrics: Dict[str, float],
    history_runs: List[Any],
) -> List[Any]:
    """查找指标短板相似的历史运行"""
    # 计算当前短板向量
    current_weakness = self._compute_weakness_vector(current_metrics)
    
    similar_runs = []
    for run in history_runs:
        run_metrics = {
            "overall_recall": getattr(run, "overall_recall", 0),
            "overall_precision": getattr(run, "overall_precision", 0),
            "overall_mrr": getattr(run, "overall_mrr", 0),
            "overall_ndcg": getattr(run, "overall_ndcg", 0),
        }
        run_weakness = self._compute_weakness_vector(run_metrics)
        
        # 计算 Jaccard 相似度
        similarity = self._jaccard_similarity(current_weakness, run_weakness)
        
        if similarity >= 0.5:
            similar_runs.append(run)
    
    return similar_runs

def _compute_weakness_vector(self, metrics: Dict[str, float]) -> set:
    """计算指标短板向量 (返回不达标的指标名集合)"""
    weaknesses = set()
    for metric, threshold in self.WEAKNESS_THRESHOLDS.items():
        value = metrics.get(metric, 1.0)
        if value < threshold:
            weaknesses.add(metric)
    return weaknesses

def _jaccard_similarity(self, set_a: set, set_b: set) -> float:
    """计算 Jaccard 相似度"""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/unit/tuning/test_history_analyzer.py -v`
Expected: PASS

---

**上一阶段:** [规则引擎](./04-phase-2c-01-rule-engine.md)  
**下一阶段:** [LLM 诊断](./04-phase-2c-03-llm-diagnoser.md)
