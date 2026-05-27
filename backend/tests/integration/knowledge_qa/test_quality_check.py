"""知识问答输出质量检查脚本

对需求文档 (docs/knowledge-qa/requirements.md) 逐项核验。
运行方式：
cd backend && uv run python tests/integration/knowledge_qa/test_quality_check.py
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

logging.basicConfig(level=logging.WARNING)  # 减少噪音
logger = logging.getLogger(__name__)


# ===== 测试问题（需求文档场景 A）=====
TEST_QUESTION = (
    "现在有一个孩子，想要改变注意力，我想根据《运动改变大脑》这本书来推荐一些运动改善。"
    "请帮我整理一下，要求出自这本书的哪一部分，有理有据的。"
)


async def setup_environment():
    """初始化运行环境（与 test_real_pipeline.py 相同）"""
    from src.core.knowledge_qa.tools import clear_http_client, set_http_client
    from src.schemas.knowledge_qa import (
        clear_partial_collector, clear_progress_context, clear_prompt_manager,
        init_partial_collector, set_progress_context, set_prompt_manager,
    )

    set_progress_context(
        callback=AsyncMock(), task_id="test-quality-check", task_type="knowledge_qa",
    )
    mock_pm = MagicMock()
    mock_pm.get_prompt = AsyncMock(return_value=None)
    set_prompt_manager(mock_pm)

    from src.utils.http_client import RagHttpClient
    http_client = RagHttpClient(base_url="http://127.0.0.1:8000")
    set_http_client(http_client)
    init_partial_collector()
    return http_client


async def cleanup_environment(http_client):
    """清理环境"""
    from src.core.knowledge_qa.tools import clear_http_client
    from src.schemas.knowledge_qa import (
        clear_partial_collector, clear_progress_context, clear_prompt_manager,
    )
    clear_progress_context()
    clear_prompt_manager()
    clear_partial_collector()
    clear_http_client()
    await http_client.close()


def print_separator(title: str):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def check_fr06_output_structure(result: dict) -> list[str]:
    """FR-06: 结构化 JSON 输出检查"""
    issues = []

    # 6.1 顶层结构
    if "question" not in result:
        issues.append("[FR-06] 缺少顶层字段: question")
    if "matched_books" not in result:
        issues.append("[FR-06] 缺少顶层字段: matched_books")
    if "sections" not in result:
        issues.append("[FR-06] 缺少顶层字段: sections")
    if "generation_metadata" not in result:
        issues.append("[FR-06] 缺少顶层字段: generation_metadata")

    # 6.1 matched_books 字段检查
    matched_books = result.get("matched_books", [])
    if matched_books:
        for i, mb in enumerate(matched_books):
            for field in ["book_id", "title", "author", "source_type", "match_reason", "is_primary"]:
                if field not in mb:
                    issues.append(f"[FR-06.1] matched_books[{i}] 缺少字段: {field}")

    # 6.2 citations 结构检查
    sections = result.get("sections", [])
    for s_idx, sec in enumerate(sections):
        sec_index = sec.get("index", s_idx + 1)
        citations = sec.get("citations", [])
        for c_idx, c in enumerate(citations):
            citation_id = c.get("citation_id", "?")
            for field in ["citation_id", "book_title", "chapter", "excerpt", "relevance"]:
                if field not in c:
                    issues.append(
                        f"[FR-06.2] 第{sec_index}节 citation[{c_idx}]({citation_id}) 缺少字段: {field}"
                    )
            # 全局唯一性检查
            excerpt = c.get("excerpt", "")
            if excerpt and len(str(excerpt)) > 500:
                issues.append(
                    f"[FR-06.2] 第{sec_index}节 citation[{c_idx}]({citation_id}) excerpt 超过 500 字"
                )

    # 6.3-6.8 structured_data 必填检查
    for s_idx, sec in enumerate(sections):
        sec_index = sec.get("index", s_idx + 1)
        if "structured_data" not in sec:
            issues.append(f"[FR-06] 第{sec_index}节缺少 structured_data")
        elif sec.get("structured_data") is None:
            issues.append(f"[FR-06] 第{sec_index}节 structured_data 为 null（降级标记）")

    # 6.9 content 必填检查
    for s_idx, sec in enumerate(sections):
        sec_index = sec.get("index", s_idx + 1)
        content = sec.get("content", "")
        if not content:
            issues.append(f"[FR-06.9] 第{sec_index}节 content 为空")

    # generation_metadata 字段
    meta = result.get("generation_metadata", {})
    for field in ["total_sections", "total_citations", "total_time_ms", "model_used", "partial"]:
        if field not in meta:
            issues.append(f"[FR-06.1] generation_metadata 缺少字段: {field}")

    return issues


def check_output_structure_constraints(sections: list) -> list[str]:
    """FR-03/F-06: 5节顺序 + 节标题检查"""
    issues = []

    # 必须恰好 5 节
    if len(sections) != 5:
        issues.append(
            f"[FR-03/FR-04] 节数应为 5，实际为 {len(sections)}"
        )

    # 节序号必须 1-5 且顺序正确
    expected_indices = [1, 2, 3, 4, 5]
    actual_indices = [s.get("index", 0) for s in sections]
    if actual_indices != expected_indices:
        issues.append(
            f"[FR-03] 节序号顺序错误: 期望 {expected_indices}, 实际 {actual_indices}"
        )

    # 每节 title 不能为空
    for s in sections:
        if not s.get("title"):
            issues.append(f"[FR-03] 第{s.get('index', '?')}节标题为空")

    return issues


def check_citations_non_empty(sections: list) -> list[str]:
    """FR-06 约束: citations[] 非空检查"""
    issues = []
    for s in sections:
        sec_index = s.get("index", "?")
        citations = s.get("citations", [])
        if not citations:
            content = s.get("content", "")
            # 允许空数组的情况：content 有标注
            if "知识库中未找到相关专业依据" in content or "缺乏充分依据" in content or "引用未通过核验" in content:
                pass  # 符合降级规则
            else:
                issues.append(
                    f"[FR-06 citations非空] 第{sec_index}节 citations 为空, "
                    f"但 content 未标注'缺乏充分依据'或'知识库中未找到相关专业依据'"
                )
    return issues


def check_nfr02_citation_traceability(sections: list) -> list[str]:
    """NFR-02: 引用可追溯检查"""
    issues = []
    for s in sections:
        sec_index = s.get("index", "?")
        for c in s.get("citations", []):
            book_title = c.get("book_title", "")
            chapter = c.get("chapter", "")
            excerpt = c.get("excerpt", "")

            if not book_title or book_title == "?" or book_title == "未知":
                issues.append(
                    f"[NFR-02] 第{sec_index}节 citation({c.get('citation_id', '?')}) book_title 为空或未知"
                )
            if not chapter or chapter == "?":
                issues.append(
                    f"[NFR-02] 第{sec_index}节 citation({c.get('citation_id', '?')}) chapter 为空"
                )
            if not excerpt or excerpt == "?":
                issues.append(
                    f"[NFR-02] 第{sec_index}节 citation({c.get('citation_id', '?')}) excerpt 为空"
                )
    return issues


def check_fr06_exercise_linkage(sections: list) -> list[str]:
    """FR-06.9: exercise_id → type_id → problem_id 可追溯链检查"""
    issues = []

    # 找到第 3 节的 exercise_types
    sec3 = next((s for s in sections if s.get("index") == 3), None)
    sec4 = next((s for s in sections if s.get("index") == 4), None)

    if sec3 and sec4:
        sd3 = sec3.get("structured_data", {}) or {}
        sd4 = sec4.get("structured_data", {}) or {}
        type_ids = {et.get("type_id") for et in sd3.get("exercise_types", []) if et.get("type_id")}

        for phase in sd4.get("phases", []):
            for week in phase.get("weeks", []):
                for day in week.get("days", []):
                    for ex in day.get("main_exercises", []):
                        ex_id = ex.get("exercise_id", "?")
                        type_id = ex.get("type_id")
                        if type_id and type_id not in type_ids:
                            issues.append(
                                f"[FR-06.9] 第4节 exercise({ex_id}) type_id={type_id} "
                                f"未在第3节 exercise_types 中找到"
                            )
    return issues


def check_fr10_error_handling(result: dict) -> list[str]:
    """FR-10: 异常处理降级检查"""
    issues = []

    sections = result.get("sections", [])
    meta = result.get("generation_metadata", {})

    # partial 标记检查
    failed_sections = [
        s for s in sections
        if "生成失败" in s.get("content", "") or "因超时未生成" in s.get("content", "")
    ]
    if failed_sections and not meta.get("partial"):
        issues.append(
            f"[FR-10] 有 {len(failed_sections)} 节生成失败，"
            f"但 partial 未标记为 true"
        )

    # 降级内容检查
    for s in sections:
        sd = s.get("structured_data")
        if sd is None:
            issues.append(
                f"[FR-10] 第{s.get('index', '?')}节 structured_data 为 null（降级）"
            )

    return issues


def check_nfr03_conclusion_basis(sections: list) -> list[str]:
    """NFR-03: 结论有依据检查"""
    issues = []

    sec5 = next((s for s in sections if s.get("index") == 5), None)
    if sec5:
        citations = sec5.get("citations", [])
        if not citations:
            issues.append("[NFR-03] 第5节(最终结论) citations 为空，所有观点缺少依据标注")

        content = sec5.get("content", "")
        if content and not citations and "未找到" not in content and "缺乏" not in content:
            issues.append("[NFR-03] 第5节有内容但无引用，可能凭空生成结论")

    return issues


def check_section_content_quality(sections: list) -> list[str]:
    """逐节内容质量检查（基于需求文档第3节输出结构约束）"""
    issues = []

    for s in sections:
        sec_index = s.get("index", "?")
        content = s.get("content", "")
        citations = s.get("citations", [])
        sd = s.get("structured_data", {})

        # 第1节：孩子状态分析
        if sec_index == 1:
            if sd:
                cp = sd.get("child_profile", {})
                if cp:
                    if not cp.get("behaviors_mentioned"):
                        issues.append("[3.1 第1节] structured_data 缺少 behaviors_mentioned")
                else:
                    issues.append("[3.1 第1节] structured_data 缺少 child_profile")
            if content and not any(kw in content for kw in ["注意", "行为", "运动", "大脑", "儿童", "孩子"]):
                issues.append("[3.1 第1节] content 可能未结合知识库专业资料做分析")

        # 第2节：问题识别
        if sec_index == 2:
            if sd:
                problems = sd.get("problems", [])
                if not problems:
                    issues.append("[3.2 第2节] structured_data 缺少 problems")
                for p in problems:
                    if "mentioned_by_user" not in p:
                        issues.append(f"[3.2 第2节] problem({p.get('problem_id', '?')}) 缺少 mentioned_by_user")
                    if "book_evidence" not in p:
                        issues.append(f"[3.2 第2节] problem({p.get('problem_id', '?')}) 缺少 book_evidence")

        # 第3节：运动类型推荐
        if sec_index == 3:
            if sd:
                ets = sd.get("exercise_types", [])
                if not ets:
                    issues.append("[3.3 第3节] structured_data 缺少 exercise_types")
                for et in ets:
                    if "tier" not in et:
                        issues.append(f"[3.3 第3节] exercise_type({et.get('type_id', '?')}) 缺少 tier 推荐优先级")
                    if "recommendation_rationale" not in et:
                        issues.append(f"[3.3 第3节] exercise_type({et.get('type_id', '?')}) 缺少推荐理由")

        # 第4节：运动方案
        if sec_index == 4:
            if sd:
                if not sd.get("phases"):
                    issues.append("[3.4 第4节] structured_data 缺少 phases")
                plan_summary = sd.get("plan_summary", {})
                for field in ["total_duration_days", "total_phases", "daily_duration_min", "weekly_frequency"]:
                    if field not in plan_summary:
                        issues.append(f"[3.4 第4节] plan_summary 缺少 {field}")
                if not sd.get("caution"):
                    issues.append("[3.4 第4节] 缺少 caution 注意事项")

        # 第5节：最终结论
        if sec_index == 5:
            if sd:
                if not sd.get("core_conclusions"):
                    issues.append("[3.5 第5节] structured_data 缺少 core_conclusions")
                for cc in sd.get("core_conclusions", []):
                    if "source_type" not in cc:
                        issues.append(f"[3.5 第5节] conclusion({cc.get('conclusion_id', '?')}) 缺少 source_type")

    return issues


def check_matched_books_quality(result: dict) -> list[str]:
    """FR-02: 书籍匹配质量检查"""
    issues = []
    matched = result.get("matched_books", [])
    question = result.get("question", "")

    if not matched:
        # 检查是否是 no_matching_books 错误
        if "error" not in result:
            issues.append("[FR-02] matched_books 为空，但未返回 no_matching_books 错误")
        return issues

    # 至少有一本 is_primary=True
    if not any(mb.get("is_primary") for mb in matched):
        issues.append("[FR-02] matched_books 中没有任何书籍标记为 is_primary=true")

    # 每本书应有匹配理由
    for mb in matched:
        if not mb.get("match_reason"):
            issues.append(f"[FR-02] 书籍({mb.get('title', '?')}) 缺少 match_reason")

    # 用户提到"运动改变大脑"，应该匹配到这本书
    if "运动改变大脑" in question:
        titles = [mb.get("title", "") for mb in matched]
        if not any("运动改变大脑" in t for t in titles):
            issues.append("[FR-02] 用户指定《运动改变大脑》但 matched_books 未包含此书")

    return issues


def check_generation_metadata(result: dict) -> list[str]:
    """FR-04a/FR-06: generation_metadata 质量检查"""
    issues = []
    meta = result.get("generation_metadata", {})

    if meta.get("total_sections", 0) != 5:
        issues.append(f"[FR-06] generation_metadata.total_sections={meta.get('total_sections')}, 期望 5")

    # model_used 应该反映实际使用的模型
    if not meta.get("model_used"):
        issues.append("[FR-04a] generation_metadata.model_used 为空")

    return issues


async def run_full_pipeline(question: str) -> dict:
    """运行完整流水线并返回结果"""
    from src.core.knowledge_qa.graph import create_knowledge_qa_graph
    from src.schemas.knowledge_qa import KnowledgeQAState

    graph = create_knowledge_qa_graph()
    state = KnowledgeQAState(question=question)

    print(f"\n📝 测试问题: {question}")

    start = time.monotonic()
    raw_result = await graph.ainvoke(state)
    elapsed = time.monotonic() - start

    # 转换为 dict
    if not isinstance(raw_result, dict):
        raw_result = raw_result

    # 构建可读的输出
    sections_list = sorted(
        [s for s in raw_result.get("sections", {}).values() if s],
        key=lambda s: s.index,
    )

    # 构建响应格式（模拟 service._build_response）
    matched_books = []
    for mb in raw_result.get("matched_books_detail", []):
        if hasattr(mb, 'model_dump'):
            matched_books.append(mb.model_dump())
        elif isinstance(mb, dict):
            matched_books.append(mb)

    sections = []
    for s in sections_list:
        if hasattr(s, 'model_dump'):
            sections.append(s.model_dump())
        elif isinstance(s, dict):
            sections.append(s)

    total_citations = sum(len(s.get("citations", [])) for s in sections)

    result = {
        "question": raw_result.get("question", question),
        "matched_books": matched_books,
        "sections": sections,
        "generation_metadata": {
            "total_sections": len(sections),
            "total_citations": total_citations,
            "total_time_ms": int(elapsed * 1000),
            "model_used": "qwen3.5-27b",
            "review_model_used": "qwen3.5-27b",
            "retries": raw_result.get("retry_counts", {}),
            "partial": raw_result.get("partial", False),
        },
    }

    print(f"⏱️  总耗时: {elapsed:.1f}s ({int(elapsed * 1000)}ms)")

    return result


def print_sections_summary(sections: list):
    """打印每节摘要"""
    for s in sections:
        sec_index = s.get("index", "?")
        title = s.get("title", "无标题")
        content = s.get("content", "")
        content_preview = content[:200].replace("\n", " ") if content else "(空)"
        citations = s.get("citations", [])
        sd = s.get("structured_data", {}) or {}

        print(f"\n{'─' * 60}")
        print(f"第{sec_index}节: {title}")
        print(f"  内容长度: {len(content)} 字")
        print(f"  引用数: {len(citations)}")
        print(f"  内容预览: {content_preview}...")
        if citations:
            for c in citations[:3]:
                print(f"    [{c.get('citation_id', '?')}] {c.get('book_title', '?')} "
                      f"第{c.get('chapter', '?')} — {str(c.get('excerpt', ''))[:80]}")

        # structured_data 摘要
        if sec_index == 1 and sd:
            cp = sd.get("child_profile", {})
            print(f"  structured_data: 年龄={cp.get('age')}, 性别={cp.get('gender')}, "
                  f"行为数={len(cp.get('behaviors_mentioned', []))}")
        elif sec_index == 2 and sd:
            print(f"  structured_data: 问题数={len(sd.get('problems', []))}")
        elif sec_index == 3 and sd:
            print(f"  structured_data: 运动类型数={len(sd.get('exercise_types', []))}")
        elif sec_index == 4 and sd:
            ps = sd.get("plan_summary", {})
            print(f"  structured_data: 阶段数={ps.get('total_phases')}, "
                  f"总天数={ps.get('total_duration_days')}, 日时长={ps.get('daily_duration_min')}min")
        elif sec_index == 5 and sd:
            print(f"  structured_data: 结论数={len(sd.get('core_conclusions', []))}, "
                  f"行动项数={len(sd.get('action_items', []))}")


def find_cross_section_linkage_issues(sections: list) -> list[str]:
    """FR-03 节间数据依赖检查"""
    issues = []

    sec1 = next((s for s in sections if s.get("index") == 1), None)
    sec2 = next((s for s in sections if s.get("index") == 2), None)
    sec3 = next((s for s in sections if s.get("index") == 3), None)
    sec4 = next((s for s in sections if s.get("index") == 4), None)

    # 第2节 应关联第1节的行为
    if sec1 and sec2:
        sd1 = sec1.get("structured_data", {}) or {}
        sd2 = sec2.get("structured_data", {}) or {}
        if isinstance(sd1, dict):
            behaviors_raw = sd1.get("child_profile", {}).get("behaviors_mentioned", [])
            if isinstance(behaviors_raw, list):
                behaviors = [b.get("behavior", "") if isinstance(b, dict) else str(b) for b in behaviors_raw]
            else:
                behaviors = [str(behaviors_raw)] if behaviors_raw else []
        else:
            behaviors = []
        for p in sd2.get("problems", []):
            linked = p.get("child_behaviors_linked", [])
            if linked:
                for lb in linked:
                    if lb not in behaviors:
                        issues.append(
                            f"[FR-03节间依赖] 第2节 problem({p.get('problem_id', '?')}) "
                            f"child_behaviors_linked 引用了第1节不存在的 behavior: {lb}"
                        )

    # 第3节 target_problem_ids 应关联第2节的 problems
    if sec2 and sec3:
        sd2 = sec2.get("structured_data", {}) or {}
        sd3 = sec3.get("structured_data", {}) or {}
        problem_ids = {p.get("problem_id") for p in sd2.get("problems", [])}
        for et in sd3.get("exercise_types", []):
            for tp_id in et.get("target_problem_ids", []):
                if tp_id not in problem_ids:
                    issues.append(
                        f"[FR-03节间依赖] 第3节 exercise_type({et.get('type_id', '?')}) "
                        f"target_problem_ids 包含不存在的 {tp_id}"
                    )

    return issues


async def main():
    print("=" * 70)
    print("  知识问答输出质量检查")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 1. 初始化环境
    print("\n🔧 初始化环境...")
    http_client = await setup_environment()

    try:
        # 2. 运行全流程
        print_separator("运行全流程 (预计 3-6 分钟)")
        result = await run_full_pipeline(TEST_QUESTION)

        # 3. 打印每节摘要
        sections = result.get("sections", [])
        print_separator("逐节摘要")
        print_sections_summary(sections)

        # 4. 逐项质量检查
        print_separator("质量检查结果")
        all_issues = []

        # 按需求文档逐项检查
        checks = [
            ("FR-06 输出结构", check_fr06_output_structure(result)),
            ("FR-03/FR-04 节结构约束", check_output_structure_constraints(sections)),
            ("FR-02 书籍匹配质量", check_matched_books_quality(result)),
            ("FR-06 citations非空", check_citations_non_empty(sections)),
            ("NFR-02 引用可追溯", check_nfr02_citation_traceability(sections)),
            ("FR-06.9 节间关联可追溯", check_fr06_exercise_linkage(sections)),
            ("FR-03 节间数据依赖", find_cross_section_linkage_issues(sections)),
            ("FR-10 异常处理降级", check_fr10_error_handling(result)),
            ("NFR-03 结论有依据", check_nfr03_conclusion_basis(sections)),
            ("内容质量（逐节）", check_section_content_quality(sections)),
            ("generation_metadata", check_generation_metadata(result)),
        ]

        for name, issues in checks:
            status = "✅ 通过" if not issues else f"⚠️  {len(issues)} 个问题"
            print(f"\n  {name}: {status}")
            for issue in issues:
                print(f"    - {issue}")
            all_issues.extend(issues)

        # 5. 总评
        print_separator("总评")
        total_checks = len(checks)
        passed_checks = sum(1 for _, issues in checks if not issues)
        print(f"  检查项: {passed_checks}/{total_checks} 通过")
        print(f"  总问题数: {len(all_issues)}")

        # 按严重度分类
        p0_issues = [i for i in all_issues if "P0" in i or "citations非空" in i or "引用可追溯" in i]
        p1_issues = [i for i in all_issues if i not in p0_issues]

        if p0_issues:
            print(f"\n  🔴 关键问题 (P0): {len(p0_issues)}")
            for i in p0_issues:
                print(f"    - {i}")
        if p1_issues:
            print(f"\n  🟡 一般问题 (P1): {len(p1_issues)}")
            for i in p1_issues[:10]:
                print(f"    - {i}")
            if len(p1_issues) > 10:
                print(f"    ... 还有 {len(p1_issues) - 10} 个")

        # 6. 保存完整输出
        output_file = Path(__file__).parent / "quality_check_output.json"
        # 清理不可序列化字段
        clean_result = json.loads(json.dumps(result, default=str, ensure_ascii=False))
        output_file.write_text(json.dumps(clean_result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n📄 完整输出已保存至: {output_file}")

        # 7. 关键指标统计
        print_separator("关键指标")
        print(f"  总节数: {len(sections)}")
        print(f"  有内容的节: {sum(1 for s in sections if s.get('content'))}")
        print(f"  有引用的节: {sum(1 for s in sections if s.get('citations'))}")
        print(f"  总引用数: {sum(len(s.get('citations', [])) for s in sections)}")
        print(f"  引用非空率: {sum(1 for s in sections if s.get('citations'))}/{len(sections) if sections else 0}")
        print(f"  匹配书籍数: {len(result.get('matched_books', []))}")
        print(f"  总耗时: {result.get('generation_metadata', {}).get('total_time_ms', 0)}ms")
        print(f"  partial: {result.get('generation_metadata', {}).get('partial', False)}")

    finally:
        await cleanup_environment(http_client)

    print("\n" + "=" * 70)
    print("  检查完成")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
