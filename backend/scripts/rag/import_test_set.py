#!/usr/bin/env python3
"""导入测试集到 RagTestManager 系统"""
import sys
import json
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.service.rag_test_manager import rag_test_manager
from src.model.rag_test import TestCase
from src.core.rag_evaluator import RAGEvaluator

def import_test_set(file_path: str):
    with open(file_path, 'r', encoding='utf-8') as f:
        test_set = json.load(f)
    
    imported_count = 0
    for item in test_set:
        test_case = TestCase(
            id=item.get("id", ""),
            query=item["query"],
            age=item["age"],
            expected_knowledge_ids=item.get("expected_knowledge_ids", []),
            expected_keywords=item.get("expected_keywords", []),
            description=item.get("description", ""),
        )
        rag_test_manager.add_test_case(test_case)
        imported_count += 1
    
    print(f"成功导入 {imported_count} 条测试用例")
    
    gt_dataset = []
    for item in test_set:
        gt_dataset.append({
            "query": item["query"],
            "relevant_docs": item.get("expected_knowledge_ids", []),
            "relevance_scores": item.get("relevance_scores", {})
        })
    
    evaluator = RAGEvaluator(gt_dataset)
    stats = evaluator.get_statistics()
    print(f"评估器统计: {stats}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_test_set.py <test_set_file>")
        sys.exit(1)
    import_test_set(sys.argv[1])
