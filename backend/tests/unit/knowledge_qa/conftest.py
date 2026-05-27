"""知识问答单元测试共享 fixture

提供 ContextVar 环境的 setup/cleanup，避免每个测试文件重复。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def setup_context_vars():
    """设置知识问答 ContextVar 环境（进度、prompt、HTTP 客户端、降级收集器）。

    使用 yield 确保测试后清理，防止 ContextVar 泄漏。
    """
    from src.core.knowledge_qa.tools import (
        clear_http_client,
        set_http_client,
    )
    from src.schemas.knowledge_qa import (
        clear_partial_collector,
        clear_progress_context,
        clear_prompt_manager,
        init_partial_collector,
        set_progress_context,
        set_prompt_manager,
    )

    set_progress_context(
        callback=AsyncMock(),
        task_id="test-task-id",
        task_type="knowledge_qa",
    )
    mock_pm = MagicMock()
    mock_pm.get_prompt = AsyncMock(return_value=None)
    set_prompt_manager(mock_pm)
    set_http_client(MagicMock())
    init_partial_collector()

    yield

    clear_progress_context()
    clear_prompt_manager()
    clear_partial_collector()
    clear_http_client()
