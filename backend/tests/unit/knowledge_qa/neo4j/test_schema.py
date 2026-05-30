"""Neo4j Schema 常量测试。"""

from src.core.knowledge_qa.neo4j import schema


class TestNodeTypes:
    """节点类型常量。"""

    def test_all_node_types_defined(self):
        expected = [
            "Book", "Problem", "RootCause", "Solution", "Exercise",
            "Prescription", "BrainRegion", "ChildProfile", "Risk",
            "Chapter", "AutoEntity", "AutoCommunity",
        ]
        for name in expected:
            assert hasattr(schema, f"NODE_{name.upper()}")

    def test_node_type_values(self):
        assert schema.NODE_BOOK == "Book"
        assert schema.NODE_PROBLEM == "Problem"
        assert schema.NODE_EXERCISE == "Exercise"
        assert schema.NODE_AUTOENTITY == "AutoEntity"


class TestRelationTypes:
    """关系类型常量。"""

    def test_all_rel_types_defined(self):
        expected = [
            "BELONGS_TO", "CAUSES", "SOLVES", "PRESCRIBES",
            "TARGETS", "AFFECTS", "REQUIRES", "CONTAINS_ENTITY", "RELATES_TO",
        ]
        for name in expected:
            assert hasattr(schema, f"REL_{name}")

    def test_cross_book_types(self):
        assert schema.CROSS_BOOK_CONSENSUS == "CONSENSUS"
        assert schema.CROSS_BOOK_COMPLEMENTS == "COMPLEMENTS"
        assert schema.CROSS_BOOK_CONFLICTS == "CONFLICTS"
