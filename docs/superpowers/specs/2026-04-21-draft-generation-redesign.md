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

### 1.3 前置依赖：Chunk Metadata 年龄字段

**关键假设**：chunk metadata 中包含 `target_age_min` 和 `target_age_max` 字段。

**现状确认**：当前 `get_document_chunks()` 返回的 metadata 仅包含 `page_label`、`topics`、`brain_regions`、`start_char_idx`、`end_char_idx`。**如果文档切分管线未写入年龄字段，需在实施本方案前补充**。

**兜底策略**（实施时必须实现）：
```python
def _get_chunk_age_range(self, chunk: dict) -> tuple[int | None, int | None]:
    """获取 chunk 的年龄范围，无则返回 (None, None)"""
    age_min = chunk['metadata'].get('target_age_min')
    age_max = chunk['metadata'].get('target_age_max')
    
    # 兜底：如果 metadata 无年龄字段，尝试从 topics 推断
    if age_min is None or age_max is None:
        topics = chunk['metadata'].get('topics', [])
        age_min, age_max = self._infer_age_from_topics(topics)
    
    return age_min, age_max

def _infer_age_from_topics(self, topics: list[str]) -> tuple[int | None, int | None]:
    """从 topics 推断年龄段（可选，根据业务规则实现）"""
    # 示例：如果 topics 包含 "0-3岁感统训练"，返回 (0, 36)
    # 如果无法推断，返回 (None, None) → 归入通用组
    return None, None
```

**如果文档切分管线确实未写入年龄字段**：所有 chunks 将归入"通用"组，方案退化为无年龄段分组，但仍保留逐 chunk 生成和忠实性校验的核心优势。

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
│  Phase 2: 逐 Chunk QA 生成（核心！并发执行）                      │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ 对每个有效组合（并发度 5，asyncio.gather）：                 │ │
│  │   对每个采样的 chunk:                                        │ │
│  │     1. 构建单 chunk prompt（原文 + 来源标注）               │ │
│  │     2. LLM 从该 chunk 提取 1 个 QA 对                      │ │
│  │     3. 强制约束：问题必须可由该 chunk 原文直接回答          │ │
│  │     4. 强制约束：答案必须引用原文关键短语                   │ │
│  │     5. 不相关 chunk → LLM 返回 skip                         │ │
│  │     6. 返回 DraftData + source_chunk_id 绑定                │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              ↓                                    │
│  Phase 3: 质量校验 + 去重 + 入库                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ 1. 忠实性校验：关键词字符串匹配 + 句子级 embedding 相似度   │ │
│  │ 2. 混合去重：字符串快速初筛 + embedding 精排灰色区间        │ │
│  │ 3. 来源标注入库（source_chunk_id, source_page, source_topic）│ │
│  │ 4. embedding_cache 全局共享（Phase 2 & 3 复用）             │ │
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
| DraftData 在两个文件中重复定义 | 统一到 `service/rag_test/types.py` | **去重** |
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
    """按页码均匀采样，保证首尾覆盖
    
    采样策略：
    - 强制包含前 10% 和后 10% 的 chunks（保证首尾覆盖）
    - 中间部分等间距采样
    - 返回值不超过 max_chunks
    """
    if len(chunks) <= max_chunks:
        return chunks

    sorted_chunks = sorted(
        chunks, 
        key=lambda c: self._safe_page_label(c['metadata'].get('page_label', '0'))
    )

    # 首尾各取 10%，至少 1 个
    head_tail_count = max(1, len(sorted_chunks) // 10)
    
    # 确保 head + tail 不超过 max_chunks 的一半
    head_tail_count = min(head_tail_count, max_chunks // 2)
    
    head = sorted_chunks[:head_tail_count]
    tail = sorted_chunks[-head_tail_count:]
    middle = sorted_chunks[head_tail_count:-head_tail_count]

    # 中间部分采样
    middle_count = max_chunks - len(head) - len(tail)
    if middle_count > 0 and middle:
        step = max(1, len(middle) // middle_count)
        sampled_middle = middle[::step][:middle_count]
    else:
        sampled_middle = []

    result = head + sampled_middle + tail
    
    # 确保不超过 max_chunks（边界情况保护）
    return result[:max_chunks]
```

**边界情况测试**：

| chunks 总数 | max_chunks | head | tail | middle | 最终返回 |
|------------|-----------|------|------|--------|---------|
| 10 | 15 | - | - | - | 10 (≤ max, 直接返回) |
| 16 | 15 | 1 | 1 | 13 | 15 (1+13+1) |
| 50 | 15 | 5 | 5 | 5 | 15 (5+5+5) |
| 100 | 15 | 5 | 5 | 5 | 15 (5+5+5) |
| 20 | 15 | 2 | 2 | 11 | 15 (2+11+2) |

---

## 5. Phase 2: 逐 Chunk QA 生成

### 5.1 核心设计：从"整段文本自由生成"到"逐 chunk 约束生成"

**旧方案**：所有采样 chunks 混在一个 prompt 里 → LLM 自由发挥 → 问题可能来自任何 chunk 或编造

**新方案**：逐 chunk 独立生成 → 每个 chunk 生成 1 个 QA → 问题必须可由该 chunk 直接回答 → 不相关的 chunk 可跳过

### 5.2 生成流程（并发执行）

**问题**：串行逐 chunk 生成会导致严重性能问题（15 chunks × 6 combos × 10s = 15 分钟），无法满足"单组合 < 60 秒"的验收标准。

**解决方案**：同一组合内的 chunk 生成是独立的，使用 `asyncio.gather()` 并发执行，通过 `asyncio.Semaphore` 控制并发度。

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
    embedding_cache: dict,  # 全局共享缓存，由 generate_drafts_matrix 创建
    progress_callback: Optional[Callable] = None,
    current_combo_index: int = 0,
    total_combinations: int = 1,
) -> Dict[str, Any]:
    """对采样的 chunks 并发生成草稿
    
    Args:
        embedding_cache: 全局共享 embedding 缓存（Phase 2 & 3 复用）
    
    Returns:
        {
            "drafts": List[DraftData],
            "skipped_chunks": int,
            "faithfulness_failed": int,
        }
    """
    # 控制并发度，避免同时过多 LLM 请求
    semaphore = asyncio.Semaphore(5)  # 最多 5 个并发
    
    async def _process_chunk(chunk: dict) -> Optional[DraftData]:
        async with semaphore:
            draft = await self._generate_qa_from_chunk(
                chunk=chunk,
                domain=domain,
                age_stage_label=age_stage_label,
                age_min_months=age_min_months,
                age_max_months=age_max_months,
                model=model,
                temperature=temperature,
                max_retries=max_retries,
                embedding_cache=embedding_cache,
            )
            
            # 推送 chunk 级进度
            if progress_callback:
                await progress_callback(
                    current_combo_index, total_combinations,
                    json.dumps({
                        "event": "draft_chunk_progress",
                        "current_combination": current_combo_index + 1,
                        "total_combinations": total_combinations,
                        "chunk_id": chunk.get('id', ''),
                        "domain": domain,
                        "age_stage": age_stage_label,
                        "draft_generated": draft is not None,
                    })
                )
            
            return draft
    
    # 并发执行所有 chunk
    tasks = [_process_chunk(chunk) for chunk in sampled_chunks]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 收集结果
    all_drafts = []
    skipped_chunks = 0
    faithfulness_failed = 0
    
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Chunk 生成异常: {result}")
            faithfulness_failed += 1
        elif result is None:
            skipped_chunks += 1
        else:
            all_drafts.append(result)
    
    return {
        "drafts": all_drafts,
        "skipped_chunks": skipped_chunks,
        "faithfulness_failed": faithfulness_failed,
    }
```

**性能预估**：
- 单组合 15 chunks，并发度 5 → 分 3 批，每批约 10 秒 → 单组合约 30 秒
- 6 个组合串行 → 总耗时约 3 分钟（远低于原方案的 15 分钟）
- 满足"单组合 < 60 秒"的验收标准

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
    embedding_cache: Optional[dict] = None,
) -> Optional[DraftData]:
    """从单个 chunk 提取 1 个 QA 对，保证问题可由该 chunk 直接回答"""

    chunk_content = chunk['content']
    chunk_id = chunk['id']
    page_label = chunk['metadata'].get('page_label', '')
    topics = chunk['metadata'].get('topics', [])

    # LLM 调用 + 解析，最多重试 2 次
    for attempt in range(max_retries + 1):
        prompt = await prompt_manager.get_prompt(
            "test_case_generation_chunk_grounded",
            variables={
                "chunk_id": chunk_id,
                "chunk_content": chunk_content,
                "chunk_page": page_label,
                "chunk_topics": ", ".join(topics) if topics else "未知",
                "domain": domain,
                "age_stage_label": age_stage_label,
                "age_min_months": age_min_months,
                "age_max_months": age_max_months,
            },
        )

        llm = LLMServiceFactoryCompat.create(
            framework=LLMFramework.LLAMAINDEX,
            model_name=model,
            scenario="test_case_generation",
            temperature=temperature + (attempt * 0.1),  # 重试时略微增加随机性
        )
        messages = [
            LLMMessage(role="system", content="你是专业的儿童发展测试用例草稿生成专家。"),
            LLMMessage(role="user", content=prompt),
        ]
        response = await llm.chat(LLMRequest(
            messages=messages,
            model_name=model,
            temperature=temperature + (attempt * 0.1),
            max_tokens=2048,
            scenario="test_case_generation",
            prompt_key="test_case_generation_chunk_grounded",
        ))
        response_text = response.content.strip()

        parsed = await self._parse_single_chunk_response(response_text)
        if parsed is not None:
            break  # 解析成功

        if attempt < max_retries:
            logger.warning(f"Chunk {chunk_id} 解析失败，重试 {attempt + 1}/{max_retries}")

    if parsed is None:
        logger.warning(f"Chunk {chunk_id} LLM 输出解析失败（{max_retries + 1} 次尝试后）")
        return None

    # 如果 LLM 返回 skip → 跳过该 chunk
    if parsed.get("skip"):
        logger.info(f"Chunk {chunk_id} 被跳过: {parsed.get('reason', '')}")
        return None

    # 校验 age 范围
    age = int(parsed['age'])
    if not (age_min_months <= age <= age_max_months):
        logger.warning(
            f"Chunk {chunk_id} age={age} 超出范围 [{age_min_months}, {age_max_months}]，"
            f"修正为 {age_min_months}"
        )
        age = age_min_months

    # 绑定来源信息
    draft = DraftData(
        query=parsed['query'],
        age=age,
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

    # 忠实性校验（使用全局 embedding 缓存）
    is_faithful, reason = await self._verify_faithfulness(
        draft, chunk_content, embedding_cache
    )
    if not is_faithful:
        logger.warning(f"Chunk {chunk_id} 忠实性校验失败: {reason}")
        return None

    return draft
```

### 5.4 LLM 输出解析

新方案 LLM 返回单个 JSON 对象（非列表），解析逻辑与旧 `_parse_llm_response` 不同：

```python
async def _parse_single_chunk_response(self, llm_output: str) -> Optional[dict]:
    """解析单 chunk LLM 输出（单个 JSON 对象，非 drafts 列表）
    
    注意：本方法不做重试。重试由调用方 _generate_qa_from_chunk 控制，
    重试时应重新调用 LLM 而非重复解析同一输出。
    """
    import json_repair

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
        logger.error(f"单 chunk LLM 输出解析失败: {e}")
        return None
```

**调用方重试逻辑**（在 `_generate_qa_from_chunk` 中）：

```python
# LLM 调用 + 解析，最多重试 2 次
for attempt in range(max_retries + 1):
    response = await llm.chat(...)
    response_text = response.content.strip()
    parsed = await self._parse_single_chunk_response(response_text)
    
    if parsed is not None:
        break  # 解析成功，跳出重试循环
    
    if attempt < max_retries:
        logger.warning(f"Chunk {chunk_id} 解析失败，重试 {attempt + 1}/{max_retries}")
        # 重试时重新调用 LLM（temperature 可略微调高增加随机性）
```

**skip 字段优先级**：解析成功后先检查 `skip` 字段。如果 JSON 格式损坏导致解析失败，返回 `None`（视为解析失败，非 skip）。

### 5.5 Prompt 设计

新 prompt key: `test_case_generation_chunk_grounded`

```
你是儿童发展、感觉统合、教育心理学领域的专业测试用例设计师。
你的任务是从给定的文档片段中提取一个可回答的测试问题。

## 源文档片段

Chunk ID: {chunk_id}
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
2. **`chunk_id` 标注**：便于调试、日志追踪和问题定位
3. **`skip` 机制**：chunk 与 domain/age 不相关时，LLM 可以选择跳过而非硬编
4. **答案可追溯**：每个 answer_point 都可以回溯到 chunk 原文
5. **关键词约束**：expected_keywords 必须出现在原文中
6. **删除旧的 `batch_configs`/`source_chunk_index`**：逐 chunk 生成不再需要批次配置和来源索引

---

## 6. Phase 3: 质量校验 + 去重 + 入库

### 6.1 忠实性校验

**问题**：LLM 生成的 answer_points 通常是改写/概括而非原文摘录，字符串 substring 匹配会误杀合理草稿。同时，短句（answer_point）与长段（chunk_content）直接做 embedding 对比，因长度差异导致分数天然偏低。

**解决方案**：采用两层校验——字符串快速初筛 + 句子级 embedding 语义相似度精排。

```python
async def _verify_faithfulness(
    self,
    draft: DraftData,
    source_chunk_content: str,
    embedding_cache: Optional[dict] = None,
) -> tuple[bool, str]:
    """验证草稿内容是否忠实于源 chunk（两层校验）"""
    
    # === 第一层：字符串快速初筛 ===
    content_lower = source_chunk_content.lower()
    
    # 关键词必须出现在原文中（关键词通常是原文术语，不应被改写）
    if draft.expected_keywords:
        keyword_hits = sum(1 for kw in draft.expected_keywords if kw.lower() in content_lower)
        keyword_rate = keyword_hits / len(draft.expected_keywords)
        if keyword_rate < 0.5:  # 降低至 50%
            return False, f"关键词命中率 {keyword_rate:.0%} 低于 50%"
    
    # === 第二层：句子级 embedding 语义相似度精排 ===
    # answer_points 允许改写，用语义相似度判断
    # 关键改进：将 chunk 拆分为句子，每个 answer_point 与每个句子对比，取最高分
    if draft.answer_points:
        sentences = self._split_into_sentences(source_chunk_content)
        
        # 预计算所有句子的 embedding
        sentence_embeddings = []
        for sent in sentences:
            sent_emb = await self._get_embedding_with_cache(sent, embedding_cache)
            sentence_embeddings.append(sent_emb)
        
        faithful_count = 0
        for point in draft.answer_points:
            point_embedding = await self._get_embedding_with_cache(point, embedding_cache)
            
            # 与每个句子对比，取最高相似度
            max_sim = 0.0
            for sent_emb in sentence_embeddings:
                sim = self._cosine_similarity(point_embedding, sent_emb)
                if sim > max_sim:
                    max_sim = sim
            
            if max_sim >= 0.65:  # 句子级语义相似度阈值
                faithful_count += 1
        
        point_rate = faithful_count / len(draft.answer_points)
        if point_rate < 0.5:  # 50% 的 answer_points 需语义相关
            return False, f"答案要点语义命中率 {point_rate:.0%} 低于 50%"
    
    return True, ""

@staticmethod
def _split_into_sentences(text: str) -> List[str]:
    """将文本拆分为句子列表"""
    import re
    # 按中文句号、感叹号、问号、分号拆分
    sentences = re.split(r'[。！？；\n]+', text)
    # 过滤空句和过短句（< 4 字）
    return [s.strip() for s in sentences if len(s.strip()) >= 4]
```

**策略说明**：

| 校验层 | 检查对象 | 方法 | 阈值 | 理由 |
|--------|----------|------|------|------|
| 第一层 | expected_keywords | 字符串匹配 | ≥ 50% | 关键词通常是原文术语，不应被改写 |
| 第二层 | answer_points | 句子级 embedding 相似度 | ≥ 0.65 | 短句与短句对比，分数更可靠 |

**为什么拆句对比**：
- `answer_point` 通常是 5-15 字的短句
- `chunk_content` 通常是 200-500 字的长段
- 直接对比：embedding 对长度敏感，短句与长段的 cosine 相似度天然偏低（0.4-0.6）
- 拆句对比：短句与短句对比，分数分布更合理（0.6-0.9），0.65 阈值更可靠

**成本控制**：一个 chunk 约 10-20 个句子，每个 answer_point 对比 10-20 次（纯计算，无 API 调用）。句子 embedding 只调用一次，缓存复用。

**辅助方法定义**：

```python
async def _get_embedding_with_cache(
    self, text: str, cache: Optional[dict] = None
) -> list[float]:
    """获取 embedding，支持缓存"""
    import hashlib
    from llama_index.core import Settings
    
    text_hash = hashlib.md5(text.encode()).hexdigest()
    
    if cache and text_hash in cache:
        return cache[text_hash]
    
    embed_model = Settings.embed_model
    embedding = await embed_model.aget_text_embedding(text)
    
    if cache is not None:
        cache[text_hash] = embedding
    
    return embedding

@staticmethod
def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算余弦相似度"""
    import numpy as np
    a_arr = np.array(a)
    b_arr = np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))
```

未通过忠实性校验的草稿：**丢弃并记录日志**，不进入入库环节。

### 6.2 混合去重策略

**去重服务整合**：将现有的 `DraftDeduplicationService` 升级为混合去重，`DraftService` 内的 `_deduplicate_against_existing` 方法删除，统一调用 `DraftDeduplicationService`。避免两套去重逻辑共存。

采用业内通用的**混合策略**：字符串快速初筛 + embedding 精排灰色区间。

**关键改进**：`embedding_cache` 由主流程创建并全局共享，忠实性校验和去重复用同一份缓存。

```python
async def _hybrid_deduplicate(
    self,
    new_drafts: List[DraftData],
    existing_drafts: List[TestCaseDraft],
    threshold: float = 0.85,
    embedding_cache: Optional[dict] = None,
) -> List[DraftData]:
    """混合去重：字符串快速初筛 + embedding 精排灰色区间
    
    Args:
        embedding_cache: 全局共享缓存（由 generate_drafts_matrix 创建）
    """
    if embedding_cache is None:
        embedding_cache = {}  # 兜底：如果没有传入则创建新的
        
    filtered = []
    
    # 预计算所有现有草稿的 embedding（仅灰色区间需要）
    existing_embeddings = {}
    for existing in existing_drafts:
        existing_embeddings[existing.id] = await self._get_embedding_with_cache(
            existing.query, embedding_cache
        )
    
    for draft in new_drafts:
        is_dup = False
        draft_embedding = None  # 延迟计算，仅灰色区间需要
        
        for existing in existing_drafts:
            str_sim = SequenceMatcher(None, draft.query, existing.query).ratio()

            if str_sim > 0.85:
                is_dup = True
                break
            elif str_sim > 0.5:
                # 灰色区间：计算语义相似度
                if draft_embedding is None:
                    draft_embedding = await self._get_embedding_with_cache(
                        draft.query, embedding_cache
                    )
                
                existing_emb = existing_embeddings.get(existing.id)
                if existing_emb is None:
                    existing_emb = await self._get_embedding_with_cache(
                        existing.query, embedding_cache
                    )
                    existing_embeddings[existing.id] = existing_emb
                
                cosine_sim = self._cosine_similarity(draft_embedding, existing_emb)
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

**成本控制**：
- 每组合 3-10 条草稿，大部分对比不会落入灰色区间
- 使用全局 `embedding_cache` 避免重复 embed 相同 query
- 延迟计算：只有落入灰色区间的 draft 才计算 embedding
- 忠实性校验和去重共享同一份缓存，最大化复用

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

### 6.4 主流程串联（新增）

`generate_drafts_matrix()` 的核心流水线代码：

```python
async def generate_drafts_matrix(
    self,
    source_document_id: str,
    params: GenerationParams,
    progress_callback: Optional[Callable] = None,
    cancellation_event: Optional[asyncio.Event] = None,
    task_id: Optional[str] = None,
    task_type: Optional[str] = None,
) -> Dict[str, Any]:
    """多维度矩阵草稿生成（三阶段流水线）"""
    start_time = time.time()
    
    # 0. 获取分布式锁
    if not await self._acquire_lock(source_document_id):
        raise ValueError("该文档正在生成草稿，请稍后重试")
    
    try:
        # 1. 获取文档
        doc = await self._get_source_document(source_document_id)
        
        # 2. 创建全局 embedding_cache（Phase 2 & 3 共享）
        embedding_cache = {}
        
        # 3. Phase 1: Chunk 选取
        all_chunks = await self._get_all_chunks_by_file_hash(doc.file_hash)
        age_groups = self._group_chunks_by_age(all_chunks, params.age_stages)
        validation = self._validate_and_report(age_groups, params.target_domains)
        
        valid_combos = validation["valid_combos"]
        total_combinations = len(valid_combos)
        
        # 推送开始事件
        if progress_callback:
            await progress_callback(0, total_combinations, json.dumps({
                "event": "draft_generation_started",
                "total_combinations": total_combinations,
                "total_sampled_chunks": sum(
                    min(len(c["chunks"]), 15) for c in valid_combos
                ),
                "mode": params.mode,
            }))
        
        # 4. Phase 2 & 3: 逐组合生成 → 去重 → 入库
        all_generated = 0
        all_skipped = 0
        all_faithfulness_failed = 0
        all_parse_failed = 0
        all_deduplicated = 0
        
        for i, combo in enumerate(valid_combos):
            # 4.1 均匀采样
            sampled = self._uniform_sample_chunks(combo["chunks"])
            
            # 4.2 Phase 2: 并发生成
            result = await self._generate_drafts_for_combination(
                sampled_chunks=sampled,
                domain=combo["domain"],
                age_stage_label=combo["age_stage"],
                age_min_months=combo.get("age_min_months", 0),
                age_max_months=combo.get("age_max_months", 216),
                model=params.llm_model,
                temperature=params.temperature,
                max_retries=2,
                embedding_cache=embedding_cache,  # 传入全局缓存
                progress_callback=progress_callback,
                current_combo_index=i,
                total_combinations=total_combinations,
            )
            
            new_drafts = result["drafts"]
            all_skipped += result["skipped_chunks"]
            all_faithfulness_failed += result["faithfulness_failed"]
            
            # 4.3 Phase 3: 去重
            existing = await self._get_existing_drafts(
                source_document_id, combo["domain"], combo["age_stage"]
            )
            deduped = await self._hybrid_deduplicate(
                new_drafts, existing, 
                embedding_cache=embedding_cache  # 复用全局缓存
            )
            all_deduplicated += len(new_drafts) - len(deduped)
            
            # 4.4 重新编号 draft_index
            for idx, draft in enumerate(deduped):
                draft.draft_index = idx
            
            # 4.5 入库
            await self._save_drafts_idempotent(
                deduped, source_document_id, params.mode
            )
            all_generated += len(deduped)
            
            # 推送组合完成事件
            if progress_callback:
                await progress_callback(i + 1, total_combinations, json.dumps({
                    "event": "draft_combination_progress",
                    "current_combination": i + 1,
                    "total_combinations": total_combinations,
                    "domain": combo["domain"],
                    "age_stage": combo["age_stage"],
                    "generated": all_generated,
                    "skipped_chunks": result["skipped_chunks"],
                    "faithfulness_failed": result["faithfulness_failed"],
                    "deduplicated": len(new_drafts) - len(deduped),
                }))
        
        # 5. 推送完成事件
        duration = time.time() - start_time
        if progress_callback:
            await progress_callback(total_combinations, total_combinations, json.dumps({
                "event": "draft_generation_completed",
                "total": all_generated,
                "total_skipped_chunks": all_skipped,
                "total_faithfulness_failed": all_faithfulness_failed,
                "total_parse_failed": all_parse_failed,
                "total_deduplicated": all_deduplicated,
                "warnings": validation.get("warnings", []),
                "duration": self._format_duration(duration),
            }))
        
        return {
            "total_combinations": total_combinations,
            "total_generated": all_generated,
            "total_skipped": all_skipped,
            "total_faithfulness_failed": all_faithfulness_failed,
            "total_deduplicated": all_deduplicated,
            "duration_seconds": duration,
            "warnings": validation.get("warnings", []),
        }
        
    finally:
        await self._release_lock(source_document_id)
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
  │   │     - 遍历所有 chunks，按 target_age_min/max 归类（使用兜底方法）
  │   │     - 一个 chunk 可属于多个年龄段
  │   │     - 无 age 的归入"通用"组，加入每个年龄段
  │   ├─ 4. 验证与用户选择的匹配度
  │   │     - 匹配的组合 → 正常生成
  │   │     - 不匹配的组合 → 跳过，记录警告
  │   │     - 全部不匹配 → 抛出异常
  │   └─ 5. 对每个有效组合，分别均匀采样 chunks
  │
  ├─ 创建全局 embedding_cache（Phase 2 & 3 共享）
  │
  ├─ Phase 2: 逐 Chunk QA 生成（并发！）
  │   │
  │   ├─ 对每个有效组合（并发度 5，asyncio.gather）:
  │   │   │
  │   │   └─ 对该组合的每个采样 chunk（并发）:
  │   │       ├─ 构建单 chunk prompt（原文 + chunk_id + 来源标注）
  │   │       ├─ LLM 生成 QA（可返回 skip，失败可重试）
  │   │       ├─ 校验 age 范围（超出则修正为 age_min）
  │   │       ├─ 绑定 source_chunk_id
  │   │       ├─ 忠实性校验（关键词匹配 + 句子级语义相似度）
  │   │       └─ 校验失败 → 丢弃，记录日志
  │   │
  │   └─ 收集所有有效草稿
  │
  ├─ Phase 3: 去重 + 入库
  │   ├─ 1. 混合去重（字符串初筛 + embedding 精排灰色区间）
  │   ├─ 2. 重新编号 draft_index（从 0 开始连续）
  │   └─ 3. 幂等入库（含来源标注字段）
  │
  └─ 返回生成结果
      { total_combinations, total_generated, total_skipped, total_faithfulness_failed,
        total_parse_failed, duration_seconds, warnings }

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
  ├─ 创建全局 embedding_cache（Phase 2 & 3 共享）
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
  │     └─ 返回 valid_combos, skipped_combos, warnings
  │
  ├─ 对每个有效组合调用 _uniform_sample_chunks(chunks) [新增]
  │
  ├─ 对每个有效组合调用 _generate_drafts_for_combination() [新增]
  │     │
  │     └─ 并发调用 _generate_qa_from_chunk() [新增]
  │           │
  │           ├─ 构建单 chunk prompt（含 chunk_id）
  │           ├─ LLM 生成 QA（可返回 skip，失败可重试）
  │           ├─ 校验 age 范围（超出则修正为 age_min）
  │           ├─ skip → 跳过，计数 +1
  │           ├─ 绑定 source_chunk_id
  │           └─ _verify_faithfulness() [升级] → 校验失败则丢弃，计数 +1
  │     │
  │     └─ 返回 { drafts, skipped_chunks, faithfulness_failed }
  │
  ├─ 调用 DraftDeduplicationService.deduplicate_drafts() [升级]
  │     │
  │     └─ 混合去重：字符串快速初筛 + embedding 精排灰色区间
  │
  ├─ 重新编号 draft_index（从 0 开始连续）[新增]
  │     for idx, draft in enumerate(deduped_drafts):
  │         draft.draft_index = idx
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

def _get_chunk_age_range(self, chunk: dict) -> tuple[int | None, int | None]:
    """获取 chunk 的年龄范围，无则返回 (None, None)"""
    age_min = chunk['metadata'].get('target_age_min')
    age_max = chunk['metadata'].get('target_age_max')
    
    # 兜底：如果 metadata 无年龄字段，尝试从 topics 推断
    if age_min is None or age_max is None:
        topics = chunk['metadata'].get('topics', [])
        age_min, age_max = self._infer_age_from_topics(topics)
    
    return age_min, age_max

def _infer_age_from_topics(self, topics: list[str]) -> tuple[int | None, int | None]:
    """从 topics 推断年龄段（可选，根据业务规则实现）"""
    # 示例：如果 topics 包含 "0-3岁感统训练"，返回 (0, 36)
    # 如果无法推断，返回 (None, None) → 归入通用组
    return None, None

def _group_chunks_by_age(self, chunks: List[dict], target_age_stages: List[str]) -> Dict[str, List[dict]]:
    """将 chunks 按年龄段分组，无年龄段的归入通用组"""
    age_groups = {stage: [] for stage in target_age_stages}
    universal_chunks = []

    for chunk in chunks:
        chunk_min, chunk_max = self._get_chunk_age_range(chunk)

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
    warnings = []  # 新增：收集警告信息

    for age_stage, chunks in age_groups.items():
        if not chunks:
            skipped_combos.append({
                "age_stage": age_stage,
                "domain": "*",
                "reason": "文档无此年龄段内容"
            })
            continue

        all_topics = self._collect_topics(chunks)
        has_topics_metadata = any(
            c['metadata'].get('topics') for c in chunks
        )
        
        if not all_topics:
            if has_topics_metadata:
                # 有 topics 字段但全部为空列表 → 真的不匹配
                matched_domains = []
            else:
                # chunks 无 topics 元数据 → 跳过领域验证，但记录警告
                matched_domains = target_domains
                warnings.append({
                    "age_stage": age_stage,
                    "warning": "文档 chunks 无 topics 元数据，跳过领域验证",
                    "affected_domains": target_domains,
                })
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
        "skipped_combos": skipped_combos,
        "warnings": warnings,  # 新增：返回警告
    }
```

**关键改进**：
- 区分"有 topics 但为空"和"无 topics 元数据"两种情况
- 无 topics 元数据时跳过领域验证，但记录警告返回给调用方
- 警告信息通过 SSE 事件推送给前端，让用户知情

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
    age: int = 0  # 统一为 int（月龄），与 prompt 约束和验收标准一致
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

**类型统一说明**：
- `DraftData.age`：`int`（月龄，如 48 表示 48 个月）
- ORM `TestCaseDraft.age`：`DECIMAL(4,1)`（兼容历史数据，新数据写入时 `int` 自动转换）
- Pydantic `TestCaseDraft.age`：`float`（API 响应层，前端展示时取整）
- 在 `_save_drafts_idempotent()` 中无需额外转换，Python `int` 可自动适配 `DECIMAL`

---

## 10. 配置项

```sql
INSERT INTO system_configs (config_key, config_value, category, description) VALUES
('draft_generation.chunk_sampling_strategy', 'uniform', 'draft', '采样策略: uniform=均匀采样'),
('draft_generation.max_chunks_per_combination', '15', 'draft', '每个组合最大采样 chunk 数'),
('draft_generation.coverage_head_tail_ratio', '0.1', 'draft', '首尾强制覆盖比例'),
('draft_generation.faithfulness_keyword_threshold', '0.5', 'draft', '忠实性校验-关键词命中率阈值'),
('draft_generation.faithfulness_answer_point_threshold', '0.5', 'draft', '忠实性校验-答案要点命中率阈值'),
('draft_generation.faithfulness_sentence_similarity_threshold', '0.65', 'draft', '忠实性校验-句子级语义相似度阈值'),
('draft_generation.semantic_dedup_threshold', '0.85', 'draft', '语义去重阈值'),
('draft_generation.dedup_string_high_threshold', '0.85', 'draft', '字符串相似度高阈值（直接判重）'),
('draft_generation.dedup_string_low_threshold', '0.5', 'draft', '字符串相似度低阈值（直接不重）'),
('draft_generation.skip_unmatched_combos', 'true', 'draft', '是否跳过不匹配的组合（而非报错）'),
('draft_generation.min_chunks_for_generation', '5', 'draft', '最少 chunks 数量，低于此值拒绝生成'),
('draft_generation.concurrency_limit', '5', 'draft', '并发 chunk 生成数（Semaphore 大小）');
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

- [ ] 新增 `_hybrid_deduplicate()` 方法（支持全局 embedding_cache）
- [ ] 修改 `_save_drafts_idempotent()` 保存来源字段
- [ ] 修改 `DraftDeduplicationService` 引用统一的 DraftData
- [ ] 去重后重新编号 draft_index（从 0 开始连续）

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
- [ ] 每个 answer_point 可回溯到源 chunk 原文的某个句子（语义相似度 ≥ 0.65）
- [ ] 每个 expected_keyword 出现在源 chunk 原文中（字符串匹配）
- [ ] 忠实性校验命中率：关键词 ≥ 50%，答案要点 ≥ 50%
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
| 忠实性校验误杀 | 丢弃了合理的草稿 | 阈值可调，初期放宽（关键词 50%、答案要点 50%、句子级相似度 0.65） |
| 混合去重误杀 | 草稿数量不足 | 阈值可调（0.85），保留字符串去重作为后备 |
| Chroma 索引不可用 | 无法读取 chunks | 检查索引状态，该文档生成失败 |
| **并发 LLM API 限流** | 部分请求被 429 拒绝 | Semaphore 控制并发度（默认 5），支持配置调整 |
| **并发内存占用过高** | 大量 embedding 缓存占用内存 | embedding_cache 按组合生命周期管理，组合结束后释放 |
| **并发顺序导致 SSE 事件乱序** | 前端进度显示不准确 | draft_chunk_progress 不依赖顺序，前端通过计数统计 |
| **Semaphore 并发度不合适** | 过低浪费资源，过高触发限流 | 通过配置项 `draft_generation.concurrency_limit` 可调 |

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
  "chunk_id": "abc-123-def",
  "domain": "感觉统合",
  "age_stage": "3-6岁",
  "draft_generated": true
}
```

**字段说明**：
- `chunk_id`：当前处理的 chunk 唯一标识
- `draft_generated`：`true` 表示成功生成草稿，`false` 表示 skip/校验失败/解析失败

> 注：由于并发执行，`current_chunk`/`total_chunks_in_combo` 不适用。前端可通过统计 `draft_chunk_progress` 事件数量自行计算进度。

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
  "total_parse_failed": 2,
  "warnings": [
    {
      "age_stage": "0-3岁",
      "warning": "文档 chunks 无 topics 元数据，跳过领域验证",
      "affected_domains": ["感觉统合", "粗大动作"]
    }
  ],
  "duration": "2m30s"
}
```

**新增字段说明**：
- `total_skipped_chunks`：LLM 返回 skip 的 chunk 数量
- `total_faithfulness_failed`：忠实性校验失败的 chunk 数量
- `total_deduplicated`：去重移除的草稿数量
- `total_parse_failed`：LLM 输出解析失败的 chunk 数量
- `warnings`：生成过程中的警告列表（如无 topics 元数据）

### 16.5 与旧格式的兼容性

- `draft_generation_started` 和 `draft_generation_completed` 事件保持与旧格式基本兼容（新增字段）
- `draft_combination_progress` 新增 `skipped_chunks` 和 `faithfulness_failed` 字段
- 新增 `draft_chunk_progress` 事件（chunk 级别进度）
- 前端需适配新字段，旧字段不删除
