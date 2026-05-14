"""God Mode 服务

超管进入租户上下文：
- 30 分钟会话超时
- 全量操作审计
- 写操作二次确认
- 并发限制（同一租户仅允许一个超管 God Mode，Redis 实现）
"""
import json
from datetime import datetime, timedelta

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.auth.exceptions import GodModeConflictError, TenantNotFoundError
from src.core.auth.jwt_service import JWTService
from src.repository.auth.tenant_repo import TenantRepository
from src.repository.auth.audit_repo import AuditRepository
from src.schemas.auth.god_mode import GodModeSession
from src.utils.logger import logger

GOD_MODE_TIMEOUT_MINUTES = 30
GOD_MODE_REDIS_PREFIX = "god_mode:"
GOD_MODE_REDIS_LOCK_PREFIX = "god_mode_lock:"


class GodModeService:
    """God Mode 服务"""

    def __init__(
        self,
        db_session_factory: async_sessionmaker,
        jwt_service: JWTService,
        redis_client: redis.Redis | None = None,
    ):
        self.db_session_factory = db_session_factory
        self.tenant_repo = TenantRepository(db_session_factory)
        self.audit_repo = AuditRepository(db_session_factory)
        self.jwt_service = jwt_service
        self._redis = redis_client

    def _get_redis(self) -> redis.Redis:
        """获取 Redis 客户端"""
        if self._redis is None:
            from src.core.redis_client import RedisClient
            self._redis = RedisClient.get_client()
        return self._redis

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

        # 检查并发限制（Redis SET NX）
        r = self._get_redis()
        lock_key = f"{GOD_MODE_REDIS_LOCK_PREFIX}{tenant_id}"
        lock_value = f"{actor_id}:{datetime.utcnow().isoformat()}"

        # 尝试获取锁，30 分钟过期
        acquired = await r.set(
            lock_key,
            lock_value,
            nx=True,
            ex=GOD_MODE_TIMEOUT_MINUTES * 60,
        )

        if not acquired:
            # 已有其他超管在 God Mode 中
            existing = await r.get(lock_key)
            if existing:
                existing_actor = existing.split(":")[0]
                if existing_actor != actor_id:
                    raise GodModeConflictError(
                        message=f"超管 {existing_actor} 已在该租户 God Mode 中"
                    )
                # 同一超管重复进入，续期
                await r.expire(lock_key, GOD_MODE_TIMEOUT_MINUTES * 60)

        # 创建会话
        expires_at = datetime.utcnow() + timedelta(minutes=GOD_MODE_TIMEOUT_MINUTES)

        # 存储会话详情到 Redis
        session_key = f"{GOD_MODE_REDIS_PREFIX}{tenant_id}"
        session_data = {
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "expires_at": expires_at.isoformat(),
            "started_at": datetime.utcnow().isoformat(),
        }
        await r.set(
            session_key,
            json.dumps(session_data),
            ex=GOD_MODE_TIMEOUT_MINUTES * 60,
        )

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
            session_started_at=datetime.utcnow(),
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
        r = self._get_redis()

        # 删除会话和锁
        session_key = f"{GOD_MODE_REDIS_PREFIX}{tenant_id}"
        lock_key = f"{GOD_MODE_REDIS_LOCK_PREFIX}{tenant_id}"

        await r.delete(session_key)
        await r.delete(lock_key)

        await self.audit_repo.log_god_mode_action(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="exit",
        )
        logger.info(f"超管 {actor_id} 退出租户 {tenant_id} God Mode")

    async def extend(self, tenant_id: str, actor_id: str, minutes: int = 30) -> GodModeSession:
        """延长 God Mode 会话"""
        r = self._get_redis()
        session_key = f"{GOD_MODE_REDIS_PREFIX}{tenant_id}"
        lock_key = f"{GOD_MODE_REDIS_LOCK_PREFIX}{tenant_id}"

        # 检查会话是否存在
        session_data_str = await r.get(session_key)
        if not session_data_str:
            raise GodModeConflictError(message="无活跃的 God Mode 会话")

        session_data = json.loads(session_data_str)
        old_expires = datetime.fromisoformat(session_data["expires_at"])
        new_expires = old_expires + timedelta(minutes=minutes)

        # 更新会话
        session_data["expires_at"] = new_expires.isoformat()
        ttl_seconds = int((new_expires - datetime.utcnow()).total_seconds())
        if ttl_seconds <= 0:
            raise GodModeConflictError(message="会话已过期")

        await r.set(session_key, json.dumps(session_data), ex=ttl_seconds)
        await r.expire(lock_key, ttl_seconds)

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

    async def check_timeout(self, tenant_id: str) -> bool:
        """检查会话是否超时"""
        r = self._get_redis()
        session_key = f"{GOD_MODE_REDIS_PREFIX}{tenant_id}"

        session_data_str = await r.get(session_key)
        if not session_data_str:
            return True  # 无会话 = 已超时

        session_data = json.loads(session_data_str)
        expires_at = datetime.fromisoformat(session_data["expires_at"])

        if datetime.utcnow() > expires_at:
            # 会话已过期，清理
            await r.delete(session_key)
            lock_key = f"{GOD_MODE_REDIS_LOCK_PREFIX}{tenant_id}"
            await r.delete(lock_key)
            return True

        return False
