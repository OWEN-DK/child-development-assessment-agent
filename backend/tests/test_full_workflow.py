import pytest
from src.model.schemas import (
    UserInput,
    ChildProfile,
    ProposedPlan,
    Activity,
    FinalReport,
    EvaluationResult,
)
from src.core.graph import agent_app
from src.controller.task_controller import assess_development


@pytest.mark.asyncio
async def test_full_workflow_output():
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
                ),
                Activity(
                    name="拍球游戏",
                    duration_minutes=20,
                    frequency_weekly=5,
                    intensity="high",
                    category="gross_motor",
                    description="双手交替拍皮球"
                )
            ],
            goals=["提升平衡能力", "改善注意力"]
        ),
        is_streaming=False
    )

    # 直接调用控制器方法
    result = await assess_development(test_input)
    
    # 验证输出类型
    assert isinstance(result, FinalReport), "输出应该是 FinalReport 类型"
    
    # 验证必填字段存在
    assert hasattr(result, 'markdown_content'), "缺少 markdown_content 字段"
    assert hasattr(result, 'structured_data'), "缺少 structured_data 字段"
    
    # 验证 Markdown 内容非空
    assert result.markdown_content, "markdown_content 不应为空"
    assert len(result.markdown_content) > 100, "markdown_content 内容过短，可能生成失败"
    
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
    
    print(f"测试通过！生成的报告分数: {score}")
    print(f"报告内容长度: {len(result.markdown_content)} 字符")
    print(f"改进建议数量: {len(structured_data['key_suggestions'])} 条")


@pytest.mark.asyncio
async def test_agent_graph_direct_invocation():
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

    # 直接调用 Agent Graph
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
    
    print(f"Agent Graph 调用测试通过！评估分数: {eval_result.score}")
    print(f"检索到文档数量: {len(result['retrieved_docs'])} 篇")
