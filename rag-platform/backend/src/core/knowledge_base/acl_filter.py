"""ACL 过滤器构建器

根据用户角色构建后端特定的文档级 ACL 过滤条件。
三种后端语法不同：Chroma where / ES filter / Milvus expr。
"""
from abc import ABC, abstractmethod
from typing import Any


class ACLFilterBuilder(ABC):
    """ACL 过滤器构建器基类"""

    @abstractmethod
    def build_filter(self, user_roles: list[str]) -> dict[str, Any]:
        """构建 ACL 过滤条件

        Args:
            user_roles: 用户角色列表（空列表 = God Mode，不过滤）

        Returns:
            后端特定的过滤条件
        """


class ChromaACLFilterBuilder(ACLFilterBuilder):
    """Chroma ACL 过滤器

    使用 $or 语法：
    - doc_acl 包含用户角色之一
    - doc_acl 为空数组（inherit 文档，对所有人可见）
    """

    def build_filter(self, user_roles: list[str]) -> dict[str, Any]:
        # God Mode：不过滤
        if not user_roles:
            return {}

        conditions = []
        # inherit 文档（空 ACL）
        conditions.append({"doc_acl": {"$size": 0}})
        # 角色匹配
        for role in user_roles:
            conditions.append({"doc_acl": {"$contains": role}})

        return {"$or": conditions}


class ESACLFilterBuilder(ACLFilterBuilder):
    """Elasticsearch ACL 过滤器

    使用 bool.filter 语法：
    - doc_acl 包含用户角色之一
    - doc_acl 不存在（inherit 文档）
    """

    def build_filter(self, user_roles: list[str]) -> dict[str, Any]:
        # God Mode：不过滤
        if not user_roles:
            return {}

        return {
            "bool": {
                "should": [
                    {"terms": {"doc_acl": user_roles}},
                    {"bool": {"must_not": [{"exists": {"field": "doc_acl"}}]}},
                ],
                "minimum_should_match": 1,
            }
        }


class MilvusACLFilterBuilder(ACLFilterBuilder):
    """Milvus ACL 过滤器

    使用 expr 语法：
    - doc_acl 包含用户角色之一
    - doc_acl 为空或 null（inherit 文档）
    """

    def build_filter(self, user_roles: list[str]) -> dict[str, Any]:
        # God Mode：不过滤
        if not user_roles:
            return {}

        role_conditions = " or ".join(
            [f'array_contains(doc_acl, "{role}")' for role in user_roles]
        )
        expr = f"({role_conditions}) or doc_acl == null or length(doc_acl) == 0"
        return {"expr": expr}


def get_acl_filter_builder(backend_type: str) -> ACLFilterBuilder:
    """根据后端类型获取 ACL 过滤器构建器"""
    builders = {
        "chroma": ChromaACLFilterBuilder,
        "elasticsearch": ESACLFilterBuilder,
        "milvus": MilvusACLFilterBuilder,
    }
    builder_class = builders.get(backend_type)
    if not builder_class:
        raise ValueError(f"不支持的向量后端: {backend_type}")
    return builder_class()
