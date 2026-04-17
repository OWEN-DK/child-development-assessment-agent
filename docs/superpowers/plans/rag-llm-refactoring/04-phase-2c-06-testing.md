# Phase 2C.6: TDD 测试策略

> **前置文档:** [Overview](./04-phase-2c-00-overview.md)
> **状态:** ⏳ 完全待实现
> **预计工期:** 0.5 人天 (与开发并行)

## 目标

遵循 SDD + TDD 工作流，每个模块实施必须按"红-绿-重构"循环推进，确保代码质量。

---

### Task 2C.6.1: 测试文件清单

| 测试文件 | 测试目标 | 优先级 | 预计用例数 |
|----------|----------|--------|------------|
| `tests/unit/tuning/test_rule_engine.py` | 规则引擎触发逻辑、参数值读取、7 规则组加载 | P0 | 7 |
| `tests/unit/tuning/test_conflict_detector.py` | 冲突检测算法、优先级排序 | P0 | 4 |
| `tests/unit/tuning/test_history_analyzer.py` | 配置快照对比、相似匹配、指标变化对比 | P1 | 6 |
| `tests/unit/tuning/test_llm_diagnoser.py` | Bad Case 聚合、LLM 输出解析 | P1 | 4 |
| `tests/unit/tuning/test_engine.py` | 统一引擎编排流程、派生指标计算 | P0 | 5 |
| `tests/integration/tuning/test_tuning_api.py` | API 接口完整流程 | P0 | 5 |
| `tests/integration/tuning/test_config_apply.py` | 配置应用与回滚 | P1 | 3 |
| `tests/unit/tuning/test_performance_baseline.py` | 性能基线验证 (新增) | P0 | 4 |

---

### Task 2C.6.2: 红绿重构步骤

> **执行顺序**: 严格按照以下步骤推进，每个步骤必须确认测试失败 (Red) 后才能进入实现 (Green)。

#### 第一轮: 规则引擎

1. **生成测试文件** `tests/unit/tuning/test_rule_engine.py`
2. **确认失败**: `pytest tests/unit/tuning/test_rule_engine.py -v` → FAIL (模块不存在)
3. **实现** `src/core/tuning/__init__.py` + `src/core/tuning/rule_engine.py`
4. **确认通过**: `pytest tests/unit/tuning/test_rule_engine.py -v` → PASS
5. **重构**: 提取 `_check_trigger` 和 `_check_condition` 方法，消除重复代码

#### 第二轮: 冲突检测

1. **生成测试文件** `tests/unit/tuning/test_conflict_detector.py`
2. **确认失败**: `pytest tests/unit/tuning/test_conflict_detector.py -v` → FAIL
3. **实现** `src/core/tuning/conflict_detector.py`
4. **确认通过**: `pytest tests/unit/tuning/test_conflict_detector.py -v` → PASS
5. **重构**: 将优先级和来源权重提取为常量

#### 第三轮: 历史对比

1. **生成测试文件** `tests/unit/tuning/test_history_analyzer.py`
2. **确认失败**: `pytest tests/unit/tuning/test_history_analyzer.py -v` → FAIL
3. **实现** `src/core/tuning/history_analyzer.py`
4. **确认通过**: `pytest tests/unit/tuning/test_history_analyzer.py -v` → PASS
5. **重构**: 提取 `_diff_configs` 为独立工具函数

#### 第四轮: LLM 诊断

1. **生成测试文件** `tests/unit/tuning/test_llm_diagnoser.py`
2. **确认失败**: `pytest tests/unit/tuning/test_llm_diagnoser.py -v` → FAIL
3. **实现** `src/core/tuning/llm_diagnoser.py`
4. **确认通过**: `pytest tests/unit/tuning/test_llm_diagnoser.py -v` → PASS
5. **重构**: 将 `_parse_llm_output` 提取为独立模块

#### 第五轮: 统一引擎

1. **生成测试文件** `tests/unit/tuning/test_engine.py`
2. **确认失败**: `pytest tests/unit/tuning/test_engine.py -v` → FAIL
3. **实现** `src/core/tuning/engine.py`
4. **确认通过**: `pytest tests/unit/tuning/test_engine.py -v` → PASS
5. **重构**: 无 (引擎逻辑已足够简洁)

#### 第六轮: 集成测试

1. **生成测试文件** `tests/integration/tuning/test_tuning_api.py`
2. **确认失败**: `pytest tests/integration/tuning/test_tuning_api.py -v` → FAIL
3. **实现** `src/controller/tuning_controller.py`
4. **确认通过**: `pytest tests/integration/tuning/test_tuning_api.py -v` → PASS
5. **重构**: 无

---

### Task 2C.6.3: 测试 Fixture 定义

**文件**: `tests/conftest.py` (追加)

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_config_manager():
    """Mock ConfigManager (包含规则 + 当前参数值)"""
    mgr = MagicMock()
    mgr.get_full_config = MagicMock(return_value={
        "rag_tuning_rules": {
            "recall_optimization": {
                "trigger": {"metric": "overall_recall", "operator": "<", "threshold": 0.7},
                "suggestions": [
                    {"param": "rag_hybrid_bm25_top_k", "action": "increase", "suggested_value": 15, "safe_range": [10, 50], "expected_effect": "提升召回率"}
                ],
                "priority": "high",
            }
        },
        "rag_hybrid_bm25_top_k": 10,  # 当前配置值（热配置）
        "rag_hybrid_vector_top_k": 10,
        "rag_reranker_final_k": 5,
    })
    return mgr

@pytest.fixture
def mock_test_run_repo():
    """Mock TestRunRepository"""
    repo = AsyncMock()
    return repo

@pytest.fixture
def mock_test_run_result_repo():
    """Mock TestRunResultRepository"""
    repo = AsyncMock()
    return repo

@pytest.fixture
def mock_test_case_repo():
    """Mock TestCaseRepository"""
    repo = AsyncMock()
    return repo

@pytest.fixture
def mock_prompt_manager():
    """Mock PromptManager"""
    mgr = AsyncMock()
    mgr.get_prompt = AsyncMock(return_value="你是一个 RAG 系统诊断专家...")
    return mgr

@pytest.fixture
def mock_llm_factory():
    """Mock LLMServiceFactory"""
    factory = MagicMock()
    llm_instance = AsyncMock()
    llm_instance.ainvoke = AsyncMock(return_value=MagicMock(content='{"summary": "测试", "findings": [], "recommendations": []}'))
    factory.create = MagicMock(return_value=llm_instance)
    return factory
```

---

### Task 2C.6.3b: 性能基线测试 (新增)

**文件**: `tests/unit/tuning/test_performance_baseline.py`

- [ ] **Step 1: 编写性能测试**

```python
"""性能基线测试：验证各组件响应时间符合验收标准"""
import pytest
import time
from unittest.mock import MagicMock, AsyncMock

async def test_rule_engine_latency(mock_config_manager):
    """规则引擎响应时间应 <50ms"""
    from src.core.tuning.rule_engine import RuleEngine
    
    engine = RuleEngine(mock_config_manager)
    metrics = {
        "overall_recall": 0.60, "overall_precision": 0.70,
        "overall_f1": 0.55, "overall_mrr": 0.60, "overall_ndcg": 0.70,
        "age_related_bad_case_ratio": 0.35, "complex_query_failure_rate": 0.45,
        "chunking_bad_case_ratio": 0.25, "avg_latency_ms": 2500,
    }
    
    start = time.perf_counter()
    suggestions = await engine.evaluate(metrics)
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    assert elapsed_ms < 50, f"规则引擎响应时间 {elapsed_ms:.1f}ms 超过 50ms 基线"

async def test_history_analyzer_latency(mock_test_run_repo, mock_config_manager):
    """历史对比分析响应时间应 <100ms (≥5 次历史运行)"""
    from src.core.tuning.history_analyzer import HistoryAnalyzer
    
    # Mock 5 次历史运行
    mock_runs = [MagicMock(
        id=f"run_{i}", config_version_id=f"v{i}",
        overall_recall=0.60 + i * 0.05, overall_precision=0.80,
        overall_f1=0.65, overall_mrr=0.60, overall_ndcg=0.70,
        created_at=MagicMock(strftime=MagicMock(return_value="2026-04-01")),
    ) for i in range(5)]
    mock_test_run_repo.get_completed_runs = AsyncMock(return_value=mock_runs)
    mock_config_manager.get_version_config = AsyncMock(return_value={"rag_hybrid_bm25_top_k": 10})
    
    analyzer = HistoryAnalyzer(mock_test_run_repo, mock_config_manager)
    
    start = time.perf_counter()
    references = await analyzer.analyze(
        current_metrics={"overall_recall": 0.65},
        current_run_id="current_run",
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    assert elapsed_ms < 100, f"历史分析响应时间 {elapsed_ms:.1f}ms 超过 100ms 基线"

async def test_llm_diagnoser_latency(mock_test_run_result_repo, mock_test_case_repo, mock_prompt_manager, mock_llm_factory):
    """LLM 诊断响应时间应在 1-3s (Bad Case 10 条)"""
    from src.core.tuning.llm_diagnoser import LLMDiagnoser
    
    # Mock 10 个 Bad Case
    mock_test_run_result_repo.get_failed_results = AsyncMock(return_value=[MagicMock(
        test_case_id=f"tc_{i}", query=f"测试查询 {i}",
        recall=0.0, actual_count=2,
    ) for i in range(10)])
    mock_test_case_repo.get_by_id = AsyncMock(MagicMock(
        domain=MagicMock(value="感觉统合"), age=2.0,
        expected_keywords=["关键词1", "关键词2"],
    ))
    
    diagnoser = LLMDiagnoser(mock_test_run_result_repo, mock_test_case_repo, mock_prompt_manager, mock_llm_factory)
    
    start = time.perf_counter()
    result = await diagnoser.diagnose("test_run_id")
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    assert 1000 <= elapsed_ms <= 3000, f"LLM 诊断响应时间 {elapsed_ms:.0f}ms 不在 1-3s 范围内"

async def test_cache_hit_rate(mock_test_run_repo, mock_config_manager):
    """同一 run_id 连续请求 5 次，规则引擎和历史分析器应被缓存（调用次数 ≤ 2）"""
    from src.core.tuning.engine import TuningSuggestionEngine
    from unittest.mock import AsyncMock
    
    # Mock 各组件
    mock_rule_engine = AsyncMock()
    mock_rule_engine.evaluate = AsyncMock(return_value=[])
    mock_history_analyzer = AsyncMock()
    mock_history_analyzer.analyze = AsyncMock(return_value=[])
    mock_llm_diagnoser = AsyncMock()
    mock_llm_diagnoser.diagnose = AsyncMock(return_value=None)
    mock_conflict_detector = MagicMock()
    mock_conflict_detector.detect = MagicMock(return_value=([], 0))
    
    mock_test_run = MagicMock(
        id="test_run_1", overall_precision=0.8, overall_recall=0.7,
        overall_f1=0.75, overall_mrr=0.7, overall_ndcg=0.8,
    )
    mock_test_run_repo.get_by_id = AsyncMock(return_value=mock_test_run)
    mock_test_run_repo.get_results = AsyncMock(return_value=[])
    
    engine = TuningSuggestionEngine(
        mock_rule_engine, mock_history_analyzer, mock_llm_diagnoser,
        mock_conflict_detector, mock_test_run_repo,
    )
    
    # 连续请求 5 次
    for _ in range(5):
        await engine.generate_suggestions("test_run_1")
    
    # 验证缓存生效：evaluate 和 analyze 调用次数应 ≤ 1（无缓存时为 5 次）
    assert mock_rule_engine.evaluate.call_count <= 1, f"规则引擎被调用 {mock_rule_engine.evaluate.call_count} 次，缓存未生效"
    assert mock_history_analyzer.analyze.call_count <= 1, f"历史分析器被调用 {mock_history_analyzer.analyze.call_count} 次，缓存未生效"
```

- [ ] **Step 2: 运行性能测试**
Run: `pytest tests/unit/tuning/test_performance_baseline.py -v`
Expected: PASS

---

### Task 2C.6.4: 全链路集成测试

**文件**: `tests/e2e/test_tuning_workflow.py`

- [ ] **Step 1: 编写端到端测试**

```python
"""调参建议引擎端到端测试"""
import pytest

async def test_full_tuning_workflow():
    """完整调参建议工作流: 测试完成 → 获取建议 → 应用参数 → 复测"""
    # 1. 执行一次测试集运行
    run_id = await create_and_run_test_set()
    
    # 2. 获取调参建议
    suggestions = await get_tuning_suggestions(run_id)
    assert suggestions.total_suggestions > 0
    
    # 3. 应用建议参数
    result = await apply_suggestions(run_id)
    assert result.new_config_version_id is not None
    
    # 4. 重新执行测试集，验证指标变化
    new_run_id = await create_and_run_test_set()
    new_run = await get_test_run(new_run_id)
    
    # 召回率应有所提升 (至少不下降)
    old_run = await get_test_run(run_id)
    assert new_run.overall_recall >= old_run.overall_recall * 0.95  # 允许 5% 波动
```

- [ ] **Step 2: 运行端到端测试**
Run: `pytest tests/e2e/test_tuning_workflow.py -v`
Expected: PASS

---

**上一阶段:** [前端集成 (MVP)](./04-phase-2c-05-frontend-mvp.md)  
**下一阶段:** [Phase 3](./05-phase-3-llm-tracing.md)
