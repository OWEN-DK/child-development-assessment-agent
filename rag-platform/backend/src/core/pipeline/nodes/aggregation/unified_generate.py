"""统一答案合成节点

LLM 调用综合多域结果生成最终答案。
"""
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.llm_helper import call_llm
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult
from src.utils.logger import logger


class UnifiedGenerateExecutor(BaseNodeExecutor):
    """统一答案合成执行器"""

    @property
    def category(self) -> str:
        return "aggregation"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行统一答案合成"""
        input_data = context.input_data
        if not input_data:
            return NodeResult(
                output="",
                node_id=context.node_id,
                node_type="unified_generate",
            )

        model = context.config.get("model", "qwen-turbo")
        temperature = context.config.get("temperature", 0.3)
        max_tokens = context.config.get("max_tokens", 2048)
        include_citations = context.config.get("include_citations", True)
        citation_format = context.config.get("citation_format", "[{domain}] {source}")

        # 提取输入
        query = input_data.get("query", "") if isinstance(input_data, dict) else str(input_data)
        sources = input_data.get("sources", []) if isinstance(input_data, dict) else []
        conflict_report = input_data.get("conflict_report", {}) if isinstance(input_data, dict) else {}

        # 构建上下文
        context_text = ""
        if sources:
            context_parts = []
            for i, src in enumerate(sources[:10], 1):
                content = src.get("content", "")
                domain = src.get("domain_id", "")
                if include_citations and domain:
                    context_parts.append(f"[{i}] [{domain}] {content}")
                else:
                    context_parts.append(f"[{i}] {content}")
            context_text = "\n".join(context_parts)

        # 构建提示词
        system_prompt = """你是一个专业的问答助手。根据提供的参考资料回答用户问题。
要求：
1. 回答准确、完整、有条理
2. 如果参考资料中有冲突信息，说明不同观点
3. 如果信息不足，明确说明
4. 引用时标注来源编号"""

        prompt = f"参考资料：\n{context_text}\n\n用户问题：{query}"

        if conflict_report and conflict_report.get("has_conflicts"):
            prompt += f"\n\n注意：检测到以下冲突信息：{conflict_report.get('conflicts', [])}"

        try:
            answer = await call_llm(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
            )
        except Exception as e:
            logger.error(f"答案生成失败: {e}")
            answer = f"答案生成失败: {e}"

        return NodeResult(
            output=answer,
            metadata={
                "model": model,
                "temperature": temperature,
                "source_count": len(sources),
                "include_citations": include_citations,
            },
            node_id=context.node_id,
            node_type="unified_generate",
        )
