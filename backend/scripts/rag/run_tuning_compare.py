#!/usr/bin/env python3
"""Quick A/B comparison: baseline vs tuned RAG config.
Writes results to a file to avoid stdout filtering issues.
"""
import sys, os, json, time, asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.service.rag_service import rag_service

TEST_SET_PATH = Path(__file__).parent.parent.parent / "src" / "data" / "test_sets" / "rag_evaluation_test_set_v1.json"
OUTPUT_PATH = Path(__file__).parent.parent.parent / "reports" / f"rag_tuning_comparison_{int(time.time())}.json"
OUTPUT_PATH.parent.mkdir(exist_ok=True)

# Queries that were problematic in baseline
QUERIES = [
    # Poor performers in baseline
    ("0岁儿童攀爬发育迟缓的表现有哪些", 0, ["攀爬", "迟缓", "表现"]),
    ("0岁孩子投球能力落后怎么办", 0, ["投球", "落后", "干预"]),
    ("1岁儿童大运动发展的里程碑是什么", 1, ["大运动", "里程碑", "发展"]),
    ("2岁儿童大运动发展的里程碑是什么", 2, ["大运动", "里程碑", "发展"]),
    ("2岁儿童攀爬不协调需要就医吗", 2, ["攀爬", "不协调", "就医"]),
    ("2岁儿童投球的发展情况如何", 2, ["投球", "发展", "里程碑"]),
    ("4岁儿童攀爬发育迟缓的表现有哪些", 4, ["攀爬", "迟缓", "表现"]),
    ("4岁孩子投球能力落后怎么办", 4, ["投球", "落后", "干预"]),
    # Good performers (control group)
    ("0岁宝宝还不会跑步正常吗", 0, ["跑步", "发育", "正常"]),
    ("如何训练1岁儿童的走路能力", 1, ["走路", "训练", "方法"]),
    ("促进3岁宝宝走路的游戏有哪些", 3, ["走路", "游戏", "促进"]),
    ("如何训练5岁儿童的走路能力", 5, ["走路", "训练", "方法"]),
]


def keyword_match_score(expected_keywords, contexts):
    if not expected_keywords or not contexts:
        return 0.0
    text = " ".join(contexts).lower()
    matches = sum(1 for kw in expected_keywords if kw.lower() in text)
    return matches / len(expected_keywords)


async def run_test(label, config_desc):
    results = []
    for query, age, expected_kw in QUERIES:
        t0 = time.time()
        try:
            ret = await rag_service.retrieve_knowledge(query=query, limit=5)
        except Exception as e:
            results.append({"query": query, "error": str(e), "latency_ms": (time.time() - t0) * 1000})
            continue
        lat = (time.time() - t0) * 1000
        contexts = [item.content for item in ret] if isinstance(ret, list) else []
        kw_score = keyword_match_score(expected_kw, contexts)
        results.append({
            "query": query,
            "age": age,
            "expected_keywords": expected_kw,
            "keyword_match_score": kw_score,
            "latency_ms": lat,
            "result_count": len(contexts),
        })

    avg_kw = sum(r.get("keyword_match_score", 0) for r in results) / len(results)
    avg_lat = sum(r.get("latency_ms", 0) for r in results) / len(results)
    perfect = sum(1 for r in results if r.get("keyword_match_score", 0) >= 1.0)
    good = sum(1 for r in results if 0.5 <= r.get("keyword_match_score", 0) < 1.0)
    poor = sum(1 for r in results if 0 < r.get("keyword_match_score", 0) < 0.5)
    zero = sum(1 for r in results if r.get("keyword_match_score", 0) == 0)

    return {
        "label": label,
        "config": config_desc,
        "avg_keyword_match": avg_kw,
        "avg_latency_ms": avg_lat,
        "distribution": {"perfect": perfect, "good": good, "poor": poor, "zero": zero},
        "results": results,
    }


async def main():
    print(f"Running A/B comparison with {len(QUERIES)} queries...", flush=True)
    print(f"Output: {OUTPUT_PATH}", flush=True)

    # Run 1: Current config
    cfg1 = {
        "bm25_weight": settings.rag_hybrid_bm25_weight,
        "vector_weight": settings.rag_hybrid_vector_weight,
        "reranker_initial_k": settings.rag_reranker_initial_k,
        "reranker_final_k": settings.rag_reranker_final_k,
    }
    run1 = await run_test("current", cfg1)
    print(f"  Current: kw={run1['avg_keyword_match']:.4f} lat={run1['avg_latency_ms']:.0f}ms dist={run1['distribution']}", flush=True)

    report = {
        "timestamp": time.time(),
        "runs": [run1],
        "comparison_notes": "Single run. Tuned config values applied to .env.dev require server restart to take effect for API-based runs.",
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print("Results Summary")
    print(f"{'='*60}")
    for run in [run1]:
        print(f"\n[{run['label']}]")
        print(f"  Config: {run['config']}")
        print(f"  Avg Keyword Match: {run['avg_keyword_match']:.4f}")
        print(f"  Avg Latency: {run['avg_latency_ms']:.0f}ms")
        print(f"  Distribution: {run['distribution']}")
        print(f"\n  Per-query results:")
        for r in run["results"]:
            kw_str = ",".join(r.get("expected_keywords", []))
            if "error" in r:
                print(f"    ✗ {r['query'][:40]:<42} ERROR: {r['error'][:30]}")
            else:
                mark = "✓" if r["keyword_match_score"] >= 0.5 else "✗"
                print(f"    {mark} {r['query'][:40]:<42} kw={r['keyword_match_score']:.2f} lat={r['latency_ms']:.0f}ms")

    print(f"\nReport saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
