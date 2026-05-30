"""MD Diff 分析器测试。"""

import pytest
from src.core.knowledge_qa.neo4j.md_diff_analyzer import (
    MDDiffAnalyzer, DiffResult, EntityDiff, ChangeType,
)


class TestMDDiffAnalyzer:
    """MDDiffAnalyzer.analyze() 测试。"""

    def setup_method(self):
        self.analyzer = MDDiffAnalyzer()

    def test_added_entities(self):
        old = {"version": 1, "book_id": "b1", "entities": []}
        new = {
            "version": 2, "book_id": "b1",
            "entities": [{"entity_type": "Problem", "name": "ADHD", "severity": "high"}],
        }
        result = self.analyzer.analyze(old, new)
        assert len(result.entity_diffs) == 1
        assert result.entity_diffs[0].change_type == ChangeType.ADDED
        assert result.entity_diffs[0].new_data["name"] == "ADHD"

    def test_deleted_entities(self):
        old = {
            "version": 1, "book_id": "b1",
            "entities": [{"entity_type": "Problem", "name": "ADHD"}],
        }
        new = {"version": 2, "book_id": "b1", "entities": []}
        result = self.analyzer.analyze(old, new)
        assert len(result.entity_diffs) == 1
        assert result.entity_diffs[0].change_type == ChangeType.DELETED

    def test_modified_entities(self):
        old = {
            "version": 1, "book_id": "b1",
            "entities": [{"entity_type": "Problem", "name": "ADHD", "severity": "low"}],
        }
        new = {
            "version": 2, "book_id": "b1",
            "entities": [{"entity_type": "Problem", "name": "ADHD", "severity": "high"}],
        }
        result = self.analyzer.analyze(old, new)
        assert len(result.entity_diffs) == 1
        assert result.entity_diffs[0].change_type == ChangeType.MODIFIED
        assert "severity" in result.entity_diffs[0].changed_fields

    def test_unchanged_entities(self):
        data = {"entity_type": "Problem", "name": "ADHD", "severity": "high"}
        old = {"version": 1, "book_id": "b1", "entities": [data.copy()]}
        new = {"version": 2, "book_id": "b1", "entities": [data.copy()]}
        result = self.analyzer.analyze(old, new)
        assert len(result.entity_diffs) == 1
        assert result.entity_diffs[0].change_type == ChangeType.UNCHANGED

    def test_mixed_changes(self):
        old = {
            "version": 1, "book_id": "b1",
            "entities": [
                {"entity_type": "Problem", "name": "ADHD"},
                {"entity_type": "Solution", "name": "有氧运动"},
            ],
        }
        new = {
            "version": 2, "book_id": "b1",
            "entities": [
                {"entity_type": "Problem", "name": "ADHD", "severity": "high"},
                {"entity_type": "Solution", "name": "瑜伽"},
            ],
        }
        result = self.analyzer.analyze(old, new)
        summary = result.summary
        assert summary["modified"] == 1  # ADHD modified
        assert summary["deleted"] == 1   # 有氧运动 deleted
        assert summary["added"] == 1     # 瑜伽 added

    def test_summary_counts(self):
        old = {"version": 1, "book_id": "b1", "entities": [], "claims": [], "prescriptions": []}
        new = {"version": 2, "book_id": "b1", "entities": [], "claims": [], "prescriptions": []}
        result = self.analyzer.analyze(old, new)
        assert result.summary == {"added": 0, "modified": 0, "deleted": 0, "unchanged": 0}

    def test_claims_and_prescriptions(self):
        old = {"version": 1, "book_id": "b1", "claims": [], "prescriptions": [
            {"exercise": "跑步", "frequency": "每天"}
        ]}
        new = {"version": 2, "book_id": "b1", "claims": [], "prescriptions": [
            {"exercise": "跑步", "frequency": "每周3次"}
        ]}
        result = self.analyzer.analyze(old, new)
        assert len(result.prescription_diffs) == 1
        assert result.prescription_diffs[0].change_type == ChangeType.MODIFIED


class TestEntityDiff:
    """EntityDiff 数据类。"""

    def test_entity_key_generation(self):
        assert MDDiffAnalyzer._key({"entity_type": "Problem", "name": "ADHD"}) == "Problem::ADHD"
        assert MDDiffAnalyzer._key({"type": "Solution", "exercise": "跑步"}) == "Solution::跑步"

    def test_find_changed_fields(self):
        old = {"name": "A", "severity": "low"}
        new = {"name": "A", "severity": "high", "description": "新增"}
        changed = MDDiffAnalyzer._find_changed_fields(old, new)
        assert "severity" in changed
        assert "description" in changed
        assert "name" not in changed
