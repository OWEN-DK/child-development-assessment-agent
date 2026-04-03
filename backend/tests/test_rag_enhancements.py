"""
RAG 系统优化功能测试

测试新增的优化功能：
1. Cross-Encoder 重排序器
2. 层次化分块策略
3. 查询扩展质量验证
4. RAG 检索评估器
5. 上下文压缩器
6. 分数归一化优化
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from llama_index.core.schema import Node, NodeWithScore

# Test 1: Cross-Encoder Reranker
def test_reranker_initialization():
    """测试重排序器初始化"""
    from src.core.reranker import CrossEncoderReranker
    
    reranker = CrossEncoderReranker(
        model_name="BAAI/bge-reranker-v2-m3",
        initial_k=30,
        final_k=5
    )
    
    assert reranker.initial_k == 30
    assert reranker.final_k == 5
    # 模型可能因为未安装 sentence-transformers 而不可用
    # 所以只检查配置参数
    
    print("✅ 重排序器初始化测试通过")


def test_reranker_rerank_without_model():
    """测试重排序器降级逻辑（无模型时）"""
    from src.core.reranker import CrossEncoderReranker
    
    reranker = CrossEncoderReranker()
    reranker.model = None  # 模拟模型不可用
    
    # 创建模拟节点
    nodes = [
        NodeWithScore(node=Node(text=f"Content {i}"), score=1.0 - i * 0.1)
        for i in range(10)
    ]
    
    # 无模型时应直接返回前 final_k 个
    result = reranker.rerank("test query", nodes)
    
    assert len(result) == 5  # final_k
    print("✅ 重排序器降级逻辑测试通过")


# Test 2: Hierarchical Chunking
def test_hierarchical_chunking():
    """测试层次化分块策略"""
    from src.core.metadata_processor import MetadataProcessor
    from llama_index.core.schema import Document
    
    # 创建带标题结构的文档
    doc_text = """
# 第一章 儿童发展

## 第一节 大运动发展

婴儿在出生后的第一年会经历快速的大运动发展。

### 抬头

新生儿在 2-3 个月时开始学会抬头。

### 翻身

4-6 个月的婴儿开始学会翻身。

## 第二节 精细动作发展

精细动作是指手眼协调和手指灵活性的发展。
"""
    
    doc = Document(text=doc_text, metadata={"source": "test.pdf"})
    
    # 测试层次化分块
    nodes = MetadataProcessor.hierarchical_chunking(
        documents=[doc],
        parent_chunk_size=1500,
        child_chunk_size=400,
        file_hash="test_hash"
    )
    
    # 应该生成父块和子块
    assert len(nodes) > 0
    
    # 检查元数据
    for node in nodes:
        assert "file_hash" in node.metadata
        assert node.metadata["file_hash"] == "test_hash"
        assert "chunk_type" in node.metadata  # parent 或 child
    
    print(f"✅ 层次化分块测试通过：生成 {len(nodes)} 个节点")


# Test 3: Query Expansion Validation
def test_query_expansion_validation():
    """测试查询扩展质量验证"""
    from src.service.retrieval_service import RetrievalService
    
    # 创建 mock 实例
    mock_index_manager = Mock()
    mock_cache_service = Mock()
    
    service = RetrievalService(mock_index_manager, mock_cache_service)
    
    # 测试有效扩展
    valid_expansion = "儿童教育 学前教育 幼儿教育"
    assert service._validate_expansion(valid_expansion, "儿童教育") == True
    
    # 测试过长扩展
    long_expansion = "这是一个非常长的扩展文本，超过了 200 个字符的限制。" * 10
    assert service._validate_expansion(long_expansion, "儿童教育") == False
    
    # 测试包含标点的扩展
    punctuated_expansion = "儿童教育。学前教育！幼儿教育？"
    assert service._validate_expansion(punctuated_expansion, "儿童教育") == False
    
    # 测试不包含原查询的扩展
    unrelated_expansion = "学前教育 幼儿教育 早期教育"
    assert service._validate_expansion(unrelated_expansion, "儿童教育") == False
    
    # 测试包含无关内容的扩展
    irrelevant_expansion = "抱歉，我不知道这个问题的答案"
    assert service._validate_expansion(irrelevant_expansion, "儿童教育") == False
    
    print("✅ 查询扩展质量验证测试通过")


# Test 4: RAG Evaluator
def test_rag_evaluator_precision():
    """测试检索评估器 - Precision@K"""
    from src.core.rag_evaluator import RAGEvaluator
    
    # 准备标注数据
    ground_truth = [
        {
            "query": "test query 1",
            "relevant_docs": ["doc1", "doc2", "doc3"],
            "relevance_scores": {"doc1": 3, "doc2": 2, "doc3": 1}
        }
    ]
    
    evaluator = RAGEvaluator(ground_truth)
    
    # 完美检索（所有结果都相关）
    perfect_results = ["doc1", "doc2", "doc3", "doc4", "doc5"]
    metrics = evaluator.evaluate_batch({"test query 1": perfect_results}, k=5)
    
    assert metrics.precision_at_k == 0.6  # 3/5
    assert metrics.recall_at_k == 1.0  # 3/3
    
    # 糟糕检索（没有相关结果）
    poor_results = ["doc4", "doc5", "doc6", "doc7", "doc8"]
    metrics = evaluator.evaluate_batch({"test query 1": poor_results}, k=5)
    
    assert metrics.precision_at_k == 0.0
    assert metrics.recall_at_k == 0.0
    
    print("✅ 检索评估器 Precision@K 测试通过")


def test_rag_evaluator_mrr():
    """测试检索评估器 - MRR"""
    from src.core.rag_evaluator import RAGEvaluator
    
    ground_truth = [
        {
            "query": "test query",
            "relevant_docs": ["doc1", "doc2"],
            "relevance_scores": {"doc1": 3, "doc2": 2}
        }
    ]
    
    evaluator = RAGEvaluator(ground_truth)
    
    # 第一个结果就相关 -> MRR = 1.0
    results1 = ["doc1", "doc2", "doc3"]
    metrics1 = evaluator.evaluate_batch({"test query": results1}, k=5)
    assert metrics1.mrr == 1.0
    
    # 第二个结果相关 -> MRR = 0.5
    results2 = ["doc3", "doc1", "doc2"]
    metrics2 = evaluator.evaluate_batch({"test query": results2}, k=5)
    assert metrics2.mrr == 0.5
    
    # 第三个结果相关 -> MRR = 0.33
    results3 = ["doc3", "doc4", "doc1"]
    metrics3 = evaluator.evaluate_batch({"test query": results3}, k=5)
    assert abs(metrics3.mrr - 0.333) < 0.01
    
    # 没有相关结果 -> MRR = 0.0
    results4 = ["doc3", "doc4", "doc5"]
    metrics4 = evaluator.evaluate_batch({"test query": results4}, k=5)
    assert metrics4.mrr == 0.0
    
    print("✅ 检索评估器 MRR 测试通过")


def test_rag_evaluator_ndcg():
    """测试检索评估器 - NDCG@K"""
    from src.core.rag_evaluator import RAGEvaluator
    
    ground_truth = [
        {
            "query": "test query",
            "relevant_docs": ["doc1", "doc2", "doc3"],
            "relevance_scores": {"doc1": 3, "doc2": 2, "doc3": 1}
        }
    ]
    
    evaluator = RAGEvaluator(ground_truth)
    
    # 理想排序（相关性降序）-> NDCG = 1.0
    ideal_results = ["doc1", "doc2", "doc3"]
    metrics = evaluator.evaluate_batch({"test query": ideal_results}, k=3)
    
    assert metrics.ndcg_at_k == 1.0
    
    # 反向排序 -> NDCG < 1.0
    reverse_results = ["doc3", "doc2", "doc1"]
    metrics = evaluator.evaluate_batch({"test query": reverse_results}, k=3)
    
    assert metrics.ndcg_at_k < 1.0
    assert metrics.ndcg_at_k > 0.0
    
    print("✅ 检索评估器 NDCG 测试通过")


# Test 5: Context Compressor
def test_context_compressor_relevance_filtering():
    """测试上下文压缩器 - 相关性过滤"""
    from src.core.context_compressor import ContextCompressor
    
    compressor = ContextCompressor(
        max_tokens=4000,
        relevance_threshold=0.3,
        similarity_threshold=0.9
    )
    
    # 创建模拟节点（不同分数）
    nodes = [
        NodeWithScore(node=Node(text=f"High score content {i}"), score=0.8 - i * 0.1)
        for i in range(10)
    ]
    
    # 压缩
    result = compressor.compress(nodes, "test query")
    
    # 应该过滤掉低分节点
    assert len(result) < len(nodes)
    
    # 所有保留的节点分数都应该 >= 阈值
    for node in result:
        assert node.score >= 0.3
    
    print(f"✅ 上下文压缩器相关性过滤测试通过：{len(nodes)} -> {len(result)}")


def test_context_compressor_token_budget():
    """测试上下文压缩器 - Token 预算控制"""
    from src.core.context_compressor import ContextCompressor
    
    # 设置很小的 Token 预算
    compressor = ContextCompressor(
        max_tokens=100,  # 只允许 100 tokens
        relevance_threshold=0.0,  # 不过滤
        similarity_threshold=0.9
    )
    
    # 创建长文本节点
    nodes = [
        NodeWithScore(
            node=Node(text="这是一个很长的文本内容。" * 50),
            score=1.0 - i * 0.1
        )
        for i in range(5)
    ]
    
    # 压缩
    result = compressor.compress(nodes, "test query")
    
    # 应该因为 Token 预算限制而截断
    assert len(result) < len(nodes)
    
    print(f"✅ 上下文压缩器 Token 预算测试通过：{len(nodes)} -> {len(result)}")


def test_context_compressor_deduplication():
    """测试上下文压缩器 - 去重"""
    from src.core.context_compressor import ContextCompressor
    
    compressor = ContextCompressor(
        max_tokens=10000,
        relevance_threshold=0.0,
        similarity_threshold=0.9
    )
    
    # 创建相似文本
    text1 = "儿童发展包括大运动、精细动作、语言、认知等方面。"
    text2 = "儿童发展涵盖了大运动、精细动作、语言表达、认知能力等发展领域。"
    
    nodes = [
        NodeWithScore(node=Node(text=text1), score=0.9),
        NodeWithScore(node=Node(text=text2), score=0.85),
        NodeWithScore(node=Node(text="完全不同的内容"), score=0.8)
    ]
    
    # 压缩
    result = compressor.compress(nodes, "test query")
    
    # 相似文本应该被去重
    assert len(result) < len(nodes)
    
    print(f"✅ 上下文压缩器去重测试通过：{len(nodes)} -> {len(result)}")


# Test 6: Hybrid Retrieval Score Normalization
def test_hybrid_retrieval_normalization():
    """测试混合检索分数归一化优化"""
    from src.core.hybrid_retrieval import HybridRetrievalMerger
    
    # 测试单节点场景
    nodes_single = [NodeWithScore(node=Node(text="single"), score=0.5)]
    normalized = HybridRetrievalMerger._normalize_all_scores(nodes_single)
    assert len(normalized) == 1
    # 单节点应该使用 Sigmoid 校准而不是强制 1.0
    assert normalized[0].score < 1.0
    
    # 测试全零分数场景
    nodes_zero = [
        NodeWithScore(node=Node(text=f"zero {i}"), score=0.0)
        for i in range(5)
    ]
    normalized = HybridRetrievalMerger._normalize_all_scores(nodes_zero)
    # 所有节点应该获得相同的默认分数
    assert all(node.score == 0.5 for node in normalized)
    
    # 测试相同分数场景
    nodes_same = [
        NodeWithScore(node=Node(text=f"same {i}"), score=0.7)
        for i in range(5)
    ]
    normalized = HybridRetrievalMerger._normalize_all_scores(nodes_same)
    # 应该有微小差异但不引入明显偏差
    assert normalized[0].score > normalized[-1].score
    assert normalized[0].score - normalized[-1].score < 0.1
    
    print("✅ 混合检索分数归一化测试通过")


def test_vector_score_calibration():
    """测试向量分数 Sigmoid 校准"""
    from src.core.hybrid_retrieval import HybridRetrievalMerger
    
    # 测试 Sigmoid 校准
    score_low = 0.2
    score_mid = 0.5
    score_high = 0.9
    
    calibrated_low = HybridRetrievalMerger._calibrate_vector_score(score_low)
    calibrated_mid = HybridRetrievalMerger._calibrate_vector_score(score_mid)
    calibrated_high = HybridRetrievalMerger._calibrate_vector_score(score_high)
    
    # 校准后的分数应该在 [0,1] 区间
    assert 0 <= calibrated_low <= 1
    assert 0 <= calibrated_mid <= 1
    assert 0 <= calibrated_high <= 1
    
    # 保持相对大小关系
    assert calibrated_low < calibrated_mid < calibrated_high
    
    print("✅ 向量分数 Sigmoid 校准测试通过")


# Test 7: Integration test
@pytest.mark.asyncio
async def test_reranker_integration():
    """测试重排序器集成"""
    from src.service.retrieval_service import RetrievalService
    from unittest.mock import Mock
    
    # 创建 mock 实例
    mock_index_manager = Mock()
    mock_cache_service = Mock()
    
    # 初始化服务（会创建重排序器）
    service = RetrievalService(mock_index_manager, mock_cache_service)
    
    # 检查重排序器是否已初始化
    assert hasattr(service, 'reranker')
    assert service.reranker is not None
    
    print("✅ 重排序器集成测试通过")


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
