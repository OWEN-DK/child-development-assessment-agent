from typing import List, Optional
from llama_index.core.schema import NodeWithScore
from src.config import settings
from src.utils.logger import logger
from src.service.monitoring_service import monitoring_service

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None
    logger.warning(
        "sentence-transformers not installed. CrossEncoderReranker will be unavailable. "
        "Install with: pip install sentence-transformers"
    )


class CrossEncoderReranker:
    """Cross-Encoder 重排序器
    
    使用预训练的 Cross-Encoder 模型对粗检索结果进行重排序，
    捕捉 query 和 document 之间的细微语义差异，提升检索质量。
    
    业界标准实践：
    - 粗检索（50-100 个候选）→ Cross-Encoder 重排序 → 精检索（5-10 个结果）
    - 基准测试：Hybrid RAG + Reranking 的 MRR 从 0.410 提升到 0.486（+18.5%）
    """
    
    def __init__(
        self, 
        model_name: str = "BAAI/bge-reranker-v2-m3",
        initial_k: int = 30,
        final_k: int = 5
    ):
        """
        Args:
            model_name: Cross-Encoder 模型名称，推荐使用 BAAI/bge-reranker-v2-m3
            initial_k: 粗检索结果数（重排序输入）
            final_k: 重排序后返回结果数
        """
        self.model_name = model_name
        self.initial_k = initial_k
        self.final_k = final_k
        self.model = None
        self._model_loading_attempted = False
        
        if CrossEncoder is None:
            logger.error("CrossEncoder not available. Please install sentence-transformers.")
            return
    
    def _load_model(self) -> None:
        """Lazy load the CrossEncoder model only when needed"""
        if self._model_loading_attempted or self.model is not None:
            return
            
        self._model_loading_attempted = True
        try:
            logger.info(f"Loading CrossEncoder model {self.model_name} (first use)...")
            self.model = CrossEncoder(self.model_name)
            logger.info(f"CrossEncoderReranker initialized successfully with {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to load CrossEncoder model {self.model_name}: {e}")
            self.model = None
    
    def rerank(
        self, 
        query: str, 
        nodes: List[NodeWithScore]
    ) -> List[NodeWithScore]:
        """
        对检索结果进行重排序
        
        Args:
            query: 用户查询
            nodes: 粗检索结果（建议 30-50 个候选）
            
        Returns:
            重排序后的结果（final_k 个）
        """
        # Lazy load model on first use
        self._load_model()
        
        if not self.model or not nodes:
            logger.debug(f"Reranking skipped: model={self.model is not None}, nodes={len(nodes)}")
            return nodes[:self.final_k]
        
        # 截断到 initial_k
        original_count = len(nodes)
        nodes = nodes[:self.initial_k]
        
        # 构造 query-document 对
        pairs = [[query, node.node.get_content()] for node in nodes]
        
        try:
            # 批量评分
            scores = self.model.predict(pairs)
            
            # 记录重排序前后得分变化
            original_top_score = max(n.score or 0 for n in nodes) if nodes else 0
            improvement_rate = 0.0
            
            # 更新分数并排序
            for node, score in zip(nodes, scores):
                node.score = float(score)
            
            nodes.sort(key=lambda x: x.score or 0, reverse=True)
            
            # 计算改进率
            if nodes and original_top_score > 0:
                new_top_score = nodes[0].score or 0
                improvement_rate = (new_top_score - original_top_score) / original_top_score if original_top_score > 0 else 0
            
            # 监控埋点
            monitoring_service.record_metric(
                "reranker_improvement_rate",
                improvement_rate,
                tags={"model": self.model_name}
            )
            monitoring_service.record_metric(
                "reranker_input_count",
                original_count,
                tags={"model": self.model_name}
            )
            monitoring_service.record_metric(
                "reranker_output_count",
                min(len(nodes), self.final_k),
                tags={"model": self.model_name}
            )
            
            logger.info(
                f"Reranking completed: {original_count} -> {len(nodes)} -> {self.final_k} results, "
                f"top score: {nodes[0].score if nodes else 0:.3f}, improvement: {improvement_rate:.2%}"
            )
            
            return nodes[:self.final_k]
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            # 降级方案：返回原始排序的前 final_k 个
            return nodes[:self.final_k]
    
    def rerank_batch(
        self,
        queries: List[str],
        nodes_list: List[List[NodeWithScore]]
    ) -> List[List[NodeWithScore]]:
        """
        批量重排序
        
        Args:
            queries: 查询列表
            nodes_list: 每个查询对应的粗检索结果
            
        Returns:
            重排序后的结果列表
        """
        # Lazy load model on first use
        self._load_model()
        
        if not self.model:
            return [nodes[:self.final_k] for nodes in nodes_list]
        
        results = []
        for query, nodes in zip(queries, nodes_list):
            reranked = self.rerank(query, nodes)
            results.append(reranked)
        
        return results
