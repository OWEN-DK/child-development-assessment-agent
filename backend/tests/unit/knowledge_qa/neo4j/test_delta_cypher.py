"""Delta Cypher 生成器测试。"""

import pytest
from src.core.knowledge_qa.neo4j.delta_cypher import generate_delta_cypher
from src.core.knowledge_qa.neo4j.md_diff_analyzer import (
    DiffResult, EntityDiff, ChangeType,
)


class TestGenerateDeltaCypher:
    """generate_delta_cypher() 测试。"""

    def test_added_entity_generates_merge(self):
        diff = DiffResult(
            old_version=1, new_version=2, book_id="b1",
            entity_diffs=[
                EntityDiff(
                    entity_key="Problem::ADHD",
                    change_type=ChangeType.ADDED,
                    new_data={"entity_type": "Problem", "name": "ADHD", "severity": "high"},
                )
            ],
        )
        stmts = generate_delta_cypher(diff)
        assert len(stmts) == 1
        assert "MERGE" in stmts[0]["query"]
        assert stmts[0]["params"]["name"] == "ADHD"
        assert stmts[0]["description"].startswith("ADD")

    def test_modified_entity_generates_set(self):
        diff = DiffResult(
            old_version=1, new_version=2, book_id="b1",
            entity_diffs=[
                EntityDiff(
                    entity_key="Problem::ADHD",
                    change_type=ChangeType.MODIFIED,
                    new_data={"entity_type": "Problem", "name": "ADHD", "severity": "high"},
                    changed_fields=["severity"],
                )
            ],
        )
        stmts = generate_delta_cypher(diff)
        assert len(stmts) == 1
        assert "SET" in stmts[0]["query"]
        assert "severity" in stmts[0]["query"]
        assert stmts[0]["description"].startswith("MODIFY")

    def test_deleted_entity_generates_soft_delete(self):
        diff = DiffResult(
            old_version=1, new_version=2, book_id="b1",
            entity_diffs=[
                EntityDiff(
                    entity_key="Problem::ADHD",
                    change_type=ChangeType.DELETED,
                    old_data={"entity_type": "Problem", "name": "ADHD"},
                )
            ],
        )
        stmts = generate_delta_cypher(diff)
        assert len(stmts) == 1
        assert "deleted" in stmts[0]["query"]
        assert stmts[0]["description"].startswith("SOFT DELETE")

    def test_unchanged_entity_no_statement(self):
        diff = DiffResult(
            old_version=1, new_version=2, book_id="b1",
            entity_diffs=[
                EntityDiff(entity_key="Problem::ADHD", change_type=ChangeType.UNCHANGED)
            ],
        )
        stmts = generate_delta_cypher(diff)
        assert len(stmts) == 0

    def test_mixed_changes(self):
        diff = DiffResult(
            old_version=1, new_version=2, book_id="b1",
            entity_diffs=[
                EntityDiff(
                    entity_key="Problem::ADHD",
                    change_type=ChangeType.ADDED,
                    new_data={"entity_type": "Problem", "name": "ADHD"},
                ),
                EntityDiff(
                    entity_key="Solution::瑜伽",
                    change_type=ChangeType.DELETED,
                    old_data={"entity_type": "Solution", "name": "瑜伽"},
                ),
            ],
        )
        stmts = generate_delta_cypher(diff)
        assert len(stmts) == 2

    def test_problem_uses_problem_label(self):
        diff = DiffResult(
            old_version=1, new_version=2, book_id="b1",
            entity_diffs=[
                EntityDiff(
                    entity_key="Problem::X",
                    change_type=ChangeType.ADDED,
                    new_data={"entity_type": "Problem", "name": "X"},
                )
            ],
        )
        stmts = generate_delta_cypher(diff)
        assert "Problem" in stmts[0]["query"]

    def test_unknown_type_uses_autoentity(self):
        diff = DiffResult(
            old_version=1, new_version=2, book_id="b1",
            entity_diffs=[
                EntityDiff(
                    entity_key="CustomType::X",
                    change_type=ChangeType.ADDED,
                    new_data={"entity_type": "CustomType", "name": "X"},
                )
            ],
        )
        stmts = generate_delta_cypher(diff)
        assert "AutoEntity" in stmts[0]["query"]
