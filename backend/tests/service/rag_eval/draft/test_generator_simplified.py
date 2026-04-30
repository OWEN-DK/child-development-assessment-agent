"""DraftGenerator 简化版测试 — 验证 age/domain 移除后的行为"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.schemas.rag_eval.draft import DraftCreate, DraftGenerationConfig


@pytest.fixture
def config():
    return DraftGenerationConfig(max_qa_per_chunk=3, min_qa_per_chunk=1)


class TestDraftGeneratorSimplified:
    """验证 generate() 不再接受 age_ranges/domains 参数"""

    def test_generate_signature_no_metadata(self):
        """generate() 签名不应包含 metadata 参数"""
        import inspect
        from src.service.rag_eval.draft.generator import DraftGenerator
        sig = inspect.signature(DraftGenerator.generate)
        assert "metadata" not in sig.parameters
        assert "age_ranges" not in sig.parameters
        assert "domains" not in sig.parameters

    def test_draft_create_no_age_domain(self):
        """DraftCreate 不应包含 age/domain 字段，也不含 source_document_id"""
        fields = DraftCreate.model_fields
        assert "age" not in fields
        assert "domain" not in fields
        assert "age_stage_label" not in fields
        assert "source_document_id" not in fields

    @pytest.mark.asyncio
    async def test_empty_chunk_skipped(self, config):
        """空 content 的 chunk 应被跳过"""
        from src.service.rag_eval.draft.generator import DraftGenerator
        gen = DraftGenerator()
        gen._config = MagicMock()
        gen._config.get_config_value.side_effect = lambda key, default=None: {
            "rag.eval.draft.concurrency": 15,
        }.get(key, default)

        chunks = [{"id": "c1", "content": ""}, {"id": "c2", "content": "   "}]
        result = await gen.generate(chunks, config)
        assert result == []

    @pytest.mark.asyncio
    async def test_build_drafts_no_age_domain(self, config):
        """_build_drafts 输出不包含 age/domain"""
        from src.service.rag_eval.draft.generator import DraftGenerator
        gen = DraftGenerator()
        items = [{"query": "测试问题", "description": "描述",
                   "expected_keywords": ["关键词"], "answer_points": ["要点"],
                   "difficulty_level": "easy"}]
        drafts = gen._build_drafts(items, "chunk_1", 1, "原文内容")
        assert len(drafts) == 1
        d = drafts[0]
        assert d.query == "测试问题"
        assert d.source_chunk_id == "chunk_1"
        assert d.source_page == 1
        assert "age" not in DraftCreate.model_fields
        assert "domain" not in DraftCreate.model_fields
        assert "source_document_id" not in DraftCreate.model_fields

    @pytest.mark.asyncio
    async def test_prompt_manager_default_injected(self, config):
        """构造函数默认注入 PromptManager 模块单例"""
        from src.service.rag_eval.draft.generator import DraftGenerator
        gen = DraftGenerator()
        assert gen._prompt_manager is not None

    @pytest.mark.asyncio
    async def test_prompt_manager_fallback(self, config):
        """PromptManager 不可用时应使用 fallback prompt"""
        from src.service.rag_eval.draft.generator import DraftGenerator
        gen = DraftGenerator(prompt_manager=None)
        prompt = gen._build_prompt(3, "测试内容")
        assert "3" in prompt
        assert "测试内容" in prompt
        assert "忠实性铁律" in prompt
