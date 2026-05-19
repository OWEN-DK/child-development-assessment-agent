"""配置模块入口

统一的配置类，聚合所有拆分后的配置。
"""

from typing import Any, Dict, List

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from src.config.core.metadata import ConfigFieldMetadata
from src.config.modules.app import AppSettings
from src.config.modules.database import database_settings
from src.config.modules.logging import LogSettings
from src.config.modules.models.embedding import EmbeddingSettings
from src.config.modules.models.llm import LLMSettings
from src.config.modules.models.ml_scoring import MLScoringSettings
from src.config.modules.paths import PathSettings
from src.config.modules.rag.chunking import RagChunkingSettings
from src.config.modules.rag.core import RagCoreSettings
from src.config.modules.rag.pageindex import PageIndexSettings
from src.config.modules.rag.pipeline import RagPipelineSettings
from src.config.modules.rag.retrieval import RagRetrievalSettings
from src.config.modules.rag.vector_store import VectorStoreSettings
from src.config.modules.rag.testing import TestCaseGenerationConfig
from src.config.modules.redis import redis_settings
from src.config.modules.tracing import TracingConfig
from src.config.rules.rules import rules

BASE_DIR = __import__("pathlib").Path(__file__).parent.parent.parent.resolve()


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
    TestCaseGenerationConfig,
):
    """统一的配置类，聚合所有拆分后的配置"""

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
        elif field_name.startswith("draft_"):
            return "rag.testing"
        elif field_name.startswith((
            "default_domains", "default_age_stages", "default_drafts_per_combination",
            "default_query_types", "default_difficulty_levels", "default_model",
            "deduplication_threshold", "batch_size", "combination_interval_seconds",
            "max_concurrent_tasks", "max_tokens_per_generation", "max_memory_mb",
            "max_llm_retries", "supported_domains", "age_stages", "query_types",
            "difficulty_levels", "enable_breakpoint_resume", "enable_quality_check",
            "enable_relevance_check",
        )):
            return "rag.testing"
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
            "query_router_",
            "fusion_",
            "rag_layered_content_",
            "bm25_scale_factor",
            "hybrid_weight",
            "rag_chunk_",
            "semantic_splitter_",
            "embedding_batch_size",
            "embedding_use_async_batch",
            "embedding_async_batch_threshold",
            "rule_",
            # LLM 相关（改为热加载）
            "model_",
            "llm_",
            "dashscope_api_key",
            "llm_providers",
            "llm_scene_configs",
            "model_pricing",
            # 草稿生成配置（热加载）
            "draft_",
            "default_domains", "default_age_stages", "default_drafts_per_combination",
            "default_query_types", "default_difficulty_levels", "default_model",
            "deduplication_threshold", "batch_size", "combination_interval_seconds",
            "max_concurrent_tasks", "max_tokens_per_generation", "max_memory_mb",
            "max_llm_retries", "supported_domains", "age_stages", "query_types",
            "difficulty_levels", "enable_breakpoint_resume", "enable_quality_check",
            "enable_relevance_check",
        )
        cold_reload_prefixes = (
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
        parent_value=None,
    ) -> Dict[str, ConfigFieldMetadata]:
        """递归展开嵌套的 Pydantic 模型为扁平化的配置元数据"""
        metadata = {}
        if not hasattr(model_class, "model_fields"):
            return metadata

        for field_name, field_info in model_class.model_fields.items():
            full_key = f"{prefix}__{field_name}" if prefix else field_name
            annotation = field_info.annotation

            if hasattr(annotation, "model_fields"):
                nested_value = None
                if parent_value and hasattr(parent_value, field_name):
                    nested_value = getattr(parent_value, field_name)
                nested_meta = self._expand_nested_model(
                    annotation, full_key, category, nested_value
                )
                metadata.update(nested_meta)
            else:
                type_name = (
                    annotation.__name__
                    if hasattr(annotation, "__name__")
                    else str(annotation)
                )

                current_value = None
                default_value = field_info.default

                if parent_value and hasattr(parent_value, field_name):
                    current_value = getattr(parent_value, field_name)
                    if (
                        current_value is None
                        or str(current_value) == "PydanticUndefined"
                    ):
                        current_value = (
                            default_value if default_value is not None else ""
                        )
                else:
                    current_value = default_value if default_value is not None else ""

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
        from pydantic_core import PydanticUndefined

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

            if (
                hasattr(annotation, "model_fields")
                and not str(annotation).startswith("Dict")
                and not str(annotation).startswith("List")
            ):
                current_value = getattr(self, field_name, None)
                nested_meta = self._expand_nested_model(
                    annotation, field_name, category, current_value
                )
                metadata.update(nested_meta)
            else:
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
                "merge_mode": self.rag_hybrid_merge_mode,
                "bm25_top_k": self.rag_hybrid_bm25_top_k,
                "vector_top_k": self.rag_hybrid_vector_top_k,
            },
            "cache": {
                "enabled": self.rag_cache_enabled,
                "max_size": self.rag_cache_max_size,
                "ttl_seconds": self.rag_cache_ttl_seconds,
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
        env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )


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


# 对外导出
from src.config.core.init import (init_embedding_model, start_config_watcher,
                                  validate_required_env_vars)
from src.config.core.singleton import get_settings, reload_settings

settings = get_settings()

# 初始化嵌入模型
init_embedding_model()

# 配置基础设施（按需导入）
from src.config.core.events import (ConfigChangedEvent, ConfigResetEvent,
                                    ConfigRollbackEvent)
from src.config.core.manager import ConfigManager, config_manager
from src.config.core.repository import ConfigRepository, JsonConfigRepository

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
    "init_embedding_model",
    "validate_required_env_vars",
    "compare_config_changes",
    "BASE_DIR",
]
