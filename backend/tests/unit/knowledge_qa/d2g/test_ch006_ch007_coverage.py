"""ch006 / ch007 覆盖率诊断测试

用法:
    # 需要真实 LLM，标记为 slow
    pytest backend/tests/unit/knowledge_qa/d2g/test_ch006_ch007_coverage.py -v -s --runslow

    # 或指定 EPUB 路径
    EPUB_PATH=/path/to/book.epub pytest backend/tests/unit/knowledge_qa/d2g/test_ch006_ch007_coverage.py -v -s --runslow
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections import Counter

import pytest

from src.core.knowledge_qa.d2g.chapter_extractor import extract_chapter
from src.core.knowledge_qa.d2g.long_chapter import segment_chapter
from src.core.knowledge_qa.d2g.master_graph import MasterGraph
from src.core.knowledge_qa.d2g.models import (
    BookContext,
    ChapterExtraction,
    ExtractedEntity,
    ExtractedRelationship,
    ModelConfig,
)
from src.core.knowledge_qa.neo4j.chapter_parser import Chapter, parse_epub

# ── 跳过标记 ──────────────────────────────────────────────────

slow = pytest.mark.skipif(
    not os.environ.get("RUNSLOW"),
    reason="设置 RUNSLOW=1 运行真实 LLM 测试",
)


def _find_epub() -> str | None:
    """尝试定位 book_id=92c50c6b 对应的 EPUB 文件。"""
    env_path = os.environ.get("EPUB_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 常见上传目录
    candidates = [
        "app_data/books",
        "uploads",
        "/tmp/uploads",
    ]
    for d in candidates:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith(".epub"):
                return os.path.join(d, f)
    return None


def _load_chapters(target_ids: list[str]) -> list[Chapter]:
    """从 EPUB 加载指定章节。"""
    epub_path = _find_epub()
    if not epub_path:
        pytest.skip("找不到 EPUB 文件，设置 EPUB_PATH 环境变量")

    book_id = "92c50c6b-4506-4ec1-9ac6-d02f3384effd"
    result = parse_epub(epub_path, book_id)

    chapters = [ch for ch in result.chapters if ch.id in target_ids]
    if not chapters:
        # 尝试按索引匹配 (ch006 = 第 6 个)
        all_chs = result.chapters
        for idx_str in ["006", "007"]:
            target_suffix = f"_ch{idx_str}"
            for ch in all_chs:
                if ch.id.endswith(target_suffix):
                    chapters.append(ch)

    if not chapters:
        # 最后尝试模糊匹配
        for ch in result.chapters:
            for tid in target_ids:
                if tid in ch.id or ch.id in tid:
                    chapters.append(ch)

    assert chapters, f"在 EPUB 中找不到章节 {target_ids}"
    return chapters


def _analyze_coverage(extraction: ChapterExtraction, chapter: Chapter) -> dict:
    """深度分析单章提取结果的覆盖率。"""
    from src.core.knowledge_qa.d2g.book_pipeline import _detect_heading_para_ids

    paragraphs = [p for p in chapter.markdown.split("\n\n") if p.strip()]
    total_paras = len(paragraphs)
    heading_ids = _detect_heading_para_ids(chapter.markdown)

    # 收集所有被引用的段落
    covered_by_entities: set[int] = set()
    covered_by_rels: set[int] = set()
    entities_without_para: list[str] = []
    rels_without_para: list[str] = []

    for e in extraction.entities:
        if e.source_para_ids:
            covered_by_entities.update(e.source_para_ids)
        else:
            entities_without_para.append(e.name)

    for r in extraction.relationships:
        if r.source_para_ids:
            covered_by_rels.update(r.source_para_ids)
        else:
            rels_without_para.append(f"{r.source}->{r.target}")

    all_covered = covered_by_entities | covered_by_rels
    uncovered = [i for i in range(1, total_paras + 1) if i not in all_covered]

    # 排除标题后的覆盖率
    uncovered_non_heading = [i for i in uncovered if i not in heading_ids]
    effective_covered = all_covered | heading_ids

    # 段落长度分布
    para_lengths = [len(p) for p in paragraphs]

    # 分析未覆盖段落的内容特征（排除标题）
    uncovered_samples = []
    for pid in uncovered_non_heading[:10]:
        if 0 < pid <= len(paragraphs):
            text = paragraphs[pid - 1]
            uncovered_samples.append({
                "pid": pid,
                "length": len(text),
                "preview": text[:150],
            })

    return {
        "total_paras": total_paras,
        "heading_count": len(heading_ids),
        "heading_ids": sorted(heading_ids),
        "covered_by_entities": sorted(covered_by_entities),
        "covered_by_rels": sorted(covered_by_rels),
        "all_covered": sorted(all_covered),
        "uncovered": uncovered,
        "uncovered_non_heading": uncovered_non_heading,
        "coverage_rate_raw": len(all_covered) / total_paras * 100 if total_paras else 0,
        "coverage_rate": len(effective_covered) / total_paras * 100 if total_paras else 0,
        "entity_coverage_rate": len(covered_by_entities) / total_paras * 100 if total_paras else 0,
        "rel_coverage_rate": len(covered_by_rels) / total_paras * 100 if total_paras else 0,
        "entities_count": len(extraction.entities),
        "rels_count": len(extraction.relationships),
        "entities_without_para": entities_without_para,
        "rels_without_para": rels_without_para,
        "entities_without_para_count": len(entities_without_para),
        "rels_without_para_count": len(rels_without_para),
        "uncovered_samples": uncovered_samples,
        "avg_para_length": sum(para_lengths) / len(para_lengths) if para_lengths else 0,
        "min_para_length": min(para_lengths) if para_lengths else 0,
        "max_para_length": max(para_lengths) if para_lengths else 0,
    }


def _print_analysis(ch_id: str, analysis: dict) -> None:
    """打印覆盖率分析报告。"""
    print(f"\n{'='*60}")
    print(f"章节 {ch_id} 覆盖率分析")
    print(f"{'='*60}")
    print(f"总段落数:           {analysis['total_paras']}")
    print(f"标题段落数:         {analysis['heading_count']} {analysis['heading_ids']}")
    print(f"实体数:             {analysis['entities_count']}")
    print(f"关系数:             {analysis['rels_count']}")
    print(f"原始覆盖率:         {analysis['coverage_rate_raw']:.1f}% (不含标题排除)")
    print(f"调整后覆盖率:       {analysis['coverage_rate']:.1f}% (标题视为已覆盖)")
    print(f"  实体贡献:         {analysis['entity_coverage_rate']:.1f}%")
    print(f"  关系贡献:         {analysis['rel_coverage_rate']:.1f}%")
    print(f"已覆盖段落:         {analysis['all_covered']}")
    print(f"未覆盖段落数:       {len(analysis['uncovered'])} (其中非标题: {len(analysis['uncovered_non_heading'])})")
    print(f"未覆盖段落:         {analysis['uncovered']}")
    print(f"未覆盖非标题段落:   {analysis['uncovered_non_heading']}")
    print(f"无 source_para_ids 的实体: {analysis['entities_without_para_count']}")
    if analysis['entities_without_para']:
        print(f"  名单: {analysis['entities_without_para'][:20]}")
    print(f"无 source_para_ids 的关系: {analysis['rels_without_para_count']}")
    if analysis['rels_without_para']:
        print(f"  名单: {analysis['rels_without_para'][:20]}")
    print(f"段落长度: avg={analysis['avg_para_length']:.0f}, "
          f"min={analysis['min_para_length']}, max={analysis['max_para_length']}")

    if analysis['uncovered_samples']:
        print(f"\n未覆盖段落样本 (前 {len(analysis['uncovered_samples'])} 个):")
        for s in analysis['uncovered_samples']:
            print(f"  [P{s['pid']}] len={s['length']}: {s['preview']!r}...")


# ── 测试用例 ──────────────────────────────────────────────────

BOOK_ID = "92c50c6b-4506-4ec1-9ac6-d02f3384effd"
TARGET_CHAPTERS = [
    f"{BOOK_ID}_ch006",
    f"{BOOK_ID}_ch007",
]


@pytest.fixture(scope="module")
def llm_client():
    """创建真实 LLM 客户端。"""
    from src.config import settings
    from src.core.llm.factory import LLMServiceFactoryCompat
    factory = LLMServiceFactoryCompat()
    return factory.create(model_name=settings.d2g_model, max_tokens=settings.d2g_max_tokens)


@pytest.fixture(scope="module")
def model_config():
    return ModelConfig()


@pytest.fixture(scope="module")
def book_context():
    """最小化 BookContext，避免调用 Phase 0。"""
    return BookContext(
        book_title="测试书籍",
        core_thesis="儿童发展与教育的核心理论与实践方法",
        key_arguments=["大脑发育关键期", "感觉统合训练", "注意力培养"],
        terminology={
            "感觉统合": "大脑整合多种感觉输入的能力",
            "前庭觉": "感知身体位置和运动的感觉系统",
            "本体觉": "感知身体各部位位置和运动的感觉",
        },
        chapter_outline="本书系统介绍儿童发展的神经科学基础和教育方法",
    )


@pytest.fixture(scope="module")
def target_chapters():
    return _load_chapters(TARGET_CHAPTERS)


@slow
@pytest.mark.asyncio
async def test_extract_ch006_ch007_and_analyze(
    llm_client, model_config, book_context, target_chapters,
):
    """提取 ch006 和 ch007，逐段分析覆盖率。"""
    results = {}

    for chapter in target_chapters:
        print(f"\n>>> 提取章节: {chapter.id} ({chapter.title})")
        print(f"    段落数: {len([p for p in chapter.markdown.split(chr(10)+chr(10)) if p.strip()])}")
        print(f"    Token: {chapter.token_count}")

        extraction = await extract_chapter(
            chapter=chapter,
            book_context=book_context,
            existing_entities=[],
            llm_client=llm_client,
            config=model_config,
        )

        analysis = _analyze_coverage(extraction, chapter)
        _print_analysis(chapter.id, analysis)
        results[chapter.id] = analysis

        # 打印每个实体的 source_para_ids
        print(f"\n  实体 source_para_ids 明细:")
        for e in extraction.entities:
            print(f"    {e.name:30s} type={e.entity_type:20s} paras={e.source_para_ids}")

        # 打印每个关系的 source_para_ids
        print(f"\n  关系 source_para_ids 明细:")
        for r in extraction.relationships:
            print(f"    {r.source:20s} -> {r.target:20s} type={r.relation_type:20s} paras={r.source_para_ids}")

    # ── 断言：覆盖率应 >= 60% ──
    for ch_id, analysis in results.items():
        assert analysis["coverage_rate"] >= 70, (
            f"{ch_id} 覆盖率 {analysis['coverage_rate']:.1f}% 过低，"
            f"未覆盖段落: {analysis['uncovered']}"
        )


@slow
@pytest.mark.asyncio
async def test_ch006_ch007_para_id_format(
    llm_client, model_config, book_context, target_chapters,
):
    """验证 LLM 返回的 source_para_ids 是否为整数。

    如果大量返回字符串（如 'P22'），说明 prompt 需要调整。
    """
    for chapter in target_chapters:
        extraction = await extract_chapter(
            chapter=chapter,
            book_context=book_context,
            existing_entities=[],
            llm_client=llm_client,
            config=model_config,
        )

        # 统计 source_para_ids 的类型
        id_types = Counter()
        for e in extraction.entities:
            for pid in e.source_para_ids:
                id_types[type(pid).__name__] += 1

        for r in extraction.relationships:
            for pid in r.source_para_ids:
                id_types[type(pid).__name__] += 1

        print(f"\n{chapter.id} source_para_ids 类型统计: {dict(id_types)}")

        # 应该全部是 int
        assert id_types.get("str", 0) == 0, (
            f"{chapter.id} 有 {id_types['str']} 个 source_para_ids 是字符串而非整数"
        )


@slow
@pytest.mark.asyncio
async def test_ch006_ch007_segment_analysis(
    llm_client, model_config, book_context, target_chapters,
):
    """分析分段策略对覆盖率的影响。

    检查是否因为分段导致某些段落被遗漏。
    """
    for chapter in target_chapters:
        segments = segment_chapter(chapter)
        print(f"\n{chapter.id}: {len(segments)} 个分段")
        for seg in segments:
            print(f"  段 {seg.index}: paras={seg.paragraph_ids}, "
                  f"tokens={seg.token_count}, "
                  f"range=[P{seg.paragraph_ids[0]}-P{seg.paragraph_ids[-1]}]")

        # 检查段落是否全覆盖
        all_para_ids = set()
        for seg in segments:
            all_para_ids.update(seg.paragraph_ids)

        total_paras = len([p for p in chapter.markdown.split("\n\n") if p.strip()])
        expected = set(range(1, total_paras + 1))
        missing = expected - all_para_ids

        if missing:
            print(f"  ⚠️ 分段未覆盖段落: {sorted(missing)}")
        else:
            print(f"  ✅ 分段覆盖所有 {total_paras} 个段落")


def test_heading_detection():
    """验证标题段落检测逻辑。"""
    from src.core.knowledge_qa.d2g.book_pipeline import _detect_heading_para_ids

    text = "普通段落\n\n## 小节标题\n\n另一个普通段落\n\n# 大标题\n\n### 三级标题\n\n最后段落"
    headings = _detect_heading_para_ids(text)
    # 段落: 1=普通, 2=##标题, 3=另一个, 4=#大标题, 5=###三级, 6=最后
    assert headings == {2, 4, 5}, f"期望 {{2, 4, 5}}, 得到 {headings}"

    # 空文本
    assert _detect_heading_para_ids("") == set()

    # 无标题
    assert _detect_heading_para_ids("段落一\n\n段落二") == set()

    # 纯标题
    assert _detect_heading_para_ids("## 标题A\n\n## 标题B") == {1, 2}


def test_heading_excluded_from_coverage():
    """验证标题段落被排除在覆盖率计算之外。"""
    from src.core.knowledge_qa.d2g.master_graph import MasterGraph
    from src.core.knowledge_qa.d2g.models import ExtractedEntity

    mg = MasterGraph(book_id="test", book_title="测试")
    mg.chapter_para_count["ch01"] = 5
    # 只覆盖段落 1 和 3
    mg.para_coverage["ch01"] = {1, 3}
    # 段落 2 和 4 是标题
    mg.register_heading_paras("ch01", {2, 4})

    metrics = mg.get_quality_metrics()
    # 有效覆盖: {1, 3} | {2, 4} = {1, 2, 3, 4}, 总 5 段 → 80%
    assert metrics.chapter_coverage["ch01"] == 80.0
