from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np


@dataclass
class RetrievalMetrics:
    """检索评估指标"""
    precision_at_k: float  # TopK 结果中相关比例
    recall_at_k: float     # 相关文档在 TopK 中的召回率
    ndcg_at_k: float       # 排序质量（考虑等级相关性）
    mrr: float             # 第一个相关结果的排名倒数
    map_score: float       # 平均精度均值
    latency_ms: float = 0.0  # 延迟（毫秒）


class RAGEvaluator:
    """
    RAG 检索评估器
    
    实现业界标准检索评估指标：
    - Precision@K: 检索结果中相关文档的比例
    - Recall@K: 所有相关文档中被检索到的比例
    - NDCG@K: 归一化折损累计增益（考虑排序质量）
    - MRR: 平均倒数排名（第一个相关结果的排名）
    - MAP: 平均精度均值（多查询场景）
    
    使用方式：
    1. 准备标注数据集（query + 相关文档 ID + 相关性评分）
    2. 调用 evaluate_batch 计算各项指标
    3. 对比不同优化策略的效果
    """
    
    def __init__(self, ground_truth_dataset: List[Dict]):
        """
        Args:
            ground_truth_dataset: 标注数据集，格式：
                [
                    {
                        "query": "查询文本",
                        "relevant_docs": ["doc_id1", "doc_id2"],  # 相关文档 ID 列表
                        "relevance_scores": {"doc_id1": 3, "doc_id2": 2}  # 相关性评分（1-3 分）
                    }
                ]
        """
        self.ground_truth = {item["query"]: item for item in ground_truth_dataset}
    
    def evaluate_batch(
        self, 
        retrieval_results: Dict[str, List[str]],  # query -> [doc_ids]
        k: int = 5
    ) -> RetrievalMetrics:
        """
        批量评估检索质量
        
        Args:
            retrieval_results: 检索结果，{查询：[文档 ID 列表]}
            k: 评估的 TopK 值
            
        Returns:
            RetrievalMetrics: 各项评估指标
        """
        precisions = []
        recalls = []
        ndcgs = []
        reciprocal_ranks = []
        average_precisions = []
        
        for query, retrieved_docs in retrieval_results.items():
            gt = self.ground_truth.get(query)
            if not gt:
                continue
            
            relevant_docs = gt["relevant_docs"]
            relevance_scores = gt.get("relevance_scores", {doc: 1 for doc in relevant_docs})
            
            # Precision@K
            precisions.append(self._precision_at_k(retrieved_docs, relevant_docs, k))
            
            # Recall@K
            recalls.append(self._recall_at_k(retrieved_docs, relevant_docs, k))
            
            # NDCG@K
            ndcgs.append(self._ndcg_at_k(retrieved_docs, relevance_scores, k))
            
            # MRR
            reciprocal_ranks.append(self._mrr(retrieved_docs, relevant_docs))
            
            # Average Precision
            average_precisions.append(self._average_precision(retrieved_docs, relevant_docs))
        
        return RetrievalMetrics(
            precision_at_k=np.mean(precisions) if precisions else 0.0,
            recall_at_k=np.mean(recalls) if recalls else 0.0,
            ndcg_at_k=np.mean(ndcgs) if ndcgs else 0.0,
            mrr=np.mean(reciprocal_ranks) if reciprocal_ranks else 0.0,
            map_score=np.mean(average_precisions) if average_precisions else 0.0,
            latency_ms=0.0
        )
    
    def evaluate_single(
        self,
        query: str,
        retrieved_docs: List[str],
        k: int = 5
    ) -> Dict[str, float]:
        """
        评估单个查询的检索结果
        
        Args:
            query: 查询文本
            retrieved_docs: 检索到的文档 ID 列表
            k: 评估的 TopK 值
            
        Returns:
            各项指标字典
        """
        gt = self.ground_truth.get(query)
        if not gt:
            return {"error": "No ground truth for this query"}
        
        relevant_docs = gt["relevant_docs"]
        relevance_scores = gt.get("relevance_scores", {doc: 1 for doc in relevant_docs})
        
        return {
            "precision_at_k": self._precision_at_k(retrieved_docs, relevant_docs, k),
            "recall_at_k": self._recall_at_k(retrieved_docs, relevant_docs, k),
            "ndcg_at_k": self._ndcg_at_k(retrieved_docs, relevance_scores, k),
            "mrr": self._mrr(retrieved_docs, relevant_docs),
            "average_precision": self._average_precision(retrieved_docs, relevant_docs)
        }
    
    def _precision_at_k(
        self, 
        retrieved: List[str], 
        relevant: List[str], 
        k: int
    ) -> float:
        """
        计算 Precision@K
        
        Precision@K = TopK 结果中相关文档数 / K
        
        Args:
            retrieved: 检索到的文档 ID 列表
            relevant: 相关文档 ID 列表
            k: TopK 值
            
        Returns:
            Precision@K 值
        """
        if not retrieved:
            return 0.0
        top_k = retrieved[:k]
        hits = sum(1 for doc in top_k if doc in relevant)
        return hits / len(top_k)
    
    def _recall_at_k(
        self, 
        retrieved: List[str], 
        relevant: List[str], 
        k: int
    ) -> float:
        """
        计算 Recall@K
        
        Recall@K = TopK 结果中相关文档数 / 总相关文档数
        
        Args:
            retrieved: 检索到的文档 ID 列表
            relevant: 相关文档 ID 列表
            k: TopK 值
            
        Returns:
            Recall@K 值
        """
        if not relevant:
            return 0.0
        top_k = retrieved[:k]
        hits = sum(1 for doc in top_k if doc in relevant)
        return hits / len(relevant)
    
    def _ndcg_at_k(
        self, 
        retrieved: List[str], 
        relevance_scores: Dict[str, int], 
        k: int
    ) -> float:
        """
        计算 NDCG@K (Normalized Discounted Cumulative Gain)
        
        NDCG 考虑了相关性等级和排序位置，是更全面的排序质量指标。
        
        DCG = Σ(2^rel_i - 1) / log2(i + 2)
        NDCG = DCG / IDCG (理想 DCG)
        
        Args:
            retrieved: 检索到的文档 ID 列表
            relevance_scores: 文档相关性评分字典 {doc_id: score}
            k: TopK 值
            
        Returns:
            NDCG@K 值（0-1 之间）
        """
        def dcg(docs: List[str], scores: Dict[str, int], k: int) -> float:
            dcg_sum = 0.0
            for i, doc in enumerate(docs[:k]):
                rel = scores.get(doc, 0)
                dcg_sum += (2 ** rel - 1) / np.log2(i + 2)
            return dcg_sum
        
        # 理想排序（按相关性降序）
        ideal_docs = sorted(
            relevance_scores.keys(), 
            key=lambda x: relevance_scores.get(x, 0), 
            reverse=True
        )
        
        dcg_value = dcg(retrieved, relevance_scores, k)
        idcg_value = dcg(ideal_docs, relevance_scores, k)
        
        return dcg_value / idcg_value if idcg_value > 0 else 0.0
    
    def _mrr(
        self, 
        retrieved: List[str], 
        relevant: List[str]
    ) -> float:
        """
        计算 MRR (Mean Reciprocal Rank)
        
        MRR = 1 / 第一个相关结果的排名
        
        Args:
            retrieved: 检索到的文档 ID 列表（按排序顺序）
            relevant: 相关文档 ID 列表
            
        Returns:
            MRR 值（0-1 之间）
        """
        for i, doc in enumerate(retrieved):
            if doc in relevant:
                return 1.0 / (i + 1)
        return 0.0
    
    def _average_precision(
        self, 
        retrieved: List[str], 
        relevant: List[str]
    ) -> float:
        """
        计算 Average Precision (AP)
        
        AP = Σ(Precision@k * rel(k)) / 总相关文档数
        
        Args:
            retrieved: 检索到的文档 ID 列表
            relevant: 相关文档 ID 列表
            
        Returns:
            AP 值（0-1 之间）
        """
        if not relevant:
            return 0.0
        
        precisions = []
        running_correct = 0
        
        for i, doc in enumerate(retrieved):
            if doc in relevant:
                running_correct += 1
                precisions.append(running_correct / (i + 1))
        
        return np.mean(precisions) if precisions else 0.0
    
    def add_ground_truth(self, query: str, relevant_docs: List[str], relevance_scores: Dict[str, int] = None):
        """
        动态添加标注数据
        
        Args:
            query: 查询文本
            relevant_docs: 相关文档 ID 列表
            relevance_scores: 相关性评分字典（可选，默认为 1）
        """
        if relevance_scores is None:
            relevance_scores = {doc: 1 for doc in relevant_docs}
        
        self.ground_truth[query] = {
            "query": query,
            "relevant_docs": relevant_docs,
            "relevance_scores": relevance_scores
        }
    
    def get_statistics(self) -> Dict[str, int]:
        """
        获取评估集统计信息
        
        Returns:
            统计信息字典
        """
        total_queries = len(self.ground_truth)
        total_relevant_docs = sum(
            len(gt["relevant_docs"]) for gt in self.ground_truth.values()
        )
        avg_relevant_per_query = (
            total_relevant_docs / total_queries if total_queries > 0 else 0
        )
        
        return {
            "total_queries": total_queries,
            "total_relevant_docs": total_relevant_docs,
            "avg_relevant_per_query": avg_relevant_per_query
        }


# 便捷函数
def create_sample_evaluator() -> RAGEvaluator:
    """
    创建示例评估器（用于测试）
    
    Returns:
        RAGEvaluator: 包含示例数据的评估器
    """
    sample_data = [
        {
            "query": "2 岁儿童前庭觉失调的表现",
            "relevant_docs": ["doc_001", "doc_023", "doc_045"],
            "relevance_scores": {"doc_001": 3, "doc_023": 2, "doc_045": 1}
        },
        {
            "query": "婴幼儿精细动作训练方法",
            "relevant_docs": ["doc_012", "doc_034"],
            "relevance_scores": {"doc_012": 3, "doc_034": 2}
        },
        {
            "query": "3 岁儿童语言发展迟缓怎么办",
            "relevant_docs": ["doc_056", "doc_078", "doc_090"],
            "relevance_scores": {"doc_056": 3, "doc_078": 2, "doc_090": 1}
        }
    ]
    
    return RAGEvaluator(sample_data)
