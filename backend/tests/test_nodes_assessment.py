import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.core.nodes.assessment import AssessmentNode
from src.model.schemas import (
    AgentState,
    ChildProfile,
    CondensedContext,
    ProposedPlan,
    Activity,
)
from src.model.schemas import ChildState


@pytest.fixture
def mock_agent_state():
    return AgentState(
        child_profile=ChildProfile(
            name="TestChild",
            age=4,
            gender="male",
            issues=["attention"],
            interests=["lego"],
        ),
        proposed_plan=ProposedPlan(
            plan_name="TestPlan",
            activities=[
                Activity(
                    name="Play",
                    duration_minutes=10,
                    frequency_weekly=3,
                    intensity="low",
                )
            ],
            goals=["fun"],
        ),
        condensed_context=CondensedContext(
            weekly_avg_duration=30,
            frequency_consistency=0.8,
            intensity_trend="stable",
            diversity_score=0.5,
            recent_feedbacks=["good"],
        ),
    )


@pytest.mark.asyncio
async def test_assessment_node_success(mock_agent_state):
    # Mock settings to enable API key
    with patch("src.core.nodes.assessment.settings") as mock_settings:
        mock_settings.dashscope_api_key = "test_key"
        mock_settings.llm_models = {"assessment": "qwen-plus"}

        # Mock DashScope
        with patch("src.core.nodes.assessment.DashScope") as MockDashScope:
            mock_llm = AsyncMock()
            MockDashScope.return_value = mock_llm

            # Mock LLM response
            mock_response = MagicMock()
            mock_response.text = """
            ```json
            {
                "vestibular_system": {
                    "status": "weak",
                    "level": 2,
                    "description": "Signs of vestibular weakness"
                },
                "overall_assessment": "Needs improvement"
            }
            ```
            """
            mock_llm.acomplete.return_value = mock_response

            node = AssessmentNode()
            result = await node(mock_agent_state)

            assert "child_state" in result
            child_state = result["child_state"]
            assert isinstance(child_state, ChildState)
            assert child_state.vestibular_system.status == "weak"
            assert child_state.overall_assessment == "Needs improvement"


@pytest.mark.asyncio
async def test_assessment_node_fallback(mock_agent_state):
    # Test fallback when API key is missing or error occurs
    with patch("src.core.nodes.assessment.settings") as mock_settings:
        mock_settings.dashscope_api_key = None  # Simulate missing key

        node = AssessmentNode()
        result = await node(mock_agent_state)

        assert "child_state" in result
        child_state = result["child_state"]
        # Should return default/fallback state
        assert child_state.vestibular_system.status == "normal"
        assert "暂无法评估" in child_state.vestibular_system.description
        assert "系统暂时无法生成详细评估" in child_state.overall_assessment


@pytest.mark.asyncio
async def test_assessment_node_exception_handling(mock_agent_state):
    # Test exception handling during LLM call
    with patch("src.core.nodes.assessment.settings") as mock_settings:
        mock_settings.dashscope_api_key = "test_key"
        mock_settings.llm_models = {"assessment": "qwen-plus"}

        with patch("src.core.nodes.assessment.DashScope") as MockDashScope:
            mock_llm = AsyncMock()
            MockDashScope.return_value = mock_llm
            # Simulate exception
            mock_llm.acomplete.side_effect = Exception("API Error")

            node = AssessmentNode()
            result = await node(mock_agent_state)

            assert "child_state" in result
            child_state = result["child_state"]
            # Should fall back to default
            assert "暂无法评估" in child_state.vestibular_system.description
