"""AI MD 生成器 — 四阶段流水线。

放置位置: backend/src/core/knowledge_qa/neo4j/md_generator.py
模型: qwen3.7-max (主力) / qwen3.5-27b (fallback)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, Protocol

from .chapter_parser import Chapter, ChapterParseResult

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """LLM 客户端协议。"""
    async def generate(self, prompt: str, model: str) -> str: ...


@dataclass
class ChapterResult:
    """单章生成结果。"""
    chapter_id: str
    success: bool
    md_content: str = ""
    error: Optional[str] = None


@dataclass
class GenerationProgress:
    """生成进度。"""
    total_chapters: int = 0
    completed: int = 0
    failed: int = 0
    current_chapter: str = ""


KG_EXTRACTION_PROMPT = """你是一位儿童发展与教育领域的知识提取专家。
从以下章节内容中提取结构化知识，输出 YAML 格式。

提取内容：
1. **概念** (concepts): Problem / Solution / BrainRegion / Risk 等实体
2. **主张** (claims): 实体之间的因果/相关关系
3. **运动处方** (prescriptions): 如有运动相关建议，提取频率/时长/强度/年龄

章节标题: {chapter_title}
章节内容:
{chapter_content}

输出格式严格按 YAML:
concepts:
  - name: "概念名"
    entity_type: Problem|Solution|BrainRegion|Risk
    description: "简要描述"
    symptoms: ["症状1"]  # 仅 Problem
    source: "章节名"

claims:
  - source_concept: "概念A"
    target_concept: "概念B"
    claim_type: causal|correlational|supports
    confidence: high|medium|low
    evidence: "证据摘要"

prescriptions:
  - exercise: "运动名称"
    frequency: "频率"
    duration: "时长"
    intensity: "强度"
    age_range: "年龄范围"
    contraindications: ["禁忌1"]
"""


async def generate_chapter_md(
    chapter: Chapter,
    llm_client: LLMClient,
    model: str = "qwen3.7-max",
    timeout: int = 120,
    max_retries: int = 3,
) -> ChapterResult:
    """为单个章节生成结构化 MD。

    Args:
        chapter: 章节数据
        llm_client: LLM 客户端
        model: 模型名称
        timeout: 超时秒数
        max_retries: 最大重试次数

    Returns:
        ChapterResult
    """
    prompt = KG_EXTRACTION_PROMPT.format(
        chapter_title=chapter.title,
        chapter_content=chapter.markdown[:8000],
    )

    for attempt in range(max_retries):
        try:
            response = await asyncio.wait_for(
                llm_client.generate(prompt=prompt, model=model),
                timeout=timeout,
            )
            return ChapterResult(chapter_id=chapter.id, success=True, md_content=response)
        except asyncio.TimeoutError:
            logger.warning("Chapter %s timeout (attempt %d/%d)", chapter.id, attempt + 1, max_retries)
        except Exception as e:
            logger.warning("Chapter %s error: %s (attempt %d/%d)", chapter.id, e, attempt + 1, max_retries)
        await asyncio.sleep(2 ** attempt)

    return ChapterResult(chapter_id=chapter.id, success=False, error="Max retries exceeded")


async def generate_book_md(
    parse_result: ChapterParseResult,
    llm_client: LLMClient,
    model: str = "qwen3.7-max",
    concurrency: int = 3,
    on_progress: Optional[Callable[[GenerationProgress], None]] = None,
) -> list[ChapterResult]:
    """并行为整本书的所有章节生成 MD。

    Args:
        parse_result: EPUB 解析结果
        llm_client: LLM 客户端
        model: 模型名称
        concurrency: 并发数
        on_progress: 进度回调

    Returns:
        所有章节的生成结果列表
    """
    progress = GenerationProgress(total_chapters=len(parse_result.chapters))
    semaphore = asyncio.Semaphore(concurrency)

    async def _gen(ch: Chapter) -> ChapterResult:
        async with semaphore:
            progress.current_chapter = ch.title
            if on_progress:
                on_progress(progress)
            result = await generate_chapter_md(ch, llm_client, model)
            if result.success:
                progress.completed += 1
            else:
                progress.failed += 1
            if on_progress:
                on_progress(progress)
            return result

    tasks = [_gen(ch) for ch in parse_result.chapters]
    results = await asyncio.gather(*tasks)
    return list(results)
