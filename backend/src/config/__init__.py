import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pydantic import Field, BaseModel
from pydantic_settings import SettingsConfigDict
from threading import RLock
import asyncio

# 可选导入watchdog
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    WATCHDOG_AVAILABLE = True
except ImportError:
    Observer = None
    FileSystemEventHandler = object
    WATCHDOG_AVAILABLE = False

# 导入各个配置模块（新路径）
from .modules.app import AppSettings
from .modules.logging import LogSettings
from .modules.paths import PathSettings
from .modules.models.llm import LLMSettings
from .modules.models.embedding import EmbeddingSettings
from .modules.models.ml_scoring import MLScoringSettings
from .modules.rag.core import RagCoreSettings
from .modules.rag.retrieval import RagRetrievalSettings
from .modules.rag.chunking import RagChunkingSettings
from .modules.rag.vector_store import VectorStoreSettings
from .modules.rag.pageindex import PageIndexSettings
from .modules.rag.pipeline import RagPipelineSettings
from .modules.database import database_settings
from .modules.redis import redis_settings
from .modules.tracing import TracingConfig

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent.parent.parent.resolve()


@dataclass
class ConfigFieldMetadata:
    key: str
    category: str
    description: str
    hot_reloadable: bool
    requires_restart: bool
    affected_components: list[str]
    field_type: str
    default_value: Any
    current_value: Any = None  # 新增：当前值（用于嵌套配置）


class Settings(
    AppSettings,
    LogSettings,
    PathSettings,
    LLMSettings,
    EmbeddingSettings,
    MLScoringSettings,
    RagCoreSettings,
    RagRetrievalSettings,
    RagChunkingSettings,
    VectorStoreSettings,
    PageIndexSettings,
    RagPipelineSettings,
    TracingConfig,
):
    """统一的配置类，聚合所有拆分后的配置"""

    # 规则相关配置（合并到rules.py体系）
    rule_metadata_development_domains: List[str] = Field(
        default_factory=lambda: [
            "粗大动作",
            "精细动作",
            "认知能力",
            "语言发展",
            "社交情感",
            "感觉统合",
        ],
        description="儿童发展领域标签列表",
    )
    rule_metadata_age_patterns: List[str] = Field(
        default_factory=lambda: [
            r"(\d+)~(\d+)个月",
            r"(\d+)-(\d+)个月",
            r"适合(\d+)到(\d+)岁",
            r"(\d+)岁左右",
            r"(\d+)月龄",
            r"(\d+)岁",
        ],
        description="规则提取年龄的正则表达式列表",
    )
    rule_metadata_difficulty_easy_threshold: int = Field(
        300, description="内容长度低于此值判定为简单难度"
    )
    rule_metadata_difficulty_hard_threshold: int = Field(
        1000, description="内容长度高于此值判定为困难难度"
    )

    def _infer_category(self, field_name: str) -> str:
        if field_name.startswith(
            (
                "rag_hybrid_",
                "rag_search_",
                "rag_cache_",
                "rag_reranker_",
                "rag_age_filter_",
                "query_router_",
                "fusion_",
                "rag_similarity_threshold",
                "rag_min_result_count",
            )
        ):
            return "rag.retrieval"
        elif field_name.startswith("model_") or field_name.startswith("llm_"):
            return "models.llm"
        elif field_name.startswith(
            (
                "rag_chunk_",
                "semantic_splitter_",
                "rag_pdf_chunk_size",
                "rag_epub_chunk_target_size",
            )
        ):
            return "rag.chunking"
        elif field_name.startswith("embedding_"):
            return "models.embedding"
        elif field_name.startswith("pageindex_"):
            return "rag.pageindex"
        elif field_name.startswith(
            ("rag_vector_store_", "rag_vector_base_threshold", "rag_auto_persist_")
        ):
            return "rag.vector_store"
        elif field_name.startswith(
            (
                "rag_upload_",
                "rag_temp_upload_dir",
                "rag_metadata_extraction_concurrency",
                "rag_vl_max_workers",
                "rag_layered_content_",
                "rag_pipeline_",
            )
        ):
            return "rag.pipeline"
        elif field_name.startswith("rag_"):
            return "rag.core"
        elif field_name.startswith("ml_"):
            return "models.ml_scoring"
        elif field_name.startswith("log_"):
            return "logging"
        elif (
            field_name.startswith("data_dir")
            or field_name.startswith("rag_storage_dir")
            or field_name.startswith("path_")
        ):
            return "paths"
        elif field_name.startswith("rule_validation_"):
            return "rules.validation"
        elif field_name.startswith("rule_assessment_"):
            return "rules.assessment"
        elif field_name.startswith("rule_scoring_"):
            return "rules.scoring"
        elif field_name.startswith("rule_preprocessing_"):
            return "rules.preprocessing"
        elif field_name.startswith("rule_metadata_"):
            return "rules.metadata"
        elif field_name.startswith(("app_", "host", "port", "debug")):
            return "app"
        else:
            return "other"

    def _is_hot_reloadable(self, field_name: str) -> bool:
        hot_reload_prefixes = (
            "rag_hybrid_",
            "rag_search_",
            "rag_cache_",
            "rag_reranker_",
            "rag_similarity_threshold",
            "rag_min_result_count",
            "rag_age_filter_",
            "query_router_",
            "fusion_",
            "rag_layered_content_",
            "bm25_scale_factor",
            "hybrid_weights",
            "rag_chunk_",
            "semantic_splitter_",
            "embedding_batch_size",
            "rule_",
        )
        cold_reload_prefixes = (
            "model_",
            "llm_",
            "dashscope_api_key",
            "pageindex_",
            "rag_storage_dir",
            "data_dir",
            "log_",
            "vector_store_",
            "ml_scoring_model_path",
            "rag_upload_max_concurrent_tasks",
            "rag_temp_upload_dir",
            "rag_metadata_extraction_concurrency",
            "rag_vl_max_workers",
        )
        if field_name.startswith(hot_reload_prefixes):
            return True
        if field_name.startswith(cold_reload_prefixes):
            return False
        return True

    def _get_affected_components(self, field_name: str) -> list[str]:
        components = []
        if "hybrid" in field_name or "search" in field_name:
            components.append("混合检索引擎")
        if "reranker" in field_name:
            components.append("重排序器")
        if "chunk" in field_name or "splitter" in field_name:
            components.append("文档分块")
        if "embedding" in field_name:
            components.append("Embedding模型")
        if "cache" in field_name:
            components.append("缓存系统")
        if "age_filter" in field_name:
            components.append("年龄过滤")
        if "pageindex" in field_name:
            components.append("PageIndex服务")
        if "query_router" in field_name or "fusion" in field_name:
            components.append("查询路由与融合")
        if "layered_content" in field_name:
            components.append("分层内容生成")
        if not components:
            components.append("通用配置")
        return components

    def _expand_nested_model(
        self,
        model_class: type,
        prefix: str,
        category: str,
        parent_value: Optional[BaseModel] = None,
    ) -> Dict[str, ConfigFieldMetadata]:
        """递归展开嵌套的 Pydantic 模型为扁平化的配置元数据"""
        metadata = {}
        if not hasattr(model_class, "model_fields"):
            return metadata

        for field_name, field_info in model_class.model_fields.items():
            full_key = f"{prefix}__{field_name}" if prefix else field_name
            annotation = field_info.annotation

            # 检查是否是嵌套的 Pydantic BaseModel
            if hasattr(annotation, "model_fields"):
                # 递归展开嵌套模型
                nested_value = None
                if parent_value and hasattr(parent_value, field_name):
                    nested_value = getattr(parent_value, field_name)
                nested_meta = self._expand_nested_model(
                    annotation, full_key, category, nested_value
                )
                metadata.update(nested_meta)
            else:
                # 基础类型字段
                type_name = (
                    annotation.__name__
                    if hasattr(annotation, "__name__")
                    else str(annotation)
                )

                # 获取默认值和当前值
                # 优先使用 parent_value 中的实际值，如果没有则使用字段默认值
                current_value = None
                default_value = field_info.default

                if parent_value and hasattr(parent_value, field_name):
                    current_value = getattr(parent_value, field_name)
                    # 如果当前值是 PydanticUndefined，则使用默认值
                    if (
                        current_value is None
                        or str(current_value) == "PydanticUndefined"
                    ):
                        current_value = (
                            default_value if default_value is not None else ""
                        )
                else:
                    current_value = default_value if default_value is not None else ""

                # 如果默认值是 PydanticUndefined，尝试从当前值推断
                if default_value is None or str(default_value) == "PydanticUndefined":
                    default_value = current_value

                metadata[full_key] = ConfigFieldMetadata(
                    key=full_key,
                    category=category,
                    description=field_info.description or "",
                    hot_reloadable=self._is_hot_reloadable(full_key),
                    requires_restart=not self._is_hot_reloadable(full_key),
                    affected_components=self._get_affected_components(full_key),
                    field_type=type_name,
                    default_value=default_value,
                    current_value=current_value,
                )

        return metadata

    def get_all_config_metadata(self) -> Dict[str, ConfigFieldMetadata]:
        metadata = {}
        for field_name, field_info in self.model_fields.items():
            category = self._infer_category(field_name)
            hot_reloadable = self._is_hot_reloadable(field_name)
            annotation = field_info.annotation
            type_name = (
                annotation.__name__
                if hasattr(annotation, "__name__")
                else str(annotation)
            )

            # 检查是否是嵌套的 Pydantic BaseModel（非 Dict/List 类型）
            if (
                hasattr(annotation, "model_fields")
                and not str(annotation).startswith("Dict")
                and not str(annotation).startswith("List")
            ):
                # 递归展开嵌套模型
                current_value = getattr(self, field_name, None)
                nested_meta = self._expand_nested_model(
                    annotation, field_name, category, current_value
                )
                metadata.update(nested_meta)
            else:
                # 基础类型或 Dict/List 类型，保持原有逻辑
                # 对于有 default_factory 的字段，调用 factory 获取默认值
                from pydantic_core import PydanticUndefined

                default_value = field_info.default
                if (
                    default_value is PydanticUndefined
                    and hasattr(field_info, "default_factory")
                    and field_info.default_factory is not None
                ):
                    try:
                        default_value = field_info.default_factory()
                    except Exception:
                        default_value = {}

                metadata[field_name] = ConfigFieldMetadata(
                    key=field_name,
                    category=category,
                    description=field_info.description or "",
                    hot_reloadable=hot_reloadable,
                    requires_restart=not hot_reloadable,
                    affected_components=self._get_affected_components(field_name),
                    field_type=type_name,
                    default_value=default_value,
                )

        # 特殊处理：将 llm_scene_configs property 展开为可编辑的配置项
        if hasattr(self, "llm_scene_configs"):
            scene_configs = self.llm_scene_configs
            for scene_name, scene_config in scene_configs.items():
                scene_meta = self._expand_nested_model(
                    type(scene_config),
                    f"llm_scene_configs__{scene_name}",
                    "models.llm",
                    scene_config,
                )
                metadata.update(scene_meta)

        return metadata

    @property
    def llm_models(self) -> Dict[str, str]:
        """获取各场景的模型名称（向后兼容）"""
        return {
            "report_generation": self.model_report_generation.model
            if hasattr(self.model_report_generation, "model")
            else self.model_report_generation,
            "assessment": self.model_assessment.model
            if hasattr(self.model_assessment, "model")
            else self.model_assessment,
            "validation": self.model_validation.model
            if hasattr(self.model_validation, "model")
            else self.model_validation,
            "query_rewrite": self.model_query_rewrite.model
            if hasattr(self.model_query_rewrite, "model")
            else self.model_query_rewrite,
            "metadata_extraction": self.model_metadata_extraction.model
            if hasattr(self.model_metadata_extraction, "model")
            else self.model_metadata_extraction,
            "vl_parsing": self.model_vl_parsing.model
            if hasattr(self.model_vl_parsing, "model")
            else self.model_vl_parsing,
            "query_classification": self.model_query_classification.model
            if hasattr(self.model_query_classification, "model")
            else self.model_query_classification,
            "test_case_generation": self.model_report_generation.model
            if hasattr(self.model_report_generation, "model")
            else self.model_report_generation,
        }

    @property
    def rag_config(self) -> Dict[str, Any]:
        return {
            "hybrid_retrieval": {
                "bm25_weight": self.rag_hybrid_bm25_weight,
                "vector_weight": self.rag_hybrid_vector_weight,
                "merge_mode": self.rag_hybrid_merge_mode,  # AND/OR
                "bm25_top_k": self.rag_hybrid_bm25_top_k,
                "vector_top_k": self.rag_hybrid_vector_top_k,
            },
            "cache": {
                "enabled": self.rag_cache_enabled,
                "max_size": self.rag_cache_max_size,  # Maximum number of cache entries
                "ttl_seconds": self.rag_cache_ttl_seconds,  # Cache expiration time in seconds (1 hour)
            },
            "query_rewrite": {"enabled": self.rag_query_rewrite_enabled},
            "filters": {
                "similarity_threshold": self.rag_similarity_threshold,
                "min_result_count": self.rag_min_result_count,
            },
            "layered_content": {
                "enabled": self.rag_layered_content_enabled,
                "enable_llm_generation": self.rag_layered_content_enable_llm_generation,
                "enable_local_fallback": self.rag_layered_content_enable_local_fallback,
                "l0_max_length": self.rag_layered_content_l0_max_length,
                "l1_max_length": self.rag_layered_content_l1_max_length,
                "batch_size": self.rag_layered_content_batch_size,
                "large_batch_threshold": self.rag_layered_content_large_batch_threshold,
                "large_batch_size": self.rag_layered_content_large_batch_size,
                "concurrency_limit": self.rag_layered_content_concurrency_limit,
            },
        }

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env.dev"), env_file_encoding="utf-8", extra="ignore"
    )


# 配置实例管理
_settings_instance = None
_lock = RLock()


def get_settings() -> Settings:
    """获取配置单例"""
    global _settings_instance
    if _settings_instance is None:
        with _lock:
            if _settings_instance is None:
                _settings_instance = Settings()
    return _settings_instance


def reload_settings() -> Settings:
    """重新加载配置并返回新的Settings实例

    实现失败回退机制：重载失败时返回原有配置实例
    """
    global _settings_instance
    with _lock:
        try:
            new_settings = Settings()
            # 执行Pydantic校验，确保配置合法
            new_settings.model_validate(new_settings.model_dump())
            old_settings = _settings_instance
            _settings_instance = new_settings
            logger.info("配置重载成功")

            # 对比变更并派发事件
            if old_settings:
                changed_fields = compare_config_changes(old_settings, new_settings)
                if changed_fields:
                    logger.info(f"配置变更字段: {list(changed_fields.keys())}")
                    # 通过公共方法同步更新 ConfigManager 缓存
            from .core.manager import config_manager

            config_manager.sync_cache_from_settings(new_settings)

            return new_settings
        except Exception as e:
            logger.error(f"配置重载失败，保留原有配置: {e}")
            return _settings_instance if _settings_instance else Settings()


def compare_config_changes(
    old_settings: Settings, new_settings: Settings
) -> Dict[str, tuple[Any, Any]]:
    """比较新旧配置的差异"""
    changes = {}
    for field_name in old_settings.model_fields.keys():
        old_value = getattr(old_settings, field_name)
        new_value = getattr(new_settings, field_name)
        if old_value != new_value:
            changes[field_name] = (old_value, new_value)
    return changes


# 文件系统监控实现
class ConfigFileChangeHandler(FileSystemEventHandler):
    """配置文件变更处理器"""

    def on_modified(self, event):
        if event.is_directory:
            return
        file_path = Path(event.src_path)
        if file_path.suffix in (".py", ".env") and not file_path.name.startswith("__"):
            logger.info(f"检测到配置文件变更: {file_path}")
            reload_settings()


def start_config_watcher() -> Optional[Observer]:
    """启动配置文件监控
    如果watchdog库未安装，则返回None并记录警告
    """
    if not WATCHDOG_AVAILABLE:
        logger.warning(
            "watchdog库未安装，配置热更新功能不可用，请安装后重试: pip install watchdog"
        )
        return None

    event_handler = ConfigFileChangeHandler()
    observer = Observer()
    # 监控配置目录
    config_dir = Path(__file__).parent
    observer.schedule(event_handler, str(config_dir), recursive=False)
    # 监控.env文件
    env_file = BASE_DIR / ".env.dev"
    if env_file.exists():
        observer.schedule(event_handler, str(env_file), recursive=False)
    observer.start()
    logger.info("配置文件监控已启动")
    return observer


# 对外导出统一的settings实例
settings = get_settings()


def validate_required_env_vars() -> list[str]:
    """校验必需的环境变量是否已配置

    注意：
    1. 此函数在 settings 创建之后调用
    2. LLM API Key 优先从数据库 system_configs 表读取（符合 CLAUDE.md 配置管理规范）
    3. 环境变量作为兜底方案（数据库不可用时）

    返回:
        缺失的环境变量名称列表
    """
    import os

    missing = []

    # LLM 相关：优先检查 settings（来自数据库），兜底检查环境变量
    settings_key = getattr(settings, "dashscope_api_key", None)
    env_key = os.environ.get("DASHSCOPE_API_KEY")
    if not settings_key and not env_key:
        missing.append("DASHSCOPE_API_KEY")

    return missing


# 初始化嵌入模型（保持与原逻辑一致）
def init_embedding_model():
    """初始化嵌入模型，配置LlamaIndex使用通义千问嵌入模型"""
    try:
        from llama_index.core import Settings as LlamaSettings
        from src.core.embedding import SafeDashScopeEmbedding

        LlamaSettings.embed_model = SafeDashScopeEmbedding(
            model_name=settings.embedding_model_name,
            api_key=settings.dashscope_api_key,
            embed_batch_size=settings.embedding_batch_size,
        )
        logger.info(
            "LlamaIndex嵌入模型初始化成功，使用模型: %s", settings.embedding_model_name
        )
    except Exception as e:
        logger.error(f"初始化嵌入模型失败: {e}")


# 自动初始化嵌入模型
init_embedding_model()

# 业务规则（独立单例）
from .rules.rules import rules

# 配置基础设施（按需导入）
from .core.manager import ConfigManager, config_manager
from .core.repository import ConfigRepository, JsonConfigRepository
from .core.events import ConfigChangedEvent, ConfigRollbackEvent, ConfigResetEvent


__all__ = [
    "settings",
    "rules",
    "Settings",
    "get_settings",
    "reload_settings",
    "start_config_watcher",
    "ConfigFieldMetadata",
    "config_manager",
    "ConfigManager",
    "ConfigRepository",
    "JsonConfigRepository",
    "ConfigChangedEvent",
    "ConfigRollbackEvent",
    "ConfigResetEvent",
    "database_settings",
    "redis_settings",
]
