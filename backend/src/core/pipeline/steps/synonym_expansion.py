import json
import re

from src.core.llm.factory import LLMFramework, LLMServiceFactory
from src.core.pipeline.orchestrator import PipelineContext, PipelineStep
from src.schemas import LLMMessage, LLMRequest
from src.utils.logger import logger


class SynonymExpansionStep(PipelineStep):
    """同义词扩展步骤：扩展查询的同义词，提高召回率"""
    
    async def execute(self, context: PipelineContext) -> PipelineContext:
        """执行同义词扩展"""
        model = self.config.get('model', 'qwen-plus')
        max_synonyms = self.config.get('max_synonyms', 5)
        min_length = self.config.get('min_length', 2)
        max_length = self.config.get('max_length', 10)
        
        # 创建LLM实例
        llm = LLMServiceFactory.create(
            framework=LLMFramework.LANGCHAIN,
            model_name=model,
            scenario='synonym_expansion',
            temperature=0.8,
        )
        
        # 构建提示词
        prompt = f"""请为以下查询生成相关的同义词和相关术语，用于儿童发展领域的知识检索：
查询：{context.query}
儿童年龄：{context.age}岁

要求：
1. 生成{max_synonyms}个以内的同义词或相关术语
2. 每个术语长度在{min_length}-{max_length}个字符之间
3. 必须和儿童发展、教育、健康领域相关
4. 不要生成和查询无关的术语

请返回JSON格式：
{{
    "synonyms": ["同义词1", "同义词2", "同义词3"]
}}
"""
        
        messages = [
            LLMMessage(role='system', content='你是一个同义词扩展专家，擅长为用户的查询生成相关的同义词和相关术语，以提高检索召回率'),
            LLMMessage(role='user', content=prompt),
        ]
        
        try:
            response = await llm.chat(
                LLMRequest(
                    messages=messages,
                    model_name=model,
                    temperature=0.8,
                    max_tokens=256,
                    scenario='synonym_expansion',
                )
            )
            
            # 解析响应
            result_text = response.content.strip()
            result_text = re.sub(r"^```(?:json)?\s*", "", result_text, flags=re.IGNORECASE)
            result_text = re.sub(r"\s*```$", "", result_text)
            
            result = json.loads(result_text)
            synonyms = result.get('synonyms', [])
            
            # 过滤同义词
            filtered_synonyms = [
                s.strip() for s in synonyms
                if min_length <= len(s.strip()) <= max_length
            ]
            
            # 去重
            filtered_synonyms = list(dict.fromkeys(filtered_synonyms))
            
            context.metadata['synonyms'] = filtered_synonyms
            logger.info(f"同义词扩展完成：{context.query[:50]}... -> {filtered_synonyms}")
            
        except Exception as e:
            logger.warning(f"同义词扩展失败：{e}")
            context.metadata['synonyms'] = []
        
        return context
