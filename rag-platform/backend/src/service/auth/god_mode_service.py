"""God Mode 服务

超管进入租户上下文：
- 30 分钟会话超时
- 全量操作审计
- 写操作二次确认
- 并发限制（同一租户仅允许一个超管 God Mode）
"""
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.auth.exceptions import GodModeConflictError, TenantNotFoundError
from src.core.auth.jwt_service import JWTService
from src.repository.auth.tenant_repo import TenantRepository
from src.repository.auth.audit_repo import AuditRepository
from src.schemas.auth.god_mode import GodModeSession
from src.utils.logger import logger

GOD_MODE_TIMEOUT_MINUTES = 30


class GodModeService:
    """God Mode 服务"""

    def __init__(
        self,
        db_session_factory: async_sessionmaker,
        jwt_service: JWTService,
    ):
        self.db_session_factory = db_session_factory
        self.tenant_repo = TenantRepository(db_session_factory)
        self.audit_repo = AuditRepository(db_session_factory)
        self.jwt_service = jwt_service
        # 内存中的 God Mode 会话（生产环境应用 Redis）
        self._active_sessions: dict[str, dict] = {}  # tenant_id → session_info

    async def enter(self, tenant_id: str, actor_id: str) -> GodModeSession:
        """进入 God Mode

        Args:
            tenant_id: 目标租户 ID
            actor_id: 超管 ID

        Returns:
            GodModeSession（含临时 JWT）

        Raises:
            TenantNotFoundError: 租户不存在
            GodModeConflictError: 已有超管在该租户 God Mode 中
        """
        # 检查租户是否存在
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if tenant is None:
            raise TenantNotFoundError(message=f"租户 {tenant_id} 不存在")

        # 检查并发限制
        if tenant_id in self._active_sessions:
            existing = self._active_sessions[tenant_id]
            if existing["actor_id"] != actor_id:
                raise GodModeConflictError(
                    message=f"超管 {existing['actor_id']} 已在该租户 God Mode 中"
                )

        # 创建会话
        expires_at = datetime.utcnow() + timedelta(minutes=GOD_MODE_TIMEOUT_MINUTES)
        session_info = {
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "expires_at": expires_at,
            "started_at": datetime.utcnow(),
        }
        self._active_sessions[tenant_id] = session_info

        # 签发临时 JWT（含 tenant_id，超管身份）
        access_token = self.jwt_service.issue_access_token(
            user_id=actor_id,
            tenant_id=tenant_id,
            roles=["*"],  # 超管全部权限
            is_superadmin=True,
            extra_claims={"god_mode": True, "god_mode_expires": expires_at.isoformat()},
        )

        # 记录审计日志
        await self.audit_repo.log_god_mode_action(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="enter",
            session_started_at=session_info["started_at"],
        )

        logger.info(f"超管 {actor_id} 进入租户 {tenant_id} God Mode")

        return GodModeSession(
            access_token=access_token,
            expires_at=expires_at,
            tenant_id=tenant_id,
            actor_id=actor_id,
        )

    async def exit(self, tenant_id: str, actor_id: str) -> None:
        """退出 God Mode"""
        if tenant_id in self._active_sessions:
            del self._active_sessions[tenant_id]

        await self.audit_repo.log_god_mode_action(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="exit",
        )
        logger.info(f"超管 {actor_id} 退出租户 {tenant_id} God Mode")

    async def extend(self, tenant_id: str, actor_id: str, minutes: int = 30) -> GodModeSession:
        """延长 God Mode 会话"""
        if tenant_id not in self._active_sessions:
            raise GodModeConflictError(message="无活跃的 God Mode 会话")

        session_info = self._active_sessions[tenant_id]
        new_expires = session_info["expires_at"] + timedelta(minutes=minutes)
        session_info["expires_at"] = new_expires

        # 重新签发 JWT
        access_token = self.jwt_service.issue_access_token(
            user_id=actor_id,
            tenant_id=tenant_id,
            roles=["*"],
            is_superadmin=True,
            extra_claims={"god_mode": True, "god_mode_expires": new_expires.isoformat()},
        )

        await self.audit_repo.log_god_mode_action(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="extend",
            details=f"延长 {minutes} 分钟",
        )

        return GodModeSession(
            access_token=access_token,
            expires_at=new_expires,
            tenant_id=tenant_id,
            actor_id=actor_id,
        )

    async def audit_operation(
        self, tenant_id: str, actor_id: str, action: str, target_type: str, target_id: str
    ) -> None:
        """记录 God Mode 写操作"""
        await self.audit_repo.log_god_mode_action(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
        )

    def check_timeout(self, tenant_id: str) -> bool:
        """检查会话是否超时"""
        if tenant_id not in self._active_sessions:
            return True  # 无会话 = 已超时

        session_info = self._active_sessions[tenant_id]
        if datetime.utcnow() > session_info["expires_at"]:
            del self._active_sessions[tenant_id]
            return True

        return False
