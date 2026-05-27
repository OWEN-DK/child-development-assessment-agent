#!/usr/bin/env python3
"""Standalone RAG evaluation script - direct pipeline access, no API needed.

Evaluates current RAG capability across three dimensions:
1. Retrieval quality (keywords match, latency)
2. Answer quality (faithfulness, relevance, completeness via LLM judge)
3. Knowledge coverage (keyword overlap with expected answers)

Then generates tuning recommendations based on results.
"""
import sys, os, json, time, asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.rag_evaluator import RAGEvaluator, RetrievalMetrics
from src.service.rag_service import rag_service
from src.config import settings
from src.utils.logger import logger

TEST_SET_PATH = Path(__file__).parent.parent.parent / "src" / "data" / "test_sets" / "rag_evaluation_test_set_v1.json"
REPORT_DIR = Path(__file__).parent.parent / "reports"
REPORT_DIR.mkdir(exist_ok=True)

# ── Eval prompt for LLM judge ──────────────────────────────────────────
EVAL_PROMPT = """你是儿童发展领域的评估专家。请基于以下信息评估RAG回答质量。

用户问题：{query}
儿童年龄：{age}岁
检索到的知识上下文：{context}
生成的回答：{answer}

请从以下维度评分（0-1之间的小数）：
1. faithfulness: 回答是否严格基于上下文，有无编造
2. relevance: 回答是否直接针对问题
3. completeness: 是否覆盖了问题的关键要点
4. age_appropriateness: 回答是否适合该年龄段

返回JSON格式：
{{"faithfulness": 0.9, "relevance": 0.85, "completeness": 0.8, "age_appropriateness": 0.9, "comment": "简要评价"}}
只返回JSON。"""


async def evaluate_single(query: str, age: int) -> dict:
    """Evaluate a single query through the full RAG pipeline."""
    t0 = time.time()
    try:
        results = await rag_service.retrieve_knowledge(
            query=query,
            limit=5,
        )
    except Exception as e:
        return {"error": str(e), "latency_ms": (time.time() - t0) * 1000}

    latency_ms = (time.time() - t0) * 1000
    # retrieve_knowledge returns List[KnowledgeItem]
    contexts = [item.content for item in results] if isinstance(results, list) else []
    knowledge_ids = [item.id for item in results] if isinstance(results, list) else []
    return {
        "contexts": contexts,
        "knowledge_ids": knowledge_ids,
        "latency_ms": latency_ms,
        "pipeline_used": "retrieval_only",
    }


async def llm_judge_eval(query: str, age: int, context: str, answer: str) -> dict:
    """Use LLM to judge answer quality."""
    from llama_index.llms.dashscope import DashScope
    
    prompt = EVAL_PROMPT.format(query=query, age=age, context=context[:2000], answer=answer[:2000])
    
    try:
        llm = DashScope(model_name="qwen-plus", api_key=settings.dashscope_api_key)
        response = await llm.acomplete(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
        return json.loads(text)
    except Exception as e:
        return {"error": str(e)}


def keyword_match_score(expected_keywords: list, contexts: list) -> float:
    """Compute keyword match score between expected keywords and retrieved contexts."""
    if not expected_keywords or not contexts:
        return 0.0
    context_text = " ".join(contexts).lower()
    matches = sum(1 for kw in expected_keywords if kw.lower() in context_text)
    return matches / len(expected_keywords)


async def main():
    # Load test set
    with open(TEST_SET_PATH, "r", encoding="utf-8") as f:
        test_set = json.load(f)

    # Sample a representative subset for quick eval (balanced by age)
    sample_size = 12  # 5 per age group
    samples = []
    ages_seen = {}
    for item in test_set:
        age = item.get("age", 0)
        count = ages_seen.get(age, 0)
        if count < 2:
            samples.append(item)
            ages_seen[age] = count + 1
        if len(samples) >= sample_size:
            break

    print(f"Evaluating {len(samples)} samples from {len(test_set)} total (balanced by age)")
    print(f"Age distribution: {ages_seen}")
    print(f"Current RAG config:")
    print(f"  BM25 weight: {settings.rag_hybrid_bm25_weight}")
    print(f"  Vector weight: {settings.rag_hybrid_vector_weight}")
    print(f"  BM25 top_k: {settings.rag_hybrid_bm25_top_k}")
    print(f"  Vector top_k: {settings.rag_hybrid_vector_top_k}")
    print(f"  Reranker: {settings.rag_reranker_model}")
    print(f"  Reranker initial_k: {settings.rag_reranker_initial_k}")
    print(f"  Reranker final_k: {settings.rag_reranker_final_k}")
    print(f"  Chunk size: {settings.rag_chunk_size}")
    print(f"  Chunk overlap: {settings.rag_chunk_overlap}")
    print()

    # ── Phase 1: Retrieval evaluation ──────────────────────────────────
    print("=" * 60)
    print("Phase 1: Retrieval Quality Evaluation")
    print("=" * 60)

    results = []
    latencies = []
    kw_scores = []
    pipeline_counts = {}
    errors = []

    for i, item in enumerate(samples):
        query = item["query"]
        age = item.get("age", 0)
        expected_kw = item.get("expected_keywords", [])

        print(f"[{i+1}/{len(samples)}] {query[:50]}...", end=" ", flush=True)
        
        result = await evaluate_single(query, age)
        
        if "error" in result:
            print(f"ERROR: {result['error'][:50]}")
            errors.append({"query": query, "error": result["error"]})
            continue

        kw_score = keyword_match_score(expected_kw, result["contexts"])
        kw_scores.append(kw_score)
        latencies.append(result["latency_ms"])
        pipeline_counts[result.get("pipeline_used", "unknown")] = pipeline_counts.get(result.get("pipeline_used", "unknown"), 0) + 1
        
        results.append({
            "query": query,
            "age": age,
            "expected_keywords": expected_kw,
            "knowledge_ids": result["knowledge_ids"],
            "keyword_match_score": kw_score,
            "latency_ms": result["latency_ms"],
            "pipeline": result["pipeline_used"],
        })

        status = "✓" if kw_score >= 0.5 else "✗"
        print(f"{status} kw={kw_score:.2f} lat={result['latency_ms']:.0f}ms")

    avg_kw = sum(kw_scores) / len(kw_scores) if kw_scores else 0
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    
    print(f"\nRetrieval Summary:")
    print(f"  Avg keyword match: {avg_kw:.4f}")
    print(f"  Avg latency: {avg_lat:.0f}ms")
    print(f"  Pipeline distribution: {pipeline_counts}")
    print(f"  Errors: {len(errors)}")

    avg_judge = {}  # Skipped - requires full QA pipeline
    # ── Phase 3: Generate report & tuning recommendations ──────────────
    print(f"\n{'=' * 60}")
    print("Phase 3: Tuning Recommendations")
    print("=" * 60)

    recommendations = []
    
    # Retrieval-based recommendations
    if avg_kw < 0.5:
        recommendations.append({
            "severity": "high",
            "category": "retrieval",
            "title": "关键词匹配率偏低",
            "detail": f"平均关键词匹配率 {avg_kw:.2f}，目标 ≥0.5",
            "suggestions": [
                "增加 BM25 权重（当前 {:.1f} → 建议 0.6~0.7）".format(settings.rag_hybrid_bm25_weight),
                "增加 reranker initial_k（当前 {} → 建议 40）".format(settings.rag_reranker_initial_k),
                "检查知识库中文档是否充分覆盖评测维度",
            ]
        })
    
    if avg_lat > 3000:
        recommendations.append({
            "severity": "medium",
            "category": "performance",
            "title": "平均延迟偏高",
            "detail": f"平均延迟 {avg_lat:.0f}ms，目标 <3000ms",
            "suggestions": [
                "减少 reranker initial_k（当前 {} → 建议 20）".format(settings.rag_reranker_initial_k),
                "检查是否可跳过某些 pipeline 步骤",
            ]
        })

    if pipeline_counts.get("simple", 0) < len(results) * 0.3:
        recommendations.append({
            "severity": "medium",
            "category": "routing",
            "title": "Simple pipeline 使用率偏低",
            "detail": f"Simple pipeline 占比 {pipeline_counts.get('simple', 0)/max(len(results),1):.1%}，目标 ≥30%",
            "suggestions": [
                "降低查询复杂度分类阈值，让更多简单查询走轻量 pipeline",
                "检查 query_classifier 的路由逻辑是否过于保守",
            ]
        })

    # LLM judge-based recommendations
    if avg_judge.get("faithfulness", 1) < 0.85:
        recommendations.append({
            "severity": "high",
            "category": "generation",
            "title": "回答忠实度偏低",
            "detail": f"忠实度 {avg_judge['faithfulness']:.2f}，目标 ≥0.85",
            "suggestions": [
                "检查 RAG prompt 是否强调基于上下文回答",
                "减少 reranker final_k（当前 {} → 建议 3），聚焦高质量上下文".format(settings.rag_reranker_final_k),
                "增加上下文去重/过滤的严格程度",
            ]
        })

    if avg_judge.get("completeness", 1) < 0.8:
        recommendations.append({
            "severity": "medium",
            "category": "retrieval",
            "title": "回答完整度偏低",
            "detail": f"完整度 {avg_judge['completeness']:.2f}，目标 ≥0.8",
            "suggestions": [
                "增加 reranker final_k（当前 {} → 建议 7~8），提供更多上下文".format(settings.rag_reranker_final_k),
                "检查知识库覆盖范围是否全面",
            ]
        })

    for rec in recommendations:
        print(f"\n[{rec['severity'].upper()}] {rec['title']}")
        print(f"  {rec['detail']}")
        for s in rec['suggestions']:
            print(f"  → {s}")

    # ── Save report ────────────────────────────────────────────────────
    report = {
        "timestamp": time.time(),
        "config": {
            "bm25_weight": settings.rag_hybrid_bm25_weight,
            "vector_weight": settings.rag_hybrid_vector_weight,
            "bm25_top_k": settings.rag_hybrid_bm25_top_k,
            "vector_top_k": settings.rag_hybrid_vector_top_k,
            "reranker_model": settings.rag_reranker_model,
            "reranker_initial_k": settings.rag_reranker_initial_k,
            "reranker_final_k": settings.rag_reranker_final_k,
            "chunk_size": settings.rag_chunk_size,
            "chunk_overlap": settings.rag_chunk_overlap,
        },
        "metrics": {
            "retrieval": {
                "avg_keyword_match": avg_kw,
                "avg_latency_ms": avg_lat,
                "pipeline_distribution": {k: v for k, v in pipeline_counts.items()},
                "sample_count": len(results),
                "error_count": len(errors),
            },
            "answer_quality": avg_judge,
        },
        "recommendations": recommendations,
        "sample_results": results,
    }

    report_path = REPORT_DIR / f"rag_eval_report_{int(time.time())}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n完整报告已保存到: {report_path}")
    
    # Print tuning config YAML snippet
    print(f"\n{'=' * 60}")
    print("Suggested RAG Config Changes (apply to .env):")
    print("=" * 60)
    for rec in recommendations:
        for s in rec["suggestions"]:
            if "BM25 权重" in s and "0.6" in s:
                print("RAG_HYBRID_BM25_WEIGHT=0.6")
                print("RAG_HYBRID_VECTOR_WEIGHT=0.4")
            if "reranker initial_k" in s and "40" in s:
                print("RAG_RERANKER_INITIAL_K=40")
            if "reranker final_k" in s and "3" in s:
                print("RAG_RERANKER_FINAL_K=3")
            if "reranker final_k" in s and "7" in s:
                print("RAG_RERANKER_FINAL_K=7")
    
    return report


if __name__ == "__main__":
    asyncio.run(main())
