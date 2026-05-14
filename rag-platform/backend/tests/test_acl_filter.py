"""ACL 过滤器单元测试"""
import pytest

from src.core.knowledge_base.acl_filter import (
    ChromaACLFilterBuilder,
    ESACLFilterBuilder,
    MilvusACLFilterBuilder,
    get_acl_filter_builder,
)


class TestChromaACLFilterBuilder:
    """Chroma ACL 过滤器测试"""

    def test_god_mode_empty_filter(self):
        """God Mode（空角色列表）返回空条件"""
        builder = ChromaACLFilterBuilder()
        result = builder.build_filter([])
        assert result == {}

    def test_single_role(self):
        """单角色过滤"""
        builder = ChromaACLFilterBuilder()
        result = builder.build_filter(["admin"])

        assert "$or" in result
        conditions = result["$or"]
        # 应包含 inherit 兜底 + 角色匹配
        assert len(conditions) >= 2

    def test_multiple_roles(self):
        """多角色过滤"""
        builder = ChromaACLFilterBuilder()
        result = builder.build_filter(["admin", "editor"])

        assert "$or" in result
        conditions = result["$or"]
        # inherit + admin + editor
        assert len(conditions) == 3

    def test_inherit_fallback(self):
        """包含 inherit 文档兜底（空 ACL）"""
        builder = ChromaACLFilterBuilder()
        result = builder.build_filter(["viewer"])

        conditions = result["$or"]
        # 检查是否有 $size: 0 条件
        has_inherit = any(
            c.get("doc_acl", {}).get("$size") == 0
            for c in conditions
        )
        assert has_inherit


class TestESACLFilterBuilder:
    """Elasticsearch ACL 过滤器测试"""

    def test_god_mode_empty_filter(self):
        """God Mode 返回空条件"""
        builder = ESACLFilterBuilder()
        result = builder.build_filter([])
        assert result == {}

    def test_single_role(self):
        """单角色过滤"""
        builder = ESACLFilterBuilder()
        result = builder.build_filter(["admin"])

        assert "bool" in result
        assert "should" in result["bool"]
        assert result["bool"]["minimum_should_match"] == 1

    def test_terms_match(self):
        """包含 terms 匹配"""
        builder = ESACLFilterBuilder()
        result = builder.build_filter(["admin", "editor"])

        should = result["bool"]["should"]
        has_terms = any("terms" in s for s in should)
        assert has_terms

    def test_inherit_fallback(self):
        """包含 inherit 文档兜底（must_not exists）"""
        builder = ESACLFilterBuilder()
        result = builder.build_filter(["viewer"])

        should = result["bool"]["should"]
        has_inherit = any(
            "bool" in s and "must_not" in s.get("bool", {})
            for s in should
        )
        assert has_inherit


class TestMilvusACLFilterBuilder:
    """Milvus ACL 过滤器测试"""

    def test_god_mode_empty_filter(self):
        """God Mode 返回空条件"""
        builder = MilvusACLFilterBuilder()
        result = builder.build_filter([])
        assert result == {}

    def test_single_role(self):
        """单角色过滤"""
        builder = MilvusACLFilterBuilder()
        result = builder.build_filter(["admin"])

        assert "expr" in result
        assert "array_contains" in result["expr"]
        assert "admin" in result["expr"]

    def test_multiple_roles(self):
        """多角色过滤"""
        builder = MilvusACLFilterBuilder()
        result = builder.build_filter(["admin", "editor"])

        assert "expr" in result
        assert "admin" in result["expr"]
        assert "editor" in result["expr"]

    def test_inherit_fallback(self):
        """包含 inherit 文档兜底"""
        builder = MilvusACLFilterBuilder()
        result = builder.build_filter(["viewer"])

        assert "doc_acl == null" in result["expr"]
        assert "length(doc_acl) == 0" in result["expr"]


class TestGetACLFilterBuilder:
    """工厂函数测试"""

    def test_chroma(self):
        builder = get_acl_filter_builder("chroma")
        assert isinstance(builder, ChromaACLFilterBuilder)

    def test_elasticsearch(self):
        builder = get_acl_filter_builder("elasticsearch")
        assert isinstance(builder, ESACLFilterBuilder)

    def test_milvus(self):
        builder = get_acl_filter_builder("milvus")
        assert isinstance(builder, MilvusACLFilterBuilder)

    def test_unsupported_backend(self):
        with pytest.raises(ValueError, match="不支持的向量后端"):
            get_acl_filter_builder("unsupported")
