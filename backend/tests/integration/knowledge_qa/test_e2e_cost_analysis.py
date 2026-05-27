"""e2e 全流程成本分析测试

运行完整知识问答流水线（真实 LLM + 真实 RAG），追踪每节点的 token 消耗和成本。

运行方式:
  cd backend && uv run pytest tests/integration/knowledge_qa/test_e2e_cost_analysis.py -v -s
"""

import asyncio
import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

import pytest

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

PRICING = {"input_per_million": 1.0, "output_per_million": 4.0, "currency": "CNY"}

_current_node: ContextVar[str] = ContextVar("current_node", default="unknown")
_call_log: list[dict] = []

NODE_ORDER = [
    "match_books",
    "prefetch_context",
    "analyze_child",
    "identify_problems",
    "recommend_types",
    "plan_outline",
    "plan_expand_content",
    "generate_s4_citations",
    "conclusion",
]


@dataclass
class NodeStats:
    node: str
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    rag_searches: int = 0
    llm_time_ms: float = 0.0

    @property
    def cost_total(self) -> float:
        return (
            self.input_tokens / 1_000_000 * PRICING["input_per_million"]
            + self.output_tokens / 1_000_000 * PRICING["output_per_million"]
        )


# ==================== Monkey-patch 追踪 ====================


def _install_patches():
    """安装 LLM 和 RAG 追踪补丁。每个调用记录时间戳，后续按顺序标注节点。"""

    from langchain_core.language_models.chat_models import BaseChatModel
    import httpx

    _orig_ainvoke = BaseChatModel.ainvoke
    _orig_get = httpx.AsyncClient.get

    async def _tracked_ainvoke(self, input, *args, **kwargs):
        t0 = time.monotonic()
        result = await _orig_ainvoke(self, input, *args, **kwargs)
        elapsed = (time.monotonic() - t0) * 1000

        # 从 response 提取 usage
        inp = 0
        out = 0
        if hasattr(result, "usage_metadata") and result.usage_metadata:
            inp = result.usage_metadata.get("input_tokens", 0) or 0
            out = result.usage_metadata.get("output_tokens", 0) or 0
        elif hasattr(result, "response_metadata") and result.response_metadata:
            tu = result.response_metadata.get("token_usage", {})
            inp = tu.get("prompt_tokens", 0)
            out = tu.get("completion_tokens", 0)

        # 估算 input（如果 API 没有返回）
        if inp == 0 and isinstance(input, list):
            chars = sum(
                len(getattr(m, "content", "") or "")
                for m in input
            )
            inp = int(chars * 0.35)
        if out == 0:
            out = int(len(str(result)) * 0.35)

        _call_log.append({
            "type": "llm",
            "node": "unknown",  # 后续 _annotate_calls_by_sequence 标注
            "time": t0,
            "input_tokens": inp,
            "output_tokens": out,
            "elapsed_ms": elapsed,
        })
        return result

    async def _tracked_get(self, url, *args, **kwargs):
        result = await _orig_get(self, url, *args, **kwargs)
        if "/rag/search" in str(url):
            _call_log.append({
                "type": "rag_search",
                "node": "unknown",  # 后续 _annotate_calls_by_sequence 标注
                "time": time.monotonic(),
            })
        return result

    BaseChatModel.ainvoke = _tracked_ainvoke
    httpx.AsyncClient.get = _tracked_get

    return _orig_ainvoke, _orig_get


def _restore_patches(orig_ainvoke, orig_get):
    from langchain_core.language_models.chat_models import BaseChatModel
    import httpx
    BaseChatModel.ainvoke = orig_ainvoke
    httpx.AsyncClient.get = orig_get


def _annotate_calls_by_sequence():
    """按调用时间顺序，将 LLM 调用分配到图节点。

    策略：每个非 prefetch 节点产生 1 个 LLM 调用（match_books 也是 1 个）。
    顺序：match_books → prefetch(无LLM) → analyze_child → identify_problems
           → recommend_types → plan_outline → plan_expand_content
           → generate_s4_citations → conclusion

    RAG 搜索按时间分配到最近的后续 LLM 调用所属节点。
    prefetch 节点通常无 LLM 调用（无 MySQL 图数据时直接跳过）。
    """
    sorted_calls = sorted(_call_log, key=lambda c: c["time"])

    # 分离 LLM 和 RAG 调用
    llm_calls = [c for c in sorted_calls if c["type"] == "llm"]
    rag_calls = [c for c in sorted_calls if c["type"] == "rag_search"]

    # 将 LLM 调用按顺序分配给图节点
    llm_per_node: dict[str, list[dict]] = {}
    node_idx = 0
    for llm in llm_calls:
        # 跳过 prefetch_context（通常无 LLM，如果有放在 prefetch）
        node = NODE_ORDER[node_idx] if node_idx < len(NODE_ORDER) else "extra"
        if node == "prefetch_context":
            node_idx += 1
            node = NODE_ORDER[node_idx] if node_idx < len(NODE_ORDER) else "extra"
        llm_per_node.setdefault(node, []).append(llm)
        llm["node"] = node
        node_idx += 1

    # 将 RAG 调用分配给最近的后续 LLM 调用所属节点
    for rag in rag_calls:
        rag_time = rag["time"]
        # 找到时间上最近的后续 LLM 调用
        best_node = "orphan_rag"
        min_gap = float("inf")
        for llm in llm_calls:
            gap = llm["time"] - rag_time
            if 0 < gap < min_gap:
                min_gap = gap
                best_node = llm.get("node", "orphan_rag")
        # 如果没有后续 LLM（尾部 RAG），分配给最后一个节点
        if best_node == "orphan_rag" and llm_calls:
            best_node = llm_calls[-1].get("node", "orphan_rag")
        rag["node"] = best_node


def _build_stats() -> dict[str, NodeStats]:
    _annotate_calls_by_sequence()

    stats: dict[str, NodeStats] = {}
    for call in _call_log:
        node = call.get("node", "unknown")
        if node not in stats:
            stats[node] = NodeStats(node=node)
        s = stats[node]
        if call["type"] == "llm":
            s.llm_calls += 1
            s.input_tokens += call.get("input_tokens", 0)
            s.output_tokens += call.get("output_tokens", 0)
            s.llm_time_ms += call.get("elapsed_ms", 0)
        elif call["type"] == "rag_search":
            s.rag_searches += 1
    return stats


# ==================== 报告打印 ====================


def _print_report(stats: dict[str, NodeStats], total_s: float, question: str, sec_count: int, cite_count: int):
    print("\n" + "=" * 95)
    print("║" + " 📊 知识问答 e2e 成本分析报告".center(80) + "║")
    print("=" * 95)
    print(f"  问题: {question}")
    print(f"  模型: qwen3.5-27b  |  ¥1.0/M in + ¥4.0/M out (CNY)")
    print(f"  总耗时: {total_s:.1f}s  |  节: {sec_count}/5  |  引用: {cite_count}")

    print("\n" + "-" * 95)
    print(f"  {'节点':<22s} {'LLM':>5s} {'RAG':>5s} {'输入tokens':>11s} {'输出tokens':>11s} {'耗时':>7s} {'成本¥':>8s}")
    print("-" * 95)

    totals = NodeStats(node="合计")
    ordered = {n: stats.pop(n, None) for n in NODE_ORDER}
    ordered.update(stats)

    for node, s in ordered.items():
        if s is None:
            print(f"  {node:<22s}  {'—':>55s}")
            continue
        totals.llm_calls += s.llm_calls
        totals.input_tokens += s.input_tokens
        totals.output_tokens += s.output_tokens
        totals.rag_searches += s.rag_searches
        totals.llm_time_ms += s.llm_time_ms
        print(f"  {node:<22s} {s.llm_calls:>5d} {s.rag_searches:>5d} {s.input_tokens:>11,d} {s.output_tokens:>11,d} {s.llm_time_ms/1000:>6.1f}s ¥{s.cost_total:>7.4f}")

    print("-" * 95)
    print(f"  {'合计':<22s} {totals.llm_calls:>5d} {totals.rag_searches:>5d} {totals.input_tokens:>11,d} {totals.output_tokens:>11,d} {totals.llm_time_ms/1000:>6.1f}s ¥{totals.cost_total:>7.4f}")
    print("=" * 95)

    total_tk = totals.input_tokens + totals.output_tokens
    if total_tk > 0:
        print(f"\n  📈 效率指标:")
        print(f"     总 token: {total_tk:,d}  (in:{totals.input_tokens:,d} out:{totals.output_tokens:,d})")
        print(f"     I/O 比: {totals.input_tokens/max(totals.output_tokens,1):.1f}:1")
        print(f"     token/s: {total_tk/max(total_s,0.1):.0f}")
        print(f"     均次 token: {total_tk/max(totals.llm_calls,1):,.0f}")
        print(f"     均节成本: ¥{totals.cost_total/max(sec_count,1):.4f}")

    active = [(n, s) for n, s in ordered.items() if s is not None and s.cost_total > 0]
    if active:
        mc = max(active, key=lambda x: x[1].cost_total)
        mt = max(active, key=lambda x: x[1].input_tokens + x[1].output_tokens)
        print(f"\n  🔥 最贵: {mc[0]} ¥{mc[1].cost_total:.4f}")
        print(f"  🔥 最多 token: {mt[0]} {mt[1].input_tokens+mt[1].output_tokens:,d}")

    print("\n" + "=" * 95)
    return totals.cost_total


# ==================== ContextVar ====================


def _setup_qa_context():
    from src.core.knowledge_qa.tools import set_http_client
    from src.schemas.knowledge_qa import (
        clear_partial_collector, clear_progress_context, clear_prompt_manager,
        init_partial_collector, set_progress_context, set_prompt_manager,
    )
    from src.utils.http_client import RagHttpClient
    from unittest.mock import AsyncMock, MagicMock

    progress_log = []

    async def log_progress(step, message, **meta):
        short = (message or "")[:100]
        progress_log.append(f"[{step}] {short}")
        if len(progress_log) <= 20:  # 只打印前 20 条
            print(f"  📌 [{step}] {short}")

    set_progress_context(callback=log_progress, task_id="e2e-cost", task_type="knowledge_qa")
    mock_pm = MagicMock()
    mock_pm.get_prompt = AsyncMock(return_value=None)
    set_prompt_manager(mock_pm)
    set_http_client(RagHttpClient(base_url="http://127.0.0.1:8000"))
    init_partial_collector()
    return progress_log


def _cleanup_qa_context():
    from src.core.knowledge_qa.tools import clear_http_client
    from src.schemas.knowledge_qa import (
        clear_partial_collector, clear_progress_context, clear_prompt_manager,
    )
    clear_progress_context()
    clear_prompt_manager()
    clear_partial_collector()
    clear_http_client()


# ==================== 测试 ====================


@pytest.fixture(autouse=True)
def _clear_caches():
    from src.core.llm.factory import LLMServiceFactoryCompat
    LLMServiceFactoryCompat._raw_instances.clear()
    yield
    LLMServiceFactoryCompat._raw_instances.clear()


@pytest.mark.asyncio
async def test_e2e_full_pipeline_cost_analysis():
    """e2e 全流程成本分析。"""
    from src.core.knowledge_qa.graph import create_knowledge_qa_graph
    from src.schemas.knowledge_qa import KnowledgeQAState

    global _call_log
    _call_log = []

    progress_log = _setup_qa_context()
    orig_ainvoke, orig_get = _install_patches()

    question = "5岁男孩，上课经常走神，一件事没做完就去做另一件，根据知识库中的书籍推荐运动改善方案"

    print("\n" + "=" * 95)
    print(f"  e2e 全流程成本分析 — 真实 LLM + 真实 RAG")
    print(f"  问题: {question}")
    print("=" * 95)

    graph = create_knowledge_qa_graph()
    start = time.monotonic()
    sec_count = 0
    cite_count = 0

    try:
        result = await asyncio.wait_for(
            graph.ainvoke(
                KnowledgeQAState(question=question),
                config={"recursion_limit": 150},
            ),
            timeout=300,
        )
        elapsed = time.monotonic() - start

        sections = result.get("sections", {})
        sec_count = len(sections)
        cite_count = sum(
            len(getattr(sec, "citations", []) or [])
            for sec in sections.values()
        )

        done = "completed" in result.get("current_step", [])
        partial = result.get("partial", False)

        print(f"\n  {'✅ 完成' if done else '⚠️ 降级完成'}")
        print(f"  总耗时: {elapsed:.1f}s  |  完成节: {sec_count}/5  |  引用: {cite_count}")
        if partial:
            print(f"  partial=True (有节点降级)")
        for e in result.get("errors", []):
            print(f"  ⚠️  {e[:150]}")

        # 打印各节摘要
        for i in sorted(sections.keys()):
            sec = sections[i]
            cnt = len(sec.content) if sec.content else 0
            cit = len(sec.citations) if sec.citations else 0
            status = "✅" if "生成失败" not in (sec.content or "") else "❌"
            print(f"  {status} 第{i}节 [{sec.title}]: {cnt}字, {cit}引用")

        stats = _build_stats()
        _print_report(stats, elapsed, question, sec_count, cite_count)

        assert sec_count >= 4, f"仅 {sec_count} 节完成"

    except asyncio.TimeoutError:
        elapsed = time.monotonic() - start
        print(f"\n  ⏰ 超时 {elapsed:.1f}s")
        stats = _build_stats()
        _print_report(stats, elapsed, question, sec_count, cite_count)
        raise

    except Exception as e:
        elapsed = time.monotonic() - start
        print(f"\n  ❌ {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        stats = _build_stats()
        _print_report(stats, elapsed, question, sec_count, cite_count)
        raise

    finally:
        _restore_patches(orig_ainvoke, orig_get)
        _cleanup_qa_context()
