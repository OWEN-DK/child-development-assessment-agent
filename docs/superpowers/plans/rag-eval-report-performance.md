# RAG 评估报告生成性能优化方案

## 问题

报告生成速度过慢。根因是 L2 指标计算阶段的 LLM 调用次数过多。

## 当前 LLM 调用分析

每个测试用例在 L2 指标计算中的 LLM 调用：

| 计算器 | 调用模式 | 每用例调用数 | 代码位置 |
|--------|---------|-------------|----------|
| Faithfulness | 1 次提取 claims + N 次逐条验证 | 1 + N | faithfulness_calc.py |
| Groundedness | 每句话 1 次判断 | M（最多 30） | groundedness_calc.py |
| AnswerRelevancy | 1 次反生成问题 | 1 | answer_relevancy_calc.py |

典型场景（5 claims、10 句子）：**1 + 5 + 10 + 1 = 17 次 LLM 调用/用例**

50 个用例 × 17 次 = **850 次 LLM 调用**，按每次 1-2 秒、并发 5，总耗时 **数分钟**。

## 优化方案

### 已完成：提高并发度

| 文件 | 改动 | 旧值 → 新值 |
|------|------|-------------|
| facade.py:45 | `_MAX_CASE_CONCURRENCY` | 5 → 10 |
| faithfulness_calc.py:129 | `faithfulness.concurrency` 默认值 | 3 → 5 |
| groundedness_calc.py:95 | `groundedness.concurrency` 默认值 | 3 → 5 |

最大并发从 5×3=15 QPS → 10×5=50 QPS。

### 待实现：减少 LLM 调用次数

将逐条串行调用合并为单次批量调用。

#### 改动 1：Faithfulness — 合并提取+验证为单次调用

**当前流程**（1 + N 次 LLM 调用）：
1. `_extract_claims` → LLM 返回 claims JSON 数组
2. 对每个 claim 调用 `_verify_claim` → LLM 返回 yes/no

**优化后流程**（1 次 LLM 调用）：
1. 单次调用：传入 answer + contexts，LLM 返回结构化 JSON

```json
{
  "claims": [
    {"claim": "声明1", "supported": true},
    {"claim": "声明2", "supported": false}
  ]
}
```

**新增 prompt**：`rag.eval.metric.faithfulness_batch_verify`

```
请从以下回答中提取所有独立的事实性声明，并逐一验证每个声明是否被检索上下文所支持。

## 回答内容
{answer}

## 检索上下文
{contexts}

## 提取规则
1. 将复合句拆分为独立的简单声明
2. 每个声明应包含一个核心事实
3. 忽略过渡语、连接词等非事实性内容
4. 最多提取 20 个声明

## 验证标准
- 声明中的所有关键信息都能从上下文中找到明确依据 → supported: true
- 声明与上下文矛盾，或完全无法从上下文中找到依据 → supported: false
- 声明部分被上下文支持但包含推断成分 → supported: false（严格标准）

## 返回格式
返回一个 JSON 对象：
{
  "claims": [
    {"claim": "声明内容", "supported": true/false},
    ...
  ]
}

仅返回 JSON，不要其他内容。
```

**修改文件**：
- `backend/src/core/prompts_fallback.py` — 新增 `RAG_EVAL_METRIC_FAITHFULNESS_BATCH_VERIFY_PROMPT`
- `backend/src/core/prompt_impl/initializer.py` — 注册新 prompt
- `backend/src/service/rag_eval/metrics/scoring/calculators/faithfulness_calc.py` — 重写 `calculate` 方法

**修改后代码逻辑**：
```python
async def calculate(self, input_data: MetricInput) -> MetricOutput:
    # ... 前置校验不变 ...

    # 单次 LLM 调用：提取 claims + 验证
    prompt = await self._prompt_manager.get_prompt(
        "rag.eval.metric.faithfulness_batch_verify",
        variables={"answer": input_data.actual_answer, "contexts": contexts_text},
    )
    llm = await self._llm_factory.create("rag_eval", "langchain")
    response = await llm.chat(LLMRequest(messages=[LLMMessage(role="user", content=prompt)], timeout=120))

    # 解析 JSON 结果
    result = json.loads(response.content)
    claims = result["claims"]
    supported = sum(1 for c in claims if c["supported"])
    score = supported / len(claims) if claims else 0.0

    return MetricOutput(score=score, passed=score >= threshold, threshold=threshold,
                        details={"total_claims": len(claims), "supported_claims": supported, ...})
```

**可删除的方法**：`_extract_claims`、`_verify_claim`、`_fallback_extract_claims`、`_get_llm_concurrency`

#### 改动 2：Groundedness — 批量句子评分

**当前流程**（M 次 LLM 调用）：
- 每句话调用一次 `_judge_support` → LLM 返回 0-1 分数

**优化后流程**（1 次 LLM 调用）：
- 单次调用：传入所有句子 + contexts，LLM 返回 JSON 数组

```json
[
  {"sentence": "句子1", "score": 0.85},
  {"sentence": "句子2", "score": 0.3}
]
```

**新增 prompt**：`rag.eval.metric.groundedness_batch`

```
你是一个严格的 RAG 质量评估专家。请逐一判断以下每个句子是否被提供的上下文所支持。

## 待评估句子
{sentences_json}

## 检索上下文
{contexts}

## 评分规则
- 1.0：句子中的所有信息都能从上下文中找到明确依据
- 0.7-0.9：句子大部分内容被上下文支持，仅有少量推断
- 0.4-0.6：句子部分被上下文支持，部分内容为合理推断
- 0.1-0.3：句子仅有少量信息能从上下文验证，大部分为推测
- 0.0：句子完全无法从上下文中找到依据，或与上下文矛盾

## 返回格式
返回一个 JSON 数组，每个元素包含句子和对应分数：
[
  {"sentence": "句子内容", "score": 0.85},
  {"sentence": "句子内容", "score": 0.3},
  ...
]

仅返回 JSON 数组，不要其他内容。
```

**修改文件**：
- `backend/src/core/prompts_fallback.py` — 新增 `RAG_EVAL_METRIC_GROUNDEDNESS_BATCH_PROMPT`
- `backend/src/core/prompt_impl/initializer.py` — 注册新 prompt
- `backend/src/service/rag_eval/metrics/scoring/calculators/groundedness_calc.py` — 重写 `calculate` 方法

**修改后代码逻辑**：
```python
async def calculate(self, input_data: MetricInput) -> MetricOutput:
    # ... 前置校验不变 ...

    sentences = self._split_sentences(input_data.actual_answer)
    contexts_text = "\n---\n".join(input_data.retrieved_contexts)

    # 单次 LLM 调用：批量评分
    prompt = await self._prompt_manager.get_prompt(
        "rag.eval.metric.groundedness_batch",
        variables={"sentences_json": json.dumps(sentences, ensure_ascii=False), "contexts": contexts_text},
    )
    llm = await self._llm_factory.create("rag_eval", "langchain")
    response = await llm.chat(LLMRequest(messages=[LLMMessage(role="user", content=prompt)], timeout=120))

    # 解析 JSON 结果
    results = json.loads(response.content)
    scores = [r["score"] for r in results]
    score = sum(scores) / len(scores) if scores else 0.0

    return MetricOutput(score=score, passed=score >= threshold, threshold=threshold,
                        details={"sentence_count": len(sentences), "sentence_results": results})
```

**可删除的方法**：`_judge_support`、`_get_llm_concurrency`

#### 改动 3：AnswerRelevancy — 无需改动

已经只有 1 次 LLM 调用，无需优化。

## 优化效果对比

| 指标 | 优化前 | 优化后 | 降幅 |
|------|--------|--------|------|
| 每用例 LLM 调用数 | 1 + N + M + 1 | 1 + 1 + 1 | **~82%** |
| 50 用例总调用数 | ~850 | ~150 | **~82%** |
| 理论耗时（并发 50 QPS） | ~17s | ~3s | **~82%** |

## 变更清单

### 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/src/core/prompts_fallback.py` | 新增 2 个 prompt 常量 | `RAG_EVAL_METRIC_FAITHFULNESS_BATCH_VERIFY_PROMPT`、`RAG_EVAL_METRIC_GROUNDEDNESS_BATCH_PROMPT` |
| `backend/src/core/prompt_impl/initializer.py` | 注册 2 个新 prompt | 在 `DEFAULT_PROMPTS` 中添加 |
| `backend/src/service/rag_eval/metrics/scoring/calculators/faithfulness_calc.py` | 重写 `calculate` | 合并 extract+verify 为单次调用，删除旧方法 |
| `backend/src/service/rag_eval/metrics/scoring/calculators/groundedness_calc.py` | 重写 `calculate` | 批量句子评分，删除旧方法 |

### 不需要改动的文件

- `answer_relevancy_calc.py` — 已经只有 1 次调用
- `facade.py` — 并发控制逻辑不变
- `orchestrator.py` — 诊断层逻辑不变
- `builder.py`、`markdown_renderer.py` — 不涉及 LLM

## 风险与降级

1. **批量 prompt 输出格式不稳定**：LLM 可能返回非标准 JSON。使用 `json-repair` 库解析，失败时降级为逐条调用（保留旧方法作为 fallback）。
2. **长文本超出 token 限制**：answer 过长时拆分为多批次，每批不超过 20 句/20 claims。
3. **批量精度可能下降**：单次 prompt 处理多条内容时，LLM 可能遗漏或评分不准确。可通过 A/B 对比验证。
