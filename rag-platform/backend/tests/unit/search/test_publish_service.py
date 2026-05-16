"""PublishService 单元测试

测试管道发布/停用/状态查询/列表/版本切换逻辑。
使用 Mock Repository 隔离数据库依赖。
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from pydantic import ValidationError

from src.models.published_endpoint import PublishedEndpoint
from src.schemas.search.publish import PublishConfig, PaginatedEndpoints
from src.service.search.publish_service import PublishService


@pytest.fixture
def mock_publish_repo():
    """Mock PublishedEndpointRepository"""
    repo = MagicMock()
    repo.get_by_pipeline_id = AsyncMock()
    repo.get_by_url_path = AsyncMock()
    repo.check_url_path_conflict = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.list_by_tenant = AsyncMock()
    repo.get_by_filter = AsyncMock()
    return repo


@pytest.fixture
def mock_pipeline_repo():
    """Mock PipelineRepository"""
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    return repo


@pytest.fixture
def service(mock_publish_repo, mock_pipeline_repo):
    """构建 PublishService 测试实例（手动注入 mock repo）"""
    svc = PublishService.__new__(PublishService)
    svc._publish_repo = mock_publish_repo
    svc._pipeline_repo = mock_pipeline_repo
    return svc


def _fake_pipeline(active_version=3, name="测试管道"):
    """构造 mock 管道对象"""
    p = MagicMock()
    p.active_version = active_version
    p.name = name
    return p


def _fake_endpoint(**overrides):
    """构造 mock PublishedEndpoint"""
    defaults = {
        "id": 1,
        "endpoint_id": "ep-001",
        "pipeline_id": "pipe-001",
        "tenant_id": "tenant-001",
        "url_path": "medical-consultation",
        "bound_version": 1,
        "http_method": "POST",
        "auth_type": "jwt",
        "rate_limit": 0,
        "enabled": True,
        "allowed_params": ["top_k"],
        "response_format": "json",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    ep = MagicMock(spec=PublishedEndpoint, **defaults)
    # 确保 attribute 访问也返回正确值
    for k, v in defaults.items():
        setattr(ep, k, v)
    return ep


class TestPublishService:
    """发布管理测试"""

    @pytest.mark.asyncio
    async def test_publish_new_endpoint(self, service, mock_publish_repo, mock_pipeline_repo):
        """首次发布管道——创建端点成功"""
        mock_publish_repo.get_by_pipeline_id.return_value = None
        mock_publish_repo.check_url_path_conflict.return_value = False
        mock_pipeline_repo.get_by_id.return_value = _fake_pipeline(active_version=3)
        created = _fake_endpoint()
        mock_publish_repo.create.return_value = created

        config = PublishConfig(url_path="medical-consultation", bound_version=1)
        result = await service.publish("pipe-001", "tenant-001", config)

        assert result.endpoint_id == "ep-001"
        assert result.url_path == "medical-consultation"
        assert result.full_url == "/search/medical-consultation"
        assert result.enabled is True

    @pytest.mark.asyncio
    async def test_publish_update_existing(self, service, mock_publish_repo, mock_pipeline_repo):
        """更新已发布管道——更新成功"""
        existing = _fake_endpoint(url_path="old-path")
        mock_publish_repo.get_by_pipeline_id.return_value = existing
        mock_publish_repo.check_url_path_conflict.return_value = False
        mock_pipeline_repo.get_by_id.return_value = _fake_pipeline()

        updated = _fake_endpoint(url_path="new-path", bound_version=2)
        mock_publish_repo.update.return_value = updated

        config = PublishConfig(url_path="new-path", bound_version=2)
        result = await service.publish("pipe-001", "tenant-001", config)

        assert result.url_path == "new-path"
        assert result.bound_version == 2

    @pytest.mark.asyncio
    async def test_publish_url_path_conflict(self, service, mock_publish_repo, mock_pipeline_repo):
        """URL 路径冲突——抛出 ValueError"""
        mock_publish_repo.get_by_pipeline_id.return_value = None
        mock_publish_repo.check_url_path_conflict.return_value = True
        mock_pipeline_repo.get_by_id.return_value = _fake_pipeline()

        config = PublishConfig(url_path="used-path", bound_version=1)
        with pytest.raises(ValueError, match="URL 路径已被占用"):
            await service.publish("pipe-001", "tenant-001", config)

    @pytest.mark.asyncio
    async def test_publish_invalid_url_path_special_chars(self, service, mock_publish_repo, mock_pipeline_repo):
        """URL 路径含特殊字符——Pydantic 校验失败"""
        with pytest.raises(ValidationError):
            PublishConfig(url_path="invalid/path!", bound_version=1)

    @pytest.mark.asyncio
    async def test_publish_invalid_url_path_too_short(self, service):
        """URL 路径过短——Pydantic 校验失败"""
        with pytest.raises(ValidationError):
            PublishConfig(url_path="ab", bound_version=1)

    @pytest.mark.asyncio
    async def test_publish_invalid_url_path_too_long(self, service):
        """URL 路径过长——Pydantic 校验失败"""
        with pytest.raises(ValidationError):
            PublishConfig(url_path="x" * 51, bound_version=1)

    @pytest.mark.asyncio
    async def test_publish_invalid_version(self, service, mock_publish_repo, mock_pipeline_repo):
        """绑定不存在的版本号——抛出 ValueError"""
        mock_publish_repo.get_by_pipeline_id.return_value = None
        mock_pipeline_repo.get_by_id.return_value = _fake_pipeline(active_version=2)

        config = PublishConfig(url_path="valid-path", bound_version=5)
        with pytest.raises(ValueError, match="版本 5 不存在"):
            await service.publish("pipe-001", "tenant-001", config)

    @pytest.mark.asyncio
    async def test_publish_pipeline_not_found(self, service, mock_publish_repo, mock_pipeline_repo):
        """管道不存在——抛出 ValueError"""
        mock_pipeline_repo.get_by_id.return_value = None

        config = PublishConfig(url_path="valid-path", bound_version=1)
        with pytest.raises(ValueError, match="管道不存在"):
            await service.publish("pipe-999", "tenant-001", config)

    @pytest.mark.asyncio
    async def test_unpublish_sets_disabled(self, service, mock_publish_repo):
        """停用端点——enabled=0，路由已移除"""
        endpoint = _fake_endpoint(enabled=True)
        mock_publish_repo.get_by_pipeline_id.return_value = endpoint

        result = await service.unpublish("pipe-001", "tenant-001")
        assert result.url_path == "medical-consultation"
        assert result.unpublished_at is not None

    @pytest.mark.asyncio
    async def test_unpublish_not_found(self, service, mock_publish_repo):
        """停用未发布的管道——抛出 ValueError"""
        mock_publish_repo.get_by_pipeline_id.return_value = None

        with pytest.raises(ValueError, match="管道未发布"):
            await service.unpublish("pipe-001", "tenant-001")

    @pytest.mark.asyncio
    async def test_get_status_published(self, service, mock_publish_repo, mock_pipeline_repo):
        """查询已发布状态——返回完整信息"""
        endpoint = _fake_endpoint(bound_version=2, enabled=True)
        mock_publish_repo.get_by_pipeline_id.return_value = endpoint
        mock_pipeline_repo.get_by_id.return_value = _fake_pipeline(active_version=3)

        status = await service.get_status("pipe-001", "tenant-001")
        assert status.published is True
        assert status.bound_version == 2
        assert status.active_version == 3
        assert status.version_behind is True

    @pytest.mark.asyncio
    async def test_get_status_not_published(self, service, mock_publish_repo):
        """查询未发布管道——published=false"""
        mock_publish_repo.get_by_pipeline_id.return_value = None

        status = await service.get_status("pipe-001", "tenant-001")
        assert status.published is False

    @pytest.mark.asyncio
    async def test_list_endpoints_pagination(self, service, mock_publish_repo, mock_pipeline_repo):
        """分页查询端点列表——返回正确分页"""
        mock_publish_repo.list_by_tenant.return_value = (
            [_fake_endpoint()],
            1,
        )
        mock_pipeline_repo.get_by_id.return_value = _fake_pipeline(name="测试管道")

        result = await service.list_endpoints("tenant-001", page=1, page_size=20)
        assert isinstance(result, PaginatedEndpoints)
        assert result.total == 1
        assert result.page == 1
        assert len(result.items) == 1
        assert result.items[0].pipeline_name == "测试管道"

    @pytest.mark.asyncio
    async def test_update_version(self, service, mock_publish_repo):
        """切换绑定版本——bound_version 更新"""
        endpoint = _fake_endpoint(bound_version=1)
        mock_publish_repo.get_by_filter.return_value = [
            endpoint
        ]  # get_by_filter 返回列表

        updated = _fake_endpoint(bound_version=3)
        mock_publish_repo.update.return_value = updated

        result = await service.update_version("ep-001", "tenant-001", 3)
        assert result.bound_version == 3

    def test_url_path_validation_valid(self, service):
        """合法 URL 路径通过校验"""
        valid_paths = ["medical", "legal-due-diligence", "test_v1", "My-Path"]
        for path in valid_paths:
            service._validate_url_path(path)  # 不抛异常

    def test_url_path_validation_special_chars(self, service):
        """含特殊字符的路径抛出 ValueError"""
        with pytest.raises(ValueError, match="仅允许字母数字下划线连字符"):
            service._validate_url_path("path/with/slash")

    def test_url_path_validation_too_short(self, service):
        """长度 < 4 抛出 ValueError"""
        with pytest.raises(ValueError, match="长度必须在 4-50"):
            service._validate_url_path("abc")
