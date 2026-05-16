"""E2E 搜索集成测试

测试完整的搜索流程（需数据库、Redis、PipelineCompiler、知识库环境）。
所有测试用 @pytest.mark.integration 标记。
"""
import pytest


pytestmark = pytest.mark.integration


class TestSearchViaPublishedUrl:
    """发布 URL 搜索"""

    @pytest.mark.asyncio
    async def test_search_via_published_url(self):
        """POST /search/{url_path} → 200 + SearchResponse"""
        pytest.skip("需完整环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_search_endpoint_not_found(self):
        """URL 路径无匹配 → 404 ENDPOINT_NOT_FOUND"""
        pytest.skip("需完整环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_search_endpoint_disabled(self):
        """端点已停用 → 404 ENDPOINT_DISABLED"""
        pytest.skip("需完整环境 — 手动执行")


class TestSearchViaGenericEndpoint:
    """通用端点搜索"""

    @pytest.mark.asyncio
    async def test_search_via_generic_endpoint(self):
        """POST /api/v1/search → 200 + SearchResponse"""
        pytest.skip("需完整环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_search_pipeline_not_found(self):
        """pipeline_id 不存在 → 404 PIPELINE_NOT_FOUND"""
        pytest.skip("需完整环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_search_empty_query(self):
        """query="" → 400 QUERY_EMPTY"""
        pytest.skip("需完整环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_search_query_too_long(self):
        """query 超过 2000 字符 → 400 QUERY_TOO_LONG"""
        pytest.skip("需完整环境 — 手动执行")


class TestSearchParamWhitelist:
    """参数白名单"""

    @pytest.mark.asyncio
    async def test_search_param_whitelist_enforcement(self):
        """allowed_params=["top_k"]，但传 temperature → temperature 被忽略"""
        pytest.skip("需完整环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_search_param_all_allowed_generic(self):
        """通用端点传任意参数 → 所有参数生效（无白名单过滤）"""
        pytest.skip("需完整环境 — 手动执行")


class TestSearchPermissionDomain:
    """权限域过滤"""

    @pytest.mark.asyncio
    async def test_search_permission_domain_filtered(self):
        """用户无某知识库权限 → filtered_domains 标注裁剪域数"""
        pytest.skip("需完整环境 — 手动执行")


class TestSearchResponseControl:
    """响应控制"""

    @pytest.mark.asyncio
    async def test_search_response_truncation(self):
        """响应体超过 2MB → truncated=true"""
        pytest.skip("需完整环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_search_response_top_k(self):
        """params.response_top_k=3 → 每个域 top_chunks ≤ 3"""
        pytest.skip("需完整环境 — 手动执行")


class TestSearchRateLimit:
    """搜索限流"""

    @pytest.mark.asyncio
    async def test_search_rate_limit_enforcement(self):
        """超过 QPS 限制 → 429 RATE_LIMITED"""
        pytest.skip("需完整环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_search_rate_limit_retry_after(self):
        """429 响应 → Retry-After header 正确"""
        pytest.skip("需完整环境 — 手动执行")


class TestSearchTracing:
    """搜索追踪"""

    @pytest.mark.asyncio
    async def test_search_tracing_spans(self):
        """搜索执行后查询 Trace → pipeline/domain/node 三级 Span 完整"""
        pytest.skip("需完整环境 — 手动执行")


class TestSearchCrossDomain:
    """跨域搜索"""

    @pytest.mark.asyncio
    async def test_search_shortcut_activated(self):
        """查询只涉及单域 → shortcut_activated=true"""
        pytest.skip("需完整环境 — 手动执行")

    @pytest.mark.asyncio
    async def test_search_cross_domain_conflicts(self):
        """含矛盾文档的多域搜索 → conflicts 数组非空"""
        pytest.skip("需完整环境 — 手动执行")
