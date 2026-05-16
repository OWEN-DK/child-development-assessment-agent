"""JWT 签发、验证、刷新

区分超管（无 tenant_id）和租户用户（有 tenant_id）。
"""
from datetime import datetime, timedelta
from typing import Any

import jwt

from src.core.auth.exceptions import AuthenticationError


# JWT 配置
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 小时
REFRESH_TOKEN_EXPIRE_DAYS = 7


class JWTService:
    """JWT 令牌服务"""

    def __init__(self, secret_key: str):
        self._secret = secret_key

    def issue_access_token(
        self,
        user_id: str,
        tenant_id: str | None,
        roles: list[str],
        is_superadmin: bool = False,
        role_slugs: list[str] | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """签发访问令牌

        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID（超管为 None）
            roles: 权限列表
            is_superadmin: 是否超管
            role_slugs: 角色标识列表（用于 KB 可见性过滤）
            extra_claims: 额外声明

        Returns:
            JWT 字符串
        """
        now = datetime.utcnow()
        payload = {
            "sub": user_id,
            "roles": roles,
            "role_slugs": role_slugs or [],
            "is_superadmin": is_superadmin,
            "iat": now,
            "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            "type": "access",
        }
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id
        if extra_claims:
            payload.update(extra_claims)

        return jwt.encode(payload, self._secret, algorithm=JWT_ALGORITHM)

    def issue_refresh_token(self, user_id: str) -> str:
        """签发刷新令牌

        Args:
            user_id: 用户 ID

        Returns:
            JWT 字符串
        """
        now = datetime.utcnow()
        payload = {
            "sub": user_id,
            "iat": now,
            "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            "type": "refresh",
        }
        return jwt.encode(payload, self._secret, algorithm=JWT_ALGORITHM)

    def decode(self, token: str) -> dict[str, Any]:
        """验证并解码令牌

        Args:
            token: JWT 字符串

        Returns:
            payload 字典

        Raises:
            AuthenticationError: 令牌无效或过期
        """
        try:
            payload = jwt.decode(token, self._secret, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationError(status_code=401, code=401, message="令牌已过期")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(status_code=401, code=401, message=f"无效令牌: {e}")

    def refresh(self, refresh_token: str) -> tuple[str, str]:
        """用刷新令牌换取新的访问令牌和刷新令牌

        Args:
            refresh_token: 刷新令牌

        Returns:
            (new_access_token, new_refresh_token)

        Raises:
            AuthenticationError: 刷新令牌无效或过期
        """
        payload = self.decode(refresh_token)
        if payload.get("type") != "refresh":
            raise AuthenticationError(status_code=401, code=401, message="非刷新令牌")

        user_id = payload["sub"]
        # 注意：刷新时无法获取原始 tenant_id 和 roles，需要从数据库查询
        # 这里返回 user_id，由调用方查询后重新签发
        raise NotImplementedError(
            "刷新令牌需要查询用户信息，请使用 refresh_with_user_info 方法"
        )

    def refresh_with_user_info(
        self,
        refresh_token: str,
        user_id: str,
        tenant_id: str | None,
        roles: list[str],
        is_superadmin: bool = False,
        role_slugs: list[str] | None = None,
    ) -> tuple[str, str]:
        """用刷新令牌换取新的访问令牌（带用户信息）

        Args:
            refresh_token: 刷新令牌
            user_id: 用户 ID
            tenant_id: 租户 ID
            roles: 权限列表
            is_superadmin: 是否超管
            role_slugs: 角色标识列表

        Returns:
            (new_access_token, new_refresh_token)
        """
        # 验证刷新令牌
        payload = self.decode(refresh_token)
        if payload.get("type") != "refresh":
            raise AuthenticationError(status_code=401, code=401, message="非刷新令牌")
        if payload.get("sub") != user_id:
            raise AuthenticationError(status_code=401, code=401, message="刷新令牌与用户不匹配")

        # 签发新令牌
        new_access = self.issue_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            roles=roles,
            is_superadmin=is_superadmin,
            role_slugs=role_slugs,
        )
        new_refresh = self.issue_refresh_token(user_id=user_id)
        return new_access, new_refresh
