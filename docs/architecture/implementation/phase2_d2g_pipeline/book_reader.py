"""Phase 0: 全书深度阅读。

放置位置: backend/src/core/knowledge_qa/neo4j/book_reader.py
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from .chapter_parser import Chapter, ChapterParseResult
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

    # Step 1: 分段阅读（并行）
    async def _read_segment(idx: int, seg: list[Chapter]) -> str:
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
        return str(result)

    analyses = await asyncio.gather(
        *[_read_segment(i, seg) for i, seg in enumerate(segments)]
    )

    # Step 2: 综合
    synthesis_prompt = BOOK_SYNTHESIS_PROMPT.format(
        book_title=parse_result.book_title,
        segment_analyses="\n\n---\n\n".join(analyses),
    )
    synthesis = await llm_client.generate_structured(
        prompt=synthesis_prompt,
        schema=dict,
        model=model,
    )

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
