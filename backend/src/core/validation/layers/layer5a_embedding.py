"""Layer 5a: Embedding 质量校验"""

import json
import logging
import random
import numpy as np
from typing import Any
from pathlib import Path
from sqlalchemy import select

from src.models.rag_eval.test_run_result import RagEvalTestRunResult
from src.models.rag_eval.test_case import RagEvalTestCase

logger = logging.getLogger(__name__)

SYNONYM_PAIRS_FILE = Path(__file__).parent.parent / "synonym_query_pairs.json"


class Layer5aEmbeddingQuality:
    """Layer 5a: Embedding 质量校验"""

    def __init__(self, session_factory, test_run):
        self.session_factory = session_factory
        self.test_run = test_run
        self._embedding = None

    async def execute(self) -> dict:
        """执行 Embedding 质量校验"""
        # 从数据库查询：通过 RagEvalTestRunResult 关联 RagEvalTestCase 获取 query 和 domain
        async with self.session_factory() as session:
            stmt = (
                select(RagEvalTestRunResult, RagEvalTestCase)
                .join(
                    RagEvalTestCase,
                    RagEvalTestRunResult.case_id == RagEvalTestCase.id,
                )
                .where(RagEvalTestRunResult.run_id == self.test_run.id)
            )
            result = await session.execute(stmt)
            rows = result.all()

        queries = [r[0].query for r in rows if r[0].query]
        test_cases = [
            {"query": r[0].query, "domain": r[1].domain.value if r[1].domain else None}
            for r in rows
            if r[0].query
        ]

        if not queries:
            return {"status": "skipped", "data": {"reason": "缺少查询列表"}}

        synonym_pairs = await self._get_synonym_pairs()

        warnings = []

        synonym_similarity = await self._check_synonym_pairs(synonym_pairs)
        if synonym_similarity is not None and synonym_similarity < 0.85:
            warnings.append(
                {
                    "level": "warning",
                    "message": f"同义对相似度低 ({synonym_similarity:.2f} < 0.85)",
                }
            )

        silhouette = await self._calc_silhouette_score(test_cases)
        if silhouette is not None and silhouette < 0.3:
            warnings.append(
                {
                    "level": "warning",
                    "message": f"区分度低 (Silhouette {silhouette:.2f} < 0.3)",
                }
            )

        anomalies = await self._detect_anomalies(queries)
        if anomalies:
            warnings.append(
                {
                    "level": "critical",
                    "message": f"发现 {len(anomalies)} 个异常向量",
                }
            )

        return {
            "status": "completed",
            "data": {
                "synonym_similarity": synonym_similarity,
                "silhouette_score": silhouette,
                "anomalies": anomalies,
                "warnings": warnings,
            },
        }

    async def _get_synonym_pairs(self) -> list:
        """获取同义查询对（优先级：手动 > 自动提取 > 内置）"""
        if SYNONYM_PAIRS_FILE.exists():
            builtin_pairs = json.loads(SYNONYM_PAIRS_FILE.read_text())
            return [
                {"query_a": p["query_a"], "query_b": p["query_b"]}
                for p in builtin_pairs[:20]
            ]
        return []

    async def _check_synonym_pairs(self, pairs: list) -> float | None:
        """检查同义对相似度"""
        if not pairs:
            return None

        from src.core.llm.embedding_factory import EmbeddingFactory

        similarities = []

        for pair in pairs:
            vec_a = await self._embed_query(pair["query_a"])
            vec_b = await self._embed_query(pair["query_b"])
            if vec_a and vec_b:
                sim = self._cosine_similarity(vec_a, vec_b)
                similarities.append(sim)

        return sum(similarities) / len(similarities) if similarities else None

    async def _get_embedding(self):
        """懒加载 Embedding 实例，全局复用"""
        if self._embedding is None:
            from src.core.llm.embedding_factory import EmbeddingFactory
            from src.config.core.manager import config_manager

            factory = EmbeddingFactory(config_manager)
            self._embedding = await factory.create(framework="langchain")
        return self._embedding

    async def _embed_query(self, query: str) -> list | None:
        """通过缓存的 Embedding 实例获取向量"""
        try:
            embedding = await self._get_embedding()
            return await embedding.aembed_query(query)
        except Exception:
            return None

    async def _calc_silhouette_score(self, test_cases: list) -> float | None:
        """计算 Silhouette Score（按领域分组）"""
        valid_cases = [tc for tc in test_cases if tc.get("query") and tc.get("domain")]
        if len(valid_cases) < 10:
            return None

        from sklearn.metrics import silhouette_score

        vectors = []
        labels = []
        domain_to_label = {}
        label_counter = 0

        for tc in valid_cases:
            vec = await self._embed_query(tc["query"])
            if vec:
                domain = tc["domain"]
                if domain not in domain_to_label:
                    domain_to_label[domain] = label_counter
                    label_counter += 1
                vectors.append(vec)
                labels.append(domain_to_label[domain])

        if len(vectors) < 10 or len(set(labels)) < 2:
            return None

        return silhouette_score(vectors, labels)

    async def _detect_anomalies(self, queries: list) -> list:
        """检测异常向量"""
        anomalies = []
        sample_size = min(20, len(queries))
        sampled_queries = (
            random.sample(queries, sample_size) if len(queries) > 20 else queries
        )

        for q in sampled_queries:
            vec = await self._embed_query(q)
            if vec is None:
                anomalies.append({"query": q, "type": "None"})
            elif np.allclose(vec, 0):
                anomalies.append({"query": q, "type": "zero_vector"})
            elif np.any(np.isnan(vec)):
                anomalies.append({"query": q, "type": "nan"})

        return anomalies

    def _cosine_similarity(self, a: list, b: list) -> float:
        """计算余弦相似度"""
        a, b = np.array(a), np.array(b)
        norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0
        return float(np.dot(a, b) / (norm_a * norm_b))
