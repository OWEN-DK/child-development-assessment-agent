# Phase 2C.4: 统一引擎 + API 实现

> **前置文档:** [Overview](./04-phase-2c-00-overview.md)
> **状态:** ⏳ 完全待实现
> **预计工期:** 1 人天

## 目标

实现统一引擎入口 `TuningSuggestionEngine`，协调三层诊断组件，并暴露 3 个 API 接口供前端调用。

---

### Task 2C.4.1: 统一引擎入口

**Files:**
- Create: `src/core/tuning/engine.py`
- Test: `tests/unit/tuning/test_engine.py`

- [ ] **Step 1: 扩展 Pydantic 模型**

```python
# src/model/tuning.py (追加)
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class TuningSuggestionResponse(BaseModel):
    """调参建议完整响应"""
    run_id: str                        # 测试运行ID
    generated_at: str                  # 生成时间
    rule_engine_suggestions: List["TuningSuggestion"]  # 规则引擎建议
    history_references: List["HistoryReference"]     # 历史参考
    llm_diagnosis: Optional["LLMDiagnosis"] = None   # LLM诊断（可选）
    conflict_filtered_count: int = 0   # 已过滤的冲突建议数
    total_suggestions: int             # 最终建议总数
```

- [ ] **Step 2: 编写测试用例**

```python
async def test_generate_suggestions_merges_three_layers(mock_test_run_repo):
    """引擎应合并三层诊断结果"""
    from src.core.tuning.engine import TuningSuggestionEngine
    from unittest.mock import AsyncMock, MagicMock
    from src.model.tuning import TuningSuggestion, HistoryReference, LLMDiagnosis
    
    # Mock 三层组件
    mock_rule_engine = AsyncMock()
    mock_rule_engine.evaluate = AsyncMock(return_value=[
        TuningSuggestion(id="rule_1", param_name="p1", current_value=1, suggested_value=2, action="increase", reason="", expected_effect="", priority="high", source="rule_engine"),
        TuningSuggestion(id="rule_2", param_name="p2", current_value=1, suggested_value=2, action="increase", reason="", expected_effect="", priority="medium", source="rule_engine"),
    ])
    mock_history_analyzer = AsyncMock()
    mock_history_analyzer.analyze = AsyncMock(return_value=[HistoryReference(run_id="run_1", date="2026-04-01", changed_params={}, metric_changes={}, conclusion="")])
    mock_llm_diagnoser = AsyncMock()
    mock_llm_diagnoser.diagnose = AsyncMock(return_value=LLMDiagnosis(summary="", findings=[], recommendations=[]))
    mock_conflict_detector = MagicMock()
    mock_conflict_detector.detect = MagicMock(return_value=([
        TuningSuggestion(id="rule_1", param_name="p1", current_value=1, suggested_value=2, action="increase", reason="", expected_effect="", priority="high", source="rule_engine"),
    ], 1))
    
    mock_test_run = MagicMock(
        id="test_run_1", overall_precision=0.8, overall_recall=0.7,
        overall_f1=0.75, overall_mrr=0.7, overall_ndcg=0.8,
    )
    mock_test_run_repo.get_by_id = AsyncMock(return_value=mock_test_run)
    mock_test_run_repo.get_results = AsyncMock(return_value=[])
    
    engine = TuningSuggestionEngine(mock_rule_engine, mock_history_analyzer, mock_llm_diagnoser, mock_conflict_detector, mock_test_run_repo)
    response = await engine.generate_suggestions("test_run_id")
    
    assert response.run_id == "test_run_id"
    assert response.conflict_filtered_count == 1
    assert response.total_suggestions == 1

async def test_generate_suggestions_skips_llm_when_bad_cases_lt_3(mock_test_run_repo):
    """Bad Case < 3 时应跳过 LLM 诊断"""
    from src.core.tuning.engine import TuningSuggestionEngine
    from unittest.mock import AsyncMock, MagicMock
    
    mock_rule_engine = AsyncMock()
    mock_rule_engine.evaluate = AsyncMock(return_value=[])
    mock_history_analyzer = AsyncMock()
    mock_history_analyzer.analyze = AsyncMock(return_value=[])
    mock_llm_diagnoser = AsyncMock()
    mock_llm_diagnoser.diagnose = AsyncMock(return_value=None)  # Bad Case 不足
    mock_conflict_detector = MagicMock()
    mock_conflict_detector.detect = MagicMock(return_value=([], 0))
    
    mock_test_run = MagicMock(
        id="test_run_1", overall_precision=0.8, overall_recall=0.7,
        overall_f1=0.75, overall_mrr=0.7, overall_ndcg=0.8,
    )
    mock_test_run_repo.get_by_id = AsyncMock(return_value=mock_test_run)
    mock_test_run_repo.get_results = AsyncMock(return_value=[])
    
    engine = TuningSuggestionEngine(mock_rule_engine, mock_history_analyzer, mock_llm_diagnoser, mock_conflict_detector, mock_test_run_repo)
    response = await engine.generate_suggestions("test_run_id")
    
    assert response.llm_diagnosis is None

async def test_generate_suggestions_computes_derived_metrics(mock_test_run_repo):
    """引擎应计算派生指标以触发对应规则"""
    from src.core.tuning.engine import TuningSuggestionEngine
    from unittest.mock import AsyncMock, MagicMock
    
    # Mock 测试运行结果包含年龄不匹配和复杂查询失败
    mock_results = [
        MagicMock(recall=0.3, precision=0.4, age_mismatch=True, query_type="comparative", chunking_issue=False, latency_ms=1500),
        MagicMock(recall=0.2, precision=0.3, age_mismatch=True, query_type="causal", chunking_issue=False, latency_ms=2000),
        MagicMock(recall=0.8, precision=0.9, age_mismatch=False, query_type="factual", chunking_issue=False, latency_ms=800),
    ]
    mock_test_run_repo.get_results = AsyncMock(return_value=mock_results)
    
    engine = TuningSuggestionEngine(AsyncMock(), AsyncMock(), AsyncMock(), MagicMock(), mock_test_run_repo)
    mock_test_run = MagicMock(id="test_run_1")
    derived = await engine._compute_derived_metrics(mock_test_run)
    
    assert derived["age_related_bad_case_ratio"] == 2 / 3  # 2/3 的 Bad Case 年龄不匹配
    assert derived["complex_query_failure_rate"] == 2 / 3   # 2/3 的 Bad Case 是复杂查询
    assert derived["avg_latency_ms"] == (1500 + 2000 + 800) / 3
```

- [ ] **Step 3: 运行测试验证失败**
Run: `pytest tests/unit/tuning/test_engine.py -v`
Expected: FAIL - 模块不存在

- [ ] **Step 4: 实现统一引擎**

```python
# src/core/tuning/engine.py
"""统一调参建议引擎：协调三层诊断组件"""
from datetime import datetime
from typing import Any, Dict, List, Optional
import time
from src.model.tuning import TuningSuggestionResponse, TuningSuggestion
from src.core.tuning.rule_engine import RuleEngine
from src.core.tuning.history_analyzer import HistoryAnalyzer
from src.core.tuning.llm_diagnoser import LLMDiagnoser
from src.core.tuning.conflict_detector import ConflictDetector
from src.utils.logger import logger


class TuningSuggestionEngine:
    """统一调参建议引擎"""
    
    # 缓存 TTL (秒)
    CACHE_TTL = 300  # 5 分钟
    
    def __init__(
        self,
        rule_engine: RuleEngine,
        history_analyzer: HistoryAnalyzer,
        llm_diagnoser: LLMDiagnoser,
        conflict_detector: ConflictDetector,
        test_run_repo=None,
    ):
        """初始化引擎"""
        self.rule_engine = rule_engine
        self.history_analyzer = history_analyzer
        self.llm_diagnoser = llm_diagnoser
        self.conflict_detector = conflict_detector
        self.test_run_repo = test_run_repo
        self._cache: Dict[str, tuple] = {}  # {run_id: (response, timestamp)}
    
    async def generate_suggestions(self, run_id: str) -> TuningSuggestionResponse:
        """生成调参建议（三层诊断）"""
        # 0. 检查缓存
        if run_id in self._cache:
            cached_response, cached_time = self._cache[run_id]
            if time.time() - cached_time < self.CACHE_TTL:
                logger.debug(f"缓存命中: run_id={run_id}")
                return cached_response
            else:
                logger.debug(f"缓存过期: run_id={run_id}")
                del self._cache[run_id]
        
        # 1. 获取测试运行和聚合指标
        test_run = await self.test_run_repo.get_by_id(run_id)
        if not test_run:
            raise ValueError(f"测试运行不存在: {run_id}")
        
        # 1a. 基础指标
        metrics = {
            "overall_precision": test_run.overall_precision or 0,
            "overall_recall": test_run.overall_recall or 0,
            "overall_f1": test_run.overall_f1 or 0,
            "overall_mrr": test_run.overall_mrr or 0,
            "overall_ndcg": test_run.overall_ndcg or 0,
        }
        
        # 1b. 派生指标计算（用于规则引擎触发条件）
        derived_metrics = await self._compute_derived_metrics(test_run)
        metrics.update(derived_metrics)
        
        # 2. 规则引擎
        rule_suggestions = await self.rule_engine.evaluate(metrics)
        logger.info(f"规则引擎生成 {len(rule_suggestions)} 条建议")
        
        # 3. 历史对比
        history_refs = await self.history_analyzer.analyze(
            current_metrics=metrics,
            current_run_id=run_id,
        )
        logger.info(f"历史对比找到 {len(history_refs)} 条参考")
        
        # 4. LLM 诊断 (若 Bad Case ≥ 3)
        llm_diag = await self.llm_diagnoser.diagnose(run_id)
        if llm_diag:
            logger.info(f"LLM 诊断生成 {len(llm_diag.recommendations)} 条建议")
            rule_suggestions.extend(llm_diag.recommendations)
        
        # 5. 冲突检测
        filtered_suggestions, conflict_count = self.conflict_detector.detect(rule_suggestions)
        
        # 6. 按优先级排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        filtered_suggestions.sort(key=lambda s: priority_order.get(s.priority, 3))
        
        response = TuningSuggestionResponse(
            run_id=run_id,
            generated_at=datetime.now().isoformat(),
            rule_engine_suggestions=[s for s in filtered_suggestions if s.source == "rule_engine"],
            history_references=history_refs,
            llm_diagnosis=llm_diag,
            conflict_filtered_count=conflict_count,
            total_suggestions=len(filtered_suggestions),
        )
        
        # 存入缓存
        self._cache[run_id] = (response, time.time())
        
        return response
    
    async def _compute_derived_metrics(self, test_run: Any) -> Dict[str, float]:
        """计算派生指标，用于规则引擎触发条件
        
        返回:
            - age_related_bad_case_ratio: 年龄相关 Bad Case 占比
            - complex_query_failure_rate: 复杂查询失败率
            - chunking_bad_case_ratio: 分块相关 Bad Case 占比
            - avg_latency_ms: 平均耗时 (ms)
        """
        # 获取该次运行的所有测试结果明细
        results = await self.test_run_repo.get_results(test_run.id)
        if not results:
            return {
                "age_related_bad_case_ratio": 0.0,
                "complex_query_failure_rate": 0.0,
                "chunking_bad_case_ratio": 0.0,
                "avg_latency_ms": 0.0,
            }
        
        total = len(results)
        age_related_failures = 0
        complex_query_failures = 0
        chunking_failures = 0
        total_latency_ms = 0
        
        for result in results:
            total_latency_ms += getattr(result, "latency_ms", 0) or 0
            
            # 判定是否为 Bad Case (recall < 0.5 或 precision < 0.5)
            is_bad_case = (result.recall or 0) < 0.5 or (result.precision or 0) < 0.5
            if not is_bad_case:
                continue
            
            # 年龄相关判定：测试用例年龄与文档适配年龄差异 > tolerance
            if getattr(result, "age_mismatch", False):
                age_related_failures += 1
            
            # 复杂查询判定：查询类型属于比较性/方案性/原因分析性
            query_type = getattr(result, "query_type", "factual")
            if query_type in ("comparative", "procedural", "causal"):
                complex_query_failures += 1
            
            # 分块相关判定：检索结果被截断或碎片化标记
            if getattr(result, "chunking_issue", False):
                chunking_failures += 1
        
        return {
            "age_related_bad_case_ratio": age_related_failures / total if total > 0 else 0.0,
            "complex_query_failure_rate": complex_query_failures / total if total > 0 else 0.0,
            "chunking_bad_case_ratio": chunking_failures / total if total > 0 else 0.0,
            "avg_latency_ms": total_latency_ms / total if total > 0 else 0.0,
        }
```

- [ ] **Step 5: 运行测试验证通过**
Run: `pytest tests/unit/tuning/test_engine.py -v`
Expected: PASS

---

### Task 2C.4.2: API 控制器实现

**Files:**
- Create: `src/controller/tuning_controller.py`
- Modify: `src/server.py` (注册路由)
- Modify: `src/core/di_container.py` (注册依赖)

- [ ] **Step 1: 实现 API 控制器**

```python
# src/controller/tuning_controller.py
"""调参建议 API 控制器"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from src.core.tuning.engine import TuningSuggestionEngine
from src.config import config_manager
from src.core.event.bus import event_bus, ConfigChangedEvent
from src.utils.logger import logger
from injector import inject

router = APIRouter(prefix="/api/v1/rag/test", tags=["调参建议"])


class PreviewRequest(BaseModel):
    """预览请求"""
    run_id: str
    param_name: str
    suggested_value: float

class PreviewResponse(BaseModel):
    """预览响应"""
    predicted_metrics: Optional[dict] = None
    based_on_history: bool = False
    message: str

class ApplyRequest(BaseModel):
    """应用请求"""
    run_id: str
    suggestion_ids: Optional[List[str]] = None  # 对应 TuningSuggestion.id (字符串)

class ApplyResponse(BaseModel):
    """应用响应"""
    new_config_version_id: str
    applied_params: dict


class TuningController:
    """调参建议 API 控制器"""
    
    @inject
    def __init__(
        self,
        tuning_engine: TuningSuggestionEngine,
        test_run_repo=None,
    ):
        """初始化控制器"""
        self.tuning_engine = tuning_engine
        self.config_mgr = config_manager  # 使用全局 ConfigManager 实例
        self.test_run_repo = test_run_repo or tuning_engine.test_run_repo
    
    def register_routes(self, app):
        """注册路由"""
        @router.get("/run/{run_id}/tuning-suggestions")
        async def get_tuning_suggestions(run_id: str):
            """获取指定测试运行的调参建议"""
            try:
                response = await self.tuning_engine.generate_suggestions(run_id)
                return response
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                logger.error(f"获取调参建议失败: {e}")
                raise HTTPException(status_code=500, detail="内部服务器错误")
        
        @router.post("/tuning-suggestions/preview")
        async def preview_suggestion(req: PreviewRequest):
            """预览应用某条建议后的预期指标变化
            
            实现逻辑:
            1. 从历史运行中查找修改过相同参数的记录
            2. 提取这些记录中该参数变更后的指标变化
            3. 取中位数作为预测值
            4. 若无历史数据，使用规则中的 expected_effect 作为 fallback
            """
            # 从历史运行中查找相似变更
            history_runs = await self.test_run_repo.get_completed_runs(limit=50)
            matching_changes = []
            
            for run in history_runs:
                old_snap = await self.config_mgr.get_version_config(run.previous_config_version_id)
                new_snap = await self.config_mgr.get_version_config(run.config_version_id)
                
                if old_snap and new_snap:
                    old_val = old_snap.get(req.param_name)
                    new_val = new_snap.get(req.param_name)
                    
                    if old_val is not None and new_val is not None:
                        # 找到相同参数的变更历史
                        matching_changes.append({
                            "from": old_val, "to": new_val,
                            "recall": run.overall_recall,
                            "precision": run.overall_precision,
                        })
            
            if matching_changes:
                # 取中位数作为预测（比平均值更抗异常值）
                recalls = sorted([c["recall"] for c in matching_changes])
                precisions = sorted([c["precision"] for c in matching_changes])
                
                def median(values: list) -> float:
                    n = len(values)
                    if n % 2 == 0:
                        return (values[n // 2 - 1] + values[n // 2]) / 2
                    return values[n // 2]
                
                predicted = {
                    "overall_recall": round(median(recalls), 4),
                    "overall_precision": round(median(precisions), 4),
                }
                return PreviewResponse(
                    predicted_metrics=predicted,
                    based_on_history=True,
                    message=f"基于 {len(matching_changes)} 次历史变更的中位数预测",
                )
            
            return PreviewResponse(
                predicted_metrics=None,
                based_on_history=False,
                message="基于规则的预期效果: 扩大检索范围，预计召回率提升 5-10%",
            )
        
        @router.post("/tuning-suggestions/apply")
        async def apply_suggestions(req: ApplyRequest):
            """一键应用建议参数到当前配置版本
            
            实现逻辑:
            1. 根据 run_id 获取调参建议
            2. 过滤出 suggestion_ids 指定的建议 (若未指定则应用全部)
            3. 校验建议值是否在 safe_range 内
            4. 通过 ConfigManager 创建新配置版本
            5. 触发热更新事件
            """
            # 获取建议
            suggestions_response = await self.tuning_engine.generate_suggestions(req.run_id)
            
            # 收集要应用的参数
            applied_params = {}
            all_suggestions = (
                suggestions_response.rule_engine_suggestions
                + (suggestions_response.llm_diagnosis.recommendations if suggestions_response.llm_diagnosis else [])
            )
            
            for s in all_suggestions:
                if req.suggestion_ids and s.id not in req.suggestion_ids:
                    continue
                
                # 安全范围校验
                if s.safe_range:
                    min_val, max_val = s.safe_range
                    if not (min_val <= s.suggested_value <= max_val):
                        logger.warning(f"建议值 {s.suggested_value} 超出安全范围 [{min_val}, {max_val}]，跳过")
                        continue
                
                applied_params[s.param_name] = s.suggested_value
            
            if not applied_params:
                raise HTTPException(status_code=400, detail="无有效参数可应用")
            
            # 通过 ConfigManager 创建新配置版本
            current_config = self.config_mgr.get_full_config()
            new_config = {**current_config, **applied_params}
            new_version_id = await self.config_mgr.create_version(
                config_data=new_config,
                description=f"调参建议应用 (run_id={req.run_id})",
            )
            
            # 触发热更新事件
            await event_bus.publish(ConfigChangedEvent(version_id=new_version_id))
            
            return ApplyResponse(
                new_config_version_id=new_version_id,
                applied_params=applied_params,
            )
        
        app.include_router(router)
```

- [ ] **Step 2: 注册路由到 server.py**

```python
# src/server.py (追加)
from src.controller.tuning_controller import TuningController

# 在应用初始化时注册
tuning_controller = TuningController(tuning_engine)
tuning_controller.register_routes(app)
```

- [ ] **Step 3: 注册依赖到 DI 容器**

```python
# src/core/di_container.py (追加)
from src.core.tuning.engine import TuningSuggestionEngine
from src.core.tuning.rule_engine import RuleEngine
from src.core.tuning.history_analyzer import HistoryAnalyzer
from src.core.tuning.llm_diagnoser import LLMDiagnoser
from src.core.tuning.conflict_detector import ConflictDetector

# 在 RepositoryModule 或新建 TuningModule 中注册
provider.bind(TuningSuggestionEngine)
provider.bind(RuleEngine)
provider.bind(HistoryAnalyzer)
provider.bind(LLMDiagnoser)
provider.bind(ConflictDetector)
```

---

**上一阶段:** [LLM 诊断](./04-phase-2c-03-llm-diagnoser.md)  
**下一阶段:** [前端集成 (MVP)](./04-phase-2c-05-frontend-mvp.md)
