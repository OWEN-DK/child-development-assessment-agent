"""图质量审计单元测试

测试 audit_graph_quality 和 generate_quality_report。
"""

import pytest

from src.core.knowledge_qa.d2g.master_graph import MasterGraph
from src.core.knowledge_qa.d2g.graph_quality import audit_graph_quality, generate_quality_report
from src.core.knowledge_qa.d2g.models import (
    EntityType,
    RelationType,
    ExtractedEntity,
    ExtractedRelationship,
    QualityThresholds,
)


@pytest.fixture
def good_graph():
    """质量良好的图"""
    mg = MasterGraph(book_id="b", book_title="t")
    entities = [
        ExtractedEntity(name=f"E{i}", entity_type=EntityType.Problem,
                       description=f"这是实体{i}的详细描述文本内容用于测试验证场景", source_para_ids=[i])
        for i in range(1, 11)
    ]
    for e in entities:
        mg.add_entity(e, "ch01")
    # 添加关系使图连通
    for i in range(1, 10):
        mg.add_relationship(ExtractedRelationship(
            source=f"E{i}", target=f"E{i+1}",
            relation_type=RelationType.RELATES_TO,
            evidence="证据",
            source_para_ids=[i],
        ), "ch01")
    mg.chapter_para_count["ch01"] = 10
    return mg


@pytest.fixture
def poor_graph():
    """质量较差的图（高孤立率、碎片化）"""
    mg = MasterGraph(book_id="b", book_title="t")
    # 5 个孤立实体
    for i in range(1, 6):
        mg.add_entity(ExtractedEntity(
            name=f"孤立{i}", entity_type=EntityType.KeyInsight,
            description=f"这是实体{i}的详细描述文本内容用于测试验证场景", source_para_ids=[i],
        ), "ch01")
    # 2 个有关系的实体（形成小连通分量）
    mg.add_entity(ExtractedEntity(
        name="A", entity_type=EntityType.Problem,
        description="问题A的详细描述文本内容用于测试验证场景验证", source_para_ids=[6],
    ), "ch01")
    mg.add_entity(ExtractedEntity(
        name="B", entity_type=EntityType.Solution,
        description="方案B的详细描述文本内容用于测试验证场景验证", source_para_ids=[7],
    ), "ch01")
    mg.add_relationship(ExtractedRelationship(
        source="B", target="A",
        relation_type=RelationType.THERAPEUTIC_TREATS,
        evidence="证据", source_para_ids=[7],
    ), "ch01")
    mg.chapter_para_count["ch01"] = 10
    return mg


# ──────────────────────────────────────────────────────────────
# audit_graph_quality 测试
# ──────────────────────────────────────────────────────────────


class TestAuditGraphQuality:
    """audit_graph_quality 函数测试"""

    def test_good_graph_no_issues(self, good_graph):
        """质量良好的图应无问题"""
        metrics, issues = audit_graph_quality(good_graph)
        assert len(issues) == 0
        assert metrics.total_entities == 10
        assert metrics.total_relationships == 9

    def test_poor_graph_has_issues(self, poor_graph):
        """质量差的图应发现问题"""
        metrics, issues = audit_graph_quality(poor_graph)
        assert len(issues) > 0
        # 应发现孤立实体率过高
        orphan_issues = [i for i in issues if "孤立" in i]
        assert len(orphan_issues) > 0

    def test_custom_thresholds(self, good_graph):
        """自定义阈值应影响检查结果"""
        strict = QualityThresholds(
            min_avg_degree=100.0,  # 不可能达到
            max_orphan_rate=0.0,
        )
        metrics, issues = audit_graph_quality(good_graph, thresholds=strict)
        assert len(issues) >= 1

    def test_empty_graph(self):
        """空图应安全处理"""
        mg = MasterGraph(book_id="b", book_title="t")
        metrics, issues = audit_graph_quality(mg)
        assert metrics.total_entities == 0
        # 空图不应报错（除 0 保护）


# ──────────────────────────────────────────────────────────────
# generate_quality_report 测试
# ──────────────────────────────────────────────────────────────


class TestGenerateQualityReport:
    """generate_quality_report 函数测试"""

    def test_report_with_issues(self, poor_graph):
        """有问题时应生成问题列表"""
        metrics, issues = audit_graph_quality(poor_graph)
        report = generate_quality_report(metrics, issues)
        assert "# 图质量报告" in report
        assert "总实体数" in report
        assert "## 问题" in report

    def test_report_no_issues(self, good_graph):
        """无问题时应显示达标"""
        metrics, issues = audit_graph_quality(good_graph)
        report = generate_quality_report(metrics, issues)
        assert "所有指标达标" in report

    def test_report_chapter_coverage(self, good_graph):
        """报告应包含章节覆盖率"""
        metrics, issues = audit_graph_quality(good_graph)
        report = generate_quality_report(metrics, issues)
        assert "章节覆盖率" in report
        assert "ch01" in report
