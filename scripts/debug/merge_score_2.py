from llama_index.core.schema import NodeWithScore, TextNode
from src.core.hybrid_retrieval import HybridRetrievalMerger

def test():
    # 模拟真实检索结果，没有命中BM25，只有一个向量结果命中了
    # 因为在没有归一化之前，分数可能比较低，比如 0.2-0.3
    vector_nodes = [
        NodeWithScore(node=TextNode(text="测试文本", id_="1"), score=0.2),
    ]
    
    print("\n=== merge_for_search 测试 (只有1个低分结果) ===")
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
