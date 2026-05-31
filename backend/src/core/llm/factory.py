"""LLM 服务工厂 - 支持多提供商和热更新"""

import asyncio
from typing import Any, Dict, Optional

from injector import singleton

from src.config.core.manager import ConfigManager
from src.config.core.events import ConfigChangedEvent
from src.core.event_bus import event_bus
from src.core.llm.adapters.langchain import LangChainLLMAdapter
from src.core.llm.adapters.llamaindex import LlamaIndexLLMAdapter
from src.core.llm.base import LLMService
from src.core.llm.provider_registry import ProviderRegistry
from src.utils.logger import logger


class LLMFramework:
    """LLM 框架枚举"""

    LANGCHAIN = "langchain"
    LLAMAINDEX = "llamaindex"


# 提供商参数白名单（不同提供商支持的参数不同）
PROVIDER_PARAM_WHITELIST = {
    "dashscope": {
        "model",
        "temperature",
        "max_tokens",
        "top_p",
        "presence_penalty",
        "frequency_penalty",
        "api_key",
        "result_format",
    },
    "openai": {
        "model",
        "temperature",
        "max_tokens",
        "top_p",
        "presence_penalty",
        "frequency_penalty",
        "api_key",
        "base_url",
    },
    "anthropic": {
        "model",
        "temperature",
        "max_tokens",
        "top_p",
        "presence_penalty",
        "frequency_penalty",
        "api_key",
        "base_url",
    },
    "deepseek": {
        "model",
        "temperature",
        "max_tokens",
        "top_p",
        "api_key",
        "base_url",
    },  # 不支持 penalty
    "ollama": {
        "model",
        "temperature",
        "max_tokens",
        "top_p",
        "base_url",
    },  # 不支持 penalty 和 api_key
}


@singleton
class LLMServiceFactory:
    """LLM 服务工厂（支持多提供商和热更新）"""

    LOCK_TIMEOUT = 10.0  # 锁超时时间（秒）

    def __init__(
        self, config_manager: ConfigManager, provider_registry: ProviderRegistry
    ):
        self.config_manager = config_manager
        self.provider_registry = provider_registry
        self._instances: Dict[
            str, Dict[str, Any]
        ] = {}  # {scene: {framework: instance}}
        self._deprecated_instances: Dict[
            str, Dict[str, Any]
        ] = {}  # {cache_key: {"instance": obj, "ref_count": int, "generation": int}}
        self._cache_lock = asyncio.Lock()  # 保护缓存操作
        self._config_lock = asyncio.Lock()  # 保护配置变更处理
        self._active_requests: Dict[str, int] = {}  # {cache_key: active_request_count}
        self._current_generation = 0  # 配置版本代际
        self._shutdown = False

        # 监听配置变更事件
        event_bus.subscribe(ConfigChangedEvent, self._on_config_changed_sync)

    async def create(self, scene: str, framework: str = "langchain") -> Any:
        """创建指定场景的 LLM 服务实例（异步安全）

        Args:
            scene: 场景名称（如 report_generation, validation）
            framework: 框架名称（langchain 或 llamaindex）

        Returns:
            LLMService 实例

        Raises:
            RuntimeError: 工厂正在关闭
            ValueError: 未知场景或提供商
        """
        if self._shutdown:
            raise RuntimeError("Factory is shutting down")

        cache_key = f"{scene}:{framework}"

        # 使用锁超时防止永久等待
        try:
            await asyncio.wait_for(
                self._cache_lock.acquire(), timeout=self.LOCK_TIMEOUT
            )
        except asyncio.TimeoutError:
            raise RuntimeError(f"Failed to acquire lock for {cache_key}")

        try:
            # 先检查缓存
            if scene in self._instances and framework in self._instances[scene]:
                self._active_requests[cache_key] = (
                    self._active_requests.get(cache_key, 0) + 1
                )
                return self._instances[scene][framework]

            # 通过 config_manager 获取最新配置
            full_config = self.config_manager.get_full_config()
            scene_config_data = full_config.get(f"llm_{scene}", {})
            if not scene_config_data:
                # 回退到 settings 中的 llm_scene_configs 属性
                from src.config import settings as app_settings
                scene_obj = app_settings.llm_scene_configs.get(scene)
                if not scene_obj:
                    raise ValueError(f"Unknown LLM scene: {scene}")
                scene_config_data = scene_obj.model_dump()

            # 使用 Pydantic 校验（复用 LLMSceneConfig 的约束）
            from src.config.modules.models.llm import LLMSceneConfig

            try:
                scene_config = LLMSceneConfig(**scene_config_data)
            except Exception as e:
                raise ValueError(f"Invalid LLM config for scene {scene}: {e}")

            # 获取提供商配置（config_snapshot 中键名为 llm_providers，非 llm_llm_providers）
            llm_providers = full_config.get("llm_providers", {})
            provider_config = llm_providers.get(scene_config.provider)
            if not provider_config:
                raise ValueError(f"Unknown LLM provider: {scene_config.provider}")

            # 从注册表获取 LLM 类
            llm_cls = self.provider_registry.get(scene_config.provider, framework)
            if not llm_cls:
                raise ValueError(
                    f"No adapter found for provider {scene_config.provider}, framework {framework}"
                )

            # 按提供商白名单过滤参数
            allowed_params = PROVIDER_PARAM_WHITELIST.get(scene_config.provider, set())

            # 构造实例参数（仅保留提供商支持的参数）
            all_params = {
                "model": scene_config.model,
                "temperature": scene_config.temperature,
                "max_tokens": scene_config.max_tokens,
                "top_p": scene_config.top_p,
                "presence_penalty": scene_config.presence_penalty,
                "frequency_penalty": scene_config.frequency_penalty,
            }
            if provider_config.get("api_key"):
                all_params["api_key"] = provider_config["api_key"]
            elif scene_config.provider == "dashscope":
                # 数据库 config_snapshot 中 llm_providers 可能缺少 api_key，回退到 .env
                from src.config import settings as app_settings
                if app_settings.dashscope_api_key:
                    all_params["api_key"] = app_settings.dashscope_api_key
            if provider_config.get("base_url"):
                all_params["base_url"] = provider_config["base_url"]

            params = {k: v for k, v in all_params.items() if k in allowed_params}

            # 创建实例
            try:
                # DashScopeMultiModalAdapter 已实现 LLMService，无需再包装
                from src.core.llm.adapters.dashscope_multimodal import \
                    DashScopeMultiModalAdapter

                if llm_cls == DashScopeMultiModalAdapter:
                    # 从配置读取多模态前缀列表
                    from src.config import settings
                    params['multimodal_prefixes'] = settings.llm_multimodal_model_prefixes
                    instance = llm_cls(**params)
                else:
                    llm_instance = llm_cls(**params)
                    # 包装为统一的 LLMService 接口
                    if framework == LLMFramework.LANGCHAIN:
                        instance = LangChainLLMAdapter(llm_instance, scene_config.model)
                    elif framework == LLMFramework.LLAMAINDEX:
                        instance = LlamaIndexLLMAdapter(llm_instance, scene_config.model)
                    else:
                        raise ValueError(f"Unsupported framework: {framework}")

            except Exception as e:
                # 实例创建失败，保留旧实例（若有）
                if scene in self._instances and framework in self._instances[scene]:
                    logger.error(
                        f"Failed to create new LLM instance for {scene}: {e}, keeping old instance"
                    )
                    self._active_requests[cache_key] = (
                        self._active_requests.get(cache_key, 0) + 1
                    )
                    return self._instances[scene][framework]
                raise RuntimeError(f"Failed to create LLM instance for {scene}: {e}")

            # 缓存实例
            if scene not in self._instances:
                self._instances[scene] = {}
            self._instances[scene][framework] = instance
            self._active_requests[cache_key] = 1

            logger.info(
                f"Created LLM instance for scene {scene}, provider {scene_config.provider}, framework {framework}"
            )
            return instance
        finally:
            self._cache_lock.release()

    async def release(self, scene: str, framework: str = "langchain"):
        """释放实例引用（调用方在使用完毕后调用）

        Args:
            scene: 场景名称
            framework: 框架名称
        """
        cache_key = f"{scene}:{framework}"
        try:
            await asyncio.wait_for(
                self._cache_lock.acquire(), timeout=self.LOCK_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning(f"Failed to acquire lock for release of {cache_key}")
            return

        try:
            count = self._active_requests.get(cache_key, 0)
            if count > 0:
                self._active_requests[cache_key] = count - 1
                # 引用计数归零时触发清理检查
                if self._active_requests[cache_key] == 0:
                    await self._try_cleanup_deprecated()
        finally:
            self._cache_lock.release()

    def _on_config_changed_sync(self, event: ConfigChangedEvent):
        """配置变更事件同步入口（安全调度异步 handler）"""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._on_config_changed(event))
        except RuntimeError:
            logger.warning(
                "LLMServiceFactory config change skipped: no running event loop"
            )

    async def _on_config_changed(self, event: ConfigChangedEvent):
        """配置变更时重建实例（先校验新配置，再清空缓存）

        Args:
            event: 配置变更事件
        """
        # 检查 changed_keys 是否包含 llm 相关配置
        changed_keys = getattr(event, "changed_keys", [])
        if not any(key.startswith("llm") for key in changed_keys):
            return

        # 使用独立的配置锁，避免与缓存操作死锁
        try:
            await asyncio.wait_for(
                self._config_lock.acquire(), timeout=self.LOCK_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning("Failed to acquire config lock for hot reload")
            return

        try:
            # 先校验新配置
            try:
                full_config = self.config_manager.get_full_config()
                scene_names = [
                    "report_generation",
                    "assessment",
                    "validation",
                    "metadata_extraction",
                    "query_rewrite",
                    "query_routing",
                    "content_generation",
                    "vl_parsing",
                    "ml_scoring",
                    "rag_eval",
                    "knowledge_qa",
                ]

                from src.config.modules.models.llm import LLMSceneConfig

                for scene_name in scene_names:
                    scene_config_data = full_config.get(f"llm_{scene_name}", {})
                    if scene_config_data:
                        try:
                            LLMSceneConfig(**scene_config_data)
                        except Exception as e:
                            logger.error(f"Invalid config for scene {scene_name}: {e}")
                            return  # 拒绝无效配置，保留旧实例
            except Exception as e:
                logger.error(f"Failed to validate new config: {e}")
                return

            logger.info(
                "LLM config changed and validated, starting instance rebuild..."
            )

            # 增加代际计数
            self._current_generation += 1
            current_gen = self._current_generation

            # 标记旧实例为 deprecated，使用代际计数追踪
            async with self._cache_lock:
                for scene, frameworks in self._instances.items():
                    for framework, instance in frameworks.items():
                        cache_key = f"{scene}:{framework}"
                        current_refs = self._active_requests.get(cache_key, 0)
                        self._deprecated_instances[cache_key] = {
                            "instance": instance,
                            "ref_count": current_refs,
                            "generation": current_gen - 1,  # 旧代际
                        }

                # 清空现有缓存
                self._instances.clear()
        finally:
            self._config_lock.release()

    async def _try_cleanup_deprecated(self):
        """尝试清理引用计数归零的废弃实例"""
        to_remove = []
        for cache_key, data in self._deprecated_instances.items():
            current_ref = self._active_requests.get(cache_key, 0)
            if current_ref <= 0:
                instance = data["instance"]
                try:
                    # 显式释放资源（若支持）
                    if hasattr(instance, "dispose"):
                        if asyncio.iscoroutinefunction(instance.dispose):
                            await instance.dispose()
                        else:
                            instance.dispose()
                    logger.debug(f"Disposed deprecated LLM instance: {cache_key}")
                except Exception as e:
                    logger.warning(f"Failed to dispose instance {cache_key}: {e}")
                to_remove.append(cache_key)

        for cache_key in to_remove:
            del self._deprecated_instances[cache_key]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} deprecated LLM instances")

    async def shutdown(self):
        """优雅关闭：等待活跃请求完成后清理所有实例"""
        self._shutdown = True
        logger.info("LLMServiceFactory shutting down...")

        # 等待活跃请求完成（最多等待 30 秒）
        for _ in range(30):
            total_active = sum(self._active_requests.values())
            if total_active == 0:
                break
            await asyncio.sleep(1)

        # 强制清理所有实例
        async with self._cache_lock:
            for scene, frameworks in self._instances.items():
                for framework, instance in frameworks.items():
                    if hasattr(instance, "dispose"):
                        try:
                            if asyncio.iscoroutinefunction(instance.dispose):
                                await instance.dispose()
                            else:
                                instance.dispose()
                        except Exception as e:
                            logger.warning(
                                f"Failed to dispose instance {scene}:{framework}: {e}"
                            )

            self._instances.clear()
            self._deprecated_instances.clear()
            self._active_requests.clear()

        logger.info("LLMServiceFactory shutdown complete")


# ===== 向后兼容：保留旧的类方法接口 =====

_legacy_factory: Optional[LLMServiceFactory] = None


def _get_legacy_factory() -> LLMServiceFactory:
    """获取遗留工厂实例（向后兼容）"""
    global _legacy_factory
    if _legacy_factory is None:
        from src.config.core.manager import config_manager
        from src.core.llm.provider_registry import ProviderRegistry

        provider_registry = ProviderRegistry()
        _legacy_factory = LLMServiceFactory(config_manager, provider_registry)
    return _legacy_factory


class LLMServiceFactoryCompat:
    """LLM 服务工厂兼容层（保留旧的类方法接口）"""

    _instances: dict[str, LLMService] = {}
    _raw_instances: dict[str, Any] = {}

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
        创建 LLM 服务实例（向后兼容）

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
        model_name = model_name or "qwen-plus"

        from src.config import settings

        # 自动识别提供商：deepseek 前缀走官方 DeepSeek API，其余走 DashScope
        if model_name.startswith("deepseek"):
            raw_llm = cls._create_deepseek_instance(model_name, temperature, max_tokens)
            instance = LangChainLLMAdapter(raw_llm, model_name)
            logger.info(f"DeepSeek 官方 LLM 实例已创建：{model_name}")
        else:
            from src.core.llm.adapters.dashscope_multimodal import \
                DashScopeMultiModalAdapter

            instance = DashScopeMultiModalAdapter(
                model=model_name,
                api_key=settings.dashscope_api_key,
                multimodal_prefixes=settings.llm_multimodal_model_prefixes,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            logger.info(f"DashScope MultiModal LLM 实例已创建：{model_name}")

        # 缓存实例
        cls._instances[cache_key] = instance

        return instance

    @staticmethod
    def _create_dashscope_instance(
        model_name: str,
        temperature: float,
        max_tokens: int,
    ):
        """创建 DashScope ChatOpenAI 实例（内部工厂方法，避免重复代码）。"""
        from src.config import settings
        from langchain_openai import ChatOpenAI

        class DashScopeChatOpenAI(ChatOpenAI):
            """ChatOpenAI 子类：适配 DashScope 兼容端点的两个限制。

            1. DashScope 不支持 json_schema structured outputs，
               with_structured_output 默认 method 从 "json_schema" 改为 "function_calling"。
            2. qwen3.5/3.6 系列默认开启思考模式，思考模式不支持 tool_choice=required，
               因此禁用思考模式（extra_body: {thinking: {type: disabled}}）。
            """

            def with_structured_output(self, schema, *, method="function_calling", **kwargs):
                return super().with_structured_output(schema, method=method, **kwargs)

        return DashScopeChatOpenAI(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=True,
            api_key=settings.dashscope_api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            extra_body={"enable_thinking": False},
        )

    @classmethod
    def create_raw(
        cls,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        *,
        no_cache: bool = False,
    ) -> "BaseChatModel":
        """
        创建原始 LangChain BaseChatModel 实例（不包装为 LLMService）。

        用途：create_react_agent、bind_tools、with_structured_output 等
        需要直接操作 BaseChatModel 的场景。

        自动识别模型提供商：
        - deepseek* → DeepSeek API
        - 其他 → DashScope OpenAI 兼容端点

        Args:
            no_cache: 为 True 时创建独立实例不走缓存。
                      用于并行场景（如 plan_expand_parallel），
                      避免共享同一 httpx 连接导致串行。
        """
        model_name = model_name or "qwen-plus"

        if not no_cache:
            cache_key = f"raw:{model_name}:{temperature}"
            if cache_key in cls._raw_instances:
                return cls._raw_instances[cache_key]

        # 自动识别提供商
        if model_name.startswith("deepseek"):
            instance = cls._create_deepseek_instance(model_name, temperature, max_tokens)
            provider = "DeepSeek"
        else:
            instance = cls._create_dashscope_instance(model_name, temperature, max_tokens)
            provider = "DashScope"

        if not no_cache:
            cache_key = f"raw:{model_name}:{temperature}"
            cls._raw_instances[cache_key] = instance
            logger.info(f"原始 BaseChatModel 实例已创建（{provider}）：{model_name}")
        return instance

    @classmethod
    def _create_deepseek_instance(
        cls,
        model_name: str,
        temperature: float,
        max_tokens: int,
    ):
        """创建 DeepSeek ChatOpenAI 实例。"""
        from src.config import settings
        from langchain_openai import ChatOpenAI

        class DeepSeekChatOpenAI(ChatOpenAI):
            """DeepSeek 适配器：使用 json_object 模式实现结构化输出"""

            def with_structured_output(self, schema, *, method="function_calling", **kwargs):
                """使用 response_format=json_object 确保 JSON 输出，配合 JsonOutputParser 解析"""
                from langchain_core.output_parsers import JsonOutputParser

                json_llm = self.bind(response_format={"type": "json_object"})
                parser = JsonOutputParser(pydantic_object=schema)

                class StructuredLLM:
                    def __init__(self, llm, parser):
                        self._llm = llm
                        self._parser = parser

                    async def ainvoke(self, prompt, **kwargs):
                        from langchain_core.messages import HumanMessage

                        format_instructions = self._parser.get_format_instructions()
                        if isinstance(prompt, str):
                            enhanced_prompt = f"{prompt}\n\n{format_instructions}"
                        elif isinstance(prompt, list):
                            enhanced_prompt = f"{prompt[-1].content}\n\n{format_instructions}"
                            prompt = prompt[:-1] + [HumanMessage(content=enhanced_prompt)]
                        else:
                            enhanced_prompt = f"{prompt}\n\n{format_instructions}"

                        response = await self._llm.ainvoke(prompt, **kwargs)
                        content = getattr(response, "content", "") or ""

                        if not content or not content.strip():
                            raise ValueError("DeepSeek 返回空内容")

                        import json as _json
                        try:
                            return self._parser.parse(content)
                        except Exception:
                            try:
                                return _json.loads(content)
                            except _json.JSONDecodeError:
                                raise ValueError(
                                    f"DeepSeek 结构化输出解析失败: {content[:300]}"
                                )

                    def invoke(self, prompt, **kwargs):
                        import asyncio
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                import concurrent.futures
                                future = asyncio.run_coroutine_threadsafe(
                                    self.ainvoke(prompt, **kwargs), loop
                                )
                                return future.result()
                        except RuntimeError:
                            pass
                        return asyncio.run(self.ainvoke(prompt, **kwargs))

                return StructuredLLM(json_llm, parser)

        return DeepSeekChatOpenAI(
            model=model_name,
            temperature=temperature,
            streaming=True,
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
            extra_body={
                "thinking": {"type": "disabled"},
                "max_tokens": max_tokens,
            },
        )

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
