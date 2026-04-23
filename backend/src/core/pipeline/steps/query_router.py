from src.core.llm.factory import LLMFramework, LLMServiceFactory, LLMServiceFactoryCompat
from src.core.pipeline.orchestrator import PipelineContext, PipelineStep
from src.schemas import LLMMessage, LLMRequest
from src.utils.logger import logger


class QueryRouterStep(PipelineStep):
    """查询路由步骤：简单/复杂查询分类"""
    
    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行查询路由"""
        model = self.config.get('model', 'qwen3-omni-flash')
        confidence_threshold = self.config.get('confidence_threshold', 0.8)
        
        # 创建 LLM 实例
        llm = LLMServiceFactoryCompat.create(
            framework=LLMFramework.LANGCHAIN,
            model_name=model,
            scenario='query_routing',
            temperature=0.1,
        )
        
        # 构建提示词
        prompt = f"""请判断以下查询的复杂度：
查询：{context.query}

分类标准：
- 简单查询：事实性问题、定义性问题、单一知识点
- 复杂查询：比较分析、多步骤推理、需要综合多个知识点

请返回 JSON 格式：
{{
    "query_type": "simple" or "complex",
    "confidence": 0.0-1.0,
    "reason": "分类理由"
}}
"""
        
        messages = [
            LLMMessage(role='system', content='你是一个查询分类专家'),
            LLMMessage(role='user', content=prompt),
        ]
        
        response = await llm.chat(
            LLMRequest(
                messages=messages,
                model_name=model,
                temperature=0.1,
                max_tokens=256,
                scenario='query_routing',
            )
        )
        
        # 解析响应
        import json
        try:
            result = json.loads(response.content)
            context.metadata['query_type'] = result['query_type']
            context.metadata['routing_confidence'] = result['confidence']
            context.metadata['routing_reason'] = result['reason']
            
            logger.info(f"查询路由：{context.query[:30]}... -> {result['query_type']} (置信度：{result['confidence']:.2f})")
            
        except Exception as e:
            logger.warning(f"查询路由解析失败，降级为复杂查询：{e}")
            context.metadata['query_type'] = 'complex'
            context.metadata['routing_confidence'] = 0.0
        
        return context