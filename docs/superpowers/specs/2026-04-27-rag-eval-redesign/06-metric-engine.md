# 06 - 指标引擎详细设计

## 需求

设计三层评估指标的计算引擎，替代当前分散在 `core/validation/` 和 `core/tuning/` 中的指标计算逻辑。

## 当前问题

1. 6层校验引擎（13个文件，~2000行）层级堆砌，子层通过脆弱的字符串替换聚合
2. 指标计算与诊断逻辑混杂（Layer1 既计算指标又检测冲突）
3. LLM 调用在 Layer3 创建新的 `LLMServiceFactory` 实例，未使用 DI
4. 当前指标与 RAGAS 标准不对齐（无 Context Precision/Recall/MRR/NDCG）
5. `tuning/engine.py` 的 in-memory cache 应使用 Redis

## 引擎架构

```
service/rag_eval/metrics/
├── __init__.py
├── facade.py                # MetricEngineFacade (~100行)
├── registry.py              # MetricRegistry (~60行)
├── base.py                  # MetricCalculator 接口 (~40行)
├── retrieval_quality.py     # L1: 检索质量指标 (~200行)
├── generation_quality.py    # L2: 生成质量指标 (~180行)
├── system_quality.py        # L3: 系统质量指标 (~150行)
└── calculators/             # 原子计算器
    ├── __init__.py
    ├── precision_recall.py  # Precision@K, Recall@K (~80行)
    ├── mrr_ndcg.py          # MRR, NDCG 计算 (~100行)
    ├── faithfulness_calc.py # RAGAS Faithfulness (~120行)
    └── groundedness_calc.py # TruLens Groundedness (~100行)
```

## MetricCalculator 接口

```python
# base.py
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any

class MetricInput(BaseModel):
    """指标输入基类，每个计算器定义自己的子类"""
    pass

class MetricOutput(BaseModel):
    score: float
    passed: bool
    details: dict[str, Any]
    threshold: float

class MetricCalculator(ABC):
    @abstractmethod
    async def calculate(self, input_data: MetricInput) -> MetricOutput:
        pass

    @property
    @abstractmethod
    def name(self) -> str: pass

    @property
    @abstractmethod
    def layer(self) -> int: pass

    @property
    @abstractmethod
    def description(self) -> str: pass
```

## L1 检索质量指标

### calculators/precision_recall.py

```python
class PrecisionAtKInput(MetricInput):
    relevance_judgments: list[bool]  # 按排名顺序，每个结果是否相关

class PrecisionAtK(MetricCalculator):
    name = "context_precision"
    layer = 1

    async def calculate(self, input_data: PrecisionAtKInput) -> MetricOutput:
        judgments = input_data.relevance_judgments
        if not judgments:
            return MetricOutput(score=0.0, passed=False, details={}, threshold=self._threshold)
        
        # RAGAS Context Precision: 加权精确率
        weighted_sum = 0.0
        relevant_count = 0
        for k, is_relevant in enumerate(judgments, 1):
            if is_relevant:
                relevant_count += 1
                precision_at_k = relevant_count / k
                weighted_sum += precision_at_k
        
        score = weighted_sum / max(relevant_count, 1)
        threshold = await self._get_threshold()
        return MetricOutput(
            score=score,
            passed=score >= threshold,
            details={"relevant_count": relevant_count, "total": len(judgments)},
            threshold=threshold,
        )


class ContextRecallInput(MetricInput):
    expected_claims: list[str]       # 期望答案中的声明列表
    retrieved_contexts: list[str]    # 检索到的上下文

class ContextRecall(MetricCalculator):
    name = "context_recall"
    layer = 1

    async def calculate(self, input_data: ContextRecallInput) -> MetricOutput:
        # 对每个声明，判断是否能从检索上下文推断
        supported = 0
        claim_details = []
        for claim in input_data.expected_claims:
            is_supported = await self._check_claim_support(
                claim, input_data.retrieved_contexts
            )
            if is_supported:
                supported += 1
            claim_details.append({"claim": claim, "supported": is_supported})
        
        score = supported / max(len(input_data.expected_claims), 1)
        threshold = await self._get_threshold()
        return MetricOutput(
            score=score,
            passed=score >= threshold,
            details={"supported": supported, "total": len(input_data.expected_claims), "claims": claim_details},
            threshold=threshold,
        )
```

### calculators/mrr_ndcg.py

```python
class MRRInput(MetricInput):
    expected_doc_ids: list[str]
    ranked_doc_ids: list[str]

class MeanReciprocalRank(MetricCalculator):
    name = "mrr"
    layer = 1

    async def calculate(self, input_data: MRRInput) -> MetricOutput:
        for rank, doc_id in enumerate(input_data.ranked_doc_ids, 1):
            if doc_id in input_data.expected_doc_ids:
                score = 1.0 / rank
                threshold = await self._get_threshold()
                return MetricOutput(
                    score=score,
                    passed=score >= threshold,
                    details={"first_relevant_rank": rank},
                    threshold=threshold,
                )
        return MetricOutput(score=0.0, passed=False, details={"first_relevant_rank": None}, threshold=0.0)


class NDCGInput(MetricInput):
    relevance_grades: dict[str, int]  # doc_id → relevance grade (0, 1, 2...)
    ranked_doc_ids: list[str]

class NormalizedDCG(MetricCalculator):
    name = "ndcg"
    layer = 1

    async def calculate(self, input_data: NDCGInput) -> MetricOutput:
        # DCG = sum((2^rel - 1) / log2(i + 1))
        dcg = sum(
            (2 ** input_data.relevance_grades.get(doc_id, 0) - 1) / math.log2(i + 1)
            for i, doc_id in enumerate(input_data.ranked_doc_ids, 1)
        )
        # Ideal DCG
        ideal_grades = sorted(input_data.relevance_grades.values(), reverse=True)
        idcg = sum(
            (2 ** grade - 1) / math.log2(i + 1)
            for i, grade in enumerate(ideal_grades, 1)
        )
        score = dcg / max(idcg, 1e-10)
        threshold = await self._get_threshold()
        return MetricOutput(
            score=score,
            passed=score >= threshold,
            details={"dcg": dcg, "idcg": idcg},
            threshold=threshold,
        )
```

## L2 生成质量指标

### calculators/faithfulness_calc.py

```python
class FaithfulnessInput(MetricInput):
    response: str
    retrieved_contexts: list[str]

class FaithfulnessCalculator(MetricCalculator):
    name = "faithfulness"
    layer = 2

    def __init__(self, llm_factory: LLMServiceFactory, config_manager: ConfigManager):
        self._llm_factory = llm_factory
        self._config = config_manager

    async def calculate(self, input_data: FaithfulnessInput) -> MetricOutput:
        # Step 1: 将答案拆分为独立声明（LLM辅助）
        claims = await self._extract_claims(input_data.response)
        
        # Step 2: 逐一判断声明是否可从上下文推断
        supported = 0
        claim_verdicts = []
        for claim in claims:
            is_supported = await self._verify_claim(claim, input_data.retrieved_contexts)
            if is_supported:
                supported += 1
            claim_verdicts.append({"claim": claim, "supported": is_supported})
        
        # Step 3: 计算忠实度
        score = supported / max(len(claims), 1)
        threshold = await self._get_threshold()
        return MetricOutput(
            score=score,
            passed=score >= threshold,
            details={"supported": supported, "total": len(claims), "claims": claim_verdicts},
            threshold=threshold,
        )

    async def _extract_claims(self, response: str) -> list[str]:
        """使用 LLM 将答案拆分为独立声明"""
        # 通过 PromptManager 获取 prompt (key: rag.eval.metric.faithfulness_extract_claims)

    async def _verify_claim(self, claim: str, contexts: list[str]) -> bool:
        """使用 LLM 判断声明是否可从上下文推断"""
        # 通过 PromptManager 获取 prompt (key: rag.eval.metric.faithfulness_verify_claim)
```

### calculators/groundedness_calc.py

```python
class GroundednessInput(MetricInput):
    response: str
    retrieved_contexts: list[str]

class GroundednessCalculator(MetricCalculator):
    name = "groundedness"
    layer = 2

    async def calculate(self, input_data: GroundednessInput) -> MetricOutput:
        # Step 1: 将答案拆分为句子
        sentences = self._split_into_sentences(input_data.response)
        
        # Step 2: 对每句话，计算其与上下文的溯源得分
        sentence_scores = []
        for sentence in sentences:
            score = await self._groundedness_score(sentence, input_data.retrieved_contexts)
            sentence_scores.append({"sentence": sentence, "score": score})
        
        # Step 3: 取均值
        avg_score = sum(s["score"] for s in sentence_scores) / max(len(sentence_scores), 1)
        threshold = await self._get_threshold()
        return MetricOutput(
            score=avg_score,
            passed=avg_score >= threshold,
            details={"sentence_count": len(sentences), "sentences": sentence_scores},
            threshold=threshold,
        )
```

## L3 系统质量指标

### system_quality.py

```python
class RuleComplianceCalculator(MetricCalculator):
    """规则合规性：格式/必填/语法检查"""
    name = "rule_compliance"
    layer = 3
    
    async def calculate(self, input_data: RuleComplianceInput) -> MetricOutput:
        rules = self._get_rules()  # 从 ConfigManager 获取规则集
        passed = 0
        failures = []
        for rule in rules:
            result = rule.check(input_data.test_results)
            if result.passed:
                passed += 1
            else:
                failures.append(result)
        score = passed / max(len(rules), 1)
        return MetricOutput(score=score, passed=score >= 1.0, details={"failures": failures}, threshold=1.0)


class RegressionScoreCalculator(MetricCalculator):
    """回归得分：与历史基线对比"""
    name = "regression_score"
    layer = 3
    
    async def calculate(self, input_data: RegressionInput) -> MetricOutput:
        metric_names = ['context_precision', 'context_recall', 'faithfulness', 'answer_relevancy']
        retention_rates = []
        for metric in metric_names:
            current = getattr(input_data.current_metrics, metric, 0)
            baseline = getattr(input_data.baseline_metrics, metric, 0)
            if baseline > 0:
                retention = min(current / baseline, baseline / current)
            else:
                retention = 1.0 if current == 0 else 0.0
            retention_rates.append(retention)
        score = sum(retention_rates) / len(retention_rates)
        threshold = await self._get_threshold()
        return MetricOutput(score=score, passed=score >= threshold, details={...}, threshold=threshold)


class CostEfficiencyCalculator(MetricCalculator):
    """成本效率：质量/成本比"""
    name = "cost_efficiency"
    layer = 3


class ConfigStabilityCalculator(MetricCalculator):
    """配置稳定性：配置变更前后一致性"""
    name = "config_stability"
    layer = 3
```

## MetricRegistry

```python
# registry.py
class MetricRegistry:
    def __init__(self):
        self._calculators: dict[str, MetricCalculator] = {}

    def register(self, calculator: MetricCalculator) -> None:
        self._calculators[calculator.name] = calculator

    def get(self, name: str) -> MetricCalculator:
        if name not in self._calculators:
            raise AppException(error_code="METRIC_NOT_FOUND", ...)
        return self._calculators[name]

    def get_by_layer(self, layer: int) -> list[MetricCalculator]:
        return [c for c in self._calculators.values() if c.layer == layer]

    def get_all(self) -> list[MetricCalculator]:
        return list(self._calculators.values())
```

## MetricEngineFacade

```python
# facade.py
class MetricEngineFacade:
    def __init__(self, registry: MetricRegistry, config_manager: ConfigManager):
        self._registry = registry
        self._config = config_manager

    async def calculate_all(self, run_id: str) -> RunMetrics:
        """计算所有三层指标"""
        run_data = await self._load_run_data(run_id)
        
        l1 = await self._calculate_layer(1, run_data)
        l2 = await self._calculate_layer(2, run_data)
        l3 = await self._calculate_layer(3, run_data)
        
        overall = self._compute_overall(l1, l2, l3)
        return RunMetrics(l1=l1, l2=l2, l3=l3, overall_score=overall, calculated_at=datetime.now())

    async def calculate_layer(self, layer: int, run_id: str) -> dict[str, MetricScore]:
        """只计算指定层的指标"""
        run_data = await self._load_run_data(run_id)
        return await self._calculate_layer(layer, run_data)

    async def _calculate_layer(self, layer: int, run_data: RunData) -> dict[str, MetricScore]:
        calculators = self._registry.get_by_layer(layer)
        results = {}
        for calc in calculators:
            input_data = self._prepare_input(calc.name, run_data)
            output = await calc.calculate(input_data)
            results[calc.name] = MetricScore(
                value=output.score,
                passed=output.passed,
                threshold=output.threshold,
                details=output.details,
            )
        return results

    def _compute_overall(self, l1: dict, l2: dict, l3: dict) -> float:
        """加权计算总分
        
        权重通过 ConfigManager 配置:
        - rag.eval.weight.l1 (默认 0.4)
        - rag.eval.weight.l2 (默认 0.4)
        - rag.eval.weight.l3 (默认 0.2)
        """
```

## 与旧代码的关系

以下旧代码在重构完成后删除：
- `core/validation/orchestrator.py` → 替换为 `MetricEngineFacade`
- `core/validation/layers/layer1_rule_engine.py` → 拆分到 `RuleComplianceCalculator`
- `core/validation/layers/layer3_llm.py` → 拆分到 `FaithfulnessCalculator` + `GroundednessCalculator`
- `core/validation/layers/layer4*.py` → 部分逻辑合并到 L1 指标
- `core/validation/layers/layer5*.py` → 部分逻辑合并到 L2 指标
- `core/validation/layers/layer6*.py` → 拆分到 L3 各计算器
- `core/tuning/engine.py` → TuningEngine（下一节）

## Prompt Key 定义

| Prompt Key | 用途 |
|---|---|
| `rag.eval.metric.faithfulness_extract_claims` | 从答案中提取独立声明 |
| `rag.eval.metric.faithfulness_verify_claim` | 验证声明是否可从上下文推断 |
| `rag.eval.metric.answer_relevancy` | 答案相关性评估 |
| `rag.eval.metric.groundedness` | 句子溯源评估 |
| `rag.eval.metric.context_recall_verify` | 声明与上下文匹配判断 |

## 配置 Key 定义

| 配置 Key | 默认值 | 说明 |
|---|---|---|
| `rag.eval.threshold.context_precision` | 0.7 | Context Precision 阈值 |
| `rag.eval.threshold.context_recall` | 0.6 | Context Recall 阈值 |
| `rag.eval.threshold.noise_sensitivity` | 0.3 | Noise Sensitivity 阈值（越低越好） |
| `rag.eval.threshold.mrr` | 0.5 | MRR 阈值 |
| `rag.eval.threshold.ndcg` | 0.6 | NDCG 阈值 |
| `rag.eval.threshold.faithfulness` | 0.8 | Faithfulness 阈值 |
| `rag.eval.threshold.answer_relevancy` | 0.7 | Answer Relevancy 阈值 |
| `rag.eval.threshold.groundedness` | 0.75 | Groundedness 阈值 |
| `rag.eval.threshold.regression_score` | 0.9 | 回归得分阈值 |
| `rag.eval.threshold.cost_efficiency` | 0.5 | 成本效率阈值 |
| `rag.eval.threshold.config_stability` | 0.95 | 配置稳定性阈值 |
| `rag.eval.weight.l1` | 0.4 | L1 层权重 |
| `rag.eval.weight.l2` | 0.4 | L2 层权重 |
| `rag.eval.weight.l3` | 0.2 | L3 层权重 |

## 验收标准

1. 每个计算器实现 `MetricCalculator` 接口
2. 每个计算器有 ≥5 个单元测试（含边界值：空输入、全相关、全不相关）
3. L1 指标（Precision/Recall/MRR/NDCG）与 RAGAS 库交叉验证（误差 < 5%）
4. 所有阈值通过 ConfigManager 获取
5. 所有 LLM Prompt 通过 PromptManager 获取
6. 计算器之间无依赖，可并行计算
7. 每个文件 < 200 行
