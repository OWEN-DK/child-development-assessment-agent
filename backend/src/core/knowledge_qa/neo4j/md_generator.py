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


KG_EXTRACTION_PROMPT = """你是一位儿童发展与教育领域的知识提取专家，擅长从书籍章节中提炼**完整、多层次**的结构化知识。

**核心原则**: 宁多勿少——每一条对读者有价值的信息都应被提取。丢弃信息比冗余信息的代价大得多。

章节标题: {chapter_title}
章节内容:
{chapter_content}

请从以上章节中提取以下 **全部 7 类** 知识（如果章节中存在的话）:

---

### 1. 实体 (concepts) — 章节中出现的任何重要概念

实体类型（entity_type）包括:
- **Problem**: 问题/障碍/困难（如 ADHD、阅读障碍、焦虑）
- **Solution**: 解决方案/干预方法（如有氧运动、冥想、认知训练）
- **BrainRegion**: 脑区（如前额叶皮层、海马体、杏仁核）
- **CognitiveProcess**: 认知过程（如注意力、工作记忆、执行功能、元认知）
- **Theory**: 理论/模型（如神经可塑性理论、双重编码理论、刻意练习理论）
- **Mechanism**: 机制/原理（如 BDNF 分泌、突触修剪、神经发生）
- **Risk**: 风险因素（如久坐、睡眠不足、屏幕时间过长）
- **DevelopmentalStage**: 发展阶段（如学龄前、青春期、关键期）
- **Strategy**: 策略/方法论（如间隔重复、费曼技巧、主动回忆）
- **KeyInsight**: 核心洞见/重要结论（如"运动是大脑的肥料"）
- **ResearchFinding**: 研究发现/实验结论（如"30 分钟有氧运动后前额叶激活增强"）

每个实体必须包含:
- name: 实体名称
- entity_type: 以上类型之一
- description: 详细描述（**不少于 20 字**，保留原文关键信息）
- source: 所在章节

额外字段（按类型可选）:
- symptoms: []（仅 Problem）
- brain_regions: []（Problem / CognitiveProcess 关联的脑区）
- evidence: "支撑证据"（ResearchFinding）
- mechanism: "运作机制"（Mechanism）
- key_figures: []（Theory 的提出者/代表人物）

### 2. 主张/论点 (claims) — 实体之间的关系

- source_concept: 关系起点实体名
- target_concept: 关系终点实体名
- relation_type: 改善|导致|抑制|促进|包含|属于|相关|替代
- confidence: high|medium|low
- evidence: "支撑这段关系的证据或出处（**至少一句话**）"

### 3. 运动处方 (prescriptions) — 如有运动/身体活动建议

- exercise: 运动名称
- frequency: 频率
- duration: 时长
- intensity: 强度
- age_range: 适用年龄
- target_problem: 解决什么问题
- contraindications: [禁忌]

### 4. 核心论点 (key_arguments) — 章节作者想要传达的中心思想

- argument: "论点内容（一句话概括）"
- supporting_evidence: ["支撑论据1", "支撑论据2"]
- counterarguments: ["可能的反驳或局限性"]

### 5. 案例/故事 (case_studies) — 章节中的具体案例

- title: "案例标题"
- summary: "案例概要（50-100字）"
- related_concepts: ["涉及的概念名"]
- takeaway: "这个案例说明了什么"

### 6. 数据/事实 (data_points) — 具体的数字、比例、实验结果

- metric: "指标名称"
- value: "数值"
- context: "这个数据的上下文"
- source_attribution: "数据来源（如论文、实验）"

### 7. 章节摘要 (chapter_summary)

- central_theme: "本章核心主题（一句话）"
- key_takeaways: ["要点1", "要点2", "要点3"]
- connection_to_book: "本章与全书主旨的关系"

---

**输出格式**: 严格 YAML（不要用 Markdown 代码块包裹）。如果某类信息在本章中不存在，直接省略该字段。
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
        chapter_content=chapter.markdown,
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
