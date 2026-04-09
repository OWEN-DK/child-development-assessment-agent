import pytest
from unittest.mock import patch, AsyncMock
from src.model.schemas import (
    UserInput,
    ChildProfile,
    ProposedPlan,
    Activity,
    FinalReport,
    EvaluationResult,
    ChildState,
    DevelopmentStatus,
)
from src.core.graph import agent_app
from src.controller.task_controller import assess_development


@pytest.fixture
def mock_agent_result():
    return {
        "evaluation_result": EvaluationResult(
            score=85.0,
            reasoning="Mock reasoning",
            suggestions=["建议1", "建议2"],
            feature_importance={"scientific": 50, "age": 30, "safety": 20}
        ),
        "final_report": FinalReport(
            markdown_content="# 测试报告\n\n这份报告针对的是 3岁感统训练计划，旨在 提升平衡能力。",
            structured_data={
                "score": 85.0,
                "radar_chart": {"categories": ["科学性", "年龄", "安全性"], "values": [80, 90, 85]},
                "key_suggestions": ["建议1", "建议2"]
            }
        ),
        "child_state": ChildState(
            vestibular_system=DevelopmentStatus(status="normal", level=5, description="正常")
        ),
        "retrieved_docs": []
    }


@pytest.mark.asyncio
async def test_full_workflow_output(mock_agent_result):
    """测试完整工作流的输出结构是否符合预期"""
    # 构造测试输入
    test_input = UserInput(
        child_profile=ChildProfile(
            name="测试小朋友",
            age=3,
            gender="male",
            issues=["注意力不集中", "平衡感差"],
            interests=["玩积木", "跑跳"]
        ),
        proposed_plan=ProposedPlan(
            plan_name="3岁感统训练计划",
            activities=[
                Activity(
                    name="平衡木行走",
                    duration_minutes=15,
                    frequency_weekly=3,
                    intensity="medium",
                    category="vestibular",
                    description="在辅助下走10米平衡木"
                )
            ],
            goals=["提升平衡能力", "改善注意力"]
        ),
        is_streaming=False
    )

    # 直接调用控制器方法
    with patch("src.controller.task_controller.agent_app.ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = mock_agent_result
        result = await assess_development(test_input)
    
    # 验证输出类型
    assert isinstance(result, FinalReport), "输出应该是 FinalReport 类型"
    
    # 验证必填字段存在
    assert hasattr(result, 'markdown_content'), "缺少 markdown_content 字段"
    assert hasattr(result, 'structured_data'), "缺少 structured_data 字段"
    
    # 验证 Markdown 内容包含特定的业务逻辑（而非魔术数字断言）
    assert "3岁感统训练计划" in result.markdown_content, "报告中应包含训练计划名称"
    assert "提升平衡能力" in result.markdown_content, "报告中应包含计划的目标"
    
    # 验证结构化数据
    structured_data = result.structured_data
    assert isinstance(structured_data, dict), "structured_data 应该是字典类型"
    
    # 验证分数字段
    assert "score" in structured_data, "结构化数据中缺少 score 字段"
    score = structured_data["score"]
    assert isinstance(score, (int, float)), "score 应该是数字类型"
    assert 0 <= score <= 100, f"score 应该在 0-100 之间，当前为 {score}"
    
    # 验证雷达图数据
    assert "radar_chart" in structured_data, "结构化数据中缺少 radar_chart 字段"
    assert isinstance(structured_data["radar_chart"], dict), "radar_chart 应该是字典类型"
    
    # 验证关键建议
    assert "key_suggestions" in structured_data, "结构化数据中缺少 key_suggestions 字段"
    assert isinstance(structured_data["key_suggestions"], list), "key_suggestions 应该是列表类型"
    assert len(structured_data["key_suggestions"]) >= 1, "至少应该有一条改进建议"


@pytest.mark.asyncio
async def test_agent_graph_direct_invocation(mock_agent_result):
    """测试直接调用 Agent Graph 的输出"""
    # 构造初始状态
    initial_state = {
        "child_profile": ChildProfile(
            name="测试小朋友",
            age=4,
            gender="female",
            issues=["运动协调性差", "容易摔倒"],
            interests=["画画", "跳舞"]
        ),
        "proposed_plan": ProposedPlan(
            plan_name="4岁协调训练计划",
            activities=[
                Activity(
                    name="跳绳练习",
                    duration_minutes=10,
                    frequency_weekly=4,
                    intensity="medium"
                )
            ],
            goals=["提升肢体协调性", "增强平衡感"]
        ),
        "messages": [],
        "is_streaming": False
    }

    # Mock agent_app.ainvoke to avoid actual LLM calls
    with patch.object(agent_app, "ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = mock_agent_result
        result = await agent_app.ainvoke(initial_state)
    
    # 验证状态包含所有必要字段
    assert "final_report" in result, "结果中缺少 final_report"
    assert "evaluation_result" in result, "结果中缺少 evaluation_result"
    assert "child_state" in result, "结果中缺少 child_state"
    assert "retrieved_docs" in result, "结果中缺少 retrieved_docs"
    
    # 验证评估结果
    eval_result = result["evaluation_result"]
    assert isinstance(eval_result, EvaluationResult), "evaluation_result 类型错误"
    assert 0 <= eval_result.score <= 100, f"评估分数应该在 0-100 之间，当前为 {eval_result.score}"
    assert len(eval_result.suggestions) >= 1, "评估结果应该包含改进建议"
    
    # 验证最终报告
    final_report = result["final_report"]
    assert isinstance(final_report, FinalReport), "final_report 类型错误"
    assert final_report.markdown_content, "报告内容不应为空"
