"""RBAC 权限检查引擎

角色→权限映射，支持通配符（* = 全部权限）。
超管直接返回 True。
"""
from src.core.auth.defaults import PERMISSION_SET


class RBACEngine:
    """权限检查引擎"""

    @staticmethod
    def check_permission(
        user_roles: list[str],
        required_permission: str,
        is_superadmin: bool = False,
    ) -> bool:
        """检查用户是否拥有指定权限

        Args:
            user_roles: 用户的权限列表（来自 roles.permissions JSON）
            required_permission: 需要的权限（如 "kb:write"）
            is_superadmin: 是否超管

        Returns:
            True 表示有权限
        """
        # 超管直接通过
        if is_superadmin:
            return True

        # 通配符检查
        if "*" in user_roles:
            return True

        # 精确匹配
        if required_permission in user_roles:
            return True

        # 分类通配符检查（如 "kb:*" 匹配 "kb:read", "kb:write" 等）
        category = required_permission.split(":")[0] if ":" in required_permission else None
        if category and f"{category}:*" in user_roles:
            return True

        return False

    @staticmethod
    def check_any_permission(
        user_roles: list[str],
        required_permissions: list[str],
        is_superadmin: bool = False,
    ) -> bool:
        """检查用户是否拥有任一指定权限

        Args:
            user_roles: 用户的权限列表
            required_permissions: 需要的权限列表（OR 关系）
            is_superadmin: 是否超管

        Returns:
            True 表示有至少一个权限
        """
        return any(
            RBACEngine.check_permission(user_roles, perm, is_superadmin)
            for perm in required_permissions
        )

    @staticmethod
    def check_all_permissions(
        user_roles: list[str],
        required_permissions: list[str],
        is_superadmin: bool = False,
    ) -> bool:
        """检查用户是否拥有全部指定权限

        Args:
            user_roles: 用户的权限列表
            required_permissions: 需要的权限列表（AND 关系）
            is_superadmin: 是否超管

        Returns:
            True 表示拥有全部权限
        """
        return all(
            RBACEngine.check_permission(user_roles, perm, is_superadmin)
            for perm in required_permissions
        )

    @staticmethod
    def get_user_permissions(role_permission_lists: list[list[str]]) -> list[str]:
        """合并多个角色的权限列表

        Args:
            role_permission_lists: 多个角色的权限列表

        Returns:
            去重后的权限列表
        """
        all_permissions = set()
        for perms in role_permission_lists:
            all_permissions.update(perms)
        return list(all_permissions)

    @staticmethod
    def filter_by_visibility(
        resources: list,
        user_roles: list[str],
        is_superadmin: bool = False,
        visibility_field: str = "visibility",
        visible_roles_field: str = "visible_roles",
        owner_field: str = "owner_id",
        user_id: str | None = None,
    ) -> list:
        """根据可见性过滤资源列表

        Args:
            resources: 资源列表
            user_roles: 用户角色列表
            is_superadmin: 是否超管
            visibility_field: 可见性字段名
            visible_roles_field: 可见角色字段名
            owner_field: 所有者字段名
            user_id: 用户 ID

        Returns:
            过滤后的资源列表
        """
        if is_superadmin:
            return resources

        filtered = []
        for resource in resources:
            visibility = getattr(resource, visibility_field, "public")

            if visibility == "public":
                filtered.append(resource)
            elif visibility == "private":
                owner = getattr(resource, owner_field, None)
                if owner == user_id:
                    filtered.append(resource)
            elif visibility == "role_scoped":
                visible_roles = getattr(resource, visible_roles_field, []) or []
                if any(role in visible_roles for role in user_roles):
                    filtered.append(resource)

        return filtered

    @staticmethod
    def get_all_permissions() -> dict[str, str]:
        """获取所有可用权限定义"""
        return PERMISSION_SET.copy()
