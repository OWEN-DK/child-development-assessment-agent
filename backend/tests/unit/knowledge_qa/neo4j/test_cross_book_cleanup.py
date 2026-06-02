"""跨书数据清理单元测试

测试清理逻辑。
"""

import pytest

from src.core.knowledge_qa.neo4j.cross_book_cleanup import (
    CrossBookCleanup,
)


# ──────────────────────────────────────────────────────────────
# 引擎测试（Mock）
# ──────────────────────────────────────────────────────────────


class TestCrossBookCleanup:
    """CrossBookCleanup 引擎测试"""

    def test_init(self):
        """初始化应正确"""
        cleanup = CrossBookCleanup(neo4j_driver=None)
        assert cleanup._neo4j is None
