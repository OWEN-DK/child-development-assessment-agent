import json
import re

from src.core.llm.factory import LLMFramework, LLMServiceFactory
from src.core.pipeline.orchestrator import PipelineContext, PipelineStep
from src.schemas import LLMMessage, LLMRequest
from src.utils.logger import logger


class QueryRewriteStep(PipelineStep):
    """查询重写步骤：优化查询语句，提高检索准确率"""
    
    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行查询重写"""
        model = self.config.get('model', 'qwen-plus')
        temperature = self.config.get('temperature', 0.3)
        
        # 创建LLM实例
        llm = LLMServiceFactory.create(
            framework=LLMFramework.LANGCHAIN,
            model_name=model,
            scenario='query_rewrite',
            temperature=temperature,
        )
        
        # 构建提示词
        prompt = f"""请优化以下用户查询，使其更适合用于知识检索，保留原始语义：
查询：{context.query}
用户儿童年龄：{context.age}岁

要求：
1. 补充查询中缺失的相关领域术语
2. 消除歧义，明确查询意图
3. 适合儿童发展领域的知识检索
4. 长度不超过原查询的2倍

请返回JSON格式：
{{
    "original_query": "{context.query}",
    "rewritten_query": "优化后的查询",
    "reason": "优化理由"
}}
"""
        
        messages = [
            LLMMessage(role='system', content='你是一个查询优化专家，擅长将用户的自然语言查询改写为更适合知识检索的形式'),
            LLMMessage(role='user', content=prompt),
        ]
        
        try:
            response = await llm.chat(
                LLMRequest(
                    messages=messages,
                    model_name=model,
                    temperature=temperature,
                    max_tokens=256,
                    scenario='query_rewrite',
                )
            )
            
            # 解析响应
            result_text = response.content.strip()
            result_text = re.sub(r"^```(?:json)?\s*", "", result_text, flags=re.IGNORECASE)
            result_text = re.sub(r"\s*```$", "", result_text)
            
            result = json.loads(result_text)
            rewritten_query = result['rewritten_query']
            
            # 更新上下文的查询
            context.metadata['original_query'] = context.query
            context.query = rewritten_query
            context.metadata['rewrite_reason'] = result['reason']
            
            logger.info(f"查询重写完成：'{result['original_query']}' -> '{rewritten_query}'")
            
        except Exception as e:
            logger.warning(f"查询重写失败，使用原始查询：{e}")
            context.metadata['rewrite_failed'] = True
        
        return context
