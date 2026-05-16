"""发布管理集成测试

测试完整的发布 → 搜索 → 停用流程（需数据库和 Redis 环境）。
所有测试用 @pytest.mark.integration 标记，CI 中需指定 --run-integration 才执行。
"""
import pytest


pytestmark = pytest.mark.integration


class TestPublishThenSearch:
    """发布后搜索"""

    @pytest.mark.asyncio
    async def test_publish_then_search(self):
        """发布管道后立即搜索——200 + SearchResponse"""
        pytest.skip("需数据库环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_unpublish_then_search_404(self):
        """停用后搜索——404 ENDPOINT_DISABLED"""
        pytest.skip("需数据库环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_publish_version_switch(self):
        """切换版本后搜索——使用新版本配置，URL 不变"""
        pytest.skip("需数据库环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_publish_version_switch_atomic(self):
        """切换版本过程中搜索——旧版本持续服务直到保存完成"""
        pytest.skip("需数据库环境 — 手动执行")


class TestPublishValidation:
    """发布校验"""

    @pytest.mark.asyncio
    async def test_url_path_special_chars_rejected(self):
        """URL 含特殊字符 → 400 INVALID_URL_PATH"""
        # 此测试验证 Pydantic 层校验，无需 DB
        from pydantic import ValidationError
        from src.schemas.search.publish import PublishConfig

        with pytest.raises(ValidationError):
            PublishConfig(url_path="path/with/slash!", bound_version=1)

    @pytest.mark.asyncio
    async def test_url_path_length_rejected(self):
        """URL < 4 或 > 50 → ValidationError"""
        from pydantic import ValidationError
        from src.schemas.search.publish import PublishConfig

        with pytest.raises(ValidationError):
            PublishConfig(url_path="ab", bound_version=1)

        with pytest.raises(ValidationError):
            PublishConfig(url_path="x" * 51, bound_version=1)


class TestPublishEndpointsList:
    """端点列表"""

    @pytest.mark.asyncio
    async def test_list_endpoints_pagination(self):
        """分页查询端点列表——正确分页含 24h 统计"""
        pytest.skip("需数据库环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_list_endpoints_filter_status(self):
        """筛选启用/停用状态"""
        pytest.skip("需数据库环境 — 手动执行")
