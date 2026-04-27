# 01 - 三层评估指标体系

## 需求

设计一套融合 RAGAS、TruLens 和自定义诊断的三层评估指标体系，取代当前的6层堆砌架构。

## 当前问题

1. 6层校验（规则/历史/LLM/质量/效果/回归）层级堆砌，层级间有串行依赖
2. 指标定义与业内 RAGAS/TruLens 标准不对齐
3. 指标计算逻辑分散在多个文件中，难以维护和测试
4. 缺少标准 IR 指标（MRR、NDCG）
5. Faithfulness 使用硬编码阈值（0.65）而非声明式计算

## 设计

### L1 检索质量指标

衡量检索系统本身的效果，不涉及生成质量。

#### L1.1 Context Precision
- **灵感**: RAGAS Context Precision
- **计算**: `∑(precision@k × relevance_k) / ∑relevance_k`，其中 relevance_k 由 LLM 或人工标注判断第 k 个检索结果是否与 query 相关
- **输入**: `query: str`, `retrieved_docs: List[RetrievedDoc]`, `relevance_judgments: List[bool]`
- **输出**: `float` ∈ [0, 1]
- **阈值**: ≥ 0.7 为合格（可配置）

#### L1.2 Context Recall
- **灵感**: RAGAS Context Recall
- **计算**: `相关上下文片段数 / 期望答案所需的总上下文片段数`，由 LLM 将期望答案拆分为声明，逐一判断是否可从检索结果推断
- **输入**: `query: str`, `expected_answer: str`, `retrieved_docs: List[RetrievedDoc]`
- **输出**: `float` ∈ [0, 1]
- **阈值**: ≥ 0.6 为合格（可配置）

#### L1.3 Noise Sensitivity
- **灵感**: RAGAS Noise Sensitivity
- **计算**: `包含无关信息的 top-k 结果数 / top-k 总数`
- **输入**: `query: str`, `retrieved_docs: List[RetrievedDoc]`, `relevance_judgments: List[bool]`
- **输出**: `float` ∈ [0, 1]，越低越好
- **阈值**: ≤ 0.3 为合格（可配置）

#### L1.4 MRR (Mean Reciprocal Rank)
- **灵感**: IR 标准
- **计算**: `1 / 第一个相关结果的排名位置`，对多个 query 取均值
- **输入**: `query: str`, `expected_doc_ids: List[str]`, `ranked_results: List[RetrievedDoc]`
- **输出**: `float` ∈ [0, 1]
- **阈值**: ≥ 0.5 为合格（可配置）

#### L1.5 NDCG (Normalized Discounted Cumulative Gain)
- **灵感**: IR 标准
- **计算**: `DCG / ideal_DCG`，其中 `DCG = ∑(2^rel_i - 1) / log2(i + 1)`
- **输入**: `query: str`, `relevance_grades: Dict[str, int]`, `ranked_results: List[RetrievedDoc]`
- **输出**: `float` ∈ [0, 1]
- **阈值**: ≥ 0.6 为合格（可配置）

### L2 生成质量指标

衡量 RAG 系统生成的答案质量。

#### L2.1 Faithfulness
- **灵感**: RAGAS Faithfulness
- **计算**: `被上下文支持的声明数 / 总声明数`
  1. 将答案拆分为独立声明（LLM 辅助）
  2. 逐一判断每条声明是否可从检索上下文推断
  3. 计算比例
- **输入**: `response: str`, `retrieved_contexts: List[str]`
- **输出**: `float` ∈ [0, 1]
- **阈值**: ≥ 0.8 为合格（可配置）
- **注意**: 当前 `draft_service.py` 中的 `_verify_faithfulness` 使用硬编码 0.65 阈值和 cosine similarity，重构后改用 LLM 辅助的声明拆分+验证方式

#### L2.2 Answer Relevancy
- **灵感**: RAGAS Answer Relevancy
- **计算**: 从答案反向生成问题的平均语义相似度
  1. 从答案中提取关键陈述
  2. 为每条陈述生成可能的原始问题
  3. 计算生成问题与原始问题的 embedding 相似度
  4. 取均值
- **输入**: `question: str`, `response: str`
- **输出**: `float` ∈ [0, 1]
- **阈值**: ≥ 0.7 为合格（可配置）

#### L2.3 Groundedness
- **灵感**: TruLens Groundedness
- **计算**: 答案中每句话的溯源得分的均值
  1. 将答案拆分为句子
  2. 对每句话，检查其在检索上下文中的支持程度（LLM 判断）
  3. 取所有句子的均值
- **输入**: `response: str`, `retrieved_contexts: List[str]`
- **输出**: `float` ∈ [0, 1]
- **阈值**: ≥ 0.75 为合格（可配置）

### L3 系统质量指标

系统级的回归验证和质量保障。

#### L3.1 Rule Compliance
- **灵感**: 当前 Layer1 规则引擎
- **计算**: 规则检查通过数 / 总规则数
- **输入**: `test_results: List[TestResultItem]`
- **输出**: `float` ∈ [0, 1]
- **规则集**: 格式合规、必填项完整、数值范围合法、无语法错误
- **阈值**: 1.0（强制全通过）

#### L3.2 Regression Score
- **灵感**: 当前 Layer6 回归校验
- **计算**: 当前运行指标与历史基线的加权对比
  - 对每个指标，计算 `min(current/baseline, baseline/current)` 得到保持率
  - 加权平均所有指标的保持率
- **输入**: `current_run: TestRunMetrics`, `baseline_run: TestRunMetrics`
- **输出**: `float` ∈ [0, 1]
- **阈值**: ≥ 0.9 为合格（可配置）

#### L3.3 Cost Efficiency
- **灵感**: 当前 Layer6c 成本效益
- **计算**: `质量综合分 / (token_cost × latency)` 的标准化值
- **输入**: `metrics: TestRunMetrics`, `token_usage: TokenUsage`, `latency_ms: float`
- **输出**: `float` ∈ [0, 1]
- **阈值**: 可配置

#### L3.4 Config Stability
- **灵感**: 自定义
- **计算**: 配置变更前后，相同测试集运行结果的稳定性
  - 使用 pairwise 指标变化率：`1 - avg(|metric_new - metric_old| / metric_old)`
- **输入**: `run_before: TestRunMetrics`, `run_after: TestRunMetrics`, `config_diff: Dict`
- **输出**: `float` ∈ [0, 1]
- **阈值**: ≥ 0.95 为合格（可配置）

### 指标计算器接口

所有指标计算器遵循统一接口：

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class MetricInput(BaseModel):
    """指标计算器的统一输入基类"""
    pass

class MetricOutput(BaseModel):
    score: float          # 0-1 归一化分数
    passed: bool          # 是否超过阈值
    details: dict         # 中间计算过程（可解释性）
    threshold: float      # 使用的阈值

class MetricCalculator(ABC):
    @abstractmethod
    async def calculate(self, input_data: MetricInput) -> MetricOutput:
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        pass
    
    @property
    @abstractmethod
    def layer(self) -> int:
        """返回所属层级: 1, 2, 或 3"""
        pass
```

### 指标注册表

```python
class MetricRegistry:
    _calculators: Dict[str, MetricCalculator] = {}
    
    def register(self, calculator: MetricCalculator) -> None:
        self._calculators[calculator.name] = calculator
    
    def get(self, name: str) -> MetricCalculator:
        return self._calculators[name]
    
    def get_by_layer(self, layer: int) -> List[MetricCalculator]:
        return [c for c in self._calculators.values() if c.layer == layer]
    
    def get_all(self) -> List[MetricCalculator]:
        return list(self._calculators.values())
```

### 配置化阈值

所有阈值通过 ConfigManager 管理，key 格式：
```
rag.eval.threshold.{metric_name}
```

示例：
```
rag.eval.threshold.context_precision = 0.7
rag.eval.threshold.faithfulness = 0.8
rag.eval.threshold.regression_score = 0.9
```

## 验收标准

1. 每个指标计算器是独立可测试的，实现 `MetricCalculator` 接口
2. 每个计算器有 ≥5 个单元测试（含边界值）
3. L1 指标计算结果与 RAGAS 官方 Python 库交叉验证（误差 < 5%）
4. 所有阈值可配置，不硬编码
5. 指标注册表支持动态注册新指标
