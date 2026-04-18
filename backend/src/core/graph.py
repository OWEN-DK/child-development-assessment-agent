from typing import Dict
from langgraph.graph import StateGraph, END
from src.model.schemas import AgentState
from src.core.nodes import (
    PreprocessingNode,
    ValidationNode,
    AssessmentNode,
    RetrievalNode,
    ScoringNode,
    ReportingNode,
)
from src.core.tracing.langgraph_middleware import TracingMiddleware


def create_agent_graph():
    """创建并编译 LangGraph 工作流"""

    # 初始化 TracingMiddleware
    tracing_middleware = TracingMiddleware()

    # 初始化 StateGraph
    workflow = StateGraph(AgentState)

    # 实例化节点
    # 注意: LangGraph 接受 Callable, 类的实例如果实现了 __call__ 也是 Callable
    preprocessing_node = PreprocessingNode()
    validation_node = ValidationNode()
    assessment_node = AssessmentNode()
    retrieval_node = RetrievalNode()
    scoring_node = ScoringNode()
    reporting_node = ReportingNode()

    # 添加节点（包裹 tracing 中间件）
    def wrap_with_tracing(node_func, node_name):
        """为节点执行包裹 tracing"""

        async def wrapper(state):
            with tracing_middleware.trace_node(node_name):
                return await node_func(state)

        return wrapper

    workflow.add_node(
        "preprocessing", wrap_with_tracing(preprocessing_node, "preprocessing")
    )
    workflow.add_node("validation", wrap_with_tracing(validation_node, "validation"))
    workflow.add_node("assessment", wrap_with_tracing(assessment_node, "assessment"))
    workflow.add_node("retrieval", wrap_with_tracing(retrieval_node, "retrieval"))
    workflow.add_node("scoring", wrap_with_tracing(scoring_node, "scoring"))
    workflow.add_node("reporting", wrap_with_tracing(reporting_node, "reporting"))

    # 定义边 (Edges)
    # 流程: Preprocessing -> Validation -> Assessment -> Retrieval -> Scoring -> Reporting -> END

    workflow.set_entry_point("preprocessing")

    workflow.add_edge("preprocessing", "validation")
    workflow.add_edge("validation", "assessment")
    workflow.add_edge("assessment", "retrieval")
    workflow.add_edge("retrieval", "scoring")
    workflow.add_edge("scoring", "reporting")
    workflow.add_edge("reporting", END)

    # 编译图
    app = workflow.compile()
    return app


# 全局单例
agent_app = create_agent_graph()
