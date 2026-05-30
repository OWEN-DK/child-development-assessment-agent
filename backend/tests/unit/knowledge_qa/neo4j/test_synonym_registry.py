"""同义词注册表测试。"""

import pytest
from src.core.knowledge_qa.neo4j.synonym_registry import SynonymRegistry, SynonymGroup


class TestSynonymRegistry:
    """SynonymRegistry 核心功能。"""

    def test_register_and_resolve(self):
        reg = SynonymRegistry()
        reg.register("有氧运动", ["跑步", "慢跑", "有氧"], entity_type="Solution")
        assert reg.resolve("有氧运动") == "有氧运动"
        assert reg.resolve("跑步") == "有氧运动"
        assert reg.resolve("慢跑") == "有氧运动"
        assert reg.resolve("有氧") == "有氧运动"

    def test_resolve_unknown_returns_original(self):
        reg = SynonymRegistry()
        assert reg.resolve("未知名称") == "未知名称"

    def test_get_aliases(self):
        reg = SynonymRegistry()
        reg.register("ADHD", ["注意力缺陷", "多动症"], entity_type="Problem")
        aliases = reg.get_aliases("ADHD")
        assert "注意力缺陷" in aliases
        assert "多动症" in aliases

    def test_get_aliases_unknown_returns_empty(self):
        reg = SynonymRegistry()
        assert reg.get_aliases("不存在") == []

    def test_multiple_groups(self):
        reg = SynonymRegistry()
        reg.register("A", ["a1", "a2"])
        reg.register("B", ["b1", "b2"])
        assert reg.resolve("a1") == "A"
        assert reg.resolve("b1") == "B"

    def test_canonical_maps_to_itself(self):
        reg = SynonymRegistry()
        reg.register("标准名", ["别名1"])
        assert reg.resolve("标准名") == "标准名"
