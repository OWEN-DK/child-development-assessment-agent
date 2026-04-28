# 03 - 双轨评估体系

## 设计理念

| 轨道 | 产出 | 定位 | 类比 |
|------|------|------|------|
| **三层标准化指标** | `MetricScore {value, passed, threshold, details}` | 得分卡——告诉你"考了多少分" | 考试成绩单 |
| **六层诊断引擎** | `LayerResult {status, score, issues, suggestions}` | 体检报告——告诉你"哪里有问题、怎么修" | 医学诊断 |

两者**并行计算**，互不依赖：
- 三层指标提供标准化得分，适合跨系统比较和趋势追踪
- 六层诊断提供具体问题定位和修复建议，适合深度调试

## 三层标准化指标（Scoring Track）

### L1 检索质量

| 指标 | 灵感 | 计算 | 阈值 |
|------|------|------|------|
| Context Precision | RAGAS | `∑(precision@k × relevance_k) / ∑relevance_k` | ≥ 0.7 |
| Context Recall | RAGAS | `相关上下文片段数 / 期望答案所需总片段数` | ≥ 0.6 |
| Noise Sensitivity | RAGAS | `无关结果数 / top-k 总数`（越低越好） | ≤ 0.3 |
| MRR | IR 标准 | `1 / 第一个相关结果的排名` | ≥ 0.5 |
| NDCG | IR 标准 | `DCG / ideal_DCG` | ≥ 0.6 |

### L2 生成质量

| 指标 | 灵感 | 计算 | 阈值 |
|------|------|------|------|
| Faithfulness | RAGAS | `被上下文支持的声明数 / 总声明数` | ≥ 0.8 |
| Answer Relevancy | RAGAS | 从答案反生成问题的平均 embedding 相似度 | ≥ 0.7 |
| Groundedness | TruLens | 答案每句话在上下文中的溯源得分均值 | ≥ 0.75 |

### L3 系统质量

| 指标 | 计算 | 阈值 |
|------|------|------|
| Rule Compliance | `规则检查通过数 / 总规则数`（与六层 Layer 1 共享规则引擎，L3 出分数，Layer 1 出问题列表） | = 1.0 |
| Regression Score | `min(current/baseline, baseline/current)` 加权均值 | ≥ 0.9 |
| Cost Efficiency | `质量综合分 / (token_cost × latency)` 归一化 | 可配置 |
| Config Stability | `1 - avg(|metric_new - metric_old| / metric_old)` | ≥ 0.95 |

### 接口

```python
class MetricScore(BaseModel):
    value: float              # 0-1 归一化
    passed: bool
    threshold: float
    details: dict[str, Any] = {}

class Layer1Metrics(BaseModel):
    context_precision: MetricScore
    context_recall: MetricScore
    noise_sensitivity: MetricScore
    mrr: MetricScore
    ndcg: MetricScore

class Layer2Metrics(BaseModel):
    faithfulness: MetricScore
    answer_relevancy: MetricScore
    groundedness: MetricScore

class Layer3Metrics(BaseModel):
    rule_compliance: MetricScore
    regression_score: MetricScore
    cost_efficiency: MetricScore
    config_stability: MetricScore

class RunMetrics(BaseModel):
    l1: Layer1Metrics
    l2: Layer2Metrics
    l3: Layer3Metrics
    overall_score: float
    weights: dict[str, float]  # {"l1": 0.4, "l2": 0.4, "l3": 0.2}
    calculated_at: datetime
```

### 指标计算器接口

```python
class MetricCalculator(ABC):
    @abstractmethod
    async def calculate(self, input_data: MetricInput) -> MetricOutput: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def layer(self) -> int: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    async def _get_threshold(self) -> float:
        """从 ConfigManager 获取阈值，key: rag.eval.threshold.{name}"""
        ...

class MetricOutput(BaseModel):
    score: float
    passed: bool
    details: dict[str, Any]
    threshold: float
```

## 六层诊断引擎（Diagnosis Track）

### 与三层指标的关系

```
三层指标是"量化评分"：每个指标输出 0-1 分数，用于横向比较
六层诊断是"定性分析"：每层输出问题列表和修复建议，用于深度调试

三层中 Faithfulness 低的用例 → 六层 Layer3 LLM诊断会深入分析为什么
三层中 Regression Score 低 → 六层 Layer6 会对比具体退化项
三层中 Rule Compliance 不足 → 六层 Layer1 会列出具体违规项

两者互补，不重复
```

### Layer 1: 规则引擎

检查测试结果的格式合规性。

| 检查项 | 说明 |
|--------|------|
| 格式合规 | 查询非空、答案非空、年龄合法 |
| 必填完整 | 期望知识点非空、领域已填 |
| 数值合法 | 年龄在 [0, 12] 范围、分数在 [0, 1] |
| 语法正确 | 无乱码、无截断、无 JSON 格式错误 |

### Layer 2: 历史对比

与历史基线对比，检测异常退化。

| 检查项 | 说明 |
|--------|------|
| 指标退化 | 任何核心指标低于历史均值超过阈值 |
| 新增失败 | 之前通过的用例现在失败 |
| 回答质量变化 | 回答长度/结构显著偏离历史基线 |

### Layer 3: LLM 诊断

使用 LLM 对失败用例进行深度分析。

| 检查项 | 说明 |
|--------|------|
| 偏离分析 | 回答是否偏离了期望答案的核心观点 |
| 幻觉检测 | 回答是否包含源文档中不存在的信息 |
| 相关性判断 | 检索到的上下文是否与问题真正相关 |

### Layer 4: 数据质量

检查底层数据的质量。

| 检查项 | 说明 |
|--------|------|
| Golden 覆盖度 | 核心测试用例的覆盖比例 |
| 分块质量 | 检索到的分块是否完整、有信息量 |
| 文档时效性 | 文档是否过期或需要更新 |

### Layer 5: 效果评估

评估 RAG 系统的综合效果。

| 检查项 | 说明 |
|--------|------|
| Embedding 质量 | 相似文档的 embedding 距离是否合理 |
| 意图识别 | 查询意图是否被正确识别 |
| 错误模式 | 失败用例的共性模式分析 |

### Layer 6: 回归检测

检测系统变更后的整体回归。

| 检查项 | 说明 |
|--------|------|
| 全局回归 | 综合指标与基线的对比 |
| 交叉验证 | 不同测试集之间的一致性 |
| 成本效果 | 质量提升是否值得额外成本 |

### 接口

```python
class LayerIssue(BaseModel):
    """单个诊断问题"""
    severity: Literal['critical', 'warning', 'info']
    category: str          # 问题类别
    description: str       # 问题描述
    affected_items: list[str] = []  # 受影响的用例/文档 ID
    suggestion: str | None = None   # 修复建议

class LayerResult(BaseModel):
    """单层诊断结果"""
    layer: int             # 1-6
    name: str              # 层名称
    status: Literal['pass', 'warn', 'fail', 'skip', 'error']
    score: float           # 0-1，该层健康度
    issues: list[LayerIssue] = []
    details: dict[str, Any] = {}
    execution_time_ms: int = 0

class DiagnosisResult(BaseModel):
    """六层诊断完整结果"""
    layer1: LayerResult
    layer2: LayerResult
    layer3: LayerResult
    layer4: LayerResult
    layer5: LayerResult
    layer6: LayerResult
    overall_health: float  # 0-1，综合健康度
    total_issues: int
    critical_issues: int
    diagnosed_at: datetime
```

## MetricEngineFacade

详细接口定义见 `07-engine-metrics.md`，此处仅展示双轨调用模式：

```python
class MetricEngineFacade:
    """双轨评估统一门面（完整接口见 07-engine-metrics.md）"""

    async def calculate_all(self, run_id: str) -> RunMetrics:
        """计算三层标准化指标"""

    async def diagnose_all(self, run_id: str) -> DiagnosisResult:
        """执行六层诊断"""

    async def calculate_and_diagnose(self, run_id: str) -> tuple[RunMetrics, DiagnosisResult]:
        """并行执行双轨评估"""
        metrics, diagnosis = await asyncio.gather(
            self.calculate_all(run_id),
            self.diagnose_all(run_id),
        )
        return metrics, diagnosis
```

## 配置 Key

### 三层指标阈值

```
rag.eval.threshold.context_precision = 0.7
rag.eval.threshold.context_recall = 0.6
rag.eval.threshold.noise_sensitivity = 0.3
rag.eval.threshold.mrr = 0.5
rag.eval.threshold.ndcg = 0.6
rag.eval.threshold.faithfulness = 0.8
rag.eval.threshold.answer_relevancy = 0.7
rag.eval.threshold.groundedness = 0.75
rag.eval.threshold.regression_score = 0.9
rag.eval.threshold.cost_efficiency = 0.5
rag.eval.threshold.config_stability = 0.95
```

### 权重

```
rag.eval.weight.l1 = 0.4
rag.eval.weight.l2 = 0.4
rag.eval.weight.l3 = 0.2
```

### 六层诊断配置

```
rag.eval.diagnosis.timeout_ms = 60000
rag.eval.diagnosis.concurrency = 3
rag.eval.diagnosis.layer3.enabled = true
rag.eval.diagnosis.layer3.model = ""
rag.eval.diagnosis.layer4.golden_case_ids = []
```

## Prompt Key

### 三层指标 LLM 调用

```
rag.eval.metric.faithfulness_extract_claims
rag.eval.metric.faithfulness_verify_claim
rag.eval.metric.answer_relevancy_extract
rag.eval.metric.answer_relevancy_generate
rag.eval.metric.groundedness
rag.eval.metric.context_recall_verify
```

### 六层诊断 LLM 调用

```
rag.eval.diagnosis.layer3.deviation_analysis
rag.eval.diagnosis.layer3.hallucination_detection
rag.eval.diagnosis.layer5.error_pattern
```
