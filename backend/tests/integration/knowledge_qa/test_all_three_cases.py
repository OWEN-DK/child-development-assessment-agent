"""知识问答全流程检查 — 3个测试用例

运行方式: cd backend && uv run python tests/integration/knowledge_qa/test_all_three_cases.py
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# 3个测试用例（来自 gap-analysis.md）
TEST_CASES = [
    {
        "id": "A",
        "question": "我的孩子注意力不集中，根据运动改变大脑推荐一些运动改善方案",
        "scenario": "指定书名",
    },
    {
        "id": "B",
        "question": "我的孩子社交能力偏弱，有什么方法可以改善？",
        "scenario": "未指定书名",
    },
    {
        "id": "C",
        "question": "3岁儿童的大运动发展里程碑是什么？",
        "scenario": "其他知识类",
    },
]


async def setup_environment():
    from src.core.knowledge_qa.tools import clear_http_client, set_http_client
    from src.schemas.knowledge_qa import (
        clear_partial_collector, clear_progress_context, clear_prompt_manager,
        init_partial_collector, set_progress_context, set_prompt_manager,
    )

    set_progress_context(
        callback=AsyncMock(), task_id="test-three-cases", task_type="knowledge_qa",
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
    from src.core.knowledge_qa.tools import clear_http_client
    from src.schemas.knowledge_qa import (
        clear_partial_collector, clear_progress_context, clear_prompt_manager,
    )
    clear_progress_context()
    clear_prompt_manager()
    clear_partial_collector()
    clear_http_client()
    await http_client.close()


async def run_single_case(case: dict) -> dict:
    """运行单个测试用例，返回完整结果"""
    from src.core.knowledge_qa.graph import create_knowledge_qa_graph
    from src.schemas.knowledge_qa import KnowledgeQAState

    graph = create_knowledge_qa_graph()
    state = KnowledgeQAState(question=case["question"])

    print(f"\n{'='*70}")
    print(f"  用例 {case['id']}: {case['scenario']}")
    print(f"  问题: {case['question']}")
    print(f"{'='*70}")

    start = time.monotonic()
    try:
        raw_result = await graph.ainvoke(state)
        elapsed = time.monotonic() - start
        error = None
    except Exception as e:
        elapsed = time.monotonic() - start
        raw_result = {"current_step": f"error: {e}", "errors": [str(e)]}
        error = str(e)
        print(f"  ❌ 异常: {e}")

    sections_dict = raw_result.get("sections", {})
    sections_list = sorted(
        [s for s in sections_dict.values() if s],
        key=lambda s: getattr(s, "index", 99) if hasattr(s, "index") else (s.get("index", 99) if isinstance(s, dict) else 99),
    )

    # 转换为可序列化格式
    matched_books = []
    for mb in raw_result.get("matched_books_detail", []):
        if hasattr(mb, "model_dump"):
            matched_books.append(mb.model_dump())
        elif isinstance(mb, dict):
            matched_books.append(mb)

    sections = []
    for s in sections_list:
        if hasattr(s, "model_dump"):
            sections.append(s.model_dump())
        elif isinstance(s, dict):
            sections.append(s)

    total_citations = sum(len(s.get("citations", [])) for s in sections)
    s4_citations = 0
    s4 = next((s for s in sections if s.get("index") == 4), None)
    if s4:
        s4_citations = len(s4.get("citations", []))

    result = {
        "case_id": case["id"],
        "scenario": case["scenario"],
        "question": case["question"],
        "matched_books": matched_books,
        "sections": sections,
        "error": error,
        "current_step": str(raw_result.get("current_step", "")),
        "errors_log": [str(e) for e in raw_result.get("errors", [])],
        "partial": raw_result.get("partial", False),
        "retry_counts": raw_result.get("retry_counts", {}),
        "generation_metadata": {
            "total_sections": len(sections),
            "total_citations": total_citations,
            "s4_citations": s4_citations,
            "total_time_ms": int(elapsed * 1000),
            "total_time_s": round(elapsed, 1),
            "partial": raw_result.get("partial", False),
        },
    }

    # 打印摘要
    print(f"  ⏱️  耗时: {elapsed:.1f}s")
    print(f"  📚 匹配书籍: {len(matched_books)} 本")
    for mb in matched_books:
        print(f"     - {mb.get('title', '?')} (primary={mb.get('is_primary')})")
    print(f"  📝 节数: {len(sections)}")
    for s in sections:
        idx = s.get("index", "?")
        c_count = len(s.get("citations", []))
        content_len = len(s.get("content", ""))
        sd = s.get("structured_data")
        sd_status = "有" if sd else "null(降级)"
        print(f"     第{idx}节 [{s.get('title', '?')[:20]}]: {content_len}字, {c_count}条引用, structured_data={sd_status}")
    print(f"  ⚠️  partial: {raw_result.get('partial', False)}")
    print(f"  ❌ errors: {raw_result.get('errors', [])}")

    return result


def analyze_results(all_results: list[dict]) -> list[dict]:
    """分析所有结果，输出新发现的问题"""
    findings = []

    for r in all_results:
        cid = r["case_id"]
        sections = r["sections"]
        matched = r["matched_books"]

        # 1. S4 引用检查
        s4 = next((s for s in sections if s.get("index") == 4), None)
        if s4:
            s4_cites = s4.get("citations", [])
            if not s4_cites:
                findings.append({
                    "case": cid,
                    "severity": "P0",
                    "category": "S4引用为空",
                    "detail": f"第4节citations为空（{len(s4.get('content', ''))}字内容无引用）",
                    "gap_analysis_known": True,
                })

        # 2. 响应时间
        elapsed = r["generation_metadata"]["total_time_s"]
        if elapsed > 120:
            findings.append({
                "case": cid,
                "severity": "P0",
                "category": "超时",
                "detail": f"响应时间 {elapsed:.1f}s 超过120s硬超时，partial={r['partial']}",
                "gap_analysis_known": True,
            })

        # 3. 书籍匹配质量
        question = r["question"]
        # 用例C不应该匹配到"运动改变大脑"
        if cid == "C":
            for mb in matched:
                if "运动" in mb.get("title", ""):
                    findings.append({
                        "case": cid,
                        "severity": "P2",
                        "category": "误匹配",
                        "detail": f"非运动类问题误匹配到《{mb.get('title')}》",
                        "gap_analysis_known": True,
                    })

        # 4. citation_id 格式
        for s in sections:
            for c in s.get("citations", []):
                cid_val = c.get("citation_id", "")
                if cid_val and not cid_val.startswith("C"):
                    findings.append({
                        "case": cid,
                        "severity": "P3",
                        "category": "citation_id格式",
                        "detail": f"第{s.get('index')}节 citation_id={cid_val} 不以C开头",
                        "gap_analysis_known": True,
                    })

        # 5. 检查每节的structured_data是否存在
        for s in sections:
            if s.get("structured_data") is None:
                findings.append({
                    "case": cid,
                    "severity": "P1",
                    "category": "structured_data为null",
                    "detail": f"第{s.get('index')}节 structured_data 为 null",
                    "gap_analysis_known": False,
                })

        # 6. 检查是否有节内容为空
        for s in sections:
            if not s.get("content", "").strip():
                findings.append({
                    "case": cid,
                    "severity": "P0",
                    "category": "节内容为空",
                    "detail": f"第{s.get('index')}节 content 为空",
                    "gap_analysis_known": False,
                })

        # 7. 检查引用中excerpt和chapter的完整性
        for s in sections:
            for c in s.get("citations", []):
                excerpt = c.get("excerpt", "")
                chapter = c.get("chapter", "")
                if excerpt and len(str(excerpt)) < 10:
                    findings.append({
                        "case": cid,
                        "severity": "P2",
                        "category": "引用excerpt过短",
                        "detail": f"第{s.get('index')}节 {c.get('citation_id')} excerpt<10字符",
                        "gap_analysis_known": False,
                    })
                if chapter and chapter == "":
                    findings.append({
                        "case": cid,
                        "severity": "P2",
                        "category": "引用chapter为空",
                        "detail": f"第{s.get('index')}节 {c.get('citation_id')} chapter为空",
                        "gap_analysis_known": False,
                    })

        # 8. 检查第5节是否有引用支撑
        s5 = next((s for s in sections if s.get("index") == 5), None)
        if s5:
            s5_cites = s5.get("citations", [])
            s5_content = s5.get("content", "")
            if s5_content and not s5_cites:
                findings.append({
                    "case": cid,
                    "severity": "P1",
                    "category": "结论无引用",
                    "detail": "第5节(结论)有内容但无引用支撑",
                    "gap_analysis_known": False,
                })

        # 9. 新发现: 检查是否有节完全缺失
        present_indices = {s.get("index") for s in sections}
        for expected_idx in [1, 2, 3, 4, 5]:
            if expected_idx not in present_indices:
                findings.append({
                    "case": cid,
                    "severity": "P0",
                    "category": "节缺失",
                    "detail": f"第{expected_idx}节完全缺失",
                    "gap_analysis_known": False,
                })

        # 10. 检查error log中是否有内容
        error_logs = r.get("errors_log", [])
        for err in error_logs:
            if "核验剔除引用" in err:
                findings.append({
                    "case": cid,
                    "severity": "P2",
                    "category": "引用被核验剔除",
                    "detail": f"引用核验剔除了部分引用: {err[:120]}",
                    "gap_analysis_known": True,
                })

        # 11. 第4节 structured_data 完整性
        if s4:
            sd4 = s4.get("structured_data", {}) or {}
            if sd4:
                phases = sd4.get("phases", [])
                if not phases:
                    findings.append({
                        "case": cid,
                        "severity": "P1",
                        "category": "第4节无phases",
                        "detail": "第4节 structured_data 缺少 phases",
                        "gap_analysis_known": False,
                    })
                else:
                    # 检查phase结构完整性
                    for p in phases:
                        weeks = p.get("weeks", [])
                        if not weeks:
                            findings.append({
                                "case": cid,
                                "severity": "P2",
                                "category": "phase无weeks",
                                "detail": f"第4节 phase({p.get('phase_name', '?')}) 无weeks",
                                "gap_analysis_known": False,
                            })

    return findings


async def main():
    print("=" * 70)
    print("  知识问答 3 用例全流程检查")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 初始化
    print("\n🔧 初始化环境...")
    http_client = await setup_environment()

    all_results = []
    try:
        for case in TEST_CASES:
            result = await run_single_case(case)
            all_results.append(result)

        # 分析结果
        print(f"\n{'='*70}")
        print("  分析结果汇总")
        print(f"{'='*70}")

        findings = analyze_results(all_results)

        # 按严重度分组
        p0 = [f for f in findings if f["severity"] == "P0"]
        p1 = [f for f in findings if f["severity"] == "P1"]
        p2 = [f for f in findings if f["severity"] == "P2"]
        p3 = [f for f in findings if f["severity"] == "P3"]

        known = [f for f in findings if f.get("gap_analysis_known")]
        new = [f for f in findings if not f.get("gap_analysis_known")]

        print(f"\n总发现: {len(findings)} 个问题")
        print(f"  已知(在gap-analysis中): {len(known)}")
        print(f"  新发现: {len(new)}")

        print(f"\n🔴 P0 (致命): {len(p0)}")
        for f in p0:
            tag = "[已知]" if f.get("gap_analysis_known") else "[🆕新]"
            print(f"  {tag} [{f['case']}] {f['category']}: {f['detail']}")

        print(f"\n🟠 P1 (重要偏离): {len(p1)}")
        for f in p1:
            tag = "[已知]" if f.get("gap_analysis_known") else "[🆕新]"
            print(f"  {tag} [{f['case']}] {f['category']}: {f['detail']}")

        print(f"\n🟡 P2 (中度): {len(p2)}")
        for f in p2:
            tag = "[已知]" if f.get("gap_analysis_known") else "[🆕新]"
            print(f"  {tag} [{f['case']}] {f['category']}: {f['detail']}")

        print(f"\n🟢 P3 (轻微): {len(p3)}")
        for f in p3:
            tag = "[已知]" if f.get("gap_analysis_known") else "[🆕新]"
            print(f"  {tag} [{f['case']}] {f['category']}: {f['detail']}")

        # 保存结果
        output_file = Path(__file__).parent / "three_cases_output.json"
        clean = json.loads(json.dumps(all_results, default=str, ensure_ascii=False))
        output_file.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n📄 完整结果保存至: {output_file}")

        # 关键指标对比表
        print(f"\n{'='*70}")
        print("  关键指标对比")
        print(f"{'='*70}")
        print(f"  {'用例':<6} {'耗时':<10} {'节数':<6} {'总引用':<8} {'S4引用':<8} {'partial':<8} {'匹配书数':<10}")
        print(f"  {'-'*60}")
        for r in all_results:
            m = r["generation_metadata"]
            print(f"  {r['case_id']:<6} {m['total_time_s']:>6.1f}s  {m['total_sections']:>4}  {m['total_citations']:>6}  {m['s4_citations']:>6}  {str(r['partial']):>8}  {len(r['matched_books']):>8}")

    finally:
        await cleanup_environment(http_client)

    print(f"\n{'='*70}")
    print("  检查完成")
    print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(main())
