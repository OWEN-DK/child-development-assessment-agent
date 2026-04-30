# 05 P3：修复静默功能失效

> 4 个静默失效问题，功能存在但不生效。
> 与 P1/P2 无硬依赖，可并行实施。

---

## P3-1 PageIndex score/confidence 字段统一（问题 11）⚠️ 暂缓

> **PageIndex 暂时不引入，本项暂缓实施。** 待 PageIndex 正式上线后再执行。

### 核实事实

`pageindex_wrapper.py:284` 输出 `"confidence"` 键。
`result_fusion.py:131` 查找 `"score"` 键，未找到时赋默认 0.5。
→ 所有 PageIndex 结果被等分对待，实际置信度被丢弃。

注意：P0-3 已在 `pageindex_enhancement.py` 中做了临时映射。
本项在源头修复，P0-3 的临时映射可以保留（双重保障不冲突）。

### 修复

**`pageindex_wrapper.py`** `_parse_response()` 方法（L284）：

```python
# 修改前
"confidence": node.get("confidence_score", 0.0),

# 修改后
"score": node.get("confidence_score", 0.0),
"confidence": node.get("confidence_score", 0.0),  # 保留兼容
```

排序也改为使用 `score`：
```python
results.sort(key=lambda x: x["score"], reverse=True)
```

### 验证

- [ ] PageIndex 结果在 `ResultFusion.fuse()` 中获得真实分数（非默认 0.5）
- [ ] 高置信度 PageIndex 结果排在低置信度之前

---

## P3-2 同义词扩展双 system prompt（问题 10）

### 核实事实

`query_rewriter.py:151` 用 `get_prompt("synonym_expansion")` 作为 user prompt。
`query_rewriter.py:169` 再次调 `get_prompt("synonym_expansion")` 作为 system prompt。
→ 同一模板同时作为 system 和 user 消息发送，浪费 token 且可能混淆模型。

`pipeline/steps/synonym_expansion.py:45-48` 使用硬编码 system prompt，与 query_rewriter 不一致。

### 修复

**`query_rewriter.py`**：

```python
# L169 修改：使用独立 system prompt，不重复加载 synonym_expansion 模板
system_prompt = "你是儿童发展领域的同义词扩展专家。根据用户查询，生成语义相关的同义词和变体表达，以提高知识库检索的召回率。输出格式为 JSON 列表。"

# L151 保持不变（user prompt 用模板）
base_prompt = await prompt_manager.get_prompt("synonym_expansion")
```

**`synonym_expansion.py`** 同步检查 system prompt 与 `query_rewriter.py` 一致。

### 验证

- [ ] LLM 收到的 system 和 user 消息内容不同
- [ ] 同义词扩展质量不低于修改前

---

## P3-3 Pipeline 路径补齐缓存（问题 14）

### 核实事实

`facade.py:149-164` `_retrieve_via_pipeline()`：
- 不接收 `user_id`
- 无缓存写入（pipeline YAML 有 `cache_check` 步骤但无 cache-write 步骤）
- 无 A/B 测试集成

非 pipeline 路径（`knowledge_retriever.py`）有完整的缓存读写和 A/B 测试。

### 修复

**Step 1**：`_retrieve_via_pipeline()` 加 `user_id` 参数

```python
async def _retrieve_via_pipeline(
    self, query: str, limit: int, user_id: str = None
) -> List[KnowledgeItem]:
```

**Step 2**：添加缓存（复用知识检索器的缓存机制）

```python
async def _retrieve_via_pipeline(
    self, query: str, limit: int, user_id: str = None
) -> List[KnowledgeItem]:
    cache_key = f"pipeline:{query}:{limit}"

    # 缓存检查
    if self._cache:
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

    try:
        raw_results = await self._pipeline_orchestrator.execute(
            query=query, limit=limit,
        )
        results = self.knowledge_retriever._convert_to_knowledge_items(
            raw_results
        )
    except Exception as e:
        logger.error(f"Pipeline 检索失败: {e}")
        raise

    # 缓存写入
    if self._cache:
        await self._cache.set(cache_key, results, ttl=300)

    return results[:limit]
```

**Step 3**：`retrieve_knowledge()` 传递 `user_id`

```python
if use_pipeline:
    return await self._retrieve_via_pipeline(query, limit, user_id=user_id)
```

A/B 测试暂不补齐，标记 TODO。

### 验证

- [ ] Pipeline 路径第二次相同查询命中缓存（无重复 LLM/向量调用）
- [ ] `user_id` 不再被丢弃

---

## P3-4 查询 Embedding 添加重试（问题 15）

### 核实事实

`embedding.py`：
- `get_text_embedding_batch()` 有 3 次重试 + 指数退避
- `get_query_embedding()` 无重试，直接调 `super().get_query_embedding()`
- `aget_query_embedding()` 同样无重试

单次瞬断会直接导致整个检索链路失败。

### 修复

```python
def get_query_embedding(self, query: str) -> List[float]:
    query = self._preprocess_query(query)
    for attempt in range(3):
        try:
            result = super().get_query_embedding(query)
            if result:
                return result
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    return super().get_query_embedding(query)

async def aget_query_embedding(self, query: str) -> List[float]:
    query = self._preprocess_query(query)
    for attempt in range(3):
        try:
            result = await super().aget_query_embedding(query)
            if result:
                return result
        except Exception as e:
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)
    return await super().aget_query_embedding(query)

def _preprocess_query(self, query: str) -> str:
    """提取公共的空值检查和截断逻辑"""
    if not query or not query.strip():
        logger.warning("Empty query encountered, replacing with placeholder.")
        return "empty"
    if len(query) > self.max_text_length:
        logger.warning(f"Query too long ({len(query)} chars), truncating.")
        return query[:self.max_text_length]
    return query
```

### 验证

- [ ] Mock Embedding API 前两次失败第三次成功，查询正常返回
- [ ] Mock 3 次全部失败，异常正确抛出
