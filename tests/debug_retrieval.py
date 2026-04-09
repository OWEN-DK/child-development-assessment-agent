import asyncio
import os
import sys

# 添加 backend 到 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from src.service.retrieval_service import RetrievalService
from src.service.index_manager_service import IndexManagerService
from src.service.cache_service import CacheService
from src.core.hybrid_retrieval import HybridRetrievalMerger

async def debug_scores():
    print("=== Debugging Retrieval Scores ===")
    index_manager = IndexManagerService()
    cache_service = CacheService()
    retrieval_service = RetrievalService(index_manager, cache_service)
    
    query = "孩子"
    expanded_query = await retrieval_service._expand_synonyms(query)
    print(f"Expanded query: {expanded_query}")
    
    # 获取 BM25 检索结果
    bm25_nodes = await retrieval_service.bm25_retriever.aretrieve(expanded_query)
    print(f"\nBM25 Retriever found {len(bm25_nodes)} nodes")
    
    # 获取 Vector 检索结果
    vector_nodes = await retrieval_service.vector_retriever.aretrieve(expanded_query)
    print(f"\nVector Retriever found {len(vector_nodes)} nodes")
    
    # 查找特定的内容片段（包含“如果世界上有什么是大家能够一致赞同的”）
    target_snippet = "如果世界上有什么是大家能够一致赞同的"
    
    target_bm25_score = None
    for node in bm25_nodes:
        content = node.get_content()
        if target_snippet in content:
            target_bm25_score = node.score
            print(f"Found target in BM25 results! Raw BM25 Score: {node.score}")
            break
    
    target_vector_score = None
    for node in vector_nodes:
        content = node.get_content()
        if target_snippet in content:
            target_vector_score = node.score
            print(f"Found target in Vector results! Raw Vector Score: {node.score}")
            break
            
    if target_bm25_score is None and target_vector_score is None:
        print("Target snippet not found in Top 10 of either retriever!")
        
        # 尝试扩大检索范围找一找
        print("\nExpanding search to top 50 to find the target...")
        retrieval_service.bm25_retriever.similarity_top_k = 50
        retrieval_service.vector_retriever.similarity_top_k = 50
        
        bm25_nodes = await retrieval_service.bm25_retriever.aretrieve(expanded_query)
        vector_nodes = await retrieval_service.vector_retriever.aretrieve(expanded_query)
        
        for node in bm25_nodes:
            if target_snippet in node.get_content():
                print(f"Found target in BM25 (Top 50)! Raw BM25 Score: {node.score}")
                target_bm25_score = node.score
                break
        for node in vector_nodes:
            if target_snippet in node.get_content():
                print(f"Found target in Vector (Top 50)! Raw Vector Score: {node.score}")
                target_vector_score = node.score
                break
                
    # 手动进行融合以查看分数变化
    print("\n=== Merging Process ===")
    merged = HybridRetrievalMerger.merge_for_search(
        bm25_nodes, vector_nodes, 
        bm25_weight=0.5, vector_weight=0.5, 
        no_match_vector_penalty=0.5, limit=10
    )
    
    for i, node in enumerate(merged):
        if target_snippet in node.get_content():
            print(f"Target node after merge: Rank #{i+1}, Merged Score: {node.score}")
            
if __name__ == "__main__":
    asyncio.run(debug_scores())
