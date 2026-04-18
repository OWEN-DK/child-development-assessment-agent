"""认证辅助工具模块

统一用户信息获取逻辑，消除重复的 current_user 判断代码。
"""

from typing import Any

from src.utils.exceptions import UnauthorizedException


def get_user_id(current_user: Any | None) -> str:
    """获取当前用户 ID

    使用方式：
        user_id = get_user_id(current_user)

    Args:
        current_user: 当前用户对象（可能为 None）

    Returns:
        用户 ID，未登录返回 "system"
    """
    if current_user is None:
        return "system"
    return getattr(current_user, "id", None) or getattr(current_user, "username", "system")


def get_username(current_user: Any | None) -> str:
    """获取当前用户名

    Args:
        current_user: 当前用户对象

    Returns:
        用户名，未登录返回 "system"
    """
    if current_user is None:
        return "system"
    return getattr(current_user, "username", "system")


def is_authenticated(current_user: Any | None) -> bool:
    """检查用户是否已认证

    Args:
        current_user: 当前用户对象

    Returns:
        是否已认证
    """
    return current_user is not None


def require_auth(current_user: Any | None) -> None:
    """要求用户已认证，否则抛出异常

    使用方式：
        require_auth(current_user)

    Raises:
        UnauthorizedException: 用户未认证
    """
    if current_user is None:
        raise UnauthorizedException()
