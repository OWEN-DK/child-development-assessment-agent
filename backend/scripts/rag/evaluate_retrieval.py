#!/usr/bin/env python3
"""检索模块评估脚本 - 基于现有 RAGEvaluator 和 RagTestManager"""
import sys
import os
import json
import asyncio
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.rag_evaluator import RAGEvaluator, RetrievalMetrics
from src.service.rag_test_manager import rag_test_manager
from src.config.settings import settings
from src.utils.logger import logger

async def evaluate_retrieval(test_set_path: str = None, k: int = 3):
    """运行检索评估"""
    test_cases = rag_test_manager.list_test_cases()
    if not test_cases:
        print("错误：没有测试用例，请先导入测试集")
        return
    
    print(f"使用 {len(test_cases)} 条测试用例进行检索评估")
    
    gt_dataset = []
    for tc in test_cases:
        gt_dataset.append({
            "query": tc.query,
            "relevant_docs": tc.expected_knowledge_ids,
            "relevance_scores": {kid: 3 for kid in tc.expected_knowledge_ids}
        })
    
    evaluator = RAGEvaluator(gt_dataset)
    
    retrieval_results = {}
    for tc in test_cases:
        try:
            results = await rag_test_manager.run_test_case(tc, limit=10)
            retrieval_results[tc.query] = [r.knowledge_id for r in results.results]
        except Exception as e:
            logger.error(f"测试用例 {tc.id} 执行失败: {e}")
            continue
    
    if not retrieval_results:
        print("错误：所有测试用例执行失败")
        return
    
    metrics = evaluator.evaluate_batch(retrieval_results, k=k)
    
    print(f"\n=== 检索评估报告 (Top-{k}) ===")
    print(f"Precision@{k}: {metrics.precision_at_k:.4f}")
    print(f"Recall@{k}: {metrics.recall_at_k:.4f}")
    print(f"NDCG@{k}: {metrics.ndcg_at_k:.4f}")
    print(f"MRR: {metrics.mrr:.4f}")
    print(f"MAP: {metrics.map_score:.4f}")
    
    os.makedirs("backend/reports", exist_ok=True)
    report = {
        "timestamp": time.time(),
        "test_cases_count": len(test_cases),
        "k": k,
        "metrics": {
            "precision_at_k": metrics.precision_at_k,
            "recall_at_k": metrics.recall_at_k,
            "ndcg_at_k": metrics.ndcg_at_k,
            "mrr": metrics.mrr,
            "map_score": metrics.map_score,
        },
        "config": {
            "bm25_weight": settings.rag_hybrid_bm25_weight,
            "vector_weight": settings.rag_hybrid_vector_weight,
            "reranker_model": settings.rag_reranker_model,
            "reranker_initial_k": settings.rag_reranker_initial_k,
            "reranker_final_k": settings.rag_reranker_final_k,
        }
    }
    
    report_path = "backend/reports/retrieval_evaluation_report_v1.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存到: {report_path}")
    
    print(f"\n=== 达标检查 ===")
    checks = [
        ("Recall@3 >= 0.90", metrics.recall_at_k >= 0.90),
        ("MRR >= 0.70", metrics.mrr >= 0.70),
        ("NDCG@3 >= 0.80", metrics.ndcg_at_k >= 0.80),
    ]
    for name, passed in checks:
        status = "✅ 通过" if passed else "❌ 未达标"
        print(f"  {name}: {status}")

if __name__ == "__main__":
    asyncio.run(evaluate_retrieval())
