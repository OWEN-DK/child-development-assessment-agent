# 02 P0：消除运行时崩溃

> 4 个运行时 TypeError/AttributeError/NameError，按依赖顺序修复。

---

## P0-1 Pipeline 重排序参数签名（问题 8）

**文件**：`backend/src/core/pipeline/steps/reranking.py`

### 核实事实

`CrossEncoderReranker.rerank()` 签名（reranker.py:110）：
```python
def rerank(self, query: str, nodes: List[NodeWithScore]) -> List[NodeWithScore]:
```
- 同步方法（`def`，非 `async def`）
- 接受 `query` 和 `nodes` 两个参数

当前调用（reranking.py:26-28）：
```python
ranked_results = await self._reranker.rerank(
    query=context.query, candidates=candidates, top_k=self._final_k
)
```

**两个 bug**：
1. `candidates=` 和 `top_k=` 不存在于 `rerank()` 签名 → `TypeError`
2. `await` 调用同步方法（Python 不报错，但语义错误）

except 块（L36-38）吞掉 TypeError，静默退化到未排序截断。

### 修复

```python
# 修改 reranking.py:26-38
try:
    ranked_results = self._reranker.rerank(
        query=context.query, nodes=candidates
    )
    context.results = ranked_results[: self._final_k]
except Exception as e:
    logger.warning(f"重排序失败，使用原始排序：{e}")
    context.results = candidates[: self._final_k]
```

注意：去掉 `await`，参数名 `candidates` → `nodes`，去掉 `top_k=`（截断在赋值时处理）。

### 验证

- [ ] Pipeline 模式下执行复杂查询，日志中不再出现"重排序失败"
- [ ] `CrossEncoderReranker.rerank()` 日志显示实际模型推理发生
- [ ] 结果顺序与非 pipeline 路径一致（都经过 reranker）

---

## P0-2 结果融合 limit 参数（问题 7）

**文件**：
- `backend/src/core/result_fusion.py` — `fuse()` 签名
- `backend/src/service/rag_service.py` — 调用方

### 核实事实

`fuse()` 签名（result_fusion.py:26-31）：
```python
def fuse(self, hybrid_results, pageindex_results, query_type) -> List[Dict]:
```

调用方（rag_service.py:73-78）传了 `limit=limit` → `TypeError`。

`_fuse_complex` 内部无截断，返回全部去重结果。
`_fuse_default` 用 `len(hybrid_results) or 10` 做内部截断，不读外部 limit。

### 修复

在 `fuse()` 签名中加 `limit` 参数，两个子方法末尾截断：

```python
def fuse(
    self,
    hybrid_results: List[Dict[str, Any]],
    pageindex_results: List[Dict[str, Any]],
    query_type: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    # ... 现有逻辑 ...
    return deduped_results[:limit]  # 两个分支都加截断
```

### 验证

- [ ] 复杂查询 + PageIndex 启用时不抛 TypeError
- [ ] 返回结果数不超过传入的 `limit`

---

## P0-3 PageIndex 增强步骤（问题 9 + 11）⚠️ 暂缓

> **PageIndex 暂时不引入，本项暂缓实施。** 待 PageIndex 正式上线后再执行。

**文件**：`backend/src/core/pipeline/steps/pageindex_enhancement.py`

### 核实事实

两个独立 bug：

**Bug A**（L27-31）：调 `pageindex.search()`，但 `PageIndexWrapper` 只有 `query()` 方法：
```python
# search() 签名不存在
pageindex_results = await pageindex.search(query=context.query, age=context.age, limit=5)

# query() 实际签名
async def query(self, query: str, context=None, max_depth=None, use_fallback=True)
```

**Bug B**（L65）：调 `fusion.fuse_pageindex()`，但 `ResultFusion` 无此方法。应使用 `fuse()`。

**Bug C**（关联问题 11）：`_parse_response()` 输出 `"confidence"` 键，但 `ResultFusion.fuse()` 查找 `"score"` 键，PageIndex 结果被赋默认 0.5。

### 修复

```python
# 修复 Bug A: search → query
pageindex_results = await pageindex.query(
    query=context.query,
    context=None,
    max_depth=self.config.get("max_depth", 3),
    use_fallback=self.config.get("use_fallback", True),
)

# 修复 Bug B + C: 用 fuse() 替代 fuse_pageindex()，统一 score 字段
def _enhance_with_pageindex(self, existing, pageindex, fuse_factor, max_hybrid):
    from src.core.result_fusion import ResultFusion
    fusion = ResultFusion()

    # 将 PageIndex 的 confidence 映射为 score
    normalized_pageindex = []
    for r in pageindex:
        normalized_pageindex.append({
            "content": r.get("content", ""),
            "score": r.get("confidence", 0.5),
            "source": r.get("source", "Unknown"),
            "metadata": r.get("metadata", {}),
        })

    return fusion.fuse(
        hybrid_results=existing,
        pageindex_results=normalized_pageindex,
        query_type="default",
        limit=max_hybrid,
    )
```

### 验证

- [ ] PageIndex 启用时，增强步骤日志显示融合成功
- [ ] PageIndex 结果的 `confidence` 值被正确映射为 `score` 参与融合排序

---

## P0-4 分层生成 fallback 变量（问题 21）

**文件**：`backend/src/core/layered_content_generator.py`

### 核实事实

L389 `layered_config["concurrency_limit"]` **不会 NameError**——`layered_config` 已在 L186（同一方法内）定义，在 except 块作用域内。

真正的问题是**设计不一致**：
- `__init__`（L35-43）将 `batch_size`、`l0_max_length` 等存入 `self.*` 快照，配置热重载后这些值过时
- L389 绕过快照直接从 `settings` 重新读取 `layered_config["concurrency_limit"]`——这是正确的做法
- 但其他代码仍用 `self.batch_size`（旧快照），导致同一方法内混合使用 stale/fresh 配置

此外 L389 用 `layered_config["concurrency_limit"]` 直接索引，若配置缺少此 key 会导致 KeyError。

### 修复

**Step 1**：防御性读取，避免 KeyError

```python
# L389 修改
base_concurrency_limit = layered_config.get("concurrency_limit", 4)
```

**Step 2**：统一配置读取方式。删除 `__init__` 中的快照存储，方法内统一从 `settings` 动态读取（支持热重载）：

```python
# __init__ 删除 L38-43 的快照赋值，改为方法内按需读取
# 示例：_generate_batch_llm 内部已通过 layered_config = settings.rag_config["layered_content"] 读取
# 其他引用 self.batch_size / self.l0_max_length 的方法也改用 settings 动态读取
```

### 验证

- [ ] Mock batch LLM 调用抛异常时，fallback 到并发调用正常执行
- [ ] 并发调用数不超过 `concurrency_limit`
- [ ] 配置热重载后（数据库更新 → Redis Pub/Sub → ConfigCache），下次调用使用新值
