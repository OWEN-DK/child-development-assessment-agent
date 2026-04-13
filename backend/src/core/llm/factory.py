import asyncio
from typing import Optional
from langchain_community.chat_models import ChatTongyi
from llama_index.llms.dashscope import DashScope
from src.config import settings
from src.core.llm.base import LLMService
from src.core.llm.adapters.langchain import LangChainLLMAdapter
from src.core.llm.adapters.llamaindex import LlamaIndexLLMAdapter
from src.utils.logger import logger


class LLMFramework:
    """LLM 框架枚举"""

    LANGCHAIN = "langchain"
    LLAMAINDEX = "llamaindex"


class LLMServiceFactory:
    """LLM 服务工厂（按场景动态生成实例）"""

    _instances: dict[str, LLMService] = {}

    @classmethod
    def create(
        cls,
        framework: str = LLMFramework.LANGCHAIN,
        model_name: Optional[str] = None,
        scenario: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMService:
        """
        创建 LLM 服务实例

        Args:
            framework: LLM 框架（langchain/llamaindex）
            model_name: 模型名称（默认从配置读取）
            scenario: 使用场景（用于 A/B 测试）
            temperature: 温度参数
            max_tokens: 最大 Token 数
        """
        # 生成缓存键
        cache_key = f"{framework}:{model_name}:{scenario}"

        # 检查缓存
        if cache_key in cls._instances:
            logger.debug(f"LLM 实例已缓存：{cache_key}")
            return cls._instances[cache_key]

        # 使用配置中的默认模型
        model_name = model_name or settings.model_report_generation

        # 创建 LLM 实例
        if framework == LLMFramework.LANGCHAIN:
            llm = ChatTongyi(
                model=model_name,
                dashscope_api_key=settings.dashscope_api_key,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            instance = LangChainLLMAdapter(llm, model_name)
            logger.info(f"LangChain LLM 实例已创建：{model_name}")

        elif framework == LLMFramework.LLAMAINDEX:
            llm = DashScope(
                model=model_name,
                api_key=settings.dashscope_api_key,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            instance = LlamaIndexLLMAdapter(llm, model_name)
            logger.info(f"LlamaIndex LLM 实例已创建：{model_name}")

        else:
            raise ValueError(f"不支持的 LLM 框架：{framework}")

        # 缓存实例
        cls._instances[cache_key] = instance

        return instance

    @classmethod
    def clear_cache(cls):
        """清空实例缓存（用于配置变更后）"""
        cls._instances.clear()
        logger.info("LLM 实例缓存已清空")

    @classmethod
    async def _dispose_old_instance(cls, instance, delay: int = 60):
        """延迟显式释放 LLM 实例（等待进行中的请求完成）"""
        logger.info(f"LLM 实例延迟释放已调度：{delay} 秒后释放")
        await asyncio.sleep(delay)
        try:
            if hasattr(instance, "dispose"):
                await instance.dispose()
                logger.info(f"LLM 实例已显式释放")
        except Exception as e:
            logger.warning(f"LLM 实例释放失败（可忽略）: {e}")

    @classmethod
    def invalidate_scene(cls, scene: str):
        """使指定场景的缓存实例失效（触发延迟释放）"""
        if scene in cls._instances:
            old_instance = cls._instances.pop(scene)
            asyncio.create_task(cls._dispose_old_instance(old_instance))
            logger.info(f"场景 {scene} 的 LLM 实例已标记失效")
