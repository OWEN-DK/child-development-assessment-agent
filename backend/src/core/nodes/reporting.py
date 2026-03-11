from typing import Dict, Any
from src.model.schemas import AgentState, FinalReport
from src.core.nodes.base import BaseNode

class ReportingNode(BaseNode):
    """报告生成"""
    
    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        print("Executing Reporting Node...")
        # TODO: 调用 LLM 生成 Markdown
        report = FinalReport(
            markdown_content="# 儿童发展评估报告\n\n## 总分: 85.5\n\n...",
            structured_data={"score": 85.5, "radar_chart": {"vestibular": 60, "core": 50}}
        )
        return {"final_report": report}
