"""Phase 7 调优引擎单元测试"""
import pytest
from src.service.rag_eval.tuning.conflict_detector import ConflictDetector
from src.service.rag_eval.tuning.advisor import TuningAdvisor


# ═══ 冲突检测器 ═══

class TestConflictDetector:

    def test_direct_conflict_same_param(self):
        """同节点同参数不同建议值 — 直接冲突"""
        detector = ConflictDetector()
        s1 = {
            "id": "tune_001",
            "title": "增大 top_k 到 20",
            "target_node_id": "bm25_search",
            "target_param": "top_k",
            "suggested_value": "20",
        }
        s2 = {
            "id": "tune_002",
            "title": "减少 top_k 到 5",
            "target_node_id": "bm25_search",
            "target_param": "top_k",
            "suggested_value": "5",
        }
        result = detector.detect([s1, s2])
        # result 是更新后的建议列表
        r1 = next(r for r in result if r["id"] == "tune_001")
        r2 = next(r for r in result if r["id"] == "tune_002")
        assert "tune_002" in r1["conflict_with"]
        assert "tune_001" in r2["conflict_with"]

    def test_indirect_conflict_weight_constraint(self):
        """同节点 vector_weight/keyword_weight 约束冲突"""
        detector = ConflictDetector()
        s1 = {
            "id": "tune_003",
            "title": "增大向量权重",
            "target_node_id": "hybrid_search",
            "target_param": "vector_weight",
            "suggested_value": "0.9",
        }
        s2 = {
            "id": "tune_004",
            "title": "增大关键词权重",
            "target_node_id": "hybrid_search",
            "target_param": "keyword_weight",
            "suggested_value": "0.5",
        }
        result = detector.detect([s1, s2])
        r1 = next(r for r in result if r["id"] == "tune_003")
        assert r1["conflict_with"] is not None
        assert "tune_004" in r1["conflict_with"]

    def test_no_conflict_different_nodes(self):
        """不同节点 — 不冲突"""
        detector = ConflictDetector()
        s1 = {
            "id": "tune_005",
            "title": "增大 BM25 top_k",
            "target_node_id": "bm25_search",
            "target_param": "top_k",
            "suggested_value": "20",
        }
        s2 = {
            "id": "tune_006",
            "title": "启用重排序",
            "target_node_id": "rerank",
            "target_param": "enabled",
            "suggested_value": "true",
        }
        result = detector.detect([s1, s2])
        r1 = next(r for r in result if r["id"] == "tune_005")
        r2 = next(r for r in result if r["id"] == "tune_006")
        assert r1["conflict_with"] is None
        assert r2["conflict_with"] is None

    def test_empty_suggestions(self):
        detector = ConflictDetector()
        result = detector.detect([])
        assert result == []


# ═══ 调优建议器 ═══

class TestTuningAdvisor:

    @pytest.mark.asyncio
    async def test_low_recall_triggers_suggestion(self):
        advisor = TuningAdvisor()
        l1 = {"avg_recall": 0.3, "avg_precision": 0.6, "avg_f1": 0.4}
        suggestions = await advisor.generate_retrieval_suggestions(
            run_id="run_001",
            l1_metrics=l1,
            domain_contributions=None,
        )
        assert len(suggestions) >= 1
        assert any("召回" in s["title"] for s in suggestions)

    @pytest.mark.asyncio
    async def test_good_metrics_no_suggestions(self):
        advisor = TuningAdvisor()
        l1 = {"avg_recall": 0.85, "avg_precision": 0.82, "avg_f1": 0.83}
        suggestions = await advisor.generate_retrieval_suggestions(
            run_id="run_001",
            l1_metrics=l1,
            domain_contributions=None,
        )
        assert len(suggestions) == 0

    @pytest.mark.asyncio
    async def test_cross_domain_imbalance_suggestion(self):
        advisor = TuningAdvisor()
        cross = {
            "domain_activation_accuracy": 0.6,
            "e2e_latency": {"p95_ms": 6000},
        }
        dc = [{
            "domain_id": "pharmacy",
            "domain_name": "药学",
            "contribution_score": 0.2,
        }]
        suggestions = await advisor.generate_cross_domain_suggestions(
            run_id="run_001",
            cross_domain_metrics=cross,
            domain_contributions=dc,
        )
        assert len(suggestions) >= 1
        assert any("药学" in s["title"] for s in suggestions)

    @pytest.mark.asyncio
    async def test_latency_bottleneck_triggers(self):
        advisor = TuningAdvisor()
        cross = {
            "domain_activation_accuracy": 0.9,
            "conflict_detection_rate": 0.8,
            "e2e_latency": {"p95_ms": 8000},
        }
        suggestions = await advisor.generate_cross_domain_suggestions(
            run_id="run_001",
            cross_domain_metrics=cross,
            domain_contributions=None,
        )
        assert any("延迟" in s["title"] for s in suggestions)

    @pytest.mark.asyncio
    async def test_good_cross_domain_no_suggestions(self):
        advisor = TuningAdvisor()
        cross = {
            "domain_activation_accuracy": 0.9,
            "conflict_detection_rate": 0.9,
            "e2e_latency": {"p95_ms": 1000},
        }
        suggestions = await advisor.generate_cross_domain_suggestions(
            run_id="run_001",
            cross_domain_metrics=cross,
            domain_contributions=None,
        )
        assert len(suggestions) == 0

    def test_make_suggestion_has_all_fields(self):
        advisor = TuningAdvisor()
        s = advisor._make_suggestion(
            run_id="run_x",
            category="retrieval",
            severity="warning",
            title="测试建议",
            description="测试描述",
            current_value="top_k=5",
            suggested_value="top_k=10",
            expected_impact="+0.15",
            target_node_id="bm25_search",
            target_param="top_k",
        )
        assert s["id"].startswith("tune_")
        assert s["target_node_id"] == "bm25_search"
        assert s["target_param"] == "top_k"
        assert s["status"] == "pending"
