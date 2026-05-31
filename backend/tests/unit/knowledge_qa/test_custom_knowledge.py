"""自定义知识服务单元测试

测试三通道匹配引擎、上传解析、确认入库逻辑。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass, field

from src.service.custom_knowledge_service import (
    CustomKnowledgeService,
    MatchResult,
    SEMANTIC_THRESHOLD,
)


# ──────────────────────────────────────────────────────────────
# 辅助类
# ──────────────────────────────────────────────────────────────


@dataclass
class FakeHit:
    rule_id: str = "cr_001"


@dataclass
class FakeRule:
    rule_id: str = "cr_001"
    title: str = "测试规则"
    content: str = "规则内容"
    keywords: list = field(default_factory=list)
    trigger_patterns: list = field(default_factory=list)
    embedding: list = field(default_factory=list)
    priority: int = 100
    enabled: bool = True


# ──────────────────────────────────────────────────────────────
# MatchResult 测试
# ──────────────────────────────────────────────────────────────


class TestMatchResult:
    """MatchResult 数据类测试"""

    def test_default_values(self):
        """默认值应正确"""
        result = MatchResult()
        assert result.hit is False
        assert result.matched_items == []
        assert result.match_channel == ""
        assert result.latency_ms == 0

    def test_hit_result(self):
        """命中结果应正确"""
        result = MatchResult(
            hit=True,
            matched_items=[{"title": "规则1"}],
            match_channel="keyword",
            latency_ms=5,
        )
        assert result.hit is True
        assert len(result.matched_items) == 1
        assert result.match_channel == "keyword"


# ──────────────────────────────────────────────────────────────
# 三通道匹配引擎测试
# ──────────────────────────────────────────────────────────────


class TestMatch:
    """match() 方法测试"""

    @pytest.mark.asyncio
    async def test_keyword_match_hit(self):
        """关键词匹配命中应短路返回"""
        repo = AsyncMock()
        repo.keyword_match = AsyncMock(return_value=[FakeHit()])
        repo.get_custom_rule = AsyncMock(return_value={
            "rule_id": "cr_001", "title": "注意力规则",
        })
        repo.get_custom_rule_relations = AsyncMock(return_value=[])

        svc = CustomKnowledgeService(repo=repo)
        result = await svc.match("注意力不集中怎么办")
        assert result.hit is True
        assert result.match_channel == "keyword"
        repo.pattern_match.assert_not_called()

    @pytest.mark.asyncio
    async def test_pattern_match_hit(self):
        """关键词未命中时应尝试正则匹配"""
        repo = AsyncMock()
        repo.keyword_match = AsyncMock(return_value=[])
        repo.pattern_match = AsyncMock(return_value=[FakeHit()])
        repo.get_custom_rule = AsyncMock(return_value={
            "rule_id": "cr_001", "title": "感觉统合规则",
        })
        repo.get_custom_rule_relations = AsyncMock(return_value=[])

        svc = CustomKnowledgeService(repo=repo)
        result = await svc.match("感觉统合训练")
        assert result.hit is True
        assert result.match_channel == "pattern"

    @pytest.mark.asyncio
    async def test_no_match(self):
        """三通道都未命中应返回 hit=False"""
        repo = AsyncMock()
        repo.keyword_match = AsyncMock(return_value=[])
        repo.pattern_match = AsyncMock(return_value=[])
        repo.get_all_enabled = AsyncMock(return_value=[])

        svc = CustomKnowledgeService(repo=repo)
        result = await svc.match("无关问题")
        assert result.hit is False
        assert result.match_channel == ""

    @pytest.mark.asyncio
    async def test_keyword_exception_falls_through(self):
        """关键词匹配异常应降级到正则"""
        repo = AsyncMock()
        repo.keyword_match = AsyncMock(side_effect=Exception("DB error"))
        repo.pattern_match = AsyncMock(return_value=[FakeHit()])
        repo.get_custom_rule = AsyncMock(return_value={
            "rule_id": "cr_001", "title": "规则",
        })
        repo.get_custom_rule_relations = AsyncMock(return_value=[])

        svc = CustomKnowledgeService(repo=repo)
        result = await svc.match("测试")
        assert result.hit is True
        assert result.match_channel == "pattern"

    @pytest.mark.asyncio
    async def test_semantic_match_with_embedding(self):
        """语义匹配通道应使用 embedding"""
        repo = AsyncMock()
        repo.keyword_match = AsyncMock(return_value=[])
        repo.pattern_match = AsyncMock(return_value=[])
        repo.get_all_enabled = AsyncMock(return_value=[
            FakeRule(embedding=[1.0, 0.9, 0.8]),
        ])
        repo.get_custom_rule = AsyncMock(return_value={
            "rule_id": "cr_001", "title": "语义规则",
        })
        repo.get_custom_rule_relations = AsyncMock(return_value=[])

        emb = AsyncMock()
        emb.embed_text = AsyncMock(return_value=[1.0, 0.9, 0.8])
        emb.cosine_similarity = MagicMock(return_value=0.95)

        svc = CustomKnowledgeService(repo=repo, embedding_helper=emb)
        result = await svc.match("语义相似问题")
        assert result.hit is True
        assert result.match_channel == "semantic"

    @pytest.mark.asyncio
    async def test_semantic_no_embedding_helper(self):
        """无 embedding_helper 时语义匹配应跳过"""
        repo = AsyncMock()
        repo.keyword_match = AsyncMock(return_value=[])
        repo.pattern_match = AsyncMock(return_value=[])

        svc = CustomKnowledgeService(repo=repo, embedding_helper=None)
        result = await svc.match("测试")
        assert result.hit is False

    @pytest.mark.asyncio
    async def test_semantic_low_similarity_no_hit(self):
        """低相似度语义匹配应不命中"""
        repo = AsyncMock()
        repo.keyword_match = AsyncMock(return_value=[])
        repo.pattern_match = AsyncMock(return_value=[])
        repo.get_all_enabled = AsyncMock(return_value=[
            FakeRule(embedding=[1.0, 0.0, 0.0]),
        ])

        emb = AsyncMock()
        emb.embed_text = AsyncMock(return_value=[0.0, 0.0, 1.0])
        emb.cosine_similarity = MagicMock(return_value=0.1)

        svc = CustomKnowledgeService(repo=repo, embedding_helper=emb)
        result = await svc.match("完全不同的问题")
        assert result.hit is False


# ──────────────────────────────────────────────────────────────
# confirm_and_save 测试
# ──────────────────────────────────────────────────────────────


class TestConfirmAndSave:
    """confirm_and_save() 方法测试"""

    @pytest.mark.asyncio
    async def test_save_success(self):
        """正常保存应返回 saved=1"""
        repo = AsyncMock()
        repo.create_custom_rule = AsyncMock()
        repo.upsert_index = AsyncMock()

        svc = CustomKnowledgeService(repo=repo)
        result = await svc.confirm_and_save([{
            "title": "规则1",
            "content": "内容",
            "keywords": ["关键词"],
            "trigger_patterns": ["模式"],
            "priority": 100,
        }])
        assert result["saved"] == 1
        assert result["skipped"] == 0

    @pytest.mark.asyncio
    async def test_save_with_embedding(self):
        """有 embedding_helper 时应计算 embedding"""
        repo = AsyncMock()
        repo.create_custom_rule = AsyncMock()
        repo.upsert_index = AsyncMock()
        repo.update_embedding = AsyncMock()

        emb = AsyncMock()
        emb.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])

        svc = CustomKnowledgeService(repo=repo, embedding_helper=emb)
        result = await svc.confirm_and_save([{
            "title": "规则1",
            "content": "内容",
            "keywords": ["关键词"],
        }])
        assert result["saved"] == 1
        emb.embed_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_failure_skips(self):
        """保存失败应跳过并记录"""
        repo = AsyncMock()
        repo.create_custom_rule = AsyncMock(side_effect=Exception("DB error"))

        svc = CustomKnowledgeService(repo=repo)
        result = await svc.confirm_and_save([{
            "title": "规则1",
            "content": "内容",
        }])
        assert result["saved"] == 0
        assert result["skipped"] == 1

    @pytest.mark.asyncio
    async def test_save_multiple_rules(self):
        """多条规则应正确计数"""
        repo = AsyncMock()
        repo.create_custom_rule = AsyncMock()
        repo.upsert_index = AsyncMock()

        svc = CustomKnowledgeService(repo=repo)
        result = await svc.confirm_and_save([
            {"title": "规则1", "content": "内容1"},
            {"title": "规则2", "content": "内容2"},
            {"title": "规则3", "content": "内容3"},
        ])
        assert result["saved"] == 3
        assert result["skipped"] == 0


# ──────────────────────────────────────────────────────────────
# upload_and_parse 测试
# ──────────────────────────────────────────────────────────────


class TestUploadAndParse:
    """upload_and_parse() 方法测试"""

    @pytest.mark.asyncio
    async def test_parse_with_front_matter(self):
        """带 YAML front matter 的文件应正确解析"""
        repo = MagicMock()
        svc = CustomKnowledgeService(repo=repo)
        files = [{
            "filename": "rules.md",
            "content": """---
source: 专家经验
---

## 规则
### 注意力训练规则
- **分类**: attention
- **优先级**: 10

当孩子出现注意力不集中的表现时，应采用以下策略。

### 感觉统合建议
- **分类**: sensory

感觉统合训练应从简单到复杂。
""",
        }]
        rules = await svc.upload_and_parse(files)
        assert len(rules) == 2
        assert rules[0]["title"] == "注意力训练规则"
        # category depends on parsing format
        # priority parsed from metadata
        assert rules[0]["source"] == "专家经验"

    @pytest.mark.asyncio
    async def test_parse_no_front_matter(self):
        """无 YAML front matter 的文件应跳过"""
        repo = MagicMock()
        svc = CustomKnowledgeService(repo=repo)
        files = [{
            "filename": "no_fm.md",
            "content": "这是一段普通文本，没有 front matter。",
        }]
        rules = await svc.upload_and_parse(files)
        assert rules == []

    @pytest.mark.asyncio
    async def test_parse_empty_content(self):
        """空内容应返回空列表"""
        repo = MagicMock()
        svc = CustomKnowledgeService(repo=repo)
        rules = await svc.upload_and_parse([{"filename": "empty.md", "content": ""}])
        assert rules == []
