"""RAG Platform 统一配置模块

聚合所有领域拆分的配置子模块，通过多重继承构建统一的 Settings 类。
提供 Settings 单例、配置热重载、配置元数据等基础设施。
"""
from pathlib import Path
from typing import Any, Dict, List

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from src.config.core.metadata import ConfigFieldMetadata
from src.config.modules.app import AppSettings
from src.config.modules.database import DatabaseSettings, database_settings
from src.config.modules.jwt import JWTSettings
from src.config.modules.logging import LogSettings
from src.config.modules.models.llm import (
    LLMProviderConfig,
    LLMSceneConfig,
    LLMSettings,
    ModelPricingConfig,
)
from src.config.modules.paths import PathSettings
from src.config.modules.rag.core import RagCoreSettings
from src.config.modules.rag.retrieval import RagRetrievalSettings
from src.config.modules.redis import RedisSettings, redis_settings

BASE_DIR = Path(__file__).parent.parent.parent.resolve()


class Settings(
    AppSettings,
    LogSettings,
    PathSettings,
    JWTSettings,
    LLMSettings,
    RagCoreSettings,
    RagRetrievalSettings,
):
    """统一配置类

    通过多重继承聚合所有领域配置子模块。
    model_config 中的 env_file 在此声明一次，由 Python MRO 优先于各子模块的 model_config。
    """

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def rag_config(self) -> Dict[str, Any]:
        """向后兼容的嵌套字典，供 CacheCore 等使用"""
        return {
            "cache": {
                "enabled": self.rag_cache_enabled,
                "max_size": self.rag_cache_max_size,
                "ttl_seconds": self.rag_cache_ttl_seconds,
            },
        }

    def _infer_category(self, field_name: str) -> str:
        """根据字段名前缀推断配置分类"""
        if field_name.startswith(("app_", "host", "port", "debug", "environment")):
            return "app"
        elif field_name.startswith("log_"):
            return "logging"
        elif field_name.startswith(("data_dir", "rag_storage_", "rag_temp_")):
            return "paths"
        elif field_name.startswith("jwt_"):
            return "auth"
        elif field_name.startswith(("dashscope_", "openai_", "anthropic_", "deepseek_", "llm_", "model_")):
            return "models.llm"
        elif field_name.startswith("es_") or field_name.startswith("milvus_"):
            return "rag.vector_store"
        elif field_name.startswith("rag_cache_"):
            return "rag.cache"
        elif field_name.startswith("rag_monitoring_"):
            return "rag.monitoring"
        elif field_name.startswith("rag_reranker_"):
            return "rag.reranker"
        elif field_name.startswith("query_router_"):
            return "rag.query_router"
        elif field_name.startswith("fusion_"):
            return "rag.fusion"
        elif field_name.startswith("rag_dedup_"):
            return "rag.dedup"
        elif field_name.startswith("rag_search_"):
            return "rag.search"
        elif field_name.startswith(("rag_hybrid_", "rag_vector_", "rag_similarity_", "rag_min_result_", "rag_relative_", "bm25_")):
            return "rag.retrieval"
        elif field_name.startswith("rag_"):
            return "rag.core"
        return "other"

    def _is_hot_reloadable(self, field_name: str) -> bool:
        """判断字段是否支持热重载"""
        cold_prefixes = (
            "data_dir", "rag_storage_dir", "rag_temp_upload_dir",
            "log_", "database_url", "redis_url", "jwt_secret",
        )
        if field_name.startswith(cold_prefixes):
            return False
        return True

    def _get_affected_components(self, field_name: str) -> List[str]:
        """返回受影响的组件列表"""
        components = []
        if any(k in field_name for k in ("hybrid", "search", "bm25", "vector", "similarity", "min_result")):
            components.append("检索引擎")
        if "reranker" in field_name:
            components.append("重排序器")
        if "cache" in field_name:
            components.append("缓存系统")
        if "query_router" in field_name or "fusion" in field_name:
            components.append("查询路由与融合")
        if "dedup" in field_name:
            components.append("去重模块")
        if not components:
            components.append("通用配置")
        return components

    def get_all_config_metadata(self) -> Dict[str, ConfigFieldMetadata]:
        """获取全部配置字段的元数据（供前端配置管理页面使用）"""
        metadata = {}
        for field_name, field_info in self.model_fields.items():
            category = self._infer_category(field_name)
            hot_reloadable = self._is_hot_reloadable(field_name)
            annotation = field_info.annotation
            type_name = (
                annotation.__name__ if hasattr(annotation, "__name__") else str(annotation)
            )
            default_value = field_info.default
            current_value = getattr(self, field_name, None)

            metadata[field_name] = ConfigFieldMetadata(
                key=field_name,
                category=category,
                description=field_info.description or "",
                hot_reloadable=hot_reloadable,
                requires_restart=not hot_reloadable,
                affected_components=self._get_affected_components(field_name),
                field_type=type_name,
                default_value=default_value,
                current_value=current_value,
            )
        return metadata


def compare_config_changes(old: Settings, new: Settings) -> Dict[str, tuple]:
    """比较新旧配置差异"""
    changes = {}
    for field_name in old.model_fields.keys():
        old_value = getattr(old, field_name)
        new_value = getattr(new, field_name)
        if old_value != new_value:
            changes[field_name] = (old_value, new_value)
    return changes


# 单例管理
from src.config.core.singleton import get_settings, reload_settings

# 初始化
from src.config.core.init import validate_required_env_vars

# 配置管理器与事件
from src.config.core.events import (
    ConfigChangedEvent,
    ConfigFactoryResetEvent,
    ConfigResetEvent,
    ConfigRollbackEvent,
)
from src.config.core.manager import ConfigManager, config_manager

settings = get_settings()

__all__ = [
    # 核心
    "settings",
    "Settings",
    "get_settings",
    "reload_settings",
    "BASE_DIR",
    # 元数据
    "ConfigFieldMetadata",
    # 独立配置实例
    "database_settings",
    "redis_settings",
    "DatabaseSettings",
    "RedisSettings",
    # 配置管理器
    "config_manager",
    "ConfigManager",
    "compare_config_changes",
    # 事件
    "ConfigChangedEvent",
    "ConfigRollbackEvent",
    "ConfigResetEvent",
    "ConfigFactoryResetEvent",
    # 模型
    "LLMSceneConfig",
    "LLMProviderConfig",
    "ModelPricingConfig",
    # 初始化
    "validate_required_env_vars",
]
