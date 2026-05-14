"""RBAC 权限引擎单元测试"""
import pytest

from src.core.auth.rbac import RBACEngine


class TestRBACEngine:
    """权限检查测试"""

    def test_superadmin_always_pass(self):
        """超管直接通过"""
        assert RBACEngine.check_permission([], "kb:write", is_superadmin=True) is True

    def test_wildcard_pass(self):
        """通配符 * 通过所有权限"""
        assert RBACEngine.check_permission(["*"], "kb:write") is True

    def test_exact_match(self):
        """精确匹配"""
        assert RBACEngine.check_permission(["kb:read", "kb:write"], "kb:write") is True

    def test_exact_mismatch(self):
        """精确不匹配"""
        assert RBACEngine.check_permission(["kb:read"], "kb:write") is False

    def test_category_wildcard(self):
        """分类通配符 kb:* 匹配 kb:read"""
        assert RBACEngine.check_permission(["kb:*"], "kb:read") is True
        assert RBACEngine.check_permission(["kb:*"], "kb:write") is True

    def test_category_wildcard_no_cross(self):
        """分类通配符不跨类别"""
        assert RBACEngine.check_permission(["kb:*"], "pipeline:read") is False

    def test_check_any_permission(self):
        """任一权限通过"""
        assert RBACEngine.check_any_permission(
            ["kb:read"], ["kb:write", "kb:read"]
        ) is True

    def test_check_any_permission_none(self):
        """无一权限通过"""
        assert RBACEngine.check_any_permission(
            ["kb:read"], ["kb:write", "kb:delete"]
        ) is False

    def test_check_all_permissions(self):
        """全部权限通过"""
        assert RBACEngine.check_all_permissions(
            ["kb:read", "kb:write"], ["kb:read", "kb:write"]
        ) is True

    def test_check_all_permissions_partial(self):
        """部分权限不通过"""
        assert RBACEngine.check_all_permissions(
            ["kb:read"], ["kb:read", "kb:write"]
        ) is False

    def test_merge_multi_role_permissions(self):
        """多角色权限合并"""
        perms = RBACEngine.get_user_permissions([
            ["kb:read", "kb:write"],
            ["pipeline:read"],
        ])
        assert set(perms) == {"kb:read", "kb:write", "pipeline:read"}

    def test_merge_dedup_permissions(self):
        """多角色权限去重"""
        perms = RBACEngine.get_user_permissions([
            ["kb:read", "kb:write"],
            ["kb:read", "pipeline:read"],
        ])
        assert perms.count("kb:read") == 1

    def test_filter_by_visibility_public(self):
        """公开资源对所有人可见"""
        from dataclasses import dataclass

        @dataclass
        class Resource:
            visibility: str
            visible_roles: list
            owner_id: str

        resources = [
            Resource("public", [], "owner_1"),
            Resource("public", [], "owner_2"),
        ]
        filtered = RBACEngine.filter_by_visibility(
            resources, ["viewer"], user_id="user_1"
        )
        assert len(filtered) == 2

    def test_filter_by_visibility_private(self):
        """私有资源仅创建者可见"""
        from dataclasses import dataclass

        @dataclass
        class Resource:
            visibility: str
            visible_roles: list
            owner_id: str

        resources = [
            Resource("private", [], "user_1"),
            Resource("private", [], "user_2"),
        ]
        filtered = RBACEngine.filter_by_visibility(
            resources, ["viewer"], user_id="user_1"
        )
        assert len(filtered) == 1
        assert filtered[0].owner_id == "user_1"

    def test_filter_by_visibility_role_scoped(self):
        """角色限定资源"""
        from dataclasses import dataclass

        @dataclass
        class Resource:
            visibility: str
            visible_roles: list
            owner_id: str

        resources = [
            Resource("role_scoped", ["admin", "editor"], "owner_1"),
            Resource("role_scoped", ["admin"], "owner_2"),
        ]
        # editor 只能看到第一个
        filtered = RBACEngine.filter_by_visibility(
            resources, ["editor"], user_id="user_1"
        )
        assert len(filtered) == 1

    def test_filter_superadmin_sees_all(self):
        """超管看到所有资源"""
        from dataclasses import dataclass

        @dataclass
        class Resource:
            visibility: str
            visible_roles: list
            owner_id: str

        resources = [
            Resource("public", [], "owner_1"),
            Resource("private", [], "owner_2"),
            Resource("role_scoped", ["admin"], "owner_3"),
        ]
        filtered = RBACEngine.filter_by_visibility(
            resources, [], is_superadmin=True, user_id="sa_1"
        )
        assert len(filtered) == 3
