"""自定义知识快速匹配节点 — 三通道匹配，注入 custom_knowledge_context + entities

放置位置: backend/src/core/knowledge_qa/nodes/fast_knowledge_match.py
超时: 3 秒（超时降级为未命中）
降级: 任何异常都不阻塞主流程
"""

from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict

from src.schemas.knowledge_qa import KnowledgeQAState, push_progress

logger = logging.getLogger(__name__)

MATCH_TIMEOUT = 3  # 秒


async def fast_knowledge_match_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """自定义知识快速匹配。

    三通道匹配: 关键词 → 正则 → 语义。
    命中 → 注入 custom_knowledge_context + custom_knowledge_entities。
    未命中 → 无注入，继续正常流程。
    """
    await push_progress("fast_knowledge_match", "正在匹配自定义知识…")

    if not state.question.strip():
        return {"fast_knowledge_hit": False, "current_step": ["fast_match_skip"]}

    try:
        result = await asyncio.wait_for(_do_match(state.question), timeout=MATCH_TIMEOUT)
        if result is not None:
            return result
    except asyncio.TimeoutError:
        logger.warning(f"自定义知识匹配超时 ({MATCH_TIMEOUT}s)，降级跳过")
    except Exception as e:
        logger.warning(f"自定义知识匹配异常: {e}，降级跳过")

    return {"fast_knowledge_hit": False, "current_step": ["fast_match_miss"]}


async def _do_match(question: str) -> Dict[str, Any] | None:
    """执行三通道匹配。"""
    from src.core.database import async_session_factory
    from src.repository.custom_knowledge_repository import CustomKnowledgeRepository
    from src.service.custom_knowledge_service import CustomKnowledgeService
    from src.core.knowledge_qa.neo4j.driver import get_neo4j_driver
    from src.utils.embedding_helper import EmbeddingHelper
    from src.config import settings

    # 构造依赖
    neo4j_driver = get_neo4j_driver()
    repo = CustomKnowledgeRepository(async_session_factory, neo4j_driver)

    emb = None
    try:
        key = getattr(settings, "dashscope_api_key", None) or getattr(settings, "embedding_api_key", None)
        if key:
            emb = EmbeddingHelper(model_name="text-embedding-v4", api_key=key)
    except Exception:
        pass

    svc = CustomKnowledgeService(repo, emb)
    match_result = await svc.match(question)

    if not match_result.hit:
        return None

    # ── 命中: 构造 context + entities ──
    parts = [
        "## ⚡ 自定义知识（最高优先级）",
        f"> 匹配通道: {match_result.match_channel} | 命中 {len(match_result.matched_items)} 条",
        "",
    ]
    entities = []

    for item in match_result.matched_items:
        title = item.get("title", "")
        content = item.get("content", "")
        source = item.get("source", "")

        header = f"### 📌 {title}"
        if source:
            header += f"（来源: {source}）"
        parts.extend([header, "", content, "", "---", ""])

        # 提取关联实体名
        for rel in item.get("relations", []):
            tn = rel.get("target_name", "")
            if tn and tn not in entities:
                entities.append(tn)
        # 标题本身也是关键实体
        if title and title not in entities:
            entities.append(title)

    context = "\n".join(parts)
    logger.info(
        f"自定义知识命中 [{match_result.match_channel}]: "
        f"{len(match_result.matched_items)} 条, {len(entities)} 实体, "
        f"{match_result.latency_ms}ms"
    )

    return {
        "custom_knowledge_context": context,
        "custom_knowledge_entities": entities,
        "fast_knowledge_hit": True,
        "current_step": ["fast_match_hit"],
    }
