from llama_index.core.schema import NodeWithScore, TextNode
from src.core.hybrid_retrieval import HybridRetrievalMerger

def test():
    bm25_nodes = [
        NodeWithScore(node=TextNode(text="测试BM25", id_="2"), score=5.0),
    ]
    vector_nodes = [
        NodeWithScore(node=TextNode(text="测试文本", id_="1"), score=0.6),
        NodeWithScore(node=TextNode(text="测试BM25", id_="2"), score=0.55),
    ]
    
    print("\n=== merge_for_search 测试 (有BM25匹配的情况) ===")
    merged = HybridRetrievalMerger.merge_for_search(
        bm25_nodes=bm25_nodes, 
        vector_nodes=vector_nodes, 
        bm25_weight=0.7, 
        vector_weight=0.3, 
        no_match_vector_penalty=0.3
    )
    for n in merged:
        print(f"Node {n.node.node_id}: score={n.score}")

test()
