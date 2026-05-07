# RAG 评估 L2 指标低分问题调查

## 结论（已定位根因）

**根因：`retrieved_contexts` 传的是文档 ID，不是文本内容。**

`MetricEngineFacade._to_metric_inputs()` 将 `retrieved_doc_ids`（ID 列表）直接赋给 `MetricInput.retrieved_contexts`。评分计算器拼接后传给 LLM 的"上下文"是 `chunk_abc123\n---\chunk_def456`，而非实际文档内容。LLM 无法基于 ID 验证任何声明，几乎所有声明都判为 `supported: false`。

**这不是评估标准问题，不是模型问题，是数据管道 bug。**

---

## 问题定位过程

### 现象

- Faithfulness（忠实度）：**24%**
- Groundedness（落地度）：**6%**

两个指标在改动前就已经很低，与批量 prompt 优化无关。

### 排查的四个假说

| 假说 | 描述 | 结论 |
|------|------|------|
| 假说 1 | 检索上下文质量差 | **排除**——问题不是质量差，而是根本没有传文本 |
| 假说 2 | Prompt 评分标准过于严格 | 次要因素，但不是根因 |
| 假说 3 | qwen 模型理解偏差 | 排除——模型收到的是 ID，与模型能力无关 |
| 假说 4 | 实际答案确实质量低 | 排除——低分来源是评估管道 bug |

### 根因分析

**数据流断裂点**：`MetricEngineFacade._to_metric_inputs()`（`facade.py:118`）

```python
# 当前代码——只传了 ID
retrieved_contexts=r.retrieved_doc_ids or [],  # ["chunk_abc123", "chunk_def456", ...]
```

`retrieved_doc_ids` 是文档 ID 字符串列表。两个评分计算器直接拼接这个字段：

- `faithfulness_calc.py:59`：`contexts_text = "\n---\n".join(input_data.retrieved_contexts)`
- `groundedness_calc.py:65`：`contexts_text = "\n---\n".join(input_data.retrieved_contexts)`

LLM 收到的 prompt 中，"检索上下文"部分是文档 ID 而非文本，无法验证任何声明。

**闭包机制只在运行时有效**：运行阶段通过 `_retrieved_items` 闭包传递实际文本给 generation 函数。但评分阶段从数据库读取结果时，只有 `retrieved_doc_ids`，没有文本内容。

### 影响范围

| 指标层 | 是否受影响 | 原因 |
|--------|-----------|------|
| L1 检索质量（precision, recall, MRR, NDCG） | 否 | 只比较 ID 集合 |
| L2 忠实度（faithfulness） | **是** | 需要上下文文本验证声明 |
| L2 落地度（groundedness） | **是** | 需要上下文文本验证句子 |
| L2 回答相关性（answer_relevancy） | **待确认** | 需检查是否依赖上下文文本 |
| L3 系统质量 | 否 | 不依赖上下文文本 |

---

## 修复方案

修复 `_to_metric_inputs` 方法，让它获取检索结果的实际文本内容。

需要确认：
1. `test_run_results` 表是否存储了检索结果的文本内容（`retrieved_contexts_text` 或类似字段）
2. 如果没有存储，需要从 Chroma 向量库或 docstore 通过 ID 反查文本
3. 或者在运行执行阶段就将文本内容持久化到数据库

---

## 次要因素（数据修复后再评估）

Prompt 确实偏严格，但修复数据管道后才能准确评估其影响：

- Faithfulness prompt："声明部分被上下文支持但包含推断成分 → supported: false（严格标准）"
- Groundedness prompt：1.0 要求"所有信息都能从上下文中找到明确依据"

建议在数据修复后，对比严格/宽松标准的分数差异，再决定是否调整。
