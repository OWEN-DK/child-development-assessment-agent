"""邀请链接生成、验证、过期处理

邀请 token 包含 tenant_id、email、roles，24 小时过期。
"""
from datetime import datetime, timedelta
from typing import Any

import jwt

from src.core.auth.exceptions import InvitationExpiredError, InvitationInvalidError

INVITATION_EXPIRE_HOURS = 24


class InvitationService:
    """邀请令牌服务"""

    def __init__(self, secret_key: str):
        self._secret = secret_key

    def generate_token(
        self, tenant_id: str, email: str, roles: list[str]
    ) -> str:
        """生成邀请令牌

        Args:
            tenant_id: 租户 ID
            email: 被邀请邮箱
            roles: 角色列表

        Returns:
            JWT 邀请令牌
        """
        now = datetime.utcnow()
        payload = {
            "tenant_id": tenant_id,
            "email": email,
            "roles": roles,
            "iat": now,
            "exp": now + timedelta(hours=INVITATION_EXPIRE_HOURS),
            "type": "invitation",
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def verify(self, token: str) -> dict[str, Any]:
        """验证邀请令牌

        Args:
            token: JWT 邀请令牌

        Returns:
            payload 字典（含 tenant_id, email, roles）

        Raises:
            InvitationExpiredError: 邀请已过期
            InvitationInvalidError: 邀请无效
        """
        try:
            payload = jwt.decode(token, self._secret, algorithms=["HS256"])
            if payload.get("type") != "invitation":
                raise InvitationInvalidError(message="非邀请令牌")
            return payload
        except jwt.ExpiredSignatureError:
            raise InvitationExpiredError(message="邀请链接已过期，请联系管理员重新发送")
        except jwt.InvalidTokenError as e:
            raise InvitationInvalidError(message=f"无效邀请链接: {e}")
