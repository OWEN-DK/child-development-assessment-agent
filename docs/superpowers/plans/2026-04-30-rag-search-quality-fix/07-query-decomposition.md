# 07 P5：复杂查询子查询分解

> 在 03（RRF 融合）和 04（分类器统一）基础上，对 COMPLEX 查询启用子查询分解。
> 复杂查询拆成多个简单子查询分别检索，结果归并后经 reranker 精排。

---

## 背景核实

当前检索链路对简单和复杂查询的处理完全相同：
1. 同义词扩展 → BM25 + 向量并行检索 → RRF 融合 → 可选 reranker → 过滤截断

复杂查询（如"分析小明在前庭觉、精细动作、社交三个维度的发展情况，生成综合评估报告"）的检索效果差，因为：
- 包含多个独立概念（"前庭觉""精细动作""社交"），单次向量检索难以同时命中
- 包含语义噪声（"小明""生成报告"），干扰检索信号
- BM25 对长查询的精确匹配效果差

**子查询分解 + 独立检索 + 结果归并** 是业内处理复杂查询的标准方案（LlamaIndex `SubQuestionQueryEngine`、LangChain `MultiQueryRetriever`）。

---

## P5-1 新增 QueryDecomposer

### 修复

**新建文件**：`backend/src/core/query_decomposer.py`

```python
"""查询分解器 — 将复杂查询拆解为多个聚焦子查询"""
import json
import re
from typing import List

from src.core.llm.factory import LLMFramework, LLMServiceFactoryCompat
from src.schemas import LLMMessage, LLMRequest
from src.utils.logger import logger


class SubQuery:
    """子查询"""
    def __init__(self, text: str, focus: str = ""):
        self.text = text        # "前庭觉训练方法"
        self.focus = focus      # "前庭觉维度"


class QueryDecomposer:
    """将复杂查询分解为 2-4 个聚焦子查询"""

    DECOMPOSE_PROMPT_KEY = "query_decomposition"

    def __init__(self, llm_enabled: bool = True, max_sub_queries: int = 4):
        self.llm_enabled = llm_enabled
        self.max_sub_queries = max_sub_queries

    async def decompose(self, query: str) -> List[SubQuery]:
        """
        分解复杂查询

        Args:
            query: 原始复杂查询

        Returns:
            List[SubQuery]: 子查询列表。
            失败时返回只包含原始查询的列表（兜底不阻塞检索）。
        """
        if not self.llm_enabled:
            return self._rule_decompose(query)

        try:
            return await self._llm_decompose(query)
        except Exception as e:
            logger.warning(f"查询分解失败，回退到原始查询: {e}")
            return [SubQuery(text=query, focus="原始查询")]

    async def _llm_decompose(self, query: str) -> List[SubQuery]:
        """LLM 拆解复杂查询"""

        prompt = f"""你是一个查询拆解专家。将用户复杂查询拆解为 2-4 个简单子查询，每个子查询聚焦于单一概念或知识点。

规则：
1. 去除"分析""评估""对比"等指令词，提炼核心检索概念
2. 去除人名、特定个体名称（如"小明"），保留通用术语
3. 每个子查询 ≤ 20 字，独立可检索
4. 子查询间不重复，覆盖原始查询的所有关键概念

示例：
复杂查询：分析小明在前庭觉、精细动作、社交三个维度的发展情况
→ 子查询：
  - "前庭觉训练方法"
  - "精细动作发展评估标准"
  - "儿童社交能力培养"

复杂查询：对比感觉统合训练和注意力训练的效果差异
→ 子查询：
  - "感觉统合训练效果"
  - "注意力训练效果"

查询："{query}"

只返回 JSON 数组，不要其他文本：
[{{"text": "子查询1", "focus": "聚焦概念1"}}, ...]"""

        llm = LLMServiceFactoryCompat.create(
            framework=LLMFramework.LLAMAINDEX,
            model_name="qwen-turbo",  # 轻量模型，拆解不需要强推理
            scenario="query_decomposition",
            temperature=0.2,
        )

        response = await llm.chat(LLMRequest(
            messages=[
                LLMMessage(role="system", content="你是儿童发展领域的查询拆解专家。"),
                LLMMessage(role="user", content=prompt),
            ],
            model_name="qwen-turbo",
            temperature=0.2,
            max_tokens=256,
            scenario="query_decomposition",
        ))

        # 解析 JSON 数组
        json_match = re.search(r"\[.*\]", response.content, re.DOTALL)
        if not json_match:
            raise ValueError(f"LLM 返回非 JSON 数组: {response.content[:100]}")

        data = json.loads(json_match.group())
        sub_queries = []
        for item in data[:self.max_sub_queries]:
            sub_queries.append(SubQuery(
                text=item.get("text", "").strip(),
                focus=item.get("focus", "").strip(),
            ))

        if not sub_queries:
            raise ValueError("拆解结果为空")

        logger.info(f"查询拆解: '{query[:50]}' → {[sq.text for sq in sub_queries]}")
        return sub_queries

    def _rule_decompose(self, query: str) -> List[SubQuery]:
        """规则兜底：按中文逗号/顿号/分号/和切分"""
        parts = re.split(r"[，、；和与及,;]", query)
        parts = [p.strip() for p in parts if len(p.strip()) >= 3]
        if len(parts) <= 1:
            return [SubQuery(text=query, focus="原始查询")]
        return [SubQuery(text=p, focus=p[:10]) for p in parts[:self.max_sub_queries]]
```

### 设计决策

| 决策点 | 选择 | 原因 |
|--------|------|------|
| LLM 模型 | `qwen-turbo` | 拆解不要求强推理，轻量模型快且便宜；可配置切换 |
| 兜底策略 | 返回原始查询 | 拆解失败不阻塞检索，一条总比零条好 |
| 子查询上限 | 4 | 超过 4 个子查询的检索延迟和 token 成本不划算 |
| 规则兜底 | 按中文标点切分 | 部分查询结构清晰（列举式），规则可零成本处理 |
| focus 字段 | 保留 | 用于上游解释结果时告诉用户"这个结果来自哪个维度" |

---

## P5-2 集成到 RetrievalFacade

### 修改文件：`backend/src/service/retrieval/facade.py`

```python
# 新增导入
from src.core.query_router import QueryRouter

class RetrievalFacade:
    def __init__(self, ...):
        # ... 现有初始化 ...
        self.query_router = QueryRouter()
        self.query_decomposer = QueryDecomposer(
            llm_enabled=settings.query_router_llm_enabled,
        )

    async def retrieve_knowledge(
        self, query: str, limit: int = 3, user_id: str = None
    ) -> List[KnowledgeItem]:
        """检索知识。复杂查询自动拆解为子查询分别检索后归并。"""

        # 1. 分类
        classification = await self.query_router.classify_async(query)

        if classification.query_type.value != "complex":
            # 简单/DEFAULT 查询：直通现有检索链路
            return await self._single_retrieve(query, limit, user_id)

        # 2. 复杂查询：拆解
        sub_queries = await self.query_decomposer.decompose(query)

        if len(sub_queries) <= 1:
            # 拆不出来，直通
            return await self._single_retrieve(query, limit, user_id)

        # 3. 各子查询并行检索
        import asyncio
        all_results = []
        tasks = [self._single_retrieve(sq.text, limit, user_id) for sq in sub_queries]
        per_query_results = await asyncio.gather(*tasks, return_exceptions=True)

        for sq, result in zip(sub_queries, per_query_results):
            if isinstance(result, Exception):
                logger.warning(f"子查询 '{sq.text}' 检索失败: {result}")
                continue
            # 标注来源子查询
            for item in result:
                item.metadata["sub_query"] = sq.text
                item.metadata["sub_focus"] = sq.focus
            all_results.extend(result)

        # 4. 去重 + 重排（传入原始查询，供 reranker 做相关性判断）
        merged = self._merge_and_rerank(query, all_results, limit)
        return merged

    async def _single_retrieve(
        self, query: str, limit: int, user_id: str = None
    ) -> List[KnowledgeItem]:
        """单次检索：走现有 RRF pipeline 或 knowledge_retriever"""
        use_pipeline = (
            settings.rag_query_pipeline_enabled
            and self._pipeline_orchestrator is not None
        )
        if use_pipeline:
            return await self._retrieve_via_pipeline(query, limit)
        else:
            return await self.knowledge_retriever.retrieve_knowledge(
                query=query, limit=limit, user_id=user_id
            )

    def _merge_and_rerank(
        self, original_query: str, results: List[KnowledgeItem], limit: int
    ) -> List[KnowledgeItem]:
        """子查询结果归并：内容去重 → reranker 精排 → 截断"""
        # 去重：基于内容 hash
        seen = set()
        deduped = []
        for item in results:
            h = hashlib.sha256(item.content.encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                deduped.append(item)

        # 如果有 reranker，对去重结果精排
        if self._pipeline_orchestrator:
            from src.core.reranker import CrossEncoderReranker
            try:
                reranker = CrossEncoderReranker()
                from llama_index.core.schema import NodeWithScore
                nodes = [NodeWithScore(node=item) for item in deduped]  # 包装
                # 注意：必须传入原始查询，bge-reranker 需要 query 做相关性判断
                # 传空 query 会导致 logits 退化为随机值，排序无效
                ranked = reranker.rerank(query=original_query, nodes=nodes)
                deduped = [self._node_to_item(n) for n in ranked]
            except Exception as e:
                logger.warning(f"合并后重排失败: {e}")

        return deduped[:limit]
```

### 修改文件：`backend/src/service/retrieval/knowledge_retriever.py`

`_execute_retrieval()` 方法签名移除 `age` 参数（已在 01 中处理）。其他逻辑不变。

---

## 验证

- [ ] `"注意力训练有哪些方法"`（SIMPLE）→ 不走分解，结果与修复前一致
- [ ] `"分析小明在前庭觉、精细动作、社交三个维度的发展情况"`（COMPLEX）→ 拆出 3+ 子查询，每个独立检索
- [ ] 子查询结果无重复（同一文档被多个子查询命中时只保留一次）
- [ ] 返回结果的 `metadata.sub_query` 字段标注了来源子查询
- [ ] 拆解 LLM 失败时不阻塞检索（回退到原始查询直通）
- [ ] `cd backend && uv run pytest` 现有测试不变
- [ ] Pipeline 和非 pipeline 路径的复杂查询结果均可返回

---

## 后续可选增强

| 增强项 | 说明 | 优先级 |
|--------|------|--------|
| 子查询权重 | 不同子查询赋予不同权重（核心概念权重高） | P6 |
| 动态子查询数 | 根据原始查询长度自适应 2-4 个子查询 | P6 |
| 缓存子查询结果 | 子查询结果独立缓存，相同子查询跨请求复用 | P7 |
| Prompt 模板化 | `query_decomposition` prompt 进 MySQL 管理 | P5（依赖 prompt 管理系统） |
