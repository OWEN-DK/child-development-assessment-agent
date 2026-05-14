"""JWT 服务单元测试"""
import pytest
from datetime import datetime, timedelta

from src.core.auth.jwt_service import JWTService
from src.core.auth.exceptions import AuthenticationError


@pytest.fixture
def jwt_service():
    return JWTService(secret_key="test-secret-key-min-32-chars-long")


class TestJWTService:
    """JWT 签发、验证、刷新测试"""

    def test_issue_access_token_tenant_user(self, jwt_service):
        """租户用户 JWT 包含 tenant_id"""
        token = jwt_service.issue_access_token(
            user_id="user_001",
            tenant_id="tenant_001",
            roles=["admin", "editor"],
            is_superadmin=False,
        )
        payload = jwt_service.decode(token)

        assert payload["sub"] == "user_001"
        assert payload["tenant_id"] == "tenant_001"
        assert payload["roles"] == ["admin", "editor"]
        assert payload["is_superadmin"] is False

    def test_issue_access_token_superadmin(self, jwt_service):
        """超管 JWT 无 tenant_id"""
        token = jwt_service.issue_access_token(
            user_id="sa_001",
            tenant_id=None,
            roles=[],
            is_superadmin=True,
        )
        payload = jwt_service.decode(token)

        assert payload["sub"] == "sa_001"
        assert "tenant_id" not in payload
        assert payload["is_superadmin"] is True

    def test_issue_refresh_token(self, jwt_service):
        """刷新令牌包含 type=refresh"""
        token = jwt_service.issue_refresh_token(user_id="user_001")
        payload = jwt_service.decode(token)

        assert payload["sub"] == "user_001"
        assert payload["type"] == "refresh"

    def test_decode_expired_token(self, jwt_service):
        """过期令牌抛出 AuthenticationError"""
        # 手动创建过期令牌
        import jwt
        now = datetime.utcnow()
        payload = {
            "sub": "user_001",
            "exp": now - timedelta(hours=1),
            "iat": now - timedelta(hours=2),
        }
        expired_token = jwt.encode(payload, "test-secret-key-min-32-chars-long", algorithm="HS256")

        with pytest.raises(AuthenticationError, match="令牌已过期"):
            jwt_service.decode(expired_token)

    def test_decode_invalid_token(self, jwt_service):
        """无效令牌抛出 AuthenticationError"""
        with pytest.raises(AuthenticationError, match="无效令牌"):
            jwt_service.decode("invalid.token.here")

    def test_refresh_with_user_info(self, jwt_service):
        """刷新令牌换取新访问令牌"""
        refresh_token = jwt_service.issue_refresh_token(user_id="user_001")
        new_access, new_refresh = jwt_service.refresh_with_user_info(
            refresh_token=refresh_token,
            user_id="user_001",
            tenant_id="tenant_001",
            roles=["viewer"],
            is_superadmin=False,
        )

        # 验证新访问令牌
        payload = jwt_service.decode(new_access)
        assert payload["sub"] == "user_001"
        assert payload["tenant_id"] == "tenant_001"

        # 验证新刷新令牌
        refresh_payload = jwt_service.decode(new_refresh)
        assert refresh_payload["type"] == "refresh"

    def test_refresh_with_wrong_user(self, jwt_service):
        """刷新令牌与用户不匹配时抛出异常"""
        refresh_token = jwt_service.issue_refresh_token(user_id="user_001")

        with pytest.raises(AuthenticationError, match="刷新令牌与用户不匹配"):
            jwt_service.refresh_with_user_info(
                refresh_token=refresh_token,
                user_id="user_002",  # 不同用户
                tenant_id="tenant_001",
                roles=[],
            )
