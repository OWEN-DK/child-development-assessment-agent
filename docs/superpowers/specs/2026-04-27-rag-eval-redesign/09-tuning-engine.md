# 09 - 调优引擎详细设计

## 需求

设计独立的调优引擎，基于指标结果自动生成调优建议。替代当前 `core/tuning/` 中的实现。

## 当前问题

1. `tuning/engine.py` 使用 in-memory cache（`_suggestion_cache`），多实例部署时缓存不共享
2. `tuning/history_analyzer.py` 有未使用方法 `_find_similar_runs`
3. `tuning/llm_diagnoser.py` 有内联 import（`import jieba`）、硬编码停用词列表
4. `tuning/llm_diagnoser.py` 在 `llm_factory` 为 None 时返回 mock 数据
5. `validation/layers/layer1_rule_engine.py` 有自己的 `_detect_conflicts`，与 `tuning/conflict_detector.py` 重复

## 引擎架构

```
service/rag_eval/tuning/
├── __init__.py
├── facade.py                # TuningEngineFacade (~80行)
├── advisor.py               # TuningAdvisor (~120行)
├── conflict_detector.py     # ConflictDetector (~80行)
└── impact_analyzer.py       # ImpactAnalyzer (~100行)
```

## 各组件职责

### TuningEngineFacade（门面）

```python
class TuningEngineFacade:
    def __init__(
        self,
        advisor: TuningAdvisor,
        conflict_detector: ConflictDetector,
        impact_analyzer: ImpactAnalyzer,
        suggestion_repo: TuningSuggestionRepository,
    ):
        self._advisor = advisor
        self._conflict_detector = conflict_detector
        self._impact = impact_analyzer
        self._repo = suggestion_repo

    async def analyze(self, run_id: str, metrics: RunMetrics) -> list[TuningSuggestion]:
        """分析指标并生成调优建议
        
        1. 通过 Advisor 生成建议
        2. 通过 ConflictDetector 检测冲突
        3. 通过 ImpactAnalyzer 预估影响
        4. 保存建议到数据库
        """

    async def get_suggestions(self, run_id: str) -> list[TuningSuggestion]:
        """获取指定运行的建议"""

    async def adopt(self, suggestion_id: str) -> None:
        """采纳建议"""

    async def reject(self, suggestion_id: str, reason: str | None) -> None:
        """拒绝建议"""

    async def get_ignored(self) -> list[TuningSuggestion]:
        """获取被忽略的建议"""
```

### TuningAdvisor（调优建议生成器）

融合规则引擎和 LLM 诊断。

```python
class TuningAdvisor:
    def __init__(
        self,
        llm_factory: LLMServiceFactory,
        prompt_manager: PromptManager,
        config_manager: ConfigManager,
    ):
        self._llm_factory = llm_factory
        self._prompt_manager = prompt_manager
        self._config = config_manager

    async def generate_suggestions(self, metrics: RunMetrics, bad_cases: list[TestRunResultItem]) -> list[TuningSuggestion]:
        """生成调优建议
        
        两阶段策略:
        1. 规则引擎: 基于阈值自动生成确定性建议
        2. LLM 诊断: 对 bad cases 进行深度分析
        
        通过 PromptManager 获取 prompt (key: rag.eval.tuning.diagnosis)
        """

    async def _rule_based_suggestions(self, metrics: RunMetrics) -> list[TuningSuggestion]:
        """规则引擎生成确定性建议
        
        规则示例:
        - if context_precision < 0.5: 建议调整 BM25/Vector 权重
        - if faithfulness < 0.7: 建议优化上下文窗口或调整生成策略
        - if noise_sensitivity > 0.5: 建议增加过滤条件
        - if cost_efficiency < 0.3: 建议减少重排序 Top-K 或使用更便宜的模型
        
        规则通过 ConfigManager 配置 (key: rag.eval.tuning.rules)
        """

    async def _llm_diagnosis(self, bad_cases: list[TestRunResultItem], metrics: RunMetrics) -> list[TuningSuggestion]:
        """LLM 深度诊断 bad cases
        
        1. 汇总 bad cases 的共同模式（使用 jieba 分词 + 关键词提取）
        2. 通过 LLM 生成针对性建议
        3. 评估建议的预期影响
        
        停用词列表通过 ConfigManager 配置 (key: rag.eval.tuning.stopwords)
        """

    def _extract_patterns(self, bad_cases: list[TestRunResultItem]) -> dict[str, Any]:
        """从 bad cases 中提取共同模式（替代硬编码停用词和内联jieba）"""
```

### ConflictDetector（冲突检测器）

```python
class ConflictDetector:
    def __init__(self, config_manager: ConfigManager):
        self._config = config_manager

    def detect_conflicts(self, suggestions: list[TuningSuggestion]) -> list[ConflictPair]:
        """检测建议之间的冲突
        
        冲突类型:
        1. 参数冲突: 两个建议修改同一参数到不同值
        2. 效果冲突: 一个建议可能使另一个建议的效果降低
        3. 成本冲突: 多个建议同时采纳导致成本超预算
        """

class ConflictPair(BaseModel):
    suggestion_id_1: str
    suggestion_id_2: str
    conflict_type: Literal['parameter', 'effect', 'cost']
    description: str
    resolution: str  # 建议的解决方式
```

### ImpactAnalyzer（影响分析器）

```python
class ImpactAnalyzer:
    def __init__(
        self,
        history_analyzer: TrendAnalyzer,
        config_manager: ConfigManager,
    ):
        self._history = history_analyzer
        self._config = config_manager

    async def estimate_impact(self, suggestion: TuningSuggestion) -> ImpactEstimate:
        """预估建议的影响
        
        1. 查找历史上类似配置变更的实际效果
        2. 基于历史数据预估指标变化范围
        3. 估算成本变化
        """

    async def preview_config_change(self, suggestion: TuningSuggestion) -> ConfigChangePreview:
        """预览配置变更
        
        展示:
        - 当前配置值 vs 建议值
        - 预估指标变化范围
        - 预估成本变化
        - 受影响的测试用例比例
        """

class ImpactEstimate(BaseModel):
    metric_change_range: tuple[float, float]  # (min, max) 预估变化
    confidence: float                          # 置信度
    cost_delta: float                          # 预估成本变化
    based_on_runs: int                         # 基于的历史运行数

class ConfigChangePreview(BaseModel):
    current_value: Any
    suggested_value: Any
    estimated_impact: ImpactEstimate
    affected_metrics: list[str]
    risk_level: Literal['low', 'medium', 'high']
```

## Prompt Key

| Prompt Key | 用途 |
|---|---|
| `rag.eval.tuning.diagnosis` | LLM 诊断 bad cases 的 prompt |
| `rag.eval.tuning.pattern_extraction` | 从 bad cases 提取共同模式的 prompt |

## 配置 Key

| 配置 Key | 默认值 | 说明 |
|---|---|---|
| `rag.eval.tuning.min_bad_cases` | 3 | 触发 LLM 诊断的最小 bad case 数 |
| `rag.eval.tuning.stopwords` | [...] | 中文停用词列表（JSON） |
| `rag.eval.tuning.rules` | [...] | 规则引擎规则列表（JSON） |
| `rag.eval.tuning.max_suggestions` | 10 | 最大建议数量 |

## 删除的旧代码

- `core/tuning/engine.py` → 被 `TuningEngineFacade` 替代
- `core/tuning/rule_engine.py` → 被合并到 `TuningAdvisor._rule_based_suggestions`
- `core/tuning/history_analyzer.py` → 逻辑合并到 `ImpactAnalyzer`
- `core/tuning/llm_diagnoser.py` → 被 `TuningAdvisor._llm_diagnosis` 替代
- `core/tuning/conflict_detector.py` → 被新的 `ConflictDetector` 替代
- `core/validation/layers/layer1_rule_engine.py` 中的 `_detect_conflicts` → 被统一到 `ConflictDetector`

## 验收标准

1. 调优建议通过规则引擎 + LLM 双阶段生成
2. 无 in-memory cache（使用数据库存储建议）
3. 停用词和规则通过 ConfigManager 配置
4. LLM Prompt 通过 PromptManager 获取
5. `llm_factory` 为 None 时抛出异常而非返回 mock 数据
6. 冲突检测统一到 `ConflictDetector`，无重复实现
7. 每个文件 < 130 行
