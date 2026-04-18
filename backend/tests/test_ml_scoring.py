import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from src.core.ml.qwen_scorer import QwenScorer
from src.schemas.assessment import (
    ChildProfile,
    ProposedPlan,
    Activity,
    ChildState,
    DevelopmentStatus,
)


@pytest.mark.asyncio
async def test_qwen_scorer():
    # 构造测试数据
    child = ChildProfile(
        name="张三",
        age=5,
        gender="male",
        issues=["注意力不集中", "平衡感差"],
        development_age=4.8,
    )

    activities = [
        Activity(
            name="平衡木训练",
            intensity="medium",
            duration_minutes=20,
            frequency_weekly=3,
            category="vestibular",
        ),
        Activity(
            name="拼图游戏",
            intensity="low",
            duration_minutes=15,
            frequency_weekly=5,
            category="other",
        ),
    ]

    plan = ProposedPlan(
        plan_name="5岁儿童平衡能力训练计划",
        activities=activities,
        goals=["提升注意力", "改善平衡能力"],
    )

    child_state = ChildState(
        vestibular_system=DevelopmentStatus(
            status="deficit", level=2, score=2, description="前庭觉发育不足"
        ),
        proprioception_system=DevelopmentStatus(
            status="normal", level=4, score=4, description="本体觉发育正常"
        ),
        tactile_system=DevelopmentStatus(
            status="normal", level=4, score=4, description="触觉发育正常"
        ),
    )

    ahp_scores = {"scientific": 75, "age": 85, "safety": 90, "total": 82}

    # 直接mock predict 方法，避免复杂的HTTP mock
    expected_score = 80.5
    expected_reasoning = (
        "计划整体合理，针对平衡感问题的训练很有针对性，时长安排也符合5岁儿童特点"
    )
    expected_feature_importance = {
        "scientific_match": 40,
        "age_appropriateness": 30,
        "safety": 20,
        "targetedness": 10,
    }

    mock_response_data = {
        "output": {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "score": expected_score,
                            "reasoning": expected_reasoning,
                            "feature_importance": expected_feature_importance
                        })
                    }
                }
            ]
        }
    }

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = mock_response_data

    # Async mock for httpx.AsyncClient.post
    async def mock_post(*args, **kwargs):
        return mock_response

    with patch("httpx.AsyncClient.post", new=mock_post):
        scorer = QwenScorer()
        score, feature_importance, reasoning = await scorer.predict(
            child, plan, child_state, [], ahp_scores
        )

        assert 0 <= score <= 100
        assert isinstance(feature_importance, dict)
        assert isinstance(reasoning, str)
        assert score == expected_score
        assert "平衡感" in reasoning
        assert (
            feature_importance["scientific_match"]
            == expected_feature_importance["scientific_match"]
        )


def test_scoring_node_initialization():
    from src.core.nodes.scoring import ScoringNode
    from src.config.settings import settings

    # 默认配置下ml_scoring_enabled为False，qwen_scorer应为None
    node = ScoringNode()
    assert node.qwen_scorer is None

    # 测试开启ML评分后的初始化
    with patch.object(settings, "ml_scoring_enabled", True):
        with patch.object(settings, "ml_scoring_mode", "qwen"):
            node = ScoringNode()
            assert node.qwen_scorer is not None
            assert isinstance(node.qwen_scorer, QwenScorer)
