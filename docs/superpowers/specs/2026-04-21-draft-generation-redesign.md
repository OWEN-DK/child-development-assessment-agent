# 草稿生成方案（Chunk-Grounded 逐块生成）

**日期**: 2026-04-23
**状态**: 待实施
**方案**: Chunk-Grounded 逐块 QA 生成（参考 RAGAS SingleHop + DeepEval Synthesizer）

---

## 1. 问题描述

### 1.1 当前代码的致命缺陷

```python
# draft_service.py 第 108 行
content_to_use = full_content[:4000] if len(full_content) > 4000 else full_content
```

**表面问题**：只读文档前 4000 字符。

**根因**：架构层面的错误——把"生成测试题"和"读文档"搞反了。

| 当前做法 | 业内正确做法 |
|---------|-------------|
| 读一整段文本 → 让 LLM 自由发挥生成问题 | 先选 chunk → 从该 chunk 提取问题 |
| 问题和答案没有源绑定 | 每个问题绑定 ground_truth_context |
| LLM 可以编造文档中不存在的内容 | 问题必须可由 chunk 原文直接回答 |
| 所有 chunks 混在一个 prompt 里 | 逐 chunk 独立生成 |
| 无事后忠实性校验 | 生成后验证答案是否可回溯到源 chunk |

### 1.2 核心原则

```
草稿生成阶段：
  按 file_hash 直接读取 chunks → 均匀采样 → 逐 chunk 生成 QA → 忠实性校验 → 保存
  ↑ 这是"读取"，不是"检索"。我们只是从自己的索引中拿数据。

测试运行阶段（后续）：
  用草稿的 query 去搜索 → 看能不能召回 source_chunk_id → 6 维评估
  ↑ 这才是"检索"，是我们要测试的能力。
```

**草稿阶段的铁律**：
1. **不使用任何搜索/检索能力**——只按 file_hash 直接读取 chunks
2. 草稿是**用来测试检索的**，不是先验证检索再生成
3. 如果草稿生成就用了检索，等于"出题人提前看了答案"，测试无效
4. **逐 chunk 独立生成问题**——每个问题从单个 chunk 提取，答案必须在 chunk 原文中
5. **按 chunk 的实际年龄段分组**——有 age 的按重叠关系归入对应年龄段，无 age 的归入"通用"组
6. **年龄段是非强制的**——不是每个段落都有年龄段信息，无 age 的段落所有年龄段都可用
7. **不匹配的组合跳过而非报错**——文档可能只覆盖部分年龄段，跳过无内容的组合，继续生成有内容的
8. **忠实性是底线**——问题的答案必须可在源 chunk 原文中找到依据，不允许编造

---

## 2. 业内通用方案调研

### 2.1 RAGAS 框架做法

RAGAS（主流 RAG 评估框架）的 `TestsetGenerator` 标准流程：

```
1. 知识图谱构建：从文档提取 chunks → 提取实体/关键短语/摘要 → 构建节点关系
2. 场景生成：基于知识图谱生成不同类型的查询场景
3. 查询合成：针对每个场景，LLM 生成 question + ground_truth_answer + ground_truth_contexts
4. 保存为评估数据集
5. 后续用 question 去检索，用 ground_truth 计算指标
```

查询类型分类：
- **SingleHop Specific**：单事实查询，从单个 chunk 即可回答（如"前庭觉的主要功能是什么？"）
- **SingleHop Abstract**：单源抽象查询，需综合解释单个 chunk 内容
- **MultiHop Specific**：跨 chunk 关联事实查询
- **MultiHop Abstract**：跨 chunk 抽象推理查询

**本项目的选择**：以 SingleHop Specific 为主。原因：
- RAG 评估的核心是"给定一个问题，系统能否检索到正确的 chunk"
- MultiHop 在当前阶段过于复杂，且偏离评估检索能力的核心目标
- SingleHop 天然保证忠实性——问题从单个 chunk 提取，答案就在该 chunk 中

### 2.2 DeepEval 做法法

DeepEval 的 `Synthesizer` 四步生成流程：

```
1. Context 提取：从文档中提取上下文段落
2. Question 生成：基于上下文用 LLM 生成问题，强制约束问题可由上下文回答
3. Answer 生成：基于问题和上下文生成参考答案
4. Golden 组装：组装 (input, expected_output, context) 三元组
```

关键设计：`generate_goldens_from_contexts()` 接口允许直接传入已切分的上下文，天然支持逐 chunk 生成。

### 2.3 Evidently AI 做法

Evidently AI 的合成数据生成：

```
1. 从知识库提取文档段落
2. 对每个段落生成 question-answer 对
3. 每个对绑定 ground_truth_context
4. 提供 UI 供领域专家审核和验证
```

### 2.4 共性总结

| 维度 | 通用做法 | 本项目采纳 |
|------|----------|-----------|
| 数据源 | 直接读取文档/chunks，不经过检索 | ✅ 按 file_hash 直接读取 |
| 覆盖策略 | 按章节/页码均匀采样，非 top-K 相关性 | ✅ 按 page_label 均匀采样 |
| 生成粒度 | 逐 chunk/段落独立生成问题 | ✅ 逐 chunk 独立生成 |
| 来源标注 | 每个问题绑定来源 chunk（ground_truth_context） | ✅ source_chunk_id + source_page + source_topic |
| 忠实性 | 答案必须可由 chunk 原文推出 | ✅ Prompt 强制 + 事后校验 |
| 跳过机制 | chunk 与目标不相关时允许跳过 | ✅ skip 机制 |
| 去重 | 字符串 + 语义混合去重 | ✅ 混合去重策略 |
| 验证时机 | 生成阶段验证来源真实性，检索质量在测试阶段验证 | ✅ 同 |

---

## 3. 架构设计

### 3.1 整体架构（三阶段流水线）

```
┌──────────────────────────────────────────────────────────────────┐
│                  DraftGenerationService (重写)                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Phase 1: Chunk 选取                                              │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ 1. 按 file_hash 直接读取所有 chunks（非检索）               │ │
│  │ 2. 按 chunk 的 target_age_min/max 分组到各年龄段            │ │
│  │ 3. 按 chunk 的 topics 匹配用户选择的 domain                 │ │
│  │ 4. 对每个有效 domain × age_stage 组合，均匀采样 chunks       │ │
│  │ 5. 跳过无 chunks 的组合，全部不匹配才抛异常                  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              ↓                                    │
│  Phase 2: 逐 Chunk QA 生成（核心！）                              │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ 对每个采样的 chunk:                                          │ │
│  │   1. 构建单 chunk prompt（原文 + 来源标注）                 │ │
│  │   2. LLM 从该 chunk 提取 1 个 QA 对                        │ │
│  │   3. 强制约束：问题必须可由该 chunk 原文直接回答            │ │
│  │   4. 强制约束：答案必须引用原文关键短语                     │ │
│  │   5. 不相关 chunk → LLM 返回 skip                          │ │
│  │   6. 返回 DraftData + source_chunk_id 绑定                  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              ↓                                    │
│  Phase 3: 质量校验 + 去重 + 入库                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ 1. 忠实性校验：keywords/answer_points 回溯 chunk 原文       │ │
│  │ 2. 混合去重：字符串快速初筛 + embedding 精排灰色区间        │ │
│  │ 3. 来源标注入库（source_chunk_id, source_page, source_topic）│ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  全程不涉及任何检索/搜索操作                                      │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 与旧代码的完整决裂清单

| 旧代码 | 新方案 | 处理 |
|--------|--------|------|
| `full_content[:4000]` 截断读取 | 逐 chunk 从 Chroma 读取 | **删除** |
| 所有 chunks 混在一个 prompt | 逐 chunk 独立生成 | **重写 `_generate_batch` → `_generate_qa_from_chunk`** |
| `_generate_batch(text=content_to_use)` | `_generate_qa_from_chunk(chunk=chunk)` | **重写** |
| 无来源绑定 | source_chunk_id + source_page + source_topic | **新增** |
| 纯 SequenceMatcher 去重 | 混合去重（字符串初筛 + embedding 精排） | **升级** |
| DraftData 在两个文件中重复定义 | 统一到 `schemas/test_case.py` | **去重** |
| 无忠实性校验 | keywords/answer_points 回溯 chunk 原文验证 | **新增** |
| LLM 无法跳过不相关 chunk | skip 机制（LLM 可返回 `{"skip": true}`） | **新增** |
| `TEST_CASE_DRAFT_GENERATION_PROMPT` | 新 prompt: `test_case_generation_chunk_grounded` | **重写** |
| `_assign_draft_configs` 轮询分配查询类型/难度 | 逐 chunk 生成，查询类型由 LLM 根据内容自然选择 | **简化** |

---

## 4. Phase 1: Chunk 选取

### 4.1 流程

```
输入: source_document_id, target_domains, target_age_stages
  │
  ├─ 1. 从 SourceDocument 表获取 file_hash
  │
  ├─ 2. 直接按 file_hash 读取该文档的所有 chunks
  │     - 调用 IndexManagerService.get_all_chunks_by_file_hash(file_hash)
  │     - 这是按主键读取，不是搜索
  │     - 返回所有 chunks（含 metadata：page_label, topics, target_age_min/max 等）
  │     - 失败 → 直接抛异常，不使用文件全文兜底
  │
  ├─ 3. 按 chunk 的 target_age_min/max 分组
  │     - 有年龄段的 chunks：按重叠关系归入对应年龄段
  │       chunk[target_age_min, target_age_max] ∩ stage[min, max] ≠ ∅
  │       一个 chunk 可归入多个年龄段
  │     - 无年龄段的 chunks（target_age_min/max 为空）：
  │       归入"通用"组，加入每个年龄段
  │     - 年龄段是**非强制**的，不是每个段落都有
  │
  ├─ 4. 验证与用户选择的匹配度
  │     - 对用户选择的每个 domain × age_stage 组合：
  │       - 取该年龄段的专属 chunks + "通用"组 chunks
  │       - 检查是否有 chunks 可用
  │       - 检查 chunks 的 topics 是否包含该 domain
  │     - 匹配 → 加入有效组合列表
  │     - 无 chunks → 跳过该组合，记录警告
  │     - 无匹配 topics → 跳过该组合，记录警告
  │     - chunks 无 topics → 跳过领域验证，仅按年龄段分组
  │     - 全部不匹配 → 抛出异常
  │
  └─ 5. 对每个有效组合，均匀采样 chunks
        - 按 page_label 排序
        - 强制包含前 10% 和后 10% 的 chunks（保证首尾覆盖）
        - 中间部分等间距采样
        - 返回该组合的采样 chunks 列表
```

### 4.2 关键区别 vs 旧方案

| | 旧方案（错误） | 新方案（正确） |
|---|---|---|
| 获取方式 | 读文件全文，截断前 4000 字 | 按 file_hash 直接读取 Chroma chunks |
| 年龄段处理 | 无分组，整体验证 | 按 chunk 分组，不匹配的组合跳过 |
| 排序方式 | 无 | 按页码均匀采样 |
| 覆盖范围 | 只覆盖前 2 页 | 强制覆盖全文档 |

### 4.3 新增方法

**`IndexOperations.get_all_chunks_by_file_hash(file_hash)`**

在现有 `get_document_chunks()` 基础上新增不分页的全量读取方法：

```python
def get_all_chunks_by_file_hash(self, file_hash: str) -> List[dict]:
    """直接按 file_hash 读取文档的所有 chunks（非检索，不分页）"""
    # 复用 get_document_chunks 的底层逻辑，但不分页
    # 1. 获取 Chroma collection
    # 2. collection.get(where={"file_hash": file_hash}, include=["metadatas", "documents"])
    # 3. 解析 metadata 中的 JSON 字符串（topics, brain_regions）
    # 4. 按 page_label 排序后返回全部 chunks
    # 注意：这是按主键读取，不涉及向量搜索
```

**`IndexManagerService.get_all_chunks_by_file_hash(file_hash)`**

门面层暴露：

```python
def get_all_chunks_by_file_hash(self, file_hash: str) -> List[dict]:
    return self.index_operations.get_all_chunks_by_file_hash(file_hash)
```

### 4.4 均匀采样算法

```python
@staticmethod
def _safe_page_label(page_label: str) -> int:
    """安全转换 page_label 为 int，非数字值返回 0"""
    try:
        return int(page_label)
    except (ValueError, TypeError):
        return 0

def _uniform_sample_chunks(self, chunks: List[dict], max_chunks: int = 15) -> List[dict]:
    """按页码均匀采样，保证首尾覆盖"""
    if len(chunks) <= max_chunks:
        return chunks

    sorted_chunks = sorted(chunks, key=lambda c: self._safe_page_label(c['metadata'].get('page_label', '0')))

    head_count = max(1, len(sorted_chunks) // 10)
    head = sorted_chunks[:head_count]
    tail = sorted_chunks[-head_count:]
    middle = sorted_chunks[head_count:-head_count]

    middle_count = max_chunks - len(head) - len(tail)
    step = max(1, len(middle) // middle_count)
    sampled_middle = middle[::step][:middle_count]

    return head + sampled_middle + tail
```

---

## 5. Phase 2: 逐 Chunk QA 生成

### 5.1 核心设计：从"整段文本自由生成"到"逐 chunk 约束生成"

**旧方案**：所有采样 chunks 混在一个 prompt 里 → LLM 自由发挥 → 问题可能来自任何 chunk 或编造

**新方案**：逐 chunk 独立生成 → 每个 chunk 生成 1 个 QA → 问题必须可由该 chunk 直接回答 → 不相关的 chunk 可跳过

### 5.2 生成流程

```python
async def _generate_drafts_for_combination(
    self,
    sampled_chunks: List[dict],
    domain: str,
    age_stage_label: str,
    age_min_months: int,
    age_max_months: int,
    model: str,
    temperature: float,
    max_retries: int,
) -> List[DraftData]:
    """对采样的 chunks 逐个生成草稿"""
    all_drafts = []

    for chunk in sampled_chunks:
        draft = await self._generate_qa_from_chunk(
            chunk=chunk,
            domain=domain,
            age_stage_label=age_stage_label,
            age_min_months=age_min_months,
            age_max_months=age_max_months,
            model=model,
            temperature=temperature,
            max_retries=max_retries,
        )
        if draft is not None:
            all_drafts.append(draft)

    return all_drafts
```

```python
async def _generate_qa_from_chunk(
    self,
    chunk: dict,
    domain: str,
    age_stage_label: str,
    age_min_months: int,
    age_max_months: int,
    model: str,
    temperature: float,
    max_retries: int,
) -> Optional[DraftData]:
    """从单个 chunk 提取 1 个 QA 对，保证问题可由该 chunk 直接回答"""

    chunk_content = chunk['content']
    chunk_id = chunk['id']
    page_label = chunk['metadata'].get('page_label', '')
    topics = chunk['metadata'].get('topics', [])

    prompt = await prompt_manager.get_prompt(
        "test_case_generation_chunk_grounded",
        variables={
            "chunk_content": chunk_content,
            "chunk_page": page_label,
            "chunk_topics": ", ".join(topics) if topics else "未知",
            "domain": domain,
            "age_stage_label": age_stage_label,
            "age_min_months": age_min_months,
            "age_max_months": age_max_months,
        },
    )

    # LLM 调用
    llm = LLMServiceFactoryCompat.create(
        framework=LLMFramework.LLAMAINDEX,
        model_name=model,
        scenario="test_case_generation",
        temperature=temperature,
    )
    messages = [
        LLMMessage(role="system", content="你是专业的儿童发展测试用例草稿生成专家。"),
        LLMMessage(role="user", content=prompt),
    ]
    response = await llm.chat(LLMRequest(
        messages=messages,
        model_name=model,
        temperature=temperature,
        max_tokens=2048,
        scenario="test_case_generation",
        prompt_key="test_case_generation_chunk_grounded",
    ))
    response_text = response.content.strip()

    # 解析 LLM 输出
    parsed = await self._parse_single_chunk_response(response_text, max_retries)
    if parsed is None:
        logger.warning(f"Chunk {chunk_id} LLM 输出解析失败")
        return None

    # 如果 LLM 返回 skip → 跳过该 chunk
    if parsed.get("skip"):
        logger.info(f"Chunk {chunk_id} 被跳过: {parsed.get('reason', '')}")
        return None

    # 绑定来源信息
    draft = DraftData(
        query=parsed['query'],
        age=parsed['age'],
        domain=domain,
        age_stage_label=age_stage_label,
        description=parsed['description'],
        expected_keywords=parsed['expected_keywords'],
        answer_points=parsed['answer_points'],
        professional_terms=parsed['professional_terms'],
        source_chunk_id=chunk_id,
        source_page=page_label,
        source_topic=", ".join(topics) if topics else "",
        source_content_snippet=chunk_content[:200],
    )

    # 忠实性校验
    is_faithful, reason = self._verify_faithfulness(draft, chunk_content)
    if not is_faithful:
        logger.warning(f"Chunk {chunk_id} 忠实性校验失败: {reason}")
        return None

    return draft
```

### 5.4 LLM 输出解析

新方案 LLM 返回单个 JSON 对象（非列表），解析逻辑与旧 `_parse_llm_response` 不同：

```python
async def _parse_single_chunk_response(self, llm_output: str, max_retries: int = 2) -> Optional[dict]:
    """解析单 chunk LLM 输出（单个 JSON 对象，非 drafts 列表）"""
    import json_repair

    for attempt in range(max_retries + 1):
        try:
            json_match = re.search(r"```json\s*(.*?)\s*```", llm_output, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                start = llm_output.find("{")
                end = llm_output.rfind("}")
                if start != -1 and end != -1:
                    json_str = llm_output[start:end + 1]
                else:
                    json_str = llm_output

            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                data = json_repair.loads(json_str)

            if not isinstance(data, dict):
                raise ValueError("LLM 输出未解析为 JSON 对象")

            return data

        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"单 chunk 解析尝试 {attempt + 1} 失败: {e}")
                continue
            else:
                logger.error(f"单 chunk LLM 输出解析失败（{max_retries} 次重试后）: {e}")
                return None
```

**skip 字段优先级**：解析成功后先检查 `skip` 字段。如果 JSON 格式损坏导致解析失败，直接返回 `None`（视为解析失败，非 skip）。

### 5.5 Prompt 设计

新 prompt key: `test_case_generation_chunk_grounded`

```
你是儿童发展、感觉统合、教育心理学领域的专业测试用例设计师。
你的任务是从给定的文档片段中提取一个可回答的测试问题。

## 源文档片段

页码: {chunk_page}
主题: {chunk_topics}

原文内容：
{chunk_content}

## 生成约束（强制，不可违反）

1. **忠实性铁律**：生成的查询(query)必须能从上述原文片段中直接找到答案
2. **禁止编造**：不允许引入原文中未提及的任何概念、数据、理论或术语
3. **答案来源**：answer_points 中的每一条必须是原文中的关键短语或其直接改写
4. **关键词来源**：expected_keywords 中的每个关键词必须出现在原文中
5. 目标领域：{domain}
6. 适用年龄段：{age_stage_label}（{age_min_months}-{age_max_months} 月）
7. age 必须为整数，范围在 {age_min_months}-{age_max_months} 月之间

## 如果原文内容不足以生成与目标领域/年龄段相关的问题

如果上述原文片段与目标领域({domain})或年龄段({age_stage_label})完全无关，
请返回：{{"skip": true, "reason": "原文与目标领域/年龄段不相关"}}

不要强行从不相关的内容中编造问题。

## 返回格式

必须返回严格的 JSON 对象：
{{
  "skip": false,
  "query": "基于原文可回答的问题",
  "age": 48,
  "description": "测试意图描述",
  "expected_keywords": ["原文中出现的关键词"],
  "answer_points": ["从原文提取的答案要点"],
  "professional_terms": ["原文中的专业术语"]
}}

仅返回 JSON，不要包含任何解释性文字。
```

**关键设计点**：

1. **单 chunk 输入**：prompt 只包含一个 chunk 的原文，LLM 无法编造其他内容
2. **`skip` 机制**：chunk 与 domain/age 不相关时，LLM 可以选择跳过而非硬编
3. **答案可追溯**：每个 answer_point 都可以回溯到 chunk 原文
4. **关键词约束**：expected_keywords 必须出现在原文中
5. **删除旧的 `batch_configs`/`source_chunk_index`**：逐 chunk 生成不再需要批次配置和来源索引

---

## 6. Phase 3: 质量校验 + 去重 + 入库

### 6.1 忠实性校验

生成后做字符串匹配验证——检查 `answer_points` 和 `expected_keywords` 是否出现在源 chunk 原文中：

```python
def _verify_faithfulness(self, draft: DraftData, source_chunk_content: str) -> tuple[bool, str]:
    """验证草稿内容是否忠实于源 chunk"""
    content_lower = source_chunk_content.lower()

    if draft.expected_keywords:
        keyword_hits = sum(1 for kw in draft.expected_keywords if kw.lower() in content_lower)
        keyword_rate = keyword_hits / len(draft.expected_keywords)
        if keyword_rate < 0.6:
            return False, f"关键词命中率 {keyword_rate:.0%} 低于 60%"

    if draft.answer_points:
        point_hits = sum(
            1 for pt in draft.answer_points
            if pt.lower() in content_lower or pt.lower()[:max(8, len(pt) // 2)] in content_lower
        )
        point_rate = point_hits / len(draft.answer_points)
        if point_rate < 0.5:
            return False, f"答案要点命中率 {point_rate:.0%} 低于 50%"

    return True, ""
```

未通过忠实性校验的草稿：**丢弃并记录日志**，不进入入库环节。

### 6.2 混合去重策略

**去重服务整合**：将现有的 `DraftDeduplicationService` 升级为混合去重，`DraftService` 内的 `_deduplicate_against_existing` 方法删除，统一调用 `DraftDeduplicationService`。避免两套去重逻辑共存。

采用业内通用的**混合策略**：字符串快速初筛 + embedding 精排灰色区间。

```python
async def _hybrid_deduplicate(
    self,
    new_drafts: List[DraftData],
    existing_drafts: List[TestCaseDraft],
    threshold: float = 0.85,
) -> List[DraftData]:
    """混合去重：字符串快速初筛 + embedding 精排灰色区间"""
    filtered = []
    for draft in new_drafts:
        is_dup = False
        for existing in existing_drafts:
            str_sim = SequenceMatcher(None, draft.query, existing.query).ratio()

            if str_sim > 0.85:
                is_dup = True
                break
            elif str_sim > 0.5:
                cosine_sim = await self._compute_cosine_similarity(
                    draft.query, existing.query
                )
                if cosine_sim > threshold:
                    is_dup = True
                    break

        if not is_dup:
            filtered.append(draft)

    return filtered
```

**策略说明**：

| 字符串相似度区间 | 处理 | 理由 |
|----------------|------|------|
| > 0.85 | 直接判重 | 几乎相同的文本，无需额外计算 |
| 0.5 - 0.85 | 调用 embedding 精排 | 灰色区间，需要语义判断 |
| < 0.5 | 直接不重 | 明显不同的文本，跳过 |

**成本控制**：每组合 3-10 条草稿，大部分对比不会落入灰色区间，实际 embedding 调用量极少。

```python
async def _compute_cosine_similarity(self, text_a: str, text_b: str) -> float:
    """计算两条文本的余弦相似度"""
    import numpy as np
    from src.config.core.init import init_embedding_model
    from llama_index.core import Settings

    embed_model = Settings.embed_model
    emb_a = await embed_model.aget_text_embedding(text_a)
    emb_b = await embed_model.aget_text_embedding(text_b)

    a = np.array(emb_a)
    b = np.array(emb_b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
```

### 6.3 来源标注入库

**数据库字段变更**：

修改 `backend/src/models/test_case.py` 的 `TestCaseDraft` 类：
```python
source_chunk_id: Mapped[str | None] = mapped_column(String(64), comment="来源 chunk ID")
source_page: Mapped[str | None] = mapped_column(String(20), comment="来源页码")
source_topic: Mapped[str | None] = mapped_column(String(100), comment="来源主题")
source_content_snippet: Mapped[str | None] = mapped_column(Text, comment="来源内容摘要（前 200 字）")
```

修改 `.ai/full_init_script_mysql57.sql`:
```sql
-- 在 test_case_drafts 表中新增
source_chunk_id VARCHAR(64) DEFAULT NULL COMMENT '来源 chunk ID',
source_page VARCHAR(20) DEFAULT NULL COMMENT '来源页码',
source_topic VARCHAR(100) DEFAULT NULL COMMENT '来源主题',
source_content_snippet TEXT DEFAULT NULL COMMENT '来源内容摘要',
```

修改 `backend/src/schemas/test_case.py` 的 `TestCaseDraft` Pydantic 模型：
```python
source_chunk_id: Optional[str] = None
source_page: Optional[str] = None
source_topic: Optional[str] = None
source_content_snippet: Optional[str] = None
```

修改 `DraftData` dataclass（统一到 `service/rag_test/types.py`）：
```python
source_chunk_id: str = ""
source_page: str = ""
source_topic: str = ""
source_content_snippet: str = ""
```

修改 `_save_drafts_idempotent()` 保存来源字段：

```python
async def _save_drafts_idempotent(self, drafts: List[DraftData], doc_id: str, mode: str):
    async with db_session_factory() as session:
        for draft in drafts:
            domain_enum = self._map_domain(draft.domain)

            stmt = select(TestCaseDraft).where(
                TestCaseDraft.source_document_id == doc_id,
                TestCaseDraft.domain == domain_enum,
                TestCaseDraft.age_stage_label == draft.age_stage_label,
                TestCaseDraft.draft_index == draft.draft_index,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing and mode == "overwrite":
                existing.query = draft.query
                existing.description = draft.description
                existing.expected_keywords = draft.expected_keywords
                existing.answer_points = draft.answer_points
                existing.professional_terms = draft.professional_terms
                existing.source_chunk_id = draft.source_chunk_id
                existing.source_page = draft.source_page
                existing.source_topic = draft.source_topic
                existing.source_content_snippet = draft.source_content_snippet
                existing.version += 1
            elif not existing:
                new_draft = TestCaseDraft(
                    id=str(uuid.uuid4()),
                    source_document_id=doc_id,
                    query=draft.query,
                    age=draft.age,
                    domain=domain_enum,
                    description=draft.description,
                    age_stage_label=draft.age_stage_label,
                    draft_index=draft.draft_index,
                    batch_id=draft.batch_id,
                    version=1,
                    expected_knowledge_ids=draft.expected_knowledge_ids or [],
                    expected_keywords=draft.expected_keywords or [],
                    answer_points=draft.answer_points or [],
                    professional_terms=draft.professional_terms or [],
                    generation_params=draft.generation_params,
                    source_chunk_id=draft.source_chunk_id,
                    source_page=draft.source_page,
                    source_topic=draft.source_topic,
                    source_content_snippet=draft.source_content_snippet,
                    status=DraftStatus.DRAFT,
                )
                session.add(new_draft)

        await session.commit()
```

---

## 7. 完整数据流

```
用户上传文档 → 文档索引完成 (Chroma)
  │
  ▼
触发草稿生成
  │
  ├─ Phase 1: Chunk 选取
  │   ├─ 1. 从 SourceDocument 获取 file_hash
  │   ├─ 2. 直接按 file_hash 读取所有 chunks（非检索！）
  │   ├─ 3. 按年龄段分组 chunks
  │   │     - 遍历所有 chunks，按 target_age_min/max 归类
  │   │     - 一个 chunk 可属于多个年龄段
  │   │     - 无 age 的归入"通用"组，加入每个年龄段
  │   ├─ 4. 验证与用户选择的匹配度
  │   │     - 匹配的组合 → 正常生成
  │   │     - 不匹配的组合 → 跳过，记录警告
  │   │     - 全部不匹配 → 抛出异常
  │   └─ 5. 对每个有效组合，分别均匀采样 chunks
  │
  ├─ Phase 2: 逐 Chunk QA 生成
  │   │
  │   ├─ 对每个有效组合:
  │   │   │
  │   │   └─ 对该组合的每个采样 chunk:
  │   │       ├─ 构建单 chunk prompt（原文 + 来源标注）
  │   │       ├─ LLM 生成 QA（可返回 skip）
  │   │       ├─ 绑定 source_chunk_id
  │   │       ├─ 忠实性校验（keywords/answer_points 回溯 chunk 原文）
  │   │       └─ 校验失败 → 丢弃，记录日志
  │   │
  │   └─ 收集所有有效草稿
  │
  ├─ Phase 3: 去重 + 入库
  │   ├─ 1. 混合去重（字符串初筛 + embedding 精排灰色区间）
  │   ├─ 2. 重新编号 draft_index
  │   └─ 3. 幂等入库（含来源标注字段）
  │
  └─ 返回生成结果
      { total_combinations, total_generated, total_skipped, total_faithfulness_failed, duration_seconds }

后续：测试运行阶段
  │
  ▼
  用草稿的 query 执行检索 ← 这才是真正的检索测试
  │
  ├─ 检查检索结果是否包含 source_chunk_id
  ├─ 计算 6 维指标 (Precision/Recall/F1/MRR/NDCG/HitRate)
  └─ 生成评估报告
```

### 7.1 方法调用链

```
DraftService.generate_drafts_matrix()
  │
  ├─ 从 SourceDocument 获取 file_hash
  │
  ├─ 调用 IndexManagerService.get_all_chunks_by_file_hash(file_hash) [新增]
  │     │
  │     └─ 直接访问 Chroma collection 按 file_hash 查询（非检索）
  │
  ├─ 调用 _group_chunks_by_age(chunks, target_age_stages) [新增]
  │     │
  │     ├─ 有 age 的 chunks → 按 target_age_min/max 分组到各年龄段
  │     ├─ 无 age 的 chunks → 归入"通用"组，加入每个年龄段
  │     └─ 返回 age_groups[stage] = 专属chunks + 通用chunks
  │
  ├─ 调用 _validate_and_report(age_groups, target_domains) [新增]
  │     │
  │     ├─ 检查每个 domain × age_stage 组合是否有 chunks
  │     ├─ 检查 topics 是否匹配
  │     └─ 返回 valid_combos 和 skipped_combos
  │
  ├─ 对每个有效组合调用 _uniform_sample_chunks(chunks) [新增]
  │
  ├─ 对每个有效组合调用 _generate_drafts_for_combination() [新增]
  │     │
  │     └─ 对每个采样 chunk 调用 _generate_qa_from_chunk() [新增]
  │           │
  │           ├─ 构建单 chunk prompt
  │           ├─ LLM 生成 QA
  │           ├─ skip → 跳过
  │           ├─ 绑定 source_chunk_id
  │           └─ _verify_faithfulness() [新增] → 校验失败则丢弃
  │
  ├─ 调用 DraftDeduplicationService.deduplicate_drafts() [升级]
  │     │
  │     └─ 混合去重：字符串快速初筛 + embedding 精排灰色区间
  │
  └─ 调用 _save_drafts_idempotent() [修改]
        │
        └─ 保存 source_chunk_id, source_page, source_topic, source_content_snippet
```

---

## 8. 错误处理

### 8.1 按年龄段分组 chunks

```python
def _get_stage_range(self, stage_label: str) -> tuple[int, int]:
    """从 TestCaseGenerationConfig.age_stages 获取年龄段的月龄范围"""
    config = await self._get_draft_config()
    for stage in config.age_stages:
        if stage["label"] == stage_label:
            return stage["age_min_months"], stage["age_max_months"]
    return 0, 216

def _group_chunks_by_age(self, chunks: List[dict], target_age_stages: List[str]) -> Dict[str, List[dict]]:
    """将 chunks 按年龄段分组，无年龄段的归入通用组"""
    age_groups = {stage: [] for stage in target_age_stages}
    universal_chunks = []

    for chunk in chunks:
        chunk_min = chunk['metadata'].get('target_age_min')
        chunk_max = chunk['metadata'].get('target_age_max')

        if chunk_min is None or chunk_max is None:
            universal_chunks.append(chunk)
            continue

        for stage in target_age_stages:
            stage_min, stage_max = self._get_stage_range(stage)
            if chunk_min < stage_max and chunk_max > stage_min:
                age_groups[stage].append(chunk)

    for stage in target_age_stages:
        age_groups[stage].extend(universal_chunks)

    return age_groups
```

### 8.2 元数据不匹配处理

```python
def _validate_and_report(self, age_groups: Dict[str, List[dict]], target_domains: List[str]) -> Dict:
    """验证并报告各年龄段的匹配情况"""
    valid_combos = []
    skipped_combos = []

    for age_stage, chunks in age_groups.items():
        if not chunks:
            skipped_combos.append({
                "age_stage": age_stage,
                "domain": "*",
                "reason": "文档无此年龄段内容"
            })
            continue

        all_topics = self._collect_topics(chunks)
        if not all_topics:
            matched_domains = target_domains
        else:
            matched_domains = [d for d in target_domains if d in all_topics]

        if not matched_domains:
            skipped_combos.append({
                "age_stage": age_stage,
                "domain": ",".join(target_domains),
                "reason": f"文档主题不包含所选领域"
            })
            continue

        for domain in matched_domains:
            valid_combos.append({
                "domain": domain,
                "age_stage": age_stage,
                "chunks": chunks,
                "chunk_count": len(chunks)
            })

    if not valid_combos:
        raise ValueError(
            f"文档内容不覆盖所选组合。跳过原因: {skipped_combos}"
        )

    return {
        "valid_combos": valid_combos,
        "skipped_combos": skipped_combos
    }
```

### 8.3 错误策略

| 场景 | 处理 |
|------|------|
| 获取 chunks 失败 | 直接失败，不使用文件全文兜底 |
| 某年龄段无匹配 chunks | 跳过该组合，记录警告，继续其他年龄段 |
| 某领域无匹配 chunks | 跳过该组合，记录警告，继续其他领域 |
| 全部组合都不匹配 | 抛出异常，告知具体原因 |
| LLM 超时 | 重试 2 次，仍失败则跳过该 chunk |
| LLM 返回 skip | 正常跳过，记录日志 |
| 忠实性校验失败 | 丢弃该草稿，记录日志 |
| chunks 无 topics | 跳过领域验证，仅按年龄段分组 |
| 文档过短（chunks < 5） | 拒绝生成，提示"文档内容不足以生成多样化草稿" |

---

## 9. DraftData 统一

当前 `DraftData` 在两个文件中重复定义：
- `backend/src/service/rag_test/draft_service.py`
- `backend/src/service/rag_test/draft_deduplication_service.py`

违反 CLAUDE.md 的"冗余代码消除"原则。

**处理**：统一到 `backend/src/service/rag_test/types.py`（新建），删除其他文件的重复定义。

注：`DraftData` 是内部数据载体（dataclass），不是 API 层的 Pydantic 模型，不应放在 `schemas/` 目录。`schemas/test_case.py` 中的 `TestCaseDraft` Pydantic 模型是 API 响应 DTO，两者职责不同。

```python
# backend/src/service/rag_test/types.py

@dataclass
class DraftData:
    """草稿数据载体（统一定义，禁止在其他文件重复）"""
    query: str = ""
    age: float = 0
    domain: str = ""
    age_stage_label: str = ""
    draft_index: int = 0
    batch_id: Optional[str] = None
    description: str = ""
    expected_knowledge_ids: List[str] = field(default_factory=list)
    expected_keywords: List[str] = field(default_factory=list)
    answer_points: List[str] = field(default_factory=list)
    professional_terms: List[str] = field(default_factory=list)
    generation_params: Optional[dict] = None
    source_chunk_id: str = ""
    source_page: str = ""
    source_topic: str = ""
    source_content_snippet: str = ""
```

---

## 10. 配置项

```sql
INSERT INTO system_configs (config_key, config_value, category, description) VALUES
('draft_generation.chunk_sampling_strategy', 'uniform', 'draft', '采样策略: uniform=均匀采样'),
('draft_generation.max_chunks_per_combination', '15', 'draft', '每个组合最大采样 chunk 数'),
('draft_generation.coverage_head_tail_ratio', '0.1', 'draft', '首尾强制覆盖比例'),
('draft_generation.faithfulness_keyword_threshold', '0.6', 'draft', '忠实性校验-关键词命中率阈值'),
('draft_generation.faithfulness_answer_point_threshold', '0.5', 'draft', '忠实性校验-答案要点命中率阈值'),
('draft_generation.semantic_dedup_threshold', '0.85', 'draft', '语义去重阈值'),
('draft_generation.dedup_string_high_threshold', '0.85', 'draft', '字符串相似度高阈值（直接判重）'),
('draft_generation.dedup_string_low_threshold', '0.5', 'draft', '字符串相似度低阈值（直接不重）'),
('draft_generation.skip_unmatched_combos', 'true', 'draft', '是否跳过不匹配的组合（而非报错）'),
('draft_generation.min_chunks_for_generation', '5', 'draft', '最少 chunks 数量，低于此值拒绝生成');
```

---

## 11. 实施计划

### 11.1 阶段 1: 基础设施 (优先级: 高)

- [ ] 新增 `IndexOperations.get_all_chunks_by_file_hash()` 方法
- [ ] 新增 `IndexManagerService.get_all_chunks_by_file_hash()` 门面方法
- [ ] 统一 `DraftData` 到 `service/rag_test/types.py`（新建），删除其他文件的重复定义
- [ ] 添加数据库字段 (source_chunk_id, source_page, source_topic, source_content_snippet)
- [ ] 更新 DDL (`full_init_script_mysql57.sql`)
- [ ] 更新 `backend/src/schemas/test_case.py` Pydantic 模型

### 11.2 阶段 2: 核心逻辑重写 (优先级: 高)

- [ ] 重写 `draft_service.py` 的 `generate_drafts_matrix()`
  - 删除 `full_content[:4000]` 整段逻辑
  - 改为 Phase 1 → Phase 2 → Phase 3 流水线
- [ ] 新增 `_group_chunks_by_age()` 方法
- [ ] 新增 `_validate_and_report()` 方法
- [ ] 新增 `_uniform_sample_chunks()` 方法
- [ ] 新增 `_generate_drafts_for_combination()` 方法
- [ ] 新增 `_generate_qa_from_chunk()` 方法（逐 chunk 生成核心）
- [ ] 新增 `_verify_faithfulness()` 方法
- [ ] 注册新 prompt key: `test_case_generation_chunk_grounded`
- [ ] 更新 `prompts_fallback.py` 兜底 prompt
- [ ] 删除旧的 `_generate_batch()` 方法
- [ ] 删除旧的 `_assign_draft_configs()` 方法

### 11.3 阶段 3: 去重升级 + 入库 (优先级: 中)

- [ ] 新增 `_hybrid_deduplicate()` 方法
- [ ] 新增 `_compute_cosine_similarity()` 方法
- [ ] 修改 `_save_drafts_idempotent()` 保存来源字段
- [ ] 修改 `DraftDeduplicationService` 引用统一的 DraftData

### 11.4 阶段 4: 测试与优化 (优先级: 中)

- [ ] 编写单元测试（年龄段分组、均匀采样、忠实性校验、skip 机制）
- [ ] 端到端测试验证覆盖度
- [ ] 前端展示来源信息

---

## 12. 验收标准

### 12.1 功能验收

- [ ] 草稿 100% 基于文档 chunks 生成（无文件全文兜底）
- [ ] **草稿生成阶段不使用任何检索/搜索能力**
- [ ] **逐 chunk 独立生成 QA，问题必须可由 chunk 原文直接回答**
- [ ] 不相关的 chunk 被 skip，不会编造问题
- [ ] 按 chunk 的 target_age_min/max 正确分组到各年龄段
- [ ] 无年龄段的 chunks 归入"通用"组，所有年龄段可用
- [ ] 某年龄段无专属 chunks 时，使用通用组 chunks 生成
- [ ] 某年龄段既无专属也无通用 chunks 时跳过该组合（不报错），继续其他年龄段
- [ ] 全部组合都不匹配时抛出明确异常
- [ ] 每个草稿标注来源（chunk_id + 页码 + 主题）
- [ ] 草稿覆盖文档的首尾和中间部分
- [ ] `DraftData` 只在 `service/rag_test/types.py` 中定义一份

### 12.2 忠实性验收

- [ ] 生成的草稿与文档内容相关度 > 80%
- [ ] 每个 answer_point 可回溯到源 chunk 原文
- [ ] 每个 expected_keyword 出现在源 chunk 原文中
- [ ] 忠实性校验命中率：关键词 ≥ 60%，答案要点 ≥ 50%
- [ ] 不存在编造的概念、数据或术语

### 12.3 质量验收

- [ ] 草稿来源页码分布均匀（不集中在 3 页内）
- [ ] 无重复或语义相似的草稿（混合去重阈值 0.85）
- [ ] 每个草稿针对不同的知识点（采样层天然保证）
- [ ] 每个草稿的 age 字段在其所属年龄段的月龄范围内
- [ ] 跳过的组合和 chunk 有明确的日志，说明跳过原因

### 12.4 性能验收

- [ ] 单 chunk 生成耗时 < 10 秒
- [ ] 单次组合生成耗时 < 60 秒（含所有 chunk）
- [ ] 内存占用 < 512MB
- [ ] 支持并发任务不互相影响

---

## 13. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 文档 chunks 无 target_age_min/max | 正常情况，归入通用组 | 通用组 chunks 加入每个年龄段 |
| 文档 chunks 无 topics | 无法验证领域匹配 | 跳过领域验证，仅按年龄段分组 |
| 用户选的年龄段文档无覆盖 | 该组合跳过 | 记录警告，继续其他年龄段 |
| 文档过短（chunks < 5） | 覆盖度不足 | 拒绝生成，提示"文档内容不足以生成多样化草稿" |
| LLM 返回 skip 导致草稿不足 | 某组合草稿数为 0 | 记录警告，该组合跳过 |
| 忠实性校验误杀 | 丢弃了合理的草稿 | 阈值可调，初期放宽（关键词 60%、答案 50%） |
| 混合去重误杀 | 草稿数量不足 | 阈值可调（0.85），保留字符串去重作为后备 |
| Chroma 索引不可用 | 无法读取 chunks | 检查索引状态，该文档生成失败 |
| 逐 chunk 生成 LLM 调用次数增加 | 成本和耗时上升 | 每个 chunk 只生成 1 个 QA；可并发调用 |

---

## 14. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/src/service/index_manager/index_operations.py` | 修改 | 新增 `get_all_chunks_by_file_hash()` |
| `backend/src/service/index_manager/facade.py` | 修改 | 暴露 `get_all_chunks_by_file_hash()` |
| `backend/src/service/rag_test/draft_service.py` | **重写** | 三阶段流水线：chunk 选取 → 逐 chunk QA 生成 → 质量校验+去重+入库 |
| `backend/src/service/rag_test/draft_deduplication_service.py` | 修改 | 引用统一的 DraftData，升级为混合去重 |
| `backend/src/service/rag_test/types.py` | **新建** | 统一 DraftData dataclass 定义 |
| `backend/src/core/prompts_fallback.py` | 修改 | 新增 `test_case_generation_chunk_grounded` 兜底 prompt |
| `backend/src/core/prompt_impl/initializer.py` | 修改 | 注册新 prompt key |
| `backend/src/models/test_case.py` | 修改 | 添加来源标注字段 |
| `backend/src/schemas/test_case.py` | 修改 | 同步添加来源字段到 Pydantic 模型 |
| `.ai/full_init_script_mysql57.sql` | 修改 | 更新 DDL |
| `backend/tests/service/test_draft_service.py` | **重写** | 旧测试全部删除，按新架构重写 |

---

## 15. 旧方法清理与兼容性

### 15.1 删除的方法

以下旧方法在新架构中不再需要，**直接删除**（零迁移原则）：

| 方法 | 所在文件 | 替代方案 |
|------|---------|---------|
| `_generate_batch()` | draft_service.py | `_generate_drafts_for_combination()` + `_generate_qa_from_chunk()` |
| `_assign_draft_configs()` | draft_service.py | 逐 chunk 生成，查询类型由 LLM 自然选择 |
| `_build_combinations()` | draft_service.py | `_validate_and_report()` 返回有效组合 |
| `_deduplicate_against_existing()` | draft_service.py | 统一使用 `DraftDeduplicationService` |
| `_get_age_stage_info()` | draft_service.py | `_get_stage_range()` |
| `_validate_and_convert_drafts()` | draft_service.py | 逐 chunk 生成不再需要批量转换 |

### 15.2 GenerationParams 兼容性

`GenerationParams` 中的 `query_types` 和 `difficulty_levels` 字段**保留**（前端仍传参），但在 `generate_drafts_matrix()` 中不再使用。原因：
- 前端表单仍然展示这些选项供用户参考
- 逐 chunk 生成时，LLM 根据 chunk 内容自然选择问题类型和难度
- 删除这些字段需要同步修改前端，不在本次范围内

### 15.3 旧服务废弃

代码库中的 `RagTestCaseService`（`rag_test_case_service.py`）与 `DraftService` 功能重叠，包含旧版 MinHash+LSH 去重和按章节分块并行生成逻辑。**该服务标记为废弃**，后续清理时删除。

### 15.4 测试文件清理

`backend/tests/service/test_draft_service.py`（369 行）大量测试即将被删除的旧方法。**全部删除并按新架构重写**。新测试覆盖：
- `_group_chunks_by_age()` 年龄段分组
- `_uniform_sample_chunks()` 均匀采样
- `_verify_faithfulness()` 忠实性校验
- `_parse_single_chunk_response()` 输出解析（含 skip、格式损坏、json_repair 降级）
- `_safe_page_label()` 非数字页码容错
- `_validate_and_report()` 组合验证与跳过

---

## 16. SSE 事件格式

新三阶段流水线的 SSE 事件格式：

### 16.1 开始事件

```json
{
  "event": "draft_generation_started",
  "total_combinations": 6,
  "total_sampled_chunks": 45,
  "mode": "append"
}
```

### 16.2 逐 chunk 进度事件

```json
{
  "event": "draft_chunk_progress",
  "current_combination": 2,
  "total_combinations": 6,
  "current_chunk": 5,
  "total_chunks_in_combo": 15,
  "domain": "感觉统合",
  "age_stage": "3-6岁",
  "chunk_skipped": false,
  "faithfulness_failed": false
}
```

### 16.3 组合完成事件

```json
{
  "event": "draft_combination_progress",
  "current_combination": 2,
  "total_combinations": 6,
  "domain": "感觉统合",
  "age_stage": "3-6岁",
  "generated": 12,
  "skipped_chunks": 2,
  "faithfulness_failed": 1,
  "deduplicated": 1
}
```

### 16.4 完成事件

```json
{
  "event": "draft_generation_completed",
  "total": 25,
  "total_skipped_chunks": 8,
  "total_faithfulness_failed": 3,
  "total_deduplicated": 4,
  "duration": "2m30s"
}
```

### 16.5 与旧格式的兼容性

- `draft_generation_started` 和 `draft_generation_completed` 事件保持与旧格式基本兼容（新增字段）
- `draft_combination_progress` 新增 `skipped_chunks` 和 `faithfulness_failed` 字段
- 新增 `draft_chunk_progress` 事件（chunk 级别进度）
- 前端需适配新字段，旧字段不删除
