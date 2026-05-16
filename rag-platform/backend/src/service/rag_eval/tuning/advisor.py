"""调优建议生成器

基于评估指标自动生成调优建议，涵盖检索、生成、系统和跨域四个维度。
每条建议指向管道中的具体节点和参数，支持前端一键跳转编辑。
"""
import uuid
from typing import Any, Optional

from src.utils.logger import logger

# 触发条件阈值（可从 ConfigCache 覆盖）
DEFAULT_THRESHOLDS = {
    "low_hit_rate": 0.5,       # Hit Rate < 0.5 → 建议调整 top_k
    "low_recall": 0.4,         # Recall < 0.4 → 建议增强检索
    "high_latency": 5000,      # P95 > 5000ms → 建议启用缓存
    "domain_activation_miss": 0.7,  # 域激活准确率 < 0.7
    "cross_domain_imbalance": 0.3,  # 域贡献度 < 0.3
    "conflict_undetected": 0.5,     # 冲突检测率 < 0.5
    "latency_bottleneck": 5000,     # e2e P95 > 5000ms
}


class TuningAdvisor:
    """调优建议生成器

    基于评估结果自动分析性能瓶颈并生成具体调优建议。
    每条建议包含 target_node_id 和 target_param，用于前端定位。
    """

    def __init__(self, config_cache: Optional[Any] = None):
        self._config_cache = config_cache

    async def generate_retrieval_suggestions(
        self,
        run_id: str,
        l1_metrics: Optional[dict[str, Any]],
        domain_contributions: Optional[list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """生成检索层调优建议

        分析 Hit Rate、Recall、Precision 等指标，
        为检索节点（BM25/向量/混合检索）生成调优建议。
        """
        suggestions = []
        if not l1_metrics:
            return suggestions

        avg_precision = l1_metrics.get("avg_precision", 0) or 0
        avg_recall = l1_metrics.get("avg_recall", 0) or 0
        avg_f1 = l1_metrics.get("avg_f1", 0) or 0

        # 低召回率 → 建议增大 top_k
        if avg_recall < self._threshold("low_recall"):
            suggestions.append(self._make_suggestion(
                run_id=run_id,
                category="retrieval",
                severity="warning" if avg_recall > 0.2 else "critical",
                title="检索召回率过低",
                description=f"当前平均召回率 {avg_recall:.3f}，可能存在遗漏相关文档的风险",
                current_value="top_k=5",
                suggested_value="top_k=10",
                expected_impact="预期召回率提升 0.15-0.25",
                target_node_id="retrieval",
                target_param="top_k",
                priority=1,
            ))

        # 低精确率 → 建议启用重排序
        if avg_precision < 0.5 and avg_recall >= 0.5:
            suggestions.append(self._make_suggestion(
                run_id=run_id,
                category="retrieval",
                severity="warning",
                title="检索精确率偏低",
                description=f"召回率 {avg_recall:.3f} 尚可但精确率 {avg_precision:.3f} 较低",
                current_value="rerank=未启用",
                suggested_value="rerank=enabled",
                expected_impact="预期精确率提升 0.10-0.20",
                target_node_id="rerank",
                target_param="enabled",
                priority=2,
            ))

        # 低 F1 → 建议调整混合检索权重
        if avg_f1 < 0.5:
            suggestions.append(self._make_suggestion(
                run_id=run_id,
                category="retrieval",
                severity="warning",
                title="检索效果整体偏低",
                description=f"F1={avg_f1:.3f}，建议调整混合检索的向量/关键词权重",
                current_value="vector_weight=0.5, keyword_weight=0.5",
                suggested_value="vector_weight=0.6, keyword_weight=0.4",
                expected_impact="预期 F1 提升 0.05-0.15",
                target_node_id="hybrid_search",
                target_param="vector_weight",
                priority=3,
            ))

        return suggestions

    async def generate_cross_domain_suggestions(
        self,
        run_id: str,
        cross_domain_metrics: Optional[dict[str, Any]],
        domain_contributions: Optional[list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """生成跨域调优建议

        分析域激活准确率、跨域覆盖率、冲突检测率、端到端延迟。
        """
        suggestions = []
        if not cross_domain_metrics:
            return suggestions

        # 域激活不准确
        activation_acc = cross_domain_metrics.get("domain_activation_accuracy", 1.0)
        if activation_acc >= 0 and activation_acc < self._threshold("domain_activation_miss"):
            suggestions.append(self._make_suggestion(
                run_id=run_id,
                category="system",
                severity="warning",
                title="域激活准确率偏低",
                description=f"当前域激活准确率 {activation_acc:.3f}，部分期望域未被激活",
                current_value="domain_keywords=默认",
                suggested_value="检查并更新各域触发关键词配置",
                expected_impact="预期域激活准确率提升至 0.8+",
                target_node_id="query_analyzer",
                target_param="domain_keywords",
                priority=5,
            ))

        # 域贡献度不平衡
        if domain_contributions:
            for dc in domain_contributions:
                contrib = dc.get("contribution_score", 0) or 0
                if contrib < self._threshold("cross_domain_imbalance"):
                    domain_name = dc.get("domain_name", dc.get("domain_id", "N/A"))
                    suggestions.append(self._make_suggestion(
                        run_id=run_id,
                        category="system",
                        severity="info",
                        title=f"{domain_name} 域贡献度过低",
                        description=f"该域贡献度仅 {contrib:.3f}，可能权重偏低或检索效果不佳",
                        current_value=f"domain_weight=默认",
                        suggested_value=f"上调 {domain_name} 的 domain_weight",
                        expected_impact="提升该域对最终答案的贡献",
                        target_node_id="cross_fusion",
                        target_param=f"domain_weight.{domain_name}",
                        priority=6,
                    ))

        # 冲突检测率低
        conflict_rate = cross_domain_metrics.get("conflict_detection_rate", 1.0)
        if conflict_rate >= 0 and conflict_rate < self._threshold("conflict_undetected"):
            suggestions.append(self._make_suggestion(
                run_id=run_id,
                category="system",
                severity="info",
                title="跨域冲突检测率偏低",
                description=f"冲突检测率仅 {conflict_rate:.3f}，可能存在未发现的跨域矛盾",
                current_value="conflict_detect=未启用或灵敏度低",
                suggested_value="启用冲突检测节点 | conflict_threshold=0.6",
                expected_impact="检测更多跨域矛盾，提升答案一致性",
                target_node_id="conflict_detect",
                target_param="enabled",
                priority=7,
            ))

        # 延迟瓶颈
        latency = cross_domain_metrics.get("e2e_latency", {})
        if isinstance(latency, dict):
            p95 = latency.get("p95_ms", 0)
            if p95 > self._threshold("latency_bottleneck"):
                suggestions.append(self._make_suggestion(
                    run_id=run_id,
                    category="system",
                    severity="warning" if p95 > 10000 else "info",
                    title="端到端延迟过高",
                    description=f"P95 延迟 {p95}ms，超出建议阈值",
                    current_value="semantic_cache=未启用",
                    suggested_value="启用语义缓存节点 | ttl=300s",
                    expected_impact="预期 P95 延迟降低 40-60%",
                    target_node_id="semantic_cache",
                    target_param="enabled",
                    priority=4,
                ))

        return suggestions

    def _make_suggestion(
        self,
        run_id: str,
        category: str,
        severity: str,
        title: str,
        description: str,
        current_value: str,
        suggested_value: str,
        expected_impact: str,
        target_node_id: str,
        target_param: str,
        priority: int = 5,
    ) -> dict[str, Any]:
        """构建标准化的调优建议"""
        return {
            "id": f"tune_{uuid.uuid4().hex[:12]}",
            "run_id": run_id,
            "category": category,
            "severity": severity,
            "title": title,
            "description": description,
            "current_value": current_value,
            "suggested_value": suggested_value,
            "expected_impact": expected_impact,
            "target_node_id": target_node_id,
            "target_param": target_param,
            "priority": priority,
            "source": "auto",
            "status": "pending",
        }

    def _threshold(self, key: str) -> float:
        """获取阈值（优先从 ConfigCache，否则默认）"""
        if self._config_cache:
            try:
                return float(
                    self._config_cache.get_value(f"rag.eval.threshold.{key}", "")
                )
            except Exception:
                pass
        return DEFAULT_THRESHOLDS.get(key, 0.5)
