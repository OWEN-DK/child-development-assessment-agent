from typing import Dict
from langgraph.graph import StateGraph, END
from src.model.schemas import AgentState
from src.core.nodes import (
    PreprocessingNode,
    ValidationNode,
    AssessmentNode,
    RetrievalNode,
    ScoringNode,
    ReportingNode
)

def create_agent_graph():
    """创建并编译 LangGraph 工作流"""
    
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

    # 添加节点
    workflow.add_node("preprocessing", preprocessing_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("assessment", assessment_node)
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("scoring", scoring_node)
    workflow.add_node("reporting", reporting_node)

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
