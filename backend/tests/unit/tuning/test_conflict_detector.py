"""冲突检测器测试:验证矛盾建议过滤逻辑"""

import pytest
from unittest.mock import MagicMock
from src.schemas.tuning import TuningSuggestion


@pytest.mark.asyncio
async def test_conflicting_actions_filtered():
    """同一参数的矛盾动作应被过滤"""
    from src.core.tuning.conflict_detector import ConflictDetector

    suggestions = [
        TuningSuggestion(
            param_name="rag_hybrid_bm25_top_k",
            action="increase",
            priority="high",
            source="rule_engine",
            current_value=10,
            suggested_value=15,
            reason="",
            expected_effect="",
        ),
        TuningSuggestion(
            param_name="rag_hybrid_bm25_top_k",
            action="decrease",
            priority="medium",
            source="history",
            current_value=10,
            suggested_value=8,
            reason="",
            expected_effect="",
        ),
    ]

    detector = ConflictDetector()
    filtered, count = detector.detect(suggestions)

    assert len(filtered) == 1
    assert count == 1
    assert filtered[0].action == "increase"


@pytest.mark.asyncio
async def test_same_direction_no_conflict():
    """同方向动作或不同参数不应视为冲突"""
    from src.core.tuning.conflict_detector import ConflictDetector

    suggestions = [
        TuningSuggestion(
            param_name="rag_hybrid_bm25_top_k",
            action="increase",
            priority="high",
            source="rule_engine",
            current_value=10,
            suggested_value=15,
            reason="",
            expected_effect="",
        ),
        TuningSuggestion(
            param_name="rag_hybrid_vector_top_k",
            action="increase",
            priority="high",
            source="rule_engine",
            current_value=10,
            suggested_value=15,
            reason="",
            expected_effect="",
        ),
    ]

    detector = ConflictDetector()
    filtered, count = detector.detect(suggestions)

    assert len(filtered) == 2
    assert count == 0


@pytest.mark.asyncio
async def test_enable_disable_conflict():
    """enable 和 disable 应视为冲突"""
    from src.core.tuning.conflict_detector import ConflictDetector

    suggestions = [
        TuningSuggestion(
            param_name="pageindex_enabled",
            action="enable",
            priority="high",
            source="rule_engine",
            current_value=False,
            suggested_value=True,
            reason="",
            expected_effect="",
        ),
        TuningSuggestion(
            param_name="pageindex_enabled",
            action="disable",
            priority="medium",
            source="llm",
            current_value=False,
            suggested_value=False,
            reason="",
            expected_effect="",
        ),
    ]

    detector = ConflictDetector()
    filtered, count = detector.detect(suggestions)

    assert len(filtered) == 1
    assert filtered[0].action == "enable"


@pytest.mark.asyncio
async def test_priority_based_filtering():
    """应保留优先级最高的建议"""
    from src.core.tuning.conflict_detector import ConflictDetector

    suggestions = [
        TuningSuggestion(
            param_name="rag_chunk_size",
            action="increase",
            priority="low",
            source="rule_engine",
            current_value=600,
            suggested_value=800,
            reason="",
            expected_effect="",
        ),
        TuningSuggestion(
            param_name="rag_chunk_size",
            action="decrease",
            priority="high",
            source="llm",
            current_value=600,
            suggested_value=400,
            reason="",
            expected_effect="",
        ),
        TuningSuggestion(
            param_name="rag_chunk_size",
            action="increase",
            priority="medium",
            source="history",
            current_value=600,
            suggested_value=700,
            reason="",
            expected_effect="",
        ),
    ]

    detector = ConflictDetector()
    filtered, count = detector.detect(suggestions)

    assert len(filtered) == 1
    assert filtered[0].priority == "high"
    assert filtered[0].suggested_value == 400
