import pytest
from src.core.nodes.scoring import ScoringNode
from src.model.schemas import (
    AgentState,
    ChildProfile,
    ProposedPlan,
    Activity,
    EvaluationResult,
    ChildState,
    DevelopmentStatus,
    KnowledgeItem,
)


@pytest.fixture
def base_state():
    return AgentState(
        child_profile=ChildProfile(
            name="TestChild",
            age=4,
            gender="male",
            issues=["balance", "attention"],
            interests=["play"],
        ),
        proposed_plan=ProposedPlan(
            plan_name="Test Plan",
            activities=[
                Activity(
                    name="Jump",
                    duration_minutes=10,
                    frequency_weekly=3,
                    intensity="medium",
                )
            ],
            goals=["Improve balance", "Increase attention"],
        ),
        child_state=ChildState(
            vestibular_system=DevelopmentStatus(
                status="weak", level=2, description="Weak"
            )
        ),
        retrieved_docs=[
            KnowledgeItem(
                content="Jumping helps balance",
                source_book="Book A",
                risk_level="Low",
                target_age_min=3,
                target_age_max=5,
                relevance_score=0.9,
            )
        ],
    )


@pytest.mark.asyncio
async def test_scoring_node_basic_flow(base_state):
    node = ScoringNode()
    result = await node(base_state)

    assert "evaluation_result" in result
    eval_result = result["evaluation_result"]
    assert isinstance(eval_result, EvaluationResult)
    # Basic check: score should be reasonable (e.g., > 50)
    assert eval_result.score > 50
    assert "shap_explanation" in eval_result.model_dump()


@pytest.mark.asyncio
async def test_scoring_scientific_match(base_state):
    # Test high relevance
    base_state.retrieved_docs[0].relevance_score = 1.0
    node = ScoringNode()
    result_high = await node(base_state)
    score_high = result_high["evaluation_result"].score

    # Test low relevance
    base_state.retrieved_docs[0].relevance_score = 0.1
    node = ScoringNode()
    result_low = await node(base_state)
    score_low = result_low["evaluation_result"].score

    # High relevance should yield higher score
    # Note: Scientific score is 40% of total.
    # High relevance (1.0) -> Scientific score 100 * 0.4 = 40
    # Low relevance (0.1) -> Scientific score 10 * 0.4 = 4
    # Difference should be significant
    assert score_high > score_low


@pytest.mark.asyncio
async def test_scoring_age_appropriateness_penalty(base_state):
    # Age < 6, duration > 30 -> Penalty
    base_state.child_profile.age = 4
    base_state.proposed_plan.activities[0].duration_minutes = 45  # > 30

    node = ScoringNode()
    result = await node(base_state)
    suggestions = result["evaluation_result"].suggestions

    # Check for specific suggestion about duration
    assert any("单次时长" in s for s in suggestions)


@pytest.mark.asyncio
async def test_scoring_safety_penalty_high_risk_activity(base_state):
    # Age < 4, High intensity -> Penalty
    base_state.child_profile.age = 3
    base_state.proposed_plan.activities[0].intensity = "high"

    node = ScoringNode()
    result = await node(base_state)
    suggestions = result["evaluation_result"].suggestions

    assert any("高强度活动" in s for s in suggestions)


@pytest.mark.asyncio
async def test_scoring_safety_penalty_vestibular_deficit(base_state):
    # Vestibular deficit + High intensity -> Penalty
    base_state.child_state.vestibular_system.status = "deficit"
    base_state.proposed_plan.activities[0].intensity = "high"

    node = ScoringNode()
    result = await node(base_state)
    suggestions = result["evaluation_result"].suggestions

    assert any("前庭觉敏感" in s for s in suggestions)


@pytest.mark.asyncio
async def test_scoring_safety_penalty_high_risk_doc(base_state):
    # High risk document -> Penalty
    base_state.retrieved_docs[0].risk_level = "High"
    base_state.retrieved_docs[0].content = "Dangerous activity"

    node = ScoringNode()
    result = await node(base_state)
    suggestions = result["evaluation_result"].suggestions

    assert any("注意风险" in s for s in suggestions)
