# 07 - MetricEngine（双轨）详细设计

## 需求

MetricEngine 是最复杂的引擎，包含两个独立子系统：
- **三层标准化指标（Scoring）**：产出 `MetricScore {value, passed, threshold, details}`，用于横向比较和趋势追踪
- **六层诊断引擎（Diagnosis）**：产出 `LayerResult {status, score, issues, suggestions}`，用于具体问题定位和修复建议

两者并行计算，互不依赖。`MetricEngineFacade` 统一对外。

## 当前问题

| 问题 | 位置 | 影响 |
|------|------|------|
| 指标和诊断混杂 | `core/validation/orchestrator.py` | 无法独立调用 |
| 无标准化评分 | 只有定性诊断 | 无法横向比较 |
| 指标计算硬编码 | `scoring.py` 各处 | 阈值修改需改代码 |
| 计算器无注册机制 | 缺失 | 扩展新指标需改核心代码 |
| LLM 诊断可能无模型 | `llm_factory` 为 None | 静默跳过或 mock 数据 |

## 引擎架构

```
MetricEngineFacade (metrics/facade.py, ~120行)
  │
  ├── ScoringFacade (metrics/scoring/facade.py, ~80行)
  │     ├── MetricRegistry (metrics/scoring/registry.py, ~60行)
  │     ├── L1: retrieval.py (~200行)
  │     │     ├── PrecisionAtK (calculators/precision_recall.py, ~80行)
  │     │     ├── ContextRecall (calculators/precision_recall.py)
  │     │     ├── NoiseSensitivity (calculators/precision_recall.py)
  │     │     ├── MRR (calculators/mrr_ndcg.py, ~100行)
  │     │     └── NDCG (calculators/mrr_ndcg.py)
  │     ├── L2: generation.py (~180行)
  │     │     ├── FaithfulnessCalculator (calculators/faithfulness_calc.py, ~120行)
  │     │     ├── AnswerRelevancyCalculator (calculators/answer_relevancy_calc.py, ~120行)
  │     │     └── GroundednessCalculator (calculators/groundedness_calc.py, ~100行)
  │     └── L3: system.py (~150行)
  │           ├── RuleComplianceCalculator
  │           ├── RegressionScoreCalculator
  │           ├── CostEfficiencyCalculator
  │           └── ConfigStabilityCalculator
  │
  └── DiagnosisOrchestrator (metrics/diagnosis/orchestrator.py, ~80行)
        ├── Layer1Rules (metrics/diagnosis/layer1_rules.py, ~100行)
        ├── Layer2History (metrics/diagnosis/layer2_history.py, ~100行)
        ├── Layer3LLM (metrics/diagnosis/layer3_llm.py, ~120行)
        ├── Layer4DataQuality (metrics/diagnosis/layer4_data_quality.py, ~100行)
        ├── Layer5Effect (metrics/diagnosis/layer5_effect.py, ~100行)
        └── Layer6Regression (metrics/diagnosis/layer6_regression.py, ~100行)
```

## 三层标准化指标（Scoring）

### MetricCalculator 抽象基类

```python
class MetricCalculator(ABC):
    """指标计算器基类"""

    @abstractmethod
    async def calculate(self, input_data: MetricInput) -> MetricOutput:
        """计算指标

        input_data 包含检索结果、期望答案、上下文等
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """指标名称，如 'context_precision'"""

    @property
    @abstractmethod
    def layer(self) -> int:
        """所属层级 1/2/3"""

    @property
    @abstractmethod
    def description(self) -> str:
        """指标描述"""

    async def _get_threshold(self) -> float:
        """从 ConfigManager 获取阈值

        key: rag.eval.threshold.{self.name}
        """
```

### MetricInput / MetricOutput

```python
class MetricInput(BaseModel):
    """指标计算输入"""
    run_id: str
    test_case_id: str
    query: str
    retrieved_contexts: list[str]          # 检索到的上下文片段
    expected_knowledge_ids: list[str]      # 期望知识片段 ID
    actual_knowledge_ids: list[str]        # 实际匹配的知识片段 ID
    expected_answer: str | None = None     # 期望答案
    actual_answer: str | None = None       # RAG 生成的实际答案
    execution_time_ms: int = 0
    token_count: int = 0
    cost_usd: float = 0.0

class MetricOutput(BaseModel):
    """指标计算输出"""
    score: float                           # 0-1 归一化
    passed: bool
    threshold: float
    details: dict[str, Any] = {}
```

### MetricRegistry

```python
class MetricRegistry:
    """指标注册表——动态注册和查找计算器"""

    def __init__(self, config_manager: ConfigManager): ...

    def register(self, calculator: MetricCalculator) -> None:
        """注册计算器，按 layer 分组"""

    def get_by_name(self, name: str) -> MetricCalculator:
        """按名称获取，不存在抛 AppException(METRIC_NOT_FOUND)"""

    def get_by_layer(self, layer: int) -> list[MetricCalculator]:
        """获取指定层的所有计算器"""

    def get_all(self) -> list[MetricCalculator]:
        """获取所有已注册计算器"""
```

### ScoringFacade

```python
class ScoringFacade:
    """三层指标计算门面"""

    def __init__(
        self,
        registry: MetricRegistry,
        config_manager: ConfigManager,
        prompt_manager: PromptManager,
        llm_factory: LLMServiceFactory,
        test_run_result_repository: TestRunResultRepository,
        test_run_repository: TestRunRepository,
    ): ...

    async def calculate_all(self, run_id: str) -> RunMetrics:
        """计算完整三层指标

        1. 查询 run 下所有 test_run_results
        2. 为每个 result 构建 MetricInput
        3. 对每个计算器计算单用例指标
        4. 聚合为 RunMetrics（取均值）
        5. 计算加权 overall_score
        6. 保存 l1/l2/l3_metrics_json 到 test_runs
        """

    async def calculate_layer(self, layer: int, run_id: str) -> dict[str, MetricScore]:
        """只计算指定层"""

    async def _aggregate_run_metrics(
        self,
        per_case_results: list[dict[str, MetricOutput]],
    ) -> RunMetrics:
        """从单用例结果聚合为 RunMetrics

        每个指标取所有用例的均值。
        overall_score = l1_weight * l1_avg + l2_weight * l2_avg + l3_weight * l3_avg
        权重从 ConfigManager 读取：rag.eval.weight.l1/l2/l3
        """
```

### L1 计算器：检索质量

**PrecisionAtK** (`calculators/precision_recall.py`)

```python
class PrecisionAtK(MetricCalculator):
    """上下文精确率（灵感来自 RAGAS）

    计算: ∑(precision@k × relevance_k) / ∑relevance_k
    阈值: ≥ 0.7
    """

class ContextRecall(MetricCalculator):
    """上下文召回率（灵感来自 RAGAS）

    计算: 相关上下文片段数 / 期望答案所需总片段数
    阈值: ≥ 0.6
    """

class NoiseSensitivity(MetricCalculator):
    """噪声敏感度（灵感来自 RAGAS）

    计算: 无关结果数 / top-k 总数（越低越好）
    阈值: ≤ 0.3（反转判断 passed）

    算法：
    1. 从 test_run_results 获取 retrieved_doc_ids（检索到的文档 ID 列表）
    2. 从 test_run_results 获取 expected_knowledge_ids（期望知识片段 ID 列表）
    3. 将 expected_knowledge_ids 映射到 source_documents 的文档 ID：
       映射路径：expected_knowledge_ids → 查询 source_documents 的 chunks（通过
       IndexManagerService.get_document_for_chunk(chunk_id) → document_id）
       若索引不可用则降级：将 expected_knowledge_ids 视为文档 ID 进行字符串匹配
       映射结果缓存以 batch_id 为 key，避免重复查询
    4. 无关结果 = retrieved_doc_ids 中不在期望文档集合中的数量
    5. noise_sensitivity = irrelevant_count / len(retrieved_doc_ids)
    6. 若 retrieved_doc_ids 为空，返回 0（无检索则无噪声）
    """
```

**MRR / NDCG** (`calculators/mrr_ndcg.py`)

```python
class MRR(MetricCalculator):
    """平均倒数排名（Mean Reciprocal Rank）

    计算: 1 / 第一个相关结果的排名
    阈值: ≥ 0.5
    """

class NDCG(MetricCalculator):
    """归一化折损累积增益（Normalized DCG）

    计算: DCG / ideal_DCG
    DCG = ∑(rel_i / log2(i+1)) for i in 1..k
    阈值: ≥ 0.6
    """
```

### L2 计算器：生成质量

**FaithfulnessCalculator** (`calculators/faithfulness_calc.py`)

```python
class FaithfulnessCalculator(MetricCalculator):
    """忠实度（灵感来自 RAGAS）

    计算: 被上下文支持的声明数 / 总声明数
    阈值: ≥ 0.8

    流程：
    1. 使用 LLM 从 actual_answer 中提取声明（claims）
       Prompt: rag.eval.metric.faithfulness_extract_claims
    2. 对每个声明，判断是否被 retrieved_contexts 支持
       Prompt: rag.eval.metric.faithfulness_verify_claim
    3. supported_claims / total_claims
    """
```

**AnswerRelevancyCalculator** (`calculators/answer_relevancy_calc.py`)

```python
class AnswerRelevancyCalculator(MetricCalculator):
    """答案相关性（灵感来自 RAGAS）

    计算: 从答案反生成问题的平均 embedding 相似度
    阈值: ≥ 0.7

    流程：
    1. 使用 LLM 从 actual_answer 反生成 3 个可能的问题
       Prompt: rag.eval.metric.answer_relevancy_generate
    2. 计算每个生成问题与原始 query 的 embedding 余弦相似度
    3. 取均值
    """
```

**GroundednessCalculator** (`calculators/groundedness.py`)

```python
class GroundednessCalculator(MetricCalculator):
    """落地度（灵感来自 TruLens）

    计算: 答案每句话在上下文中的溯源得分均值
    阈值: ≥ 0.75

    流程：
    1. 将 actual_answer 拆分为句子
    2. 对每句话，使用 LLM 判断其在 retrieved_contexts 中的支持程度
       Prompt: rag.eval.metric.groundedness
    3. 取均值
    """
```

### L3 计算器：系统质量

**所有 L3 计算器在 `system.py` 中定义（~150 行总计）**

```python
class RuleComplianceCalculator(MetricCalculator):
    """规则合规度

    计算: 规则检查通过数 / 总规则数
    阈值: = 1.0（必须全部通过）

    规则集（与六层诊断 Layer 1 共享规则检查函数，但入口/输出不同）：
    - Layer 1 诊断：调用 _check_rules_for_diagnosis() → LayerResult + issues（定性分析）
    - L3 RuleCompliance：调用 _check_rules_for_scoring() → 0-1 分数（定量评分）

    共享边界设计（防止交叉耦合）：
    ┌─────────────────────────────────────┐
    │  RuleCheckEngine（共享，utils/）     │
    │  ├── check_query_nonempty(item)      │
    │  ├── check_answer_nonempty(item)     │
    │  ├── check_age_range(item)           │
    │  ├── check_domain_valid(item)        │
    │  ├── check_expected_ids(item)        │
    │  ├── check_metric_range(item)        │
    │  ├── check_no_error(item)            │
    │  └── check_timeout(item)             │
    │                                       │
    │  check_all(item) → list[RuleResult]  │  ← 唯一共享接口
    │    RuleResult: {rule_name, passed,   │
    │                 detail, severity}     │
    └──────────┬──────────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
  Layer1Rules     RuleComplianceCalculator
  按 severity      按 passed 计数
  分组输出         输出分数
  LayerResult      0.75 (= 6/8)
  + issues         MetricScore

    检查规则（共 8 条）：
    1. 查询非空且长度 > 0
    2. 答案非空且长度 > 0
    3. 年龄在 [0, 12] 范围内
    4. domain 为合法 TestDomain 枚举值
    5. expected_knowledge_ids 非空
    6. 检索指标（precision/recall/f1）在 [0, 1] 范围内
    7. 无 error_message（执行成功）
    8. execution_time_ms > 0 且 < 超时阈值
    """

class RegressionScoreCalculator(MetricCalculator):
    """回归评分

    计算: min(current/baseline, baseline/current) 加权均值
    阈值: ≥ 0.9
    需要历史基线数据（从上一次 run 获取）
    """

class CostEfficiencyCalculator(MetricCalculator):
    """成本效率

    计算: 质量综合分 / (token_cost × latency) 归一化
    阈值: 可配置

    归一化方式：
    1. 质量综合分 = l1_weight * l1_avg + l2_weight * l2_avg（不含 L3）
    2. 原始成本效率 = quality_score / (total_token_cost_usd + 0.001) / (avg_latency_ms + 1)
    3. 归一化：使用 sigmoid 函数将原始值映射到 [0, 1]
       normalized = sigmoid(raw_value * scale_factor)
       scale_factor 从配置读取（rag.eval.threshold.cost_efficiency_scale，默认 1000）
    4. 若 token_cost 和 latency 均为 0（测试环境），返回 1.0

    该指标衡量"单位成本能获得多少质量"，值越高说明成本效益越好。
    """

class ConfigStabilityCalculator(MetricCalculator):
    """配置稳定性

    计算: 1 - avg(|metric_new - metric_old| / metric_old)
    阈值: ≥ 0.95
    需要上一次 run 的指标数据
    """
```

## 六层诊断引擎（Diagnosis）

### DiagnosisOrchestrator

```python
class DiagnosisOrchestrator:
    """六层诊断编排器"""

    def __init__(
        self,
        layers: dict[int, DiagnosisLayer],  # {1: Layer1Rules, ..., 6: Layer6Regression}
        config_manager: ConfigManager,
    ): ...

    async def run_all(self, run_id: str) -> DiagnosisResult:
        """执行全部 6 层诊断

        按顺序执行 1→6，每层独立，前一层失败不阻塞后续。
        并发控制：rag.eval.diagnosis.concurrency
        超时：rag.eval.diagnosis.timeout_ms
        """

    async def run_layer(self, layer: int, run_id: str) -> LayerResult:
        """只执行指定层"""
```

### 层接口

```python
class DiagnosisLayer(ABC):
    """诊断层基类"""

    @property
    @abstractmethod
    def layer_number(self) -> int: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def diagnose(
        self,
        run_id: str,
        results: list[TestRunResultItem],
        run_data: TestRunRead,
    ) -> LayerResult:
        """执行该层诊断"""
```

### Layer 1: 规则引擎 (`layer1_rules.py`)

```python
class Layer1Rules(DiagnosisLayer):
    """检查测试结果的格式合规性

    检查项：
    - 格式合规：查询非空、答案非空、年龄合法
    - 必填完整：期望知识点非空、领域已填
    - 数值合法：年龄在 [0, 12]、分数在 [0, 1]
    - 语法正确：无乱码、无截断、无 JSON 格式错误

    注意：所有规则检查函数委托给共享的 RuleCheckEngine（utils/rule_check_engine.py），
    Layer1Rules 仅负责将 RuleResult 列表按 severity 分组、构建 LayerResult。
    与 L3 RuleComplianceCalculator 的关系见上方共享边界图。
    """
```

### Layer 2: 历史对比 (`layer2_history.py`)

```python
class Layer2History(DiagnosisLayer):
    """与历史基线对比，检测异常退化

    检查项：
    - 指标退化：核心指标低于历史均值超过阈值
    - 新增失败：之前通过的用例现在失败
    - 回答质量变化：回答长度/结构显著偏离历史基线

    依赖：查询上一次同测试集的 run 作为基线
    """
```

### Layer 3: LLM 诊断 (`layer3_llm.py`)

```python
class Layer3LLM(DiagnosisLayer):
    """使用 LLM 对失败用例进行深度分析

    检查项：
    - 偏离分析：回答是否偏离期望答案核心观点
    - 幻觉检测：回答是否包含源文档中不存在的信息
    - 相关性判断：检索到的上下文是否与问题真正相关

    Prompt keys:
    - rag.eval.diagnosis.layer3.deviation_analysis
    - rag.eval.diagnosis.layer3.hallucination_detection

    关键约束：
    - llm_factory 为 None 时抛 AppException，不使用 mock 数据
    - rag.eval.diagnosis.layer3.enabled = false 时跳过
    """
```

### Layer 4: 数据质量 (`layer4_data_quality.py`)

```python
class Layer4DataQuality(DiagnosisLayer):
    """检查底层数据的质量

    检查项：
    - Golden 覆盖度：核心测试用例的覆盖比例
    - 分块质量：检索到的分块是否完整、有信息量
    - 文档时效性：文档是否过期或需要更新
    """
```

### Layer 5: 效果评估 (`layer5_effect.py`)

```python
class Layer5Effect(DiagnosisLayer):
    """评估 RAG 系统的综合效果

    检查项：
    - Embedding 质量：相似文档的 embedding 距离是否合理
    - 意图识别：查询意图是否被正确识别
    - 错误模式：失败用例的共性模式分析

    Prompt key: rag.eval.diagnosis.layer5.error_pattern
    """
```

### Layer 6: 回归检测 (`layer6_regression.py`)

```python
class Layer6Regression(DiagnosisLayer):
    """检测系统变更后的整体回归

    检查项：
    - 全局回归：综合指标与基线的对比
    - 交叉验证：不同测试集之间的一致性
    - 成本效果：质量提升是否值得额外成本
    """
```

## MetricEngineFacade

```python
class MetricEngineFacade:
    """双轨评估统一门面"""

    def __init__(
        self,
        scoring_facade: ScoringFacade,
        diagnosis_orchestrator: DiagnosisOrchestrator,
        config_manager: ConfigManager,
    ): ...

    async def calculate_all(self, run_id: str) -> RunMetrics:
        """计算三层标准化指标"""
        return await self._scoring.calculate_all(run_id)

    async def diagnose_all(self, run_id: str) -> DiagnosisResult:
        """执行六层诊断"""
        return await self._diagnosis.run_all(run_id)

    async def calculate_and_diagnose(
        self, run_id: str,
    ) -> tuple[RunMetrics, DiagnosisResult]:
        """并行执行双轨评估"""
        metrics, diagnosis = await asyncio.gather(
            self.calculate_all(run_id),
            self.diagnose_all(run_id),
        )
        return metrics, diagnosis

    async def calculate_layer(
        self, layer: int, run_id: str,
    ) -> dict[str, MetricScore]:
        """只计算指定层的三层指标"""

    async def diagnose_layer(
        self, layer: int, run_id: str,
    ) -> LayerResult:
        """只执行指定层的诊断"""
```

## DI 注册

```python
class RagEvalModule(Module):
    # 三层指标计算器
    @provider @singleton
    def provide_precision_at_k(self, ...) -> PrecisionAtK: ...
    @provider @singleton
    def provide_context_recall(self, ...) -> ContextRecall: ...
    @provider @singleton
    def provide_noise_sensitivity(self, ...) -> NoiseSensitivity: ...
    @provider @singleton
    def provide_mrr(self, ...) -> MRR: ...
    @provider @singleton
    def provide_ndcg(self, ...) -> NDCG: ...
    @provider @singleton
    def provide_faithfulness_calculator(self, ...) -> FaithfulnessCalculator: ...
    @provider @singleton
    def provide_answer_relevancy_calculator(self, ...) -> AnswerRelevancyCalculator: ...
    @provider @singleton
    def provide_groundedness_calculator(self, ...) -> GroundednessCalculator: ...
    @provider @singleton
    def provide_rule_compliance_calculator(self, ...) -> RuleComplianceCalculator: ...
    @provider @singleton
    def provide_regression_score_calculator(self, ...) -> RegressionScoreCalculator: ...
    @provider @singleton
    def provide_cost_efficiency_calculator(self, ...) -> CostEfficiencyCalculator: ...
    @provider @singleton
    def provide_config_stability_calculator(self, ...) -> ConfigStabilityCalculator: ...

    @provider @singleton
    def provide_metric_registry(self, ...) -> MetricRegistry:
        registry = MetricRegistry(...)
        for calc in [precision_at_k, context_recall, ...]:
            registry.register(calc)
        return registry

    # 六层诊断
    @provider @singleton
    def provide_layer1_rules(self, ...) -> Layer1Rules: ...
    # ... layer2-layer6 同理

    @provider @singleton
    def provide_diagnosis_orchestrator(self, ...) -> DiagnosisOrchestrator: ...

    # Facades
    @provider @singleton
    def provide_scoring_facade(self, ...) -> ScoringFacade: ...
    @provider @singleton
    def provide_metric_engine_facade(self, ...) -> MetricEngineFacade: ...
```

## 配置 Key

### 三层指标阈值

| Key | 默认值 | 说明 |
|-----|--------|------|
| `rag.eval.threshold.context_precision` | 0.7 | L1 Context Precision |
| `rag.eval.threshold.context_recall` | 0.6 | L1 Context Recall |
| `rag.eval.threshold.noise_sensitivity` | 0.3 | L1 Noise Sensitivity |
| `rag.eval.threshold.mrr` | 0.5 | L1 MRR |
| `rag.eval.threshold.ndcg` | 0.6 | L1 NDCG |
| `rag.eval.threshold.faithfulness` | 0.8 | L2 Faithfulness |
| `rag.eval.threshold.answer_relevancy` | 0.7 | L2 Answer Relevancy |
| `rag.eval.threshold.groundedness` | 0.75 | L2 Groundedness |
| `rag.eval.threshold.regression_score` | 0.9 | L3 Regression Score |
| `rag.eval.threshold.cost_efficiency` | 0.5 | L3 Cost Efficiency |
| `rag.eval.threshold.config_stability` | 0.95 | L3 Config Stability |

### 权重

| Key | 默认值 | 说明 |
|-----|--------|------|
| `rag.eval.weight.l1` | 0.4 | L1 权重 |
| `rag.eval.weight.l2` | 0.4 | L2 权重 |
| `rag.eval.weight.l3` | 0.2 | L3 权重 |

### 六层诊断配置

| Key | 默认值 | 说明 |
|-----|--------|------|
| `rag.eval.diagnosis.timeout_ms` | 60000 | 诊断超时 |
| `rag.eval.diagnosis.concurrency` | 3 | 诊断并发 |
| `rag.eval.diagnosis.layer3.enabled` | true | LLM 诊断开关 |
| `rag.eval.diagnosis.layer3.model` | "" | LLM 诊断专用模型 |
| `rag.eval.diagnosis.layer4.golden_case_ids` | [] | Golden 用例 ID |

## Prompt Key

### 三层指标

| Key | 用途 |
|-----|------|
| `rag.eval.metric.faithfulness_extract_claims` | 从答案中提取声明 |
| `rag.eval.metric.faithfulness_verify_claim` | 验证声明是否被上下文支持 |
| `rag.eval.metric.answer_relevancy_generate` | 从答案反生成问题 |
| `rag.eval.metric.groundedness` | 判断答案句子在上下文中的支持度 |

### 六层诊断

| Key | 用途 |
|-----|------|
| `rag.eval.diagnosis.layer3.deviation_analysis` | 偏离分析 |
| `rag.eval.diagnosis.layer3.hallucination_detection` | 幻觉检测 |
| `rag.eval.diagnosis.layer5.error_pattern` | 错误模式分析 |

## 验收标准

1. 所有文件 ≤ 200 行（`retrieval.py` ≤ 200 行为最长文件）
2. `MetricCalculator` ABC 定义在 `metrics/scoring/base.py`
3. `MetricRegistry` 支持动态注册，扩展新指标无需修改 `ScoringFacade`
4. 三层指标聚合逻辑正确：`overall_score = Σ(weight_i × avg_score_i)`
5. L1 指标与 RAGAS 官方库交叉验证误差 < 10%
6. L2 指标（Faithfulness/AnswerRelevancy/Groundedness）均使用 LLM 辅助计算
7. L3 指标中 `RegressionScoreCalculator` 和 `ConfigStabilityCalculator` 正确获取历史基线
8. `NoiseSensitivity` 反转判断：score ≤ threshold 时 passed = true
9. 六层诊断按 1→6 顺序执行，单层失败不阻塞后续
10. Layer 3 LLM 诊断：`llm_factory` 为 None 时抛 `AppException`，不返回 mock 数据
11. Layer 3 可通过 `rag.eval.diagnosis.layer3.enabled` 开关控制
12. 每个三层指标计算器有 ≥ 5 个测试用例
13. 每个六层诊断层有 ≥ 5 个测试用例
14. `MetricEngineFacade` 通过 `RagEvalModule` DI 注入
15. 所有阈值从 `ConfigManager` 读取，无硬编码
16. 所有 Prompt 从 `PromptManager` 获取，无硬编码
17. `MetricOutput.details` 包含足够信息用于报告展示（如声明列表、匹配排名等）
