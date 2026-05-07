# RAG 评估报告诊断与改动方案

> 基于报告 `bdf661dc-8af0-43a8-bdbe-d19a8035122e`（2026-05-06 10:55 生成）

## 一、报告概览

| 指标 | 值 | 阈值 | 状态 |
|------|-----|------|------|
| **总分** | 0.6079 | — | — |
| L1 检索质量 | 0.7812 | — | 基本达标 |
| L2 生成质量 | **0.2396** | — | **严重不达标** |
| L3 系统质量 | 0.9979 | — | 达标 |
| 诊断健康度 | 0.975 | — | — |
| 总用例数 | 40 | — | — |
| 通过用例 | 0 | — | — |
| 关键问题 | 6 | — | — |

## 二、L1 检索质量明细

| 指标 | 值 | 阈值 | 状态 |
|------|-----|------|------|
| context_precision | 0.7583 | 0.7 | 边缘通过 |
| context_recall | 0.8000 | 0.6 | 通过 |
| noise_sensitivity | 0.8204 | 0.3 | 通过 |
| mrr | 0.7583 | 0.5 | 通过 |
| ndcg | 0.7690 | 0.6 | 通过 |

**passed=false 原因（已修复）**：原代码 `passed` 使用 `all(s.passed for s in scores)` 逻辑——40 个用例中只要有任何一个未达标，整体 `passed` 即为 `False`。已改为 `avg_v >= threshold`，与 value 聚合逻辑一致。修复后 L1 所有指标均应显示"通过"。

**附带问题**：avg_precision=0.1796 远低于 L1 的 context_precision=0.7583，说明存在大量用例检索精度极低（拉低了简单平均），但 RAGAS 加权算法因排序靠前的相关文档较多而给出了较高分数。需排查低精度用例的分布。

## 三、L2 生成质量明细

| 指标 | 值 | 阈值 | 状态 |
|------|-----|------|------|
| faithfulness | **0** | 0.8 | 严重不达标 |
| answer_relevancy | 0.7187 | 0.7 | 边缘通过 |
| groundedness | **0** | 0.75 | 严重不达标 |

**根因分析（代码级追踪）**：

faithfulness 和 groundedness 为 **精确 0.0**，不是个别用例拉低，而是系统性归零。完整链路如下：

**Step 1 — DI 容器无参实例化**（`di_container.py:259-270`）：
```python
def provide_faithfulness_calculator(self) -> FaithfulnessCalculator:
    return FaithfulnessCalculator()        # 无参，llm_factory 默认 None

def provide_answer_relevancy_calculator(self) -> AnswerRelevancyCalculator:
    return AnswerRelevancyCalculator()     # 无参，llm_factory 默认 None

def provide_groundedness_calculator(self) -> GroundednessCalculator:
    return GroundednessCalculator()        # 无参，llm_factory 默认 None
```
`LLMServiceFactory` 从未在 DI 容器中注册为 provider，三个 calculator 全部收到 `_llm_factory = None`。

**Step 2 — faithfulness 归零路径**（`faithfulness_calc.py`）：
- `_fallback_extract_claims()`（line 109-112）按标点分句，**成功提取 claims**
- `_verify_claim()`（line 114-117）：`if not self._llm_factory: return False` → **每个 claim 都被判为"不支持"**
- 最终分数 = 0 / len(claims) = **0.0**

**Step 3 — groundedness 归零路径**（`groundedness_calc.py`）：
- `_judge_support()`（line 89-90）：`if not self._llm_factory: return 0.0` → **每句得分 0.0**
- 最终分数 = mean([0.0, 0.0, ...]) = **0.0**

**Step 4 — answer_relevancy 为何不为零**（`answer_relevancy_calc.py`）：
- `_generate_questions()`（line 95-98）：`_llm_factory` 为 None 时走 fallback，返回合成问题
- 后续 embedding 相似度计算通过 `EmbeddingHelper` 直接调 DashScope API，**不依赖 `_llm_factory`**
- 最终分数 = **0.7187**（真实的 embedding 余弦相似度）

**结论**：三个 calculator 的 DI 注入全部缺失，但 faithfulness/groundedness 的 fallback 是"无条件返回 0"，而 answer_relevancy 的 fallback 能产出真实分数。这是 fallback 策略差异导致的表面分化，根因都是 `LLMServiceFactory` 未注册。

**2 个超时用例的影响**：即使修复了 DI 注入，这 2 个用例的 `actual_answer` 为空，faithfulness/groundedness 仍会因 early-exit 返回 0.0（代码 line 50-51）。但这是合理的——空回答确实不应有忠实度得分。

## 四、L3 系统质量明细

| 指标 | 值 | 阈值 | 状态 |
|------|-----|------|------|
| rule_compliance | 0.9917 | 1.0 | 未通过（阈值不合理） |
| regression_score | 1.0 | 0.9 | 通过 |
| cost_efficiency | 1.0 | 0.5 | 通过 |
| config_stability | 1.0 | 0.95 | 通过 |

## 五、全量用例统计

| 统计项 | 值 |
|--------|-----|
| 总用例 | 40 |
| 空回答 | 2 |
| 有错误 | 2 |
| avg_precision | 0.1796 |
| avg_recall | 0.8000 |
| avg_f1 | 0.2916 |
| avg_execution_time | 20011ms |
| min_execution_time | 8328ms |
| max_execution_time | 31679ms |

**precision vs recall 剪刀差**：recall=0.80 但 precision=0.18，说明检索倾向于返回大量文档（高覆盖但低精度）。可能原因：
- top_k 设置过大
- expected_knowledge_ids 标注过少（每个用例只标注了少量片段，但检索返回了大量文档）
- 重排序未有效过滤低分结果

## 六、诊断层详情

### Layer 1 规则引擎校验（score=0.95，FAIL）

2 个用例触发 **critical** 级 Rule 7（error_message 存在）：

| 用例 | 错误 | 耗时 |
|------|------|------|
| tc_36716c9a2606 | LLM 调用超时 | 31505ms |
| tc_2e7dfb28504f | LLM 调用超时 | 31640ms |

score = (40 - 2) / 40 = 0.95

**超时来源分析**：executor 层 `asyncio.wait_for` 超时为 300s * concurrent_count，但实际在 ~31s 超时。说明超时发生在更底层的 LLM 客户端（DashScope/OpenAI SDK 默认 timeout ~30s），不是 executor 层。

### Layer 2 语义一致性校验（score=1.0，SKIP）

无历史基线数据，跳过。

### Layer 3 提示词质量校验（score=0.95，FAIL）

4 个 critical 问题，均与上述 2 个超时用例相关：
- tc_36716c9a2606：实际回答为空，完全未响应查询
- tc_2e7dfb28504f：实际回答完全缺失，构成无依据的概括性断言

score = (40 - 2) / 40 = 0.95

### Layer 4 知识库质量校验（score=0.95，WARN）

2 个用例检索分块数 < 3（阈值）：tc_9718e9fc3f90, tc_7af70efd314c

score = (40 - 2) / 40 = 0.95

### Layer 5 重排序效果校验（score=1.0，PASS）

无问题。注意：embedding 质量检查会跳过 `actual_answer` 为空的用例（2 个超时用例被静默排除）。

### Layer 6 融合策略校验（score=1.0，SKIP）

无基线数据，跳过回归检测。

## 七、Bad Cases

| 用例 ID | 查询 | precision | recall | 错误 |
|---------|------|-----------|--------|------|
| tc_36716c9a2606 | 为什么故事比课程知识更容易被记住？ | 0.2 | 1.0 | LLM 调用超时 |
| tc_2e7dfb28504f | 为什么大多数老师或课程都很无聊？ | 0.2 | 1.0 | LLM 调用超时 |

## 八、改动方案

### P0-1：修复 L2 calculator DI 注入缺失（最高优先级）

**影响**：L2 从 0.24 修复后预计提升至 ~0.7

**根因**：`LLMServiceFactory` 从未在 DI 容器中注册为 provider。三个 L2 calculator 全部以无参方式实例化，收到 `_llm_factory = None`。faithfulness/groundedness 的 fallback 策略是"无条件返回 0"，answer_relevancy 的 fallback 走 embedding 所以不受影响。

**改动项**：
1. `di_container.py` 的 `RagEvalModule` 中新增 `provide_llm_factory()` 方法，返回 `LLMServiceFactory` 单例
2. 修改三个 provider 方法注入 `llm_factory` 参数：
   - `provide_faithfulness_calculator(self, llm_factory: LLMServiceFactory)`
   - `provide_answer_relevancy_calculator(self, llm_factory: LLMServiceFactory)`
   - `provide_groundedness_calculator(self, llm_factory: LLMServiceFactory)`
3. 参考 `factory.py:403-412` 的 `_get_legacy_factory()` 实现
4. 验证：修复后 faithfulness 应 > 0（对有回答的用例），groundedness 应 > 0

### P0-2：排查 LLM 客户端超时配置

**影响**：消除 2 个用例的超时错误

**根因**：executor 层超时为 300s，但实际 ~31s 超时，说明超时发生在 LLM SDK 层（DashScope 默认 ~30s）。

**改动项**：
1. 在 `generation_fn` 调用链中找到 LLM client 的 timeout 配置
2. 将 LLM client timeout 提高到 60-120s，或支持通过 `rag.eval.*` 配置项动态调整
3. 文件：`backend/src/service/rag_eval/run/executor.py` 及 LLM provider 初始化代码

### P0-3：空回答容错机制

**影响**：避免 2 个超时用例拉低整体指标

**当前行为**：
- faithfulness/groundedness：空回答 early-exit 返回 0.0（代码层面合理）
- Layer 1：`actual_answer=None` 被跳过（不报 issue）
- Layer 3：`None` 被转为空字符串传给 LLM（可能误报偏差/幻觉）
- Layer 5：空回答被静默排除

**改动项**：
1. L2 指标聚合时，将空回答用例标记为 N/A 从分母剔除，而非计为 0
2. 统一各诊断层对 NULL answer 的处理策略
3. 文件：`backend/src/service/rag_eval/metrics/scoring/facade.py`、各 layer 文件

### P1：检索精度偏低（avg_precision=0.1796）

**影响**：precision 和 F1 严重偏低

**根因分析**：recall=0.80 但 precision=0.18 的剪刀差表明：
- 检索返回了大量不相关文档
- 或 expected_knowledge_ids 标注过少

**改动项**：
1. **检查 top_k 设置**——检索返回结果过多会稀释 precision
2. **优化重排序 score 阈值**——reranking 层已 PASS，可微调阈值过滤低分结果
3. **审查 expected_knowledge_ids 标注质量**——可能是标注的 expected 片段太少导致 precision 计算偏严格

### P2：2 个用例检索分块数不足

**涉及用例**：tc_9718e9fc3f90, tc_7af70efd314c

**改动项**：
- 检查 `boundary_handler` 是否截断了检索结果
- 检查相关文档内容是否本身较少

### P3：rule_compliance 阈值 1.0 不合理

**现状**：rule_compliance=0.9917，阈值=1.0，显示"未通过"。

**根因**：

1. **阈值硬编码 1.0**（`base.py:26`）：`_DEFAULT_THRESHOLDS["rule_compliance"] = 1.0`，数据库从未写入覆盖值，1.0 始终生效
2. **6 条规则中有 2 条是空壳**：Rule 4（retrieval metrics in range）和 Rule 5（no error）硬编码 `+= 1`，永远通过。实际只检查 4 条规则
3. **0.9917 的含义**：40 个用例中 39 个得 6/6=1.0，1 个得 5/6=0.8333（大概率是 2 个超时用例中某条规则命中了 Rule 2 "answer 非空"），均值 = (39×1.0 + 1×0.8333) / 40 ≈ 0.9917
4. **1.0 阈值意味着零容忍**：只要 40 个用例中有任何一个用例的任何一条规则未通过，整体即判"未通过"

**改动项**：
1. 将阈值从 1.0 降至 0.95（允许少量用例个别规则不通过）
2. 移除 Rule 4、Rule 5 空壳规则，或实现真实检查逻辑
3. 通过数据库配置 `rag.eval.threshold.rule_compliance` 覆盖，或修改 `base.py` 默认值

---

## 附录 A：页面展示问题——L1/L2 状态与数值矛盾（已修复）

### 问题描述

页面上 L1、L2 均显示"未通过"，但查看明细指标后发现存在明显矛盾：

**L1 检索质量**：5 个子指标全部超过阈值（context_precision 0.7583 > 0.7、context_recall 0.80 > 0.6、noise_sensitivity 0.8204 > 0.3、mrr 0.7583 > 0.5、ndcg 0.769 > 0.6），但 L1 整体显示"未通过"。

**L2 生成质量**：answer_relevancy 0.7187 > 0.7 达标，但 faithfulness=0 和 groundedness=0 导致 L2=0.2396 显示"未通过"。而 faithfulness/groundedness 归零是 DI 注入故障导致的系统性错误，并非真实的生成质量问题。

### 根因：`passed` 聚合逻辑与 `value` 聚合逻辑不一致

原代码 `_avg()` 和 `calculate_layer()` 中 `passed` 使用 `all(s.passed for s in scores)` 逻辑（全量 AND），而 `value` 使用算术平均。40 个用例中只要 1 个未达标，整体 `passed` 即为 `False`，即使均值远超阈值。

### 修复方案（已实施）

`facade.py` 的 `_avg()` 和 `calculate_layer()` 均改为：

```python
passed = avg_v >= first.threshold    # 基于聚合值判断
pass_rate = sum(1 for s in scores if s.passed) / len(scores)
details = {"case_count": len(scores), "pass_rate": round(pass_rate, 4)}
```

- **passed**：聚合值 >= 阈值即通过（L1 全部达标 → 通过）
- **pass_rate**：个案通过率放入 details 供参考（如 38/40 = 0.95）
- **L2 faithfulness/groundedness**：聚合值 0 < 阈值，正确显示"未通过"

---

## 附录 B：代码级发现汇总

| 发现 | 影响 | 严重度 |
|------|------|--------|
| faithfulness/groundedness 的 `_llm_factory` 未注入 | L2 系统性归零 | P0 |
| LLM 超时发生在 SDK 层（~30s），非 executor 层（300s） | 2 个用例失败 | P0 |
| `passed` 聚合用 `all()`，`value` 聚合用 `avg()`，逻辑不一致 | L1 数值达标但显示未通过 | P1 |
| 页面无法区分"质量不达标"和"指标计算故障" | L2 归零原因不可见 | P1 |
| avg_precision(0.18) 与 context_precision(0.76) 差异巨大 | 精度分布不均 | P1 |
| 各诊断层对 NULL answer 处理不一致 | 潜在误报 | P2 |
| Layer 5 embedding 检查静默跳过空回答 | 遗漏分析 | 低 |
| 指标无中文名、无解释，用户无法理解含义 | 可用性差 | P1 |

---

## 附录 C：指标展示问题——无中文名、无解释

### 问题描述

页面上 L1/L2/L3 每个指标直接显示英文原始名（如 `context_precision`、`faithfulness`、`mrr`），无中文名称，无任何解释说明。用户看到这些指标无法理解其含义、计算方式和阈值设定理由。

### 现状代码

| 组件 | 文件 | 问题 |
|------|------|------|
| MetricScoreCard | `features/rag-eval/components/common/MetricScoreCard.tsx` | name 直接显示为 `<Text strong>`，无 tooltip、无中文映射 |
| LayerScoreCard | `features/rag-eval/components/metrics/LayerScoreCard.tsx` | 遍历 metrics 对象，key 是原始英文名 |
| ScoringDashboard | `features/rag-eval/components/metrics/ScoringDashboard.tsx` | L1/L2/L3 标题有中文，但子指标没有 |
| constants.ts | `entities/rag-eval/constants.ts` | 有 `LAYER_NAMES` 等映射，但无指标名称/描述映射 |

### 参考模式（系统配置页）

系统配置页使用 **Tooltip + QuestionCircleOutlined** 模式（`DynamicConfigForm.tsx:182-189`）：

```tsx
<div className={styles.configLabelGroup}>
  <span className={styles.configLabel}>{displayLabel}</span>
  <Tooltip title={field.description || '暂无描述'}>
    <QuestionCircleOutlined className={styles.helpIcon} />
  </Tooltip>
</div>
```

场景级描述还有额外的蓝色左边框内联展示块。

### 建议改动方向

1. **`entities/rag-eval/constants.ts`** 新增两个映射：

```typescript
// 指标中文名
export const METRIC_LABELS: Record<string, string> = {
  context_precision: '检索精度',
  context_recall: '检索召回',
  noise_sensitivity: '噪音敏感度',
  mrr: '平均倒数排名',
  ndcg: '归一化折损累积增益',
  faithfulness: '忠实度',
  answer_relevancy: '回答相关性',
  groundedness: '接地性',
  rule_compliance: '规则合规率',
  regression_score: '回归分数',
  cost_efficiency: '成本效率',
  config_stability: '配置稳定性',
}

// 指标解释（tooltip 内容）
export const METRIC_DESCRIPTIONS: Record<string, string> = {
  context_precision: 'RAGAS 加权检索精度。对每个相关文档位置 k 计算 precision@k，再按相关性加权平均。反映检索结果中相关文档的排序质量。阈值 0.7。',
  context_recall: '检索结果对预期知识的覆盖比例。= 命中的 expected_knowledge_ids 数 / expected_knowledge_ids 总数。阈值 0.6。',
  noise_sensitivity: '回答中包含检索噪音（不相关文档内容）的程度。值越高越好（低敏感 = 少受噪音影响）。阈值 0.3。',
  mrr: 'Mean Reciprocal Rank。第一个相关文档出现在检索结果中的平均排名倒数。值越高说明相关文档排得越靠前。阈值 0.5。',
  ndcg: 'Normalized Discounted Cumulative Gain。衡量检索结果排序质量，位置靠前的相关文档权重更高。阈值 0.6。',
  faithfulness: 'RAGAS 忠实度。LLM 提取回答中的每个声明，逐一验证是否被检索上下文支持。= 被支持的声明数 / 总声明数。阈值 0.8。注：需要 LLM 服务。',
  answer_relevancy: '回答与原始查询的相关程度。通过 LLM 从回答反向生成问题，再用 embedding 计算与原查询的余弦相似度。阈值 0.7。',
  groundedness: 'TruLens 接地性。将回答拆句，逐句由 LLM 判断是否有检索上下文支持。= 各句支持度的均值。阈值 0.75。注：需要 LLM 服务。',
  rule_compliance: '规则合规率。检查 6 条基础规则（query 非空、answer 非空、expected_ids 存在等）的通过比例。阈值 1.0（当前阈值偏严，建议降至 0.95）。',
  regression_score: '与历史基线的回归对比分数。1.0 表示无回归。阈值 0.9。',
  cost_efficiency: '成本效率。评估单次运行的 LLM 调用成本是否在合理范围内。阈值 0.5。',
  config_stability: '配置稳定性。检查运行期间配置是否发生变化。1.0 表示配置完全稳定。阈值 0.95。',
}
```

2. **`MetricScoreCard.tsx`** 改为使用 Tooltip 模式：

```tsx
import { Tooltip } from 'antd'
import { QuestionCircleOutlined } from '@ant-design/icons'
import { METRIC_LABELS, METRIC_DESCRIPTIONS } from '@entities/rag-eval/constants'

// 原来：
<Text strong>{name}</Text>

// 改为：
<div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
  <Text strong>{METRIC_LABELS[name] || name}</Text>
  <Tooltip title={METRIC_DESCRIPTIONS[name] || '暂无描述'}>
    <QuestionCircleOutlined style={{ color: '#8c8c8c', cursor: 'pointer', fontSize: 13 }} />
  </Tooltip>
</div>
```

3. **Layer 级标题** 也可以增加解释（如 L1/L2/L3 的整体含义），在 `ScoringDashboard.tsx` 的 title 处加 Tooltip。
