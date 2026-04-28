# 09 - TuningEngine 详细设计

## 需求

基于双轨评估结果（三层指标 + 六层诊断），自动生成调优建议，检测建议间冲突，支持建议采纳/拒绝和配置版本回滚。

## 当前问题

| 问题 | 位置 | 影响 |
|------|------|------|
| in-memory cache | `tuning/engine.py` `_suggestion_cache` | 多实例不共享 |
| 未使用方法 | `tuning/history_analyzer.py` `_find_similar_runs` | 死代码 |
| 内联 import | `tuning/llm_diagnoser.py` `import jieba` | 启动变慢 |
| 硬编码停用词 | `tuning/llm_diagnoser.py` | 无法动态调整 |
| mock 数据 | `llm_factory` 为 None 时返回假数据 | 掩盖错误 |
| 重复冲突检测 | `validation/layer1` 和 `tuning/conflict_detector.py` | 逻辑不一致 |
| 无配置回滚 | 调优后无法撤销 | 生产风险 |

## 引擎架构

```
TuningEngineFacade (tuning/facade.py, ~100行)
  ├── TuningAdvisor (tuning/advisor.py, ~150行)
  ├── ConflictDetector (tuning/conflict_detector.py, ~100行)
  └── ConfigChanger (tuning/config_changer.py, ~120行)
```

## 组件设计

### TuningEngineFacade

```python
class TuningEngineFacade:
    def __init__(
        self,
        advisor: TuningAdvisor,
        conflict_detector: ConflictDetector,
        config_changer: ConfigChanger,
        suggestion_repo: TuningSuggestionRepository,
    ): ...

    async def analyze(self, run_id: str, metrics: RunMetrics, diagnosis: DiagnosisResult) -> list[TuningSuggestion]:
        """分析双轨结果并生成调优建议

        1. Advisor 生成建议（规则 + LLM）
        2. ConflictDetector 检测冲突
        3. 标记冲突关系
        4. 保存到数据库
        """

    async def get_suggestions(self, run_id: str) -> list[TuningSuggestion]: ...
    async def adopt(self, suggestion_id: str) -> ConfigVersion:
        """采纳建议：通过 ConfigChanger 应用配置变更"""
    async def reject(self, suggestion_id: str, reason: str | None = None) -> None: ...
    async def ignore(self, suggestion_id: str) -> None: ...
```

### TuningAdvisor

双阶段建议生成：

```python
class TuningAdvisor:
    def __init__(
        self,
        llm_factory: LLMServiceFactory,
        prompt_manager: PromptManager,
        config_manager: ConfigManager,
    ): ...

    async def generate_suggestions(
        self, metrics: RunMetrics, diagnosis: DiagnosisResult, bad_cases: list[TestRunResultItem]
    ) -> list[TuningSuggestion]:
        """两阶段策略：
        1. 规则引擎：基于阈值自动生成确定性建议
        2. LLM 诊断：对 bad cases 深度分析（仅在 bad_cases >= min_bad_cases 时触发）
        """

    async def _rule_based_suggestions(self, metrics: RunMetrics, diagnosis: DiagnosisResult) -> list[TuningSuggestion]:
        """规则引擎示例：
        - context_precision < 0.5 → 建议调整 BM25/Vector 权重
        - faithfulness < 0.7 → 建议优化上下文窗口
        - noise_sensitivity > 0.5 → 建议增加过滤条件
        - cost_efficiency < 0.3 → 建议减少 Top-K 或换更便宜的模型
        - diagnosis.layer3.status == 'fail' → 建议检查提示词
        """

    async def _llm_diagnosis(self, bad_cases: list[TestRunResultItem], metrics: RunMetrics) -> list[TuningSuggestion]:
        """LLM 深度诊断坏案
        
        通过 PromptManager 获取 prompt (key: rag.eval.tuning.diagnosis)
        llm_factory 为 None 时抛 AppException，不返回 mock 数据
        """
```

### ConflictDetector

```python
class ConflictDetector:
    def detect_conflicts(self, suggestions: list[TuningSuggestion]) -> list[ConflictPair]:
        """检测类型：
        1. parameter：两个建议修改同一参数到不同值
        2. effect：一个建议可能使另一个效果降低
        3. cost：多个建议同时采纳导致成本超预算
        """

class ConflictPair(BaseModel):
    suggestion_id_1: str
    suggestion_id_2: str
    conflict_type: Literal['parameter', 'effect', 'cost']
    description: str
    resolution: str
```

### ConfigChanger

```python
class ConfigChanger:
    def __init__(
        self,
        config_version_repo: ConfigVersionRepository,
        change_set_repo: ConfigChangeSetRepository,
        config_cache: ConfigCache,          # 已有基础设施，位于 `core/config/cache.py`
        config_manager: ConfigManager,
    ): ...

    async def apply_suggestion(self, suggestion: TuningSuggestion) -> ConfigVersion:
        """应用建议：
        1. 创建新配置快照
        2. 创建 ConfigVersion 记录
        3. 创建 ConfigChangeSet 记录
        4. 更新 ConfigCache（调用 config_cache.reload()）
        5. 通过 Redis Pub/Sub 发布 config_changed 事件通知其他实例
           （ConfigCache 已订阅该事件，其他实例自动刷新缓存）
        """

    async def rollback(self, change_set_id: str, reason: str) -> None:
        """回滚变更集：
        1. 加载变更前的配置快照
        2. 恢复配置
        3. 更新 ChangeSet 状态为 rolled_back
        4. 更新 ConfigCache 并发布 config_changed 事件
        """
```

## Prompt Key

| Key | 用途 |
|-----|------|
| `rag.eval.tuning.diagnosis` | LLM 诊断 bad cases |
| `rag.eval.tuning.pattern_extraction` | 从 bad cases 提取共同模式 |

## 配置 Key

| Key | 默认值 | 说明 |
|-----|--------|------|
| `rag.eval.tuning.min_bad_cases` | 3 | 触发 LLM 诊断的最小 bad case 数 |
| `rag.eval.tuning.max_suggestions` | 10 | 最大建议数量 |
| `rag.eval.tuning.rules` | [] | 规则引擎规则列表（JSON） |
| `rag.eval.tuning.stopwords` | [] | 中文停用词列表（JSON） |

## 删除的旧代码

- `core/tuning/engine.py` → TuningEngineFacade
- `core/tuning/rule_engine.py` → TuningAdvisor._rule_based_suggestions
- `core/tuning/history_analyzer.py` → TrendAnalyzer + ConfigChanger
- `core/tuning/llm_diagnoser.py` → TuningAdvisor._llm_diagnosis
- `core/tuning/conflict_detector.py` → 新 ConflictDetector
- `core/validation/layers/layer1_rule_engine.py._detect_conflicts` → 统一到 ConflictDetector
- `service/tuning_suggestion_service.py` → TuningEngineFacade
- `service/ignored_suggestion_service.py` → TuningEngineFacade（ignored 状态在 tuning_suggestions 表中）
- `service/config_change_set_service.py` → ConfigChanger
- `service/config_rollback_service.py` → ConfigChanger.rollback

## 验收标准

1. 调优建议通过规则引擎 + LLM 双阶段生成
2. 无 in-memory cache，全部使用数据库存储
3. `llm_factory` 为 None 时抛 `AppException`，不返回 mock 数据
4. 冲突检测统一到 `ConflictDetector`，无重复实现
5. 配置变更通过 `ConfigChanger` 原子执行，支持回滚
6. 每个文件 < 160 行
