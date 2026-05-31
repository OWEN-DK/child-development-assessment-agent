"""Phase 0: 全书深度阅读。

放置位置: backend/src/core/knowledge_qa/d2g/book_reader.py
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Protocol

from src.core.knowledge_qa.neo4j.chapter_parser import Chapter, ChapterParseResult
from .models import BookContext

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """LLM 客户端协议。"""
    async def generate_structured(
        self, prompt: str, schema: type, model: str,
    ) -> dict | list: ...


# ──────────────────────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────────────────────

SEGMENT_READING_PROMPT = """你是一位学术编辑，正在深度阅读《{book_title}》的第 {segment_index}/{total_segments} 部分。

## 本部分内容（完整原文）
{segment_content}

---

请输出以下分析:

### 本部分核心主张
用 2-3 句话概括作者在本部分最想说服读者相信的观点。

### 关键论点
列出作者在本部分论证的 2-4 个关键论点，每个附带简要说明和支撑证据。

### 关键术语
列出本部分出现的专业术语（5-10 个），每个给出完整定义。

### 本部分案例/故事
标题 + 完整概要（保留关键细节，不是一句话概括）。

### 本部分关键数据
每个数据附带: 数值、上下文、来源、意义。

### 与前面部分的关联
引用了什么、呼应了什么、推进了什么。

### 留给后续部分的悬念/铺垫
作者预告了什么、哪些问题尚未解答。
"""


BOOK_SYNTHESIS_PROMPT = """你是一位学术编辑，正在综合《{book_title}》全书各部分的深度阅读结果。

## 各部分阅读结果
{segment_analyses}

---

请输出以下全书概览:

### 全书主旨
用 2-3 句话概括这本书最核心的主张。不是"这本书讲了什么"，而是"作者想要说服你相信什么"。

### 核心论点
列出作者在全书中反复论证的 3-5 个关键论点。每个论点用一句话概括，附带简要说明。

### 关键术语表
列出全书中反复出现的专业术语（10-20 个），每个给出完整定义。

### 章节脉络
简述各章之间的逻辑关系（"第X章为第Y章提供了理论基础"等）。
"""


# ──────────────────────────────────────────────────────────────
# 公开 API
# ──────────────────────────────────────────────────────────────


async def deep_book_reading(
    parse_result: ChapterParseResult,
    llm_client: LLMClient,
    model: str = "qwen-turbo",
    segment_size: int = 5,
    on_progress: "Callable[[dict], None] | None" = None,
) -> BookContext:
    """全书深度阅读: 分段阅读 → 综合全书脉络。

    Args:
        parse_result: EPUB 解析结果
        llm_client: LLM 客户端
        model: 模型名称
        segment_size: 每段包含的章节数

    Returns:
        BookContext 全书上下文
    """
    chapters = parse_result.chapters
    segments = [
        chapters[i : i + segment_size]
        for i in range(0, len(chapters), segment_size)
    ]
    logger.info("[Phase 0] 开始全书深度阅读: %d 章 → %d 段 (model=%s)",
        len(chapters), len(segments), model)

    import time as _time

    # Step 1: 分段阅读（并行）
    async def _read_segment(idx: int, seg: list[Chapter]) -> str:
        seg_titles = ", ".join(ch.title[:20] for ch in seg)
        logger.info("[Phase 0] 段 %d/%d 开始阅读: %s", idx + 1, len(segments), seg_titles)
        _t = _time.monotonic()
        full_text = "\n\n---\n\n".join(
            f"## {ch.title}\n\n{ch.markdown}" for ch in seg
        )
        prompt = SEGMENT_READING_PROMPT.format(
            book_title=parse_result.book_title,
            segment_index=idx + 1,
            total_segments=len(segments),
            segment_content=full_text,
        )
        result = await llm_client.generate_structured(
            prompt=prompt,
            schema=dict,  # 自由文本输出
            model=model,
        )
        logger.info("[Phase 0] 段 %d/%d 阅读完成 (%.1fs)", idx + 1, len(segments), _time.monotonic() - _t)
        return str(result)

    _t_all = _time.monotonic()
    _segments_completed = 0
    _total_segments = len(segments)

    async def _read_segment_with_progress(idx: int, seg: list[Chapter]) -> str:
        nonlocal _segments_completed
        result = await _read_segment(idx, seg)
        _segments_completed += 1
        logger.info("[Phase 0] 段进度: %d/%d 完成", _segments_completed, _total_segments)
        if on_progress:
            on_progress({
                "phase": "phase0_reading",
                "phase_label": f"正在深度阅读全书...（{_segments_completed}/{_total_segments} 段）",
                "segments_completed": _segments_completed,
                "total_segments": _total_segments,
            })
        return result

    analyses = await asyncio.gather(
        *[_read_segment_with_progress(i, seg) for i, seg in enumerate(segments)]
    )
    logger.info("[Phase 0] 全部分段阅读完成 (%.1fs)", _time.monotonic() - _t_all)

    # Step 2: 综合
    logger.info("[Phase 0] 开始全书综合")
    _t_syn = _time.monotonic()
    synthesis_prompt = BOOK_SYNTHESIS_PROMPT.format(
        book_title=parse_result.book_title,
        segment_analyses="\n\n---\n\n".join(analyses),
    )
    synthesis = await llm_client.generate_structured(
        prompt=synthesis_prompt,
        schema=dict,
        model=model,
    )
    logger.info("[Phase 0] 全书综合完成 (%.1fs)", _time.monotonic() - _t_syn)

    # 从综合结果中提取结构化字段
    # synthesis 是 LLM 的文本输出，需要解析
    synthesis_text = str(synthesis)

    return BookContext(
        book_title=parse_result.book_title,
        core_thesis=_extract_section(synthesis_text, "全书主旨"),
        key_arguments=_extract_list(synthesis_text, "核心论点"),
        terminology=_extract_terminology(synthesis_text),
        chapter_outline=_extract_section(synthesis_text, "章节脉络"),
    )




# ──────────────────────────────────────────────────────────────
# Phase 0 自校验（§07-8.1）
# ──────────────────────────────────────────────────────────────


async def validate_book_context(
    book_context: BookContext,
    segment_analyses: list[str],
) -> dict:
    """Phase 0 完成后执行自校验：术语重叠率 + 跨段一致性检查。

    日志记录: book_id, term_overlap_rate, validation_passed, corrections_applied, duration_ms
    告警阈值: term_overlap_rate < 40% → 建议重跑 Phase 0

    Returns:
        {
            "term_overlap_rate": float,      # 术语在段间的重叠率
            "validation_passed": bool,       # 是否通过校验
            "corrections_applied": int,      # 修正次数
            "issues": list[str],             # 发现的问题列表
        }
    """
    import re
    import time
    start = time.monotonic()

    issues: list[str] = []
    corrections = 0

    # ── 1. 术语重叠率检查 ──
    # 从各段中提取"**术语**: 定义"模式的术语名
    segment_terms: list[set[str]] = []
    for analysis in segment_analyses:
        terms = set()
        for m in re.finditer(r'\*\*(.+?)\*\*[：:]', analysis):
            terms.add(m.group(1).strip())
        segment_terms.append(terms)

    # 计算段间术语重叠率（Jaccard 平均）
    overlap_rates = []
    for i in range(len(segment_terms)):
        for j in range(i + 1, len(segment_terms)):
            union = segment_terms[i] | segment_terms[j]
            intersection = segment_terms[i] & segment_terms[j]
            if union:
                overlap_rates.append(len(intersection) / len(union))

    avg_overlap = sum(overlap_rates) / len(overlap_rates) if overlap_rates else 0.0

    if avg_overlap < 0.40:
        issues.append(
            f"术语重叠率 {avg_overlap:.1%} 低于 40% 阈值，Phase 0 全书阅读质量可能严重偏差，建议重跑"
        )

    # ── 2. 全书术语覆盖检查 ──
    all_terms: set[str] = set()
    for terms in segment_terms:
        all_terms |= terms

    # 检查 key_terminology 是否包含了段中出现的术语
    context_terms = set(book_context.terminology.keys()) if book_context.terminology else set()
    missing_in_context = all_terms - context_terms
    if len(missing_in_context) > 5:
        issues.append(
            f"有 {len(missing_in_context)} 个术语出现在分段阅读中但未纳入全书术语表: "
            f"{', '.join(sorted(list(missing_in_context))[:10])}..."
        )

    # ── 3. 核心论点一致性检查 ──
    # 简单检查：全书核心论点不应为空
    if not book_context.key_arguments or len(book_context.key_arguments) < 2:
        issues.append("核心论点数量过少（< 2），Phase 0 提取可能不充分")
        corrections += 1

    if not book_context.core_thesis or len(book_context.core_thesis) < 20:
        issues.append("全书主旨过短或为空（< 20 字），Phase 0 提取可能不充分")
        corrections += 1

    duration_ms = int((time.monotonic() - start) * 1000)
    passed = len(issues) == 0

    logger.info(
        "Phase 0 自校验完成: book_id=%s, term_overlap_rate=%.1f%%, "
        "validation_passed=%s, corrections_applied=%d, duration_ms=%d",
        book_context.book_title, avg_overlap * 100, passed, corrections, duration_ms,
    )

    if not passed:
        logger.warning("Phase 0 自校验发现问题: %s", issues)

    return {
        "term_overlap_rate": round(avg_overlap, 4),
        "validation_passed": passed,
        "corrections_applied": corrections,
        "issues": issues,
    }


# ──────────────────────────────────────────────────────────────
# 内部工具函数
# ──────────────────────────────────────────────────────────────


def _extract_section(text: str, heading: str) -> str:
    """从文本中提取指定标题下的内容。"""
    import re
    pattern = rf"###?\s*{heading}\s*\n(.*?)(?=###?\s|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _extract_list(text: str, heading: str) -> list[str]:
    """从文本中提取指定标题下的列表项。"""
    section = _extract_section(text, heading)
    if not section:
        return []
    import re
    items = re.findall(r"^[-\d.*]+\s*(.+)$", section, re.MULTILINE)
    return [item.strip() for item in items if item.strip()]


def _extract_terminology(text: str) -> dict[str, str]:
    """从术语表中提取 {术语: 定义}。"""
    section = _extract_section(text, "关键术语")
    if not section:
        return {}
    import re
    terms = {}
    for match in re.finditer(r"[-*]\s*\*\*(.+?)\*\*[：:]\s*(.+)", section):
        terms[match.group(1).strip()] = match.group(2).strip()
    return terms
