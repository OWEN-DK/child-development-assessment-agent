"""动态层级遍历 — 查询时从社区树中探索相关块

流程: 向量种子 → 种子社区 → 公共祖先 → 层级遍历(便宜LLM剪枝) → 加载命中块 → 构建知识上下文
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

# 相关性判定阈值（保守值，宁多勿少）
RELEVANCE_THRESHOLD = 0.5

# 默认 token 预算（知识上下文最大 token 数）
DEFAULT_MAX_TOKENS = 12000

# 连续失败熔断阈值：连续 N 次 LLM 判定失败后，后续默认返回 False（不相关）
CONSECUTIVE_FAILURE_THRESHOLD = 3

# 请求级连续失败计数器（通过 ContextVar 跟踪）
_consecutive_failures: dict[str, int] = defaultdict(int)

RELEVANCE_CHECK_SYSTEM = """你是一个文档相关性判定助手。你的任务是判断一个知识社区是否与用户问题相关。

用户问题: {question}

社区: {label}
包含概念: {entities}
概念类型: {entity_types}

这个社区与用户的问题相关吗？只需回答"相关"或"不相关"。
如果社区中的概念与问题的任何方面有直接或间接联系，都应判定为"相关"。"""


@dataclass
class TraversalHit:
    """层级遍历命中的社区及其关联块"""

    node_id: str
    label: str
    entity_names: list[str] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)



def _n(node: Any, key: str, default: Any = None) -> Any:
    """统一节点属性访问：兼容 dict 和 ORM 对象。"""
    if node is None:
        return default
    if isinstance(node, dict):
        return node.get(key, default)
    return getattr(node, key, default)




async def _check_relevance(
    question: str,
    community: dict,
    model_name: str = "qwen3.5-27b",
) -> bool:
    """用 27B 判定单个社区的相关性。

    内置连续失败熔断：连续失败超过阈值后直接返回 False，避免无效等待。
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    from src.core.llm.factory import LLMServiceFactoryCompat

    # 熔断检查：连续失败过多时直接返回 False
    if _consecutive_failures[question] >= CONSECUTIVE_FAILURE_THRESHOLD:
        logger.warning(f"连续 {_consecutive_failures[question]} 次相关性判定失败，熔断返回 False")
        return False

    entity_types = community.get("entity_types", [])
    type_str = ", ".join(entity_types) if entity_types else "未知"

    system = RELEVANCE_CHECK_SYSTEM.format(
        question=question,
        label=community.get("label", "未命名社区"),
        entities=", ".join(community.get("entity_names", [])[:10]),
        entity_types=type_str,
    )

    try:
        model = LLMServiceFactoryCompat.create_raw(
            model_name=model_name,
            temperature=0.0,
        )
        response = await model.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content="这个社区与用户问题相关吗？"),
        ])
        content = response.content if hasattr(response, "content") else str(response)
        # 反向逻辑："不相关" 不在回答中即判定为相关
        result = "不相关" not in content and content.strip() != ""
        # 成功调用，重置失败计数
        _consecutive_failures[question] = 0
        return result
    except Exception as e:
        _consecutive_failures[question] += 1
        logger.warning(f"相关性判定失败 ({_consecutive_failures[question]}/{CONSECUTIVE_FAILURE_THRESHOLD}): {e}")
        # 未达熔断阈值时保守判定为相关
        return True


async def _batch_check_relevance(
    question: str,
    communities: list[dict],
    model_name: str = "qwen3.5-27b",
) -> list[bool]:
    """批量判定多个社区的相关性（并行）。"""
    semaphore = asyncio.Semaphore(10)

    async def _limited_check(comm: dict) -> bool:
        async with semaphore:
            return await _check_relevance(question, comm, model_name)

    return await asyncio.gather(*[_limited_check(c) for c in communities])


async def find_lowest_common_ancestor(
    community_ids: list[str],
    community_repo: Any,
) -> str | None:
    """找到种子社区的最低公共祖先（LCA）。

    通过查询每个社区的 parent 链，找到所有链的最深公共节点。
    """
    if not community_ids:
        return None
    if len(community_ids) == 1:
        return community_ids[0]

    async def _get_ancestor_chain(cid: str) -> list[str]:
        """获取单个社区的祖先链（从自身到根）。"""
        chain: list[str] = [cid]
        current_id = cid
        for _ in range(20):  # 防止无限循环
            node = await community_repo.get_node(current_id)
            if node is None or _n(node, 'parent_id') is None:
                break
            chain.append(_n(node, 'parent_id'))
            current_id = _n(node, 'parent_id')
        return chain

    # 并行获取所有祖先链
    ancestor_chains = await asyncio.gather(
        *[_get_ancestor_chain(cid) for cid in community_ids]
    )

    # 从根向叶找最深公共节点
    # 反转链使其从根到叶
    reversed_chains = [list(reversed(c)) for c in ancestor_chains]
    min_len = min(len(c) for c in reversed_chains)

    lca = reversed_chains[0][0]  # 至少共享根节点
    for i in range(min_len):
        nodes_at_i = {c[i] for c in reversed_chains}
        if len(nodes_at_i) == 1:
            lca = nodes_at_i.pop()
        else:
            break

    return lca


async def explore_community_tree(
    question: str,
    root_id: str,
    community_repo: Any,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    relevance_model: str = "qwen3.5-27b",
    entity_boost_names: set[str] | None = None,
) -> list[TraversalHit]:
    """从根节点开始，逐层判定社区相关性，剪枝后加载命中叶子社区的 chunk_ids。

    优化：非根层携带完整节点对象（避免冗余 get_node），
    同层非叶子节点批量查询子节点（get_children_batch 单次 DB 查询）。

    Returns:
        命中叶子社区的 TraversalHit 列表（含社区标签、实体名、块ID）
    """
    hits: list[TraversalHit] = []
    token_budget = max_tokens
    visited: set[str] = set()

    # 第一层：只有 root_id，需要查一次 get_node
    root_node = await community_repo.get_node(root_id)
    if root_node is None:
        return hits
    current_level: list[Any] = [root_node]  # 携带完整 GraphCommunityNode 对象

    while current_level and token_budget > 0:
        next_level: list[Any] = []

        # 去重 + 分离叶子/非叶子
        non_leaf_nodes: list[Any] = []
        for node in current_level:
            if token_budget <= 0:
                break
            if _n(node, 'node_id') in visited:
                continue
            visited.add(_n(node, 'node_id'))

            # 叶子社区：记录命中
            if _n(node, 'is_leaf'):
                chunk_ids = _n(node, 'chunk_ids') or []
                hits.append(TraversalHit(
                    node_id=_n(node, 'node_id'),
                    label=_n(node, 'label') or "未命名社区",
                    entity_names=_n(node, 'entity_names') or [],
                    chunk_ids=chunk_ids,
                ))
                token_budget -= len(chunk_ids) * 500
            else:
                non_leaf_nodes.append(node)

        # 批量查询所有非叶子节点的子节点（单次 DB 查询）
        if non_leaf_nodes:
            non_leaf_ids = [n.node_id for n in non_leaf_nodes]
            children_map = await community_repo.get_children_batch(non_leaf_ids)

            # 并行判定所有子节点的相关性
            all_children: list[Any] = []
            parent_of: dict[str, str] = {}  # child_id → parent_id
            for parent_id, children in children_map.items():
                for c in children:
                    all_children.append(c)
                    parent_of[_n(c, 'node_id')] = parent_id

            if all_children:
                child_infos = [
                    {
                        "id": _n(c, 'node_id'),
                        "label": _n(c, 'label') or "未命名",
                        "entity_names": _n(c, 'entity_names') or [],
                    }
                    for c in all_children
                ]

                # ── 实体加分: 包含 Neo4j 实体的社区直接判定为相关（跳过 LLM）──
                boosted_ids: set[str] = set()
                if entity_boost_names:
                    for info in child_infos:
                        community_ents = set(info.get("entity_names") or [])
                        if community_ents & entity_boost_names:
                            boosted_ids.add(info["id"])
                    if boosted_ids:
                        logger.debug(
                            "实体加分: %d/%d 个社区包含关联实体，跳过 LLM 判定",
                            len(boosted_ids), len(child_infos),
                        )

                # 只对未被加分的社区做 LLM 相关性判定
                unchecked_items = [
                    (c, info) for c, info in zip(all_children, child_infos)
                    if info["id"] not in boosted_ids
                ]

                if unchecked_items:
                    unchecked_infos = [info for _, info in unchecked_items]
                    relevance_scores = await _batch_check_relevance(
                        question=question,
                        communities=unchecked_infos,
                        model_name=relevance_model,
                    )
                    for (child, _), relevant in zip(unchecked_items, relevance_scores):
                        if relevant and child.node_id not in visited:
                            next_level.append(child)

                # 加分社区直接加入下一层
                for child in all_children:
                    if child.node_id in boosted_ids and child.node_id not in visited:
                        next_level.append(child)

        current_level = next_level

    total_chunks = sum(len(h.chunk_ids) for h in hits)
    logger.info(
        f"层级遍历完成: 命中 {len(hits)} 个社区, {total_chunks} 个块, "
        f"剩余 token 预算 {token_budget}"
    )
    return hits


async def build_knowledge_context(
    question: str,
    hits: list[TraversalHit],
    chunk_loader: Callable[[list[str]], Coroutine[Any, Any, dict[str, str]]] | None = None,
    max_chars: int | None = None,
) -> str:
    """将遍历命中结果组织为结构化 Markdown 知识上下文。

    Args:
        question: 用户问题
        hits: explore_community_tree 返回的命中列表
        chunk_loader: 可选的块文本加载器，接收 chunk_ids 返回 {id: text}
        max_chars: 上下文最大字符数。默认按 DEFAULT_MAX_TOKENS × 2 估算
            （中文约 1 token = 2 字符）。超出时截断尾部社区。

    Returns:
        结构化的 Markdown 知识上下文
    """
    if not hits:
        return ""

    # 字符级截断阈值（中文约 1 token ≈ 2 字符）
    char_limit = max_chars or (DEFAULT_MAX_TOKENS * 2)

    # 加载块文本（如果提供了 loader）
    all_chunk_ids = list(dict.fromkeys(
        cid for h in hits for cid in h.chunk_ids
    ))
    chunk_texts: dict[str, str] = {}
    if chunk_loader and all_chunk_ids:
        try:
            chunk_texts = await chunk_loader(all_chunk_ids)
        except Exception as e:
            logger.warning(f"块文本加载失败: {e}，仅使用社区元信息")

    # 按社区组织输出（逐个追加，超出阈值时截断）
    header = (
        "## 知识上下文\n"
        f"> 从知识图谱中动态探索得到，共命中 {len(hits)} 个社区、"
        f"{len(all_chunk_ids)} 个原文片段。\n"
    )
    parts: list[str] = [header]
    total_chars = len(header)
    included_count = 0

    for hit in hits:
        section_parts: list[str] = []
        section_parts.append(f"### 社区：{hit.label}\n")

        # 关键概念
        if hit.entity_names:
            concepts = "、".join(hit.entity_names[:8])
            if len(hit.entity_names) > 8:
                concepts += f" 等 {len(hit.entity_names)} 个"
            section_parts.append(f"**关键概念**：{concepts}\n")

        # 原文片段
        if chunk_texts and hit.chunk_ids:
            section_parts.append("**原文片段**：\n")
            for i, cid in enumerate(hit.chunk_ids[:5], 1):
                text = chunk_texts.get(cid, "")
                if text:
                    excerpt = text[:200].replace("\n", " ")
                    section_parts.append(f"- [片段{i}] {excerpt}...\n")
            if len(hit.chunk_ids) > 5:
                section_parts.append(f"- ...还有 {len(hit.chunk_ids) - 5} 个片段\n")

        section_parts.append("\n")
        section_text = "".join(section_parts)

        if total_chars + len(section_text) > char_limit:
            logger.info(
                f"知识上下文达到字符上限 ({char_limit})，截断："
                f"已包含 {included_count}/{len(hits)} 社区"
            )
            break

        parts.append(section_text)
        total_chars += len(section_text)
        included_count += 1

    context = "".join(parts)
    logger.info(f"知识上下文构建完成: {len(context)} 字符 ({included_count}/{len(hits)} 社区)")
    return context
