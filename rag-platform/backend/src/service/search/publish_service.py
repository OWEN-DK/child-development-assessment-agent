"""发布管理服务

管道发布/停用/状态查询/列表/版本切换。
"""
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.published_endpoint import PublishedEndpoint
from src.repository.pipeline.pipeline_repo import PipelineRepository
from src.repository.search.publish_repo import PublishedEndpointRepository
from src.schemas.search.publish import (
    EndpointItem,
    PaginatedEndpoints,
    PublishConfig,
    PublishResult,
    PublishStatus,
    UnpublishResult,
)
from src.utils.exceptions import (
    DuplicateResourceException,
    InvalidParamsException,
    ResourceNotFoundException,
)
from src.utils.logger import logger

# URL 路径格式校验
_URL_PATH_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class PublishService:
    """发布管理服务"""

    def __init__(self, db_session_factory: async_sessionmaker):
        self._publish_repo = PublishedEndpointRepository(db_session_factory)
        self._pipeline_repo = PipelineRepository(db_session_factory)

    async def publish(
        self, pipeline_id: str, tenant_id: str, config: PublishConfig
    ) -> PublishResult:
        """发布或更新管道 URL

        Args:
            pipeline_id: 管道ID
            tenant_id: 租户ID
            config: 发布配置

        Returns:
            PublishResult 发布结果

        Raises:
            ValueError: URL 路径格式不合法、路径冲突、版本不存在
        """
        # 校验 URL 路径格式
        self._validate_url_path(config.url_path)

        # 校验管道存在
        pipeline = await self._pipeline_repo.get_by_id(pipeline_id, tenant_id)
        if not pipeline:
            raise ResourceNotFoundException(message=f"管道不存在: {pipeline_id}")

        # 校验版本存在（简化：检查 bound_version <= active_version）
        if config.bound_version > pipeline.active_version:
            raise ResourceNotFoundException(
                message=f"版本 {config.bound_version} 不存在，当前活动版本: {pipeline.active_version}"
            )

        # 检查是否已有端点
        existing = await self._publish_repo.get_by_pipeline_id(pipeline_id, tenant_id)

        if existing:
            # 更新
            update_data = {
                "url_path": config.url_path,
                "bound_version": config.bound_version,
                "http_method": config.http_method,
                "auth_type": config.auth_type,
                "rate_limit": config.rate_limit,
                "enabled": 1 if config.enabled else 0,
                "allowed_params": config.allowed_params,
                "response_format": config.response_format,
            }
            # 如果 URL 路径变更，检查冲突
            if existing.url_path != config.url_path:
                conflict = await self._publish_repo.check_url_path_conflict(config.url_path)
                if conflict:
                    raise DuplicateResourceException(message=f"URL 路径已被占用: {config.url_path}")

            updated = await self._publish_repo.update(existing.id, update_data)
            logger.info(f"管道发布更新: {pipeline_id} → {config.url_path}")
            return self._to_result(updated)

        # 新建
        conflict = await self._publish_repo.check_url_path_conflict(config.url_path)
        if conflict:
            raise DuplicateResourceException(message=f"URL 路径已被占用: {config.url_path}")

        endpoint_id = str(uuid.uuid4()).replace("-", "")[:24]
        create_data = {
            "endpoint_id": endpoint_id,
            "pipeline_id": pipeline_id,
            "tenant_id": tenant_id,
            "url_path": config.url_path,
            "bound_version": config.bound_version,
            "http_method": config.http_method,
            "auth_type": config.auth_type,
            "rate_limit": config.rate_limit,
            "enabled": 1 if config.enabled else 0,
            "allowed_params": config.allowed_params,
            "response_format": config.response_format,
        }
        created = await self._publish_repo.create(create_data)
        logger.info(f"管道发布成功: {pipeline_id} → {config.url_path}")
        return self._to_result(created)

    async def unpublish(
        self, pipeline_id: str, tenant_id: str
    ) -> UnpublishResult:
        """停用管道发布 URL

        幂等：已停用再次调用仍返回成功。
        """
        endpoint = await self._publish_repo.get_by_pipeline_id(pipeline_id, tenant_id)
        if not endpoint:
            raise ResourceNotFoundException(message=f"管道未发布: {pipeline_id}")

        url_path = endpoint.url_path

        if endpoint.enabled:
            await self._publish_repo.update(endpoint.id, {"enabled": 0})
            logger.info(f"管道停用: {pipeline_id} ({url_path})")

        return UnpublishResult(
            pipeline_id=pipeline_id,
            url_path=url_path,
            unpublished_at=datetime.now(timezone.utc),
        )

    async def get_status(
        self, pipeline_id: str, tenant_id: str
    ) -> PublishStatus:
        """查询发布状态"""
        endpoint = await self._publish_repo.get_by_pipeline_id(pipeline_id, tenant_id)
        if not endpoint:
            return PublishStatus(published=False)

        pipeline = await self._pipeline_repo.get_by_id(pipeline_id, tenant_id)
        active_version = pipeline.active_version if pipeline else 0

        return PublishStatus(
            published=True,
            endpoint_id=endpoint.endpoint_id,
            url_path=endpoint.url_path,
            bound_version=endpoint.bound_version,
            active_version=active_version,
            version_behind=endpoint.bound_version < active_version,
            enabled=bool(endpoint.enabled),
        )

    async def list_endpoints(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        enabled_only: Optional[bool] = None,
        keyword: Optional[str] = None,
    ) -> PaginatedEndpoints:
        """列出端点"""
        items, total = await self._publish_repo.list_by_tenant(
            tenant_id, page, page_size, enabled_only, keyword
        )

        endpoint_items = []
        for ep in items:
            pipeline = await self._pipeline_repo.get_by_id(ep.pipeline_id, tenant_id)
            endpoint_items.append(EndpointItem(
                endpoint_id=ep.endpoint_id,
                pipeline_id=ep.pipeline_id,
                pipeline_name=pipeline.name if pipeline else "",
                url_path=ep.url_path,
                bound_version=ep.bound_version,
                auth_type=ep.auth_type,
                rate_limit=ep.rate_limit,
                enabled=bool(ep.enabled),
                created_at=ep.created_at,
                updated_at=ep.updated_at,
            ))

        return PaginatedEndpoints(
            items=endpoint_items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update_version(
        self, endpoint_id: str, tenant_id: str, bound_version: int
    ) -> PublishResult:
        """切换绑定版本"""
        endpoint = await self._publish_repo.get_by_filter(
            tenant_id=tenant_id, endpoint_id=endpoint_id
        )
        if not endpoint:
            raise ResourceNotFoundException(message=f"端点不存在: {endpoint_id}")

        # 取第一条（endpoint_id 全局唯一）
        ep = endpoint[0] if isinstance(endpoint, list) else endpoint
        updated = await self._publish_repo.update(ep.id, {"bound_version": bound_version})
        logger.info(f"端点版本切换: {endpoint_id} → v{bound_version}")
        return self._to_result(updated)

    def _validate_url_path(self, url_path: str) -> None:
        """校验 URL 路径格式"""
        if len(url_path) < 4 or len(url_path) > 50:
            raise InvalidParamsException(message=f"URL 路径长度必须在 4-50 之间: {url_path}")
        if not _URL_PATH_PATTERN.match(url_path):
            raise InvalidParamsException(message=f"URL 路径仅允许字母数字下划线连字符: {url_path}")

    def _to_result(self, ep: PublishedEndpoint) -> PublishResult:
        """转换为 PublishResult"""
        return PublishResult(
            endpoint_id=ep.endpoint_id,
            pipeline_id=ep.pipeline_id,
            url_path=ep.url_path,
            full_url=f"/search/{ep.url_path}",
            bound_version=ep.bound_version,
            http_method=ep.http_method,
            auth_type=ep.auth_type,
            rate_limit=ep.rate_limit,
            enabled=bool(ep.enabled),
            allowed_params=ep.allowed_params or [],
            response_format=ep.response_format,
            created_at=ep.created_at,
            updated_at=ep.updated_at,
        )
