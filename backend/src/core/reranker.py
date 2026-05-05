import math
from typing import List, Optional

from llama_index.core.schema import NodeWithScore

from src.config import settings
from src.service.monitoring_service import monitoring_service
from src.utils.logger import logger

try:
    from sentence_transformers import CrossEncoder
    _CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CrossEncoder = None
    _CROSS_ENCODER_AVAILABLE = False

try:
    import dashscope
    _DASHSCOPE_AVAILABLE = True
except ImportError:
    _DASHSCOPE_AVAILABLE = False


class CrossEncoderReranker:
    """Cross-Encoder 重排序器
    
    使用预训练的 Cross-Encoder 模型对粗检索结果进行重排序，
    捕捉 query 和 document 之间的细微语义差异，提升检索质量。
    
    业界标准实践：
    - 粗检索（50-100 个候选）→ Cross-Encoder 重排序 → 精检索（5-10 个结果）
    - 基准测试：Hybrid RAG + Reranking 的 MRR 从 0.410 提升到 0.486（+18.5%）
    """
    
    # 类级别标志，确保只打印一次缺少依赖的警告
    _warning_logged = False

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        initial_k: int = 30,
        final_k: int = 5,
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
        self._warmed_model = None

        if not _CROSS_ENCODER_AVAILABLE and not CrossEncoderReranker._warning_logged:
            logger.warning(
                "sentence-transformers not installed. CrossEncoderReranker will be unavailable. "
                "Install with: pip install sentence-transformers"
            )
            CrossEncoderReranker._warning_logged = True

    def set_warmed_model(self, model) -> None:
        """设置预热后的模型"""
        if model is not None:
            self._warmed_model = model
            logger.info("使用预热后的 Cross-Encoder 模型")

    def _load_model(self) -> None:
        """Lazy load the CrossEncoder model only when needed"""
        if self._model_loading_attempted or self.model is not None:
            return

        if self._warmed_model is not None:
            self.model = self._warmed_model
            self._model_loading_attempted = True
            logger.info("使用预热模型，跳过懒加载")
            return

        self._model_loading_attempted = True
        try:
            logger.info(f"Loading CrossEncoder model {self.model_name} (first use)...")
            self.model = CrossEncoder(self.model_name)
            logger.info(
                f"CrossEncoderReranker initialized successfully with {self.model_name}"
            )
        except Exception as e:
            logger.error(f"Failed to load CrossEncoder model {self.model_name}: {e}")
            self.model = None

    def _calculate_initial_k(self, query: str) -> int:
        """
        根据查询复杂度动态计算 initial_k

        规则：
        - 简单查询（<5 字）→ initial_k=15
        - 短词查询（5-10 字）→ initial_k=20
        - 中等查询（10-15 字）→ initial_k=30
        - 复杂查询（>15 字）→ initial_k=50
        """
        dynamic_enabled = getattr(settings, "rag_reranker_dynamic_initial_k", True)
        if not dynamic_enabled:
            return self.initial_k

        query_len = len(query.replace(" ", ""))

        if query_len < 5:
            return 15
        elif query_len < 10:
            return 20
        elif query_len <= 15:
            return 30
        else:
            return 50

    def rerank(self, query: str, nodes: List[NodeWithScore]) -> List[NodeWithScore]:
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
            logger.debug(
                f"Reranking skipped: model={self.model is not None}, nodes={len(nodes)}"
            )
            return nodes[: self.final_k]

        dynamic_initial_k = self._calculate_initial_k(query)
        original_count = len(nodes)
        nodes = nodes[:dynamic_initial_k]

        pairs = [[query, node.node.get_content()] for node in nodes]

        try:
            scores = self.model.predict(pairs)

            original_top_score = max(n.score or 0 for n in nodes) if nodes else 0
            improvement_rate = 0.0

            for node, score in zip(nodes, scores):
                node.score = 1.0 / (1.0 + math.exp(-float(score)))  # sigmoid → (0, 1)

            nodes.sort(key=lambda x: x.score or 0, reverse=True)

            if nodes and original_top_score > 0:
                new_top_score = nodes[0].score or 0
                improvement_rate = (
                    (new_top_score - original_top_score) / original_top_score
                    if original_top_score > 0
                    else 0
                )

            monitoring_service.record_metric(
                "reranker_improvement_rate",
                improvement_rate,
                tags={"model": self.model_name},
            )
            monitoring_service.record_metric(
                "reranker_input_count", original_count, tags={"model": self.model_name}
            )
            monitoring_service.record_metric(
                "reranker_output_count",
                min(len(nodes), self.final_k),
                tags={"model": self.model_name},
            )

            logger.info(
                f"Reranking completed: {original_count} -> {len(nodes)} -> {self.final_k} results, "
                f"initial_k={dynamic_initial_k}, top score: {nodes[0].score if nodes else 0:.3f}, "
                f"improvement: {improvement_rate:.2%}"
            )

            return nodes[: self.final_k]

        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            # 降级方案：返回原始排序的前 final_k 个
            return nodes[: self.final_k]

    def rerank_batch(
        self, queries: List[str], nodes_list: List[List[NodeWithScore]]
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
            return [nodes[: self.final_k] for nodes in nodes_list]

        results = []
        for query, nodes in zip(queries, nodes_list):
            reranked = self.rerank(query, nodes)
            results.append(reranked)

        return results


class DashScopeReranker:
    """DashScope API 重排序器

    使用阿里云百炼平台的 qwen3-rerank 模型对粗检索结果进行重排序，
    无需本地加载模型，通过 API 调用完成。
    """

    def __init__(
        self,
        model_name: str = "qwen3-rerank",
        initial_k: int = 30,
        final_k: int = 5,
    ):
        self.model_name = model_name
        self.initial_k = initial_k
        self.final_k = final_k

        if not _DASHSCOPE_AVAILABLE:
            logger.warning(
                "dashscope SDK 未安装，DashScopeReranker 不可用。"
                "请执行: pip install dashscope"
            )
        elif settings.dashscope_api_key:
            dashscope.api_key = settings.dashscope_api_key

    def _calculate_initial_k(self, query: str) -> int:
        """根据查询复杂度动态计算 initial_k"""
        dynamic_enabled = getattr(settings, "rag_reranker_dynamic_initial_k", True)
        if not dynamic_enabled:
            return self.initial_k

        query_len = len(query.replace(" ", ""))

        if query_len < 5:
            return 15
        elif query_len < 10:
            return 20
        elif query_len <= 15:
            return 30
        else:
            return 50

    def rerank(self, query: str, nodes: List[NodeWithScore]) -> List[NodeWithScore]:
        """对检索结果进行重排序

        Args:
            query: 用户查询
            nodes: 粗检索结果

        Returns:
            重排序后的结果（final_k 个）
        """
        if not _DASHSCOPE_AVAILABLE or not nodes:
            return nodes[: self.final_k]

        dynamic_initial_k = self._calculate_initial_k(query)
        original_count = len(nodes)
        candidates = nodes[:dynamic_initial_k]

        documents = [node.node.get_content() for node in candidates]

        try:
            response = dashscope.TextReRank.call(
                model=self.model_name,
                query=query,
                documents=documents,
                top_n=min(len(documents), self.final_k),
            )

            if response.status_code != 200:
                logger.error(
                    f"DashScope Rerank API 失败: {response.code} - {response.message}"
                )
                return nodes[: self.final_k]

            # API 返回的 relevance_score 已在 [0, 1] 范围内，无需 sigmoid
            for result in response.output.results:
                candidates[result.index].score = result.relevance_score

            candidates.sort(key=lambda x: x.score or 0, reverse=True)

            # 记录监控指标
            if candidates and original_count > 0:
                monitoring_service.record_metric(
                    "reranker_input_count",
                    original_count,
                    tags={"model": self.model_name, "provider": "dashscope"},
                )
                monitoring_service.record_metric(
                    "reranker_output_count",
                    min(len(candidates), self.final_k),
                    tags={"model": self.model_name, "provider": "dashscope"},
                )

            logger.info(
                f"DashScope 重排序完成: {original_count} -> {len(candidates)} -> {self.final_k} 结果, "
                f"模型={self.model_name}, top score: {candidates[0].score if candidates else 0:.3f}"
            )

            return candidates[: self.final_k]

        except Exception as e:
            logger.error(f"DashScope 重排序异常: {e}")
            return nodes[: self.final_k]

    def rerank_batch(
        self, queries: List[str], nodes_list: List[List[NodeWithScore]]
    ) -> List[List[NodeWithScore]]:
        """批量重排序"""
        return [self.rerank(q, ns) for q, ns in zip(queries, nodes_list)]


def create_reranker(
    model_name: Optional[str] = None,
    initial_k: Optional[int] = None,
    final_k: Optional[int] = None,
):
    """根据配置创建重排序器实例

    优先使用 DashScope API，sentence-transformers 不可用时自动降级。
    """
    provider = getattr(settings, "rag_reranker_provider", "dashscope")

    if model_name is None:
        model_name = getattr(settings, "rag_reranker_model", "qwen3-rerank")
    if initial_k is None:
        initial_k = getattr(settings, "rag_reranker_initial_k", 30)
    if final_k is None:
        final_k = getattr(settings, "rag_reranker_final_k", 5)

    if provider == "dashscope":
        logger.info(f"使用 DashScope Reranker: model={model_name}")
        return DashScopeReranker(
            model_name=model_name, initial_k=initial_k, final_k=final_k
        )
    elif provider == "local":
        if not _CROSS_ENCODER_AVAILABLE:
            logger.warning(
                "sentence-transformers 不可用，回退到 DashScope Reranker"
            )
            return DashScopeReranker(
                model_name="qwen3-rerank", initial_k=initial_k, final_k=final_k
            )
        logger.info(f"使用本地 CrossEncoder Reranker: model={model_name}")
        return CrossEncoderReranker(
            model_name=model_name, initial_k=initial_k, final_k=final_k
        )
    else:
        logger.warning(f"未知的 reranker provider '{provider}'，使用 DashScope")
        return DashScopeReranker(
            model_name="qwen3-rerank", initial_k=initial_k, final_k=final_k
        )
