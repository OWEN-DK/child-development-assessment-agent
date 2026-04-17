# Phase 2C.1: 规则引擎

> **前置文档:** [Overview](./04-phase-2c-00-overview.md)
> **状态:** ⏳ 完全待实现
> **预计工期:** 1.5 人天

## 目标

实现规则引擎核心逻辑，规则通过 ConfigManager 存入 MySQL，支持热更新。根据测试指标短板自动映射到参数调整建议，并实现冲突检测算法过滤矛盾建议。

---

### Task 2C.1.1: 规则配置化 (MySQL 存储)

**Files:**
- Create: `src/core/tuning/__init__.py`
- Test: `tests/unit/tuning/test_rule_engine.py`

- [ ] **Step 1: 编写测试用例**
```python
def test_rules_loaded_from_config_manager():
    """验证规则从 ConfigManager 正确加载（覆盖全部 7 个规则组）"""
    from src.core.tuning.rule_engine import RuleEngine
    from src.config import config_manager
    
    engine = RuleEngine(config_manager)
    rules = engine._load_rules()
    assert "recall_optimization" in rules
    assert "precision_optimization" in rules
    assert "ranking_optimization" in rules
    assert "comprehensive_optimization" in rules
    assert "age_adaptation_optimization" in rules
    assert "complex_query_optimization" in rules
    assert "chunking_optimization" in rules
    assert "performance_optimization" in rules
    assert rules["recall_optimization"]["trigger"]["metric"] == "overall_recall"
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/unit/tuning/test_rule_engine.py::test_rules_loaded_from_config_manager -v`
Expected: FAIL - 模块不存在

- [ ] **Step 3: 创建模块入口**
```python
# src/core/tuning/__init__.py
"""智能调参建议引擎模块"""
from src.core.tuning.engine import TuningSuggestionEngine
from src.core.tuning.rule_engine import RuleEngine
from src.core.tuning.conflict_detector import ConflictDetector

__all__ = ["TuningSuggestionEngine", "RuleEngine", "ConflictDetector"]
```

- [ ] **Step 4: 初始规则数据写入**

> **⚠️ 规则存储约束**: 规则必须通过 `ConfigManager` 存入 MySQL `config_versions` 表，禁止使用本地 JSON 文件。首次部署时通过初始化脚本写入默认规则。
>
> **📌 与 Spec 的偏离说明**: Spec §8.3.2 提到规则存储在 `rules.json` 的 `rag_tuning_rules` 字段。但根据 CLAUDE.md 的强制约束"禁止直接写入本地 JSON 文件"，本方案将规则统一存入 MySQL `config_versions` 表，通过 ConfigManager 热更新管理。`rules.json` 仅作为首次部署时的初始化数据源，部署后不再读取本地文件。

通过 ConfigManager 写入初始规则 (配置键: `rag_tuning_rules`):

```json
{
  "recall_optimization": {
    "trigger": {"metric": "overall_recall", "operator": "<", "threshold": 0.7},
    "suggestions": [
      {"param": "rag_hybrid_bm25_top_k", "action": "increase", "suggested_value": 15, "safe_range": [10, 50], "expected_effect": "扩大 BM25 检索范围，提升召回率"},
      {"param": "rag_hybrid_vector_top_k", "action": "increase", "suggested_value": 15, "safe_range": [10, 50], "expected_effect": "扩大向量检索范围，提升召回率"},
      {"param": "rag_hybrid_base_threshold", "action": "decrease", "suggested_value": 0.05, "safe_range": [0.05, 0.15], "expected_effect": "降低检索门槛，允许更多候选进入"},
      {"param": "rag_similarity_threshold", "action": "decrease", "suggested_value": 0.6, "safe_range": [0.5, 0.8], "expected_effect": "降低相似度门槛，放宽匹配条件"}
    ],
    "priority": "high"
  },
  "precision_optimization": {
    "trigger": {"metric": "overall_precision", "operator": "<", "threshold": 0.75},
    "suggestions": [
      {"param": "rag_reranker_final_k", "action": "decrease", "suggested_value": 3, "safe_range": [3, 10], "expected_effect": "减少最终返回数量，提升精度"},
      {"param": "rag_search_score_threshold_hybrid", "action": "increase", "suggested_value": 0.4, "safe_range": [0.25, 0.6], "expected_effect": "提高分数门槛，过滤低质量结果"},
      {"param": "rag_search_no_match_vector_penalty", "action": "increase", "suggested_value": 0.6, "safe_range": [0.5, 0.8], "expected_effect": "增加无关键词匹配惩罚，减少噪声"}
    ],
    "priority": "high"
  },
  "ranking_optimization": {
    "trigger": {"metric": "overall_mrr", "operator": "<", "threshold": 0.65},
    "suggestions": [
      {"param": "rag_reranker_initial_k", "action": "increase", "suggested_value": 40, "safe_range": [30, 60], "expected_effect": "增加重排序候选池，提升排序质量"},
      {"param": "fusion_score_boost_for_pageindex", "action": "increase", "suggested_value": 1.3, "safe_range": [1.0, 1.5], "expected_effect": "增强 PageIndex 分数，提升层级检索效果"}
    ],
    "priority": "medium"
  },
  "comprehensive_optimization": {
    "trigger": {"or": [
      {"metric": "overall_f1", "operator": "<", "threshold": 0.6},
      {"metric": "overall_ndcg", "operator": "<", "threshold": 0.75}
    ]},
    "suggestions": [
      {"param": "rag_hybrid_merge_mode", "action": "switch", "suggested_value": "AND", "expected_effect": "切换为 AND 模式，平衡召回与精度"},
      {"param": "rag_relative_cutoff_ratio", "action": "increase", "suggested_value": 0.4, "safe_range": [0.3, 0.6], "expected_effect": "调整截断比例，优化结果质量"}
    ],
    "priority": "medium"
  },
  "age_adaptation_optimization": {
    "trigger": {"metric": "age_related_bad_case_ratio", "operator": ">", "threshold": 0.3},
    "suggestions": [
      {"param": "rag_age_filter_strictness", "action": "decrease", "suggested_value": 0.5, "safe_range": [0.3, 0.8], "expected_effect": "降低年龄过滤严格度，扩大适配范围"},
      {"param": "rag_age_filter_tolerance", "action": "increase", "suggested_value": 3, "safe_range": [1, 5], "expected_effect": "增加年龄容忍范围"},
      {"param": "rag_age_fit_weight", "action": "increase", "suggested_value": 0.4, "safe_range": [0.2, 0.6], "expected_effect": "提高年龄适配度权重"}
    ],
    "priority": "medium"
  },
  "complex_query_optimization": {
    "trigger": {"metric": "complex_query_failure_rate", "operator": ">", "threshold": 0.4},
    "suggestions": [
      {"param": "pageindex_enabled", "action": "enable", "suggested_value": true, "expected_effect": "开启 PageIndex 增强复杂查询处理"},
      {"param": "rag_query_rewrite_enabled", "action": "enable", "suggested_value": true, "expected_effect": "开启查询重写，提升复杂查询理解"},
      {"param": "query_router_llm_enabled", "action": "enable", "suggested_value": true, "expected_effect": "开启 LLM 查询路由，智能分类处理"}
    ],
    "priority": "high"
  },
  "chunking_optimization": {
    "trigger": {"metric": "chunking_bad_case_ratio", "operator": ">", "threshold": 0.2},
    "suggestions": [
      {"param": "rag_chunk_size", "action": "increase", "suggested_value": 800, "safe_range": [400, 1200], "expected_effect": "增大分块尺寸，减少内容碎片化"},
      {"param": "rag_chunk_overlap", "action": "increase", "suggested_value": 150, "safe_range": [50, 300], "expected_effect": "增加重叠比例，保留跨块上下文"},
      {"param": "rag_semantic_chunk_threshold", "action": "decrease", "suggested_value": 0.3, "safe_range": [0.2, 0.5], "expected_effect": "降低语义分块阈值，减少过度切分"},
      {"param": "rag_chapter_max_size", "action": "increase", "suggested_value": 3000, "safe_range": [2000, 5000], "expected_effect": "增大章节最大尺寸，保持章节完整性"}
    ],
    "priority": "medium"
  },
  "performance_optimization": {
    "trigger": {"metric": "avg_latency_ms", "operator": ">", "threshold": 2000},
    "suggestions": [
      {"param": "rag_max_workers", "action": "increase", "suggested_value": 30, "safe_range": [10, 50], "expected_effect": "增加并行线程数，提升处理吞吐量"},
      {"param": "rag_concurrency_limit", "action": "increase", "suggested_value": 15, "safe_range": [5, 30], "expected_effect": "提高并发上限，减少排队等待"},
      {"param": "rag_cache_max_size", "action": "increase", "suggested_value": 20000, "safe_range": [5000, 50000], "expected_effect": "扩大缓存容量，提升缓存命中率"},
      {"param": "rag_cache_ttl_seconds", "action": "increase", "suggested_value": 3600, "safe_range": [600, 7200], "expected_effect": "延长缓存过期时间，减少重复检索"}
    ],
    "priority": "low"
  }
}
```

- [ ] **Step 5: 运行测试验证通过**
Run: `pytest tests/unit/tuning/test_rule_engine.py::test_rules_loaded_from_config_manager -v`
Expected: PASS

---

### Task 2C.1.2: 规则引擎核心实现

**Files:**
- Create: `src/core/tuning/rule_engine.py`
- Create: `src/model/tuning.py`
- Test: `tests/unit/tuning/test_rule_engine.py`

- [ ] **Step 1: 定义 Pydantic 模型**

```python
# src/model/tuning.py
"""调参建议数据模型"""
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Tuple

class TuningSuggestion(BaseModel):
    """单条调参建议"""
    id: Optional[str] = None           # 唯一标识 (用于前端选择应用)
    param_name: str                    # 参数名
    current_value: Any                 # 当前值
    suggested_value: Any               # 建议值
    action: str                        # 动作: increase/decrease/enable/disable/switch
    reason: str                        # 建议原因
    expected_effect: str               # 预期效果
    priority: str                      # high/medium/low
    source: str                        # 来源: rule_engine/history/llm
    safe_range: Optional[Tuple[Any, Any]] = None  # 安全范围
```

- [ ] **Step 2: 编写核心测试用例**

```python
async def test_recall_below_threshold_triggers_suggestion(mock_config_manager):
    """召回率低于阈值时应触发召回优化建议"""
    from src.core.tuning.rule_engine import RuleEngine
    
    metrics = {"overall_recall": 0.65, "overall_precision": 0.80}
    engine = RuleEngine(mock_config_manager)
    suggestions = await engine.evaluate(metrics)
    
    # 应包含 rag_hybrid_bm25_top_k 建议
    assert any(s.param_name == "rag_hybrid_bm25_top_k" for s in suggestions)

async def test_no_trigger_when_metrics_above_threshold(mock_config_manager):
    """指标高于阈值时不应触发建议"""
    from src.core.tuning.rule_engine import RuleEngine
    
    metrics = {"overall_recall": 0.85, "overall_precision": 0.90}
    engine = RuleEngine(mock_config_manager)
    suggestions = await engine.evaluate(metrics)
    
    recall_suggestions = [s for s in suggestions if "recall" in s.reason.lower()]
    assert len(recall_suggestions) == 0

async def test_current_value_from_config_manager(mock_config_manager):
    """建议的当前值应从 ConfigManager 读取（热配置兼容）"""
    from src.core.tuning.rule_engine import RuleEngine
    
    # Mock ConfigManager 返回包含参数值的配置
    mock_config = {
        "rag_tuning_rules": {
            "recall_optimization": {
                "trigger": {"metric": "overall_recall", "operator": "<", "threshold": 0.7},
                "suggestions": [
                    {"param": "rag_hybrid_bm25_top_k", "action": "increase", "suggested_value": 15, "safe_range": [10, 50], "expected_effect": "提升召回率"}
                ],
                "priority": "high",
            }
        },
        "rag_hybrid_bm25_top_k": 10,  # 当前配置值
    }
    mock_config_manager.get_full_config.return_value = mock_config
    
    engine = RuleEngine(mock_config_manager)
    suggestions = await engine.evaluate({"overall_recall": 0.60})
    
    assert len(suggestions) > 0
    assert suggestions[0].current_value == 10  # 从 ConfigManager 读取
    assert suggestions[0].suggested_value == 15
```

- [ ] **Step 3: 运行测试验证失败**
Run: `pytest tests/unit/tuning/test_rule_engine.py -v`
Expected: FAIL - 模块不存在或方法未实现

- [ ] **Step 4: 实现规则引擎**

```python
# src/core/tuning/rule_engine.py
"""规则引擎：根据测试指标生成参数调整建议"""
from typing import Any, Dict, List
import uuid
from src.model.tuning import TuningSuggestion
from src.config import config_manager
from src.utils.logger import logger


class RuleEngine:
    """规则引擎：指标驱动的参数诊断"""
    
    # 操作符映射
    OPERATORS = {
        "<": lambda a, b: a < b,
        ">": lambda a, b: a > b,
        "<=": lambda a, b: a <= b,
        ">=": lambda a, b: a >= b,
        "==": lambda a, b: a == b,
    }
    
    def __init__(self, config_mgr=None):
        """初始化规则引擎"""
        self.config_mgr = config_mgr or config_manager
        self._current_config_cache: Dict[str, Any] = {}
    
    def _load_rules(self) -> Dict[str, Any]:
        """从 ConfigManager 加载调参规则"""
        full_config = self.config_mgr.get_full_config()
        return full_config.get("rag_tuning_rules", {})
    
    def _refresh_config_cache(self):
        """刷新当前配置缓存（热配置场景下每次评估前调用）"""
        self._current_config_cache = self.config_mgr.get_full_config()
    
    def _get_current_value(self, param_name: str) -> Any:
        """根据参数名从 ConfigManager 当前配置中读取当前值（热配置兼容）"""
        # 优先从缓存中读取，支持扁平化参数名解析
        value = self._current_config_cache.get(param_name)
        if value is not None:
            return value
        # 支持嵌套路径解析 (如 "rag.hybrid_bm25_top_k" -> config["rag"]["hybrid_bm25_top_k"])
        parts = param_name.split(".")
        current = self._current_config_cache
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current
    
    def _check_trigger(self, trigger: Dict, metrics: Dict[str, float]) -> bool:
        """检查触发条件是否满足"""
        # 处理 or 组合条件
        if "or" in trigger:
            return any(self._check_condition(cond, metrics) for cond in trigger["or"])
        # 处理 and 组合条件
        if "and" in trigger:
            return all(self._check_condition(cond, metrics) for cond in trigger["and"])
        # 单一条件
        return self._check_condition(trigger, metrics)
    
    def _check_condition(self, condition: Dict, metrics: Dict[str, float]) -> bool:
        """检查单一条件"""
        metric = condition["metric"]
        operator = condition["operator"]
        threshold = condition["threshold"]
        
        actual_value = metrics.get(metric)
        if actual_value is None:
            return False
        
        op_func = self.OPERATORS.get(operator)
        if op_func is None:
            logger.warning(f"未知操作符: {operator}")
            return False
        
        return op_func(actual_value, threshold)
    
    async def evaluate(self, metrics: Dict[str, float]) -> List[TuningSuggestion]:
        """根据指标评估生成调参建议"""
        # 刷新配置缓存，确保读取最新值
        self._refresh_config_cache()
        
        rules = self._load_rules()
        suggestions = []
        
        for rule_name, rule in rules.items():
            trigger = rule.get("trigger", {})
            if not self._check_trigger(trigger, metrics):
                continue
            
            # 触发规则，生成建议
            priority = rule.get("priority", "medium")
            for suggestion_template in rule.get("suggestions", []):
                param_name = suggestion_template["param"]
                suggestion = TuningSuggestion(
                    id=f"rule_{rule_name}_{param_name}",
                    param_name=param_name,
                    current_value=self._get_current_value(param_name),
                    suggested_value=suggestion_template["suggested_value"],
                    action=suggestion_template["action"],
                    reason=f"{rule_name} 规则触发: 指标不达标",
                    expected_effect=suggestion_template.get("expected_effect", ""),
                    priority=priority,
                    source="rule_engine",
                    safe_range=tuple(suggestion_template.get("safe_range", [])) if suggestion_template.get("safe_range") else None,
                )
                suggestions.append(suggestion)
        
        logger.info(f"规则引擎评估完成: 生成 {len(suggestions)} 条建议")
        return suggestions
```

- [ ] **Step 5: 运行测试验证通过**
Run: `pytest tests/unit/tuning/test_rule_engine.py -v`
Expected: PASS

---

### Task 2C.1.3: 冲突检测算法

**Files:**
- Create: `src/core/tuning/conflict_detector.py`
- Test: `tests/unit/tuning/test_conflict_detector.py`

- [ ] **Step 1: 编写测试用例**

```python
async def test_conflicting_actions_filtered():
    """同一参数的矛盾动作应被过滤"""
    from src.core.tuning.conflict_detector import ConflictDetector
    from src.model.tuning import TuningSuggestion
    
    suggestions = [
        TuningSuggestion(
            param_name="rag_hybrid_bm25_top_k",
            action="increase",
            priority="high",
            source="rule_engine",
            current_value=10,
            suggested_value=15,
            reason="",
            expected_effect="",
        ),
        TuningSuggestion(
            param_name="rag_hybrid_bm25_top_k",
            action="decrease",
            priority="medium",
            source="history",
            current_value=10,
            suggested_value=8,
            reason="",
            expected_effect="",
        ),
    ]
    
    detector = ConflictDetector()
    filtered, count = detector.detect(suggestions)
    
    assert len(filtered) == 1
    assert count == 1
    assert filtered[0].action == "increase"  # 保留高优先级

async def test_same_direction_no_conflict():
    """同方向动作或不同参数不应视为冲突"""
    from src.core.tuning.conflict_detector import ConflictDetector
    from src.model.tuning import TuningSuggestion
    
    suggestions = [
        TuningSuggestion(param_name="rag_hybrid_bm25_top_k", action="increase", priority="high", source="rule_engine", current_value=10, suggested_value=15, reason="", expected_effect=""),
        TuningSuggestion(param_name="rag_hybrid_vector_top_k", action="increase", priority="high", source="rule_engine", current_value=10, suggested_value=15, reason="", expected_effect=""),
    ]
    
    detector = ConflictDetector()
    filtered, count = detector.detect(suggestions)
    
    assert len(filtered) == 2
    assert count == 0

async def test_enable_disable_conflict():
    """enable 和 disable 应视为冲突"""
    from src.core.tuning.conflict_detector import ConflictDetector
    from src.model.tuning import TuningSuggestion
    
    suggestions = [
        TuningSuggestion(param_name="pageindex_enabled", action="enable", priority="high", source="rule_engine", current_value=False, suggested_value=True, reason="", expected_effect=""),
        TuningSuggestion(param_name="pageindex_enabled", action="disable", priority="medium", source="llm", current_value=False, suggested_value=False, reason="", expected_effect=""),
    ]
    
    detector = ConflictDetector()
    filtered, count = detector.detect(suggestions)
    
    assert len(filtered) == 1
    assert filtered[0].action == "enable"
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/unit/tuning/test_conflict_detector.py -v`
Expected: FAIL - 模块不存在

- [ ] **Step 3: 实现冲突检测器**

```python
# src/core/tuning/conflict_detector.py
"""冲突检测器：过滤矛盾的调参建议"""
from typing import List, Tuple
from src.model.tuning import TuningSuggestion
from src.utils.logger import logger


# 矛盾动作对
CONFLICT_PAIRS = {
    ("increase", "decrease"),
    ("enable", "disable"),
    ("switch", "switch"),  # 同一参数不建议同时 switch 到不同值
}

# 优先级权重
PRIORITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}

# 来源权重
SOURCE_WEIGHT = {"rule_engine": 3, "history": 2, "llm": 1}


class ConflictDetector:
    """冲突检测器：按参数名分组，检测并过滤矛盾建议"""
    
    def detect(self, suggestions: List[TuningSuggestion]) -> Tuple[List[TuningSuggestion], int]:
        """检测并过滤冲突建议"""
        # 按参数名分组
        param_groups = {}
        for s in suggestions:
            if s.param_name not in param_groups:
                param_groups[s.param_name] = []
            param_groups[s.param_name].append(s)
        
        filtered = []
        conflict_count = 0
        
        for param_name, group in param_groups.items():
            if len(group) == 1:
                filtered.extend(group)
                continue
            
            # 检测冲突
            has_conflict = False
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    if self._is_conflict(group[i], group[j]):
                        has_conflict = True
                        break
                if has_conflict:
                    break
            
            if has_conflict:
                # 保留优先级最高的建议
                group.sort(key=lambda s: (
                    PRIORITY_WEIGHT.get(s.priority, 0),
                    SOURCE_WEIGHT.get(s.source, 0),
                ), reverse=True)
                filtered.append(group[0])
                conflict_count += len(group) - 1
                logger.info(f"冲突检测: 参数 {param_name} 过滤 {len(group) - 1} 条冲突建议")
            else:
                filtered.extend(group)
        
        logger.info(f"冲突检测完成: 过滤 {conflict_count} 条冲突建议，保留 {len(filtered)} 条")
        return filtered, conflict_count
    
    def _is_conflict(self, s1: TuningSuggestion, s2: TuningSuggestion) -> bool:
        """判断两条建议是否冲突"""
        pair = (s1.action, s2.action)
        return pair in CONFLICT_PAIRS or (s2.action, s1.action) in CONFLICT_PAIRS
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/unit/tuning/test_conflict_detector.py -v`
Expected: PASS

---

**上一阶段:** [Overview](./04-phase-2c-00-overview.md)  
**下一阶段:** [历史对比分析](./04-phase-2c-02-history-analyzer.md)
