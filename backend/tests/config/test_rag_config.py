"""RAG 配置模块测试"""

import pytest


def test_reranker_provider_config():
    """验证 RAG 检索配置包含 reranker_provider 字段"""
    from src.config import settings

    # 验证 reranker_provider 字段存在
    assert hasattr(settings, "rag_reranker_provider"), (
        "rag_reranker_provider 字段不存在"
    )
    assert settings.rag_reranker_provider == "local"

    # 验证旧字段仍然存在（向后兼容）
    assert hasattr(settings, "rag_reranker_model")
    assert settings.rag_reranker_model == "BAAI/bge-reranker-v2-m3"
    assert settings.rag_reranker_initial_k == 30
    assert settings.rag_reranker_final_k == 5
