"""Provider Registry - 多提供商适配器注册表"""

from typing import Dict, Optional, Tuple, Type

from injector import singleton


@singleton
class ProviderRegistry:
    """LLM 提供商适配器注册表

    负责注册和管理不同提供商的 LLM 适配器类，
    支持 LangChain 和 LlamaIndex 两种框架。
    """

    def __init__(self):
        self._registry: Dict[Tuple[str, str], Type] = {}
        self._register_default_providers()

    def register(self, provider: str, framework: str, cls: Type):
        """注册 LLM 类到注册表

        Args:
            provider: 提供商名称（如 dashscope, openai）
            framework: 框架名称（langchain 或 llamaindex）
            cls: LLM 类
        """
        self._registry[(provider.lower(), framework.lower())] = cls

    def get(self, provider: str, framework: str) -> Optional[Type]:
        """根据提供商和框架获取 LLM 类（自动归一化为小写）

        Args:
            provider: 提供商名称
            framework: 框架名称

        Returns:
            LLM 类，若未找到返回 None
        """
        return self._registry.get((provider.lower(), framework.lower()))

    def _register_default_providers(self):
        """注册默认提供商适配器（按提供商隔离 ImportError）"""
        # DashScope
        try:
            from langchain_community.chat_models import ChatTongyi

            self.register("dashscope", "langchain", ChatTongyi)
        except ImportError:
            pass

        try:
            from llama_index.llms.dashscope import DashScope

            self.register("dashscope", "llamaindex", DashScope)
        except ImportError:
            pass

        # OpenAI
        try:
            from langchain_openai import ChatOpenAI

            self.register("openai", "langchain", ChatOpenAI)
        except ImportError:
            pass

        try:
            from llama_index.llms.openai import OpenAI

            self.register("openai", "llamaindex", OpenAI)
        except ImportError:
            pass

        # Anthropic
        try:
            from langchain_anthropic import ChatAnthropic

            self.register("anthropic", "langchain", ChatAnthropic)
        except ImportError:
            pass

        try:
            from llama_index.llms.anthropic import Anthropic

            self.register("anthropic", "llamaindex", Anthropic)
        except ImportError:
            pass

        # Ollama
        try:
            from langchain_ollama import ChatOllama

            self.register("ollama", "langchain", ChatOllama)
        except ImportError:
            pass

        try:
            from llama_index.llms.ollama import Ollama

            self.register("ollama", "llamaindex", Ollama)
        except ImportError:
            pass

        # DeepSeek (通过 OpenAI 兼容接口，需配合 base_url 覆盖)
        try:
            from langchain_openai import ChatOpenAI

            self.register("deepseek", "langchain", ChatOpenAI)
        except ImportError:
            pass

        try:
            from llama_index.llms.openai import OpenAI

            self.register("deepseek", "llamaindex", OpenAI)
        except ImportError:
            pass
