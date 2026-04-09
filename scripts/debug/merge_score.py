from llama_index.core.schema import NodeWithScore, TextNode
from src.core.hybrid_retrieval import HybridRetrievalMerger

def test():
    # 模拟纯向量检索结果（没有命中BM25）
    bm25_nodes = []
    vector_nodes = [
        NodeWithScore(node=TextNode(text="测试文本", id_="1"), score=0.6),
        NodeWithScore(node=TextNode(text="测试文本2", id_="2"), score=0.55),
    ]
    
    print("=== _normalize_all_scores 独立测试 ===")
    nodes_copy = [NodeWithScore(node=n.node, score=n.score) for n in vector_nodes]
    norm_nodes = HybridRetrievalMerger._normalize_all_scores(nodes_copy)
    for n in norm_nodes:
        print(f"Node {n.node.node_id}: norm={n.score}")
    
    print("\n=== merge_for_search 测试 ===")
    merged = HybridRetrievalMerger.merge_for_search(
        bm25_nodes=[], 
        vector_nodes=vector_nodes, 
        bm25_weight=0.7, 
        vector_weight=0.3, 
        no_match_vector_penalty=0.3
    )
    for n in merged:
        print(f"Node {n.node.node_id}: score={n.score}")

test()
