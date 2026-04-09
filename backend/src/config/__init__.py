import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pydantic import Field
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

# 导入各个配置类
from .app_settings import AppSettings
from .model_settings import ModelSettings
from .rag_settings import RAGSettings
from .log_settings import LogSettings
from .path_settings import PathSettings
from .pageindex_settings import PageIndexSettings
from .query_fusion_settings import QueryFusionSettings
from .embedding_settings import EmbeddingSettings
from .vector_store_settings import VectorStoreSettings
from .semantic_splitter_settings import SemanticSplitterSettings
from .ml_scoring_settings import MLScoringSettings

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


class Settings(
    AppSettings,
    ModelSettings,
    RAGSettings,
    LogSettings,
    PathSettings,
    PageIndexSettings,
    QueryFusionSettings,
    EmbeddingSettings,
    VectorStoreSettings,
    SemanticSplitterSettings,
    MLScoringSettings,
):
    """统一的配置类，聚合所有拆分后的配置"""
    
    # 规则相关配置（合并到rules.py体系）
    rule_metadata_development_domains: List[str] = Field(
        default_factory=lambda: [
            "粗大动作", "精细动作", "认知能力", "语言发展", "社交情感", "感觉统合"
        ],
        description="儿童发展领域标签列表"
    )
    rule_metadata_age_patterns: List[str] = Field(
        default_factory=lambda: [
            r"(\d+)~(\d+)个月", r"(\d+)-(\d+)个月", r"适合(\d+)到(\d+)岁", 
            r"(\d+)岁左右", r"(\d+)月龄", r"(\d+)岁"
        ],
        description="规则提取年龄的正则表达式列表"
    )
    rule_metadata_difficulty_easy_threshold: int = Field(
        300,
        description="内容长度低于此值判定为简单难度"
    )
    rule_metadata_difficulty_hard_threshold: int = Field(
        1000,
        description="内容长度高于此值判定为困难难度"
    )

    def _infer_category(self, field_name: str) -> str:
        if field_name.startswith(("rag_hybrid_", "rag_search_", "rag_cache_")):
            return "混合检索配置"
        elif field_name.startswith("model_"):
            return "模型设置"
        elif field_name.startswith("rag_reranker_"):
            return "重排序配置"
        elif field_name.startswith(("rag_chunk_", "semantic_splitter_")):
            return "分块配置"
        elif field_name.startswith("embedding_"):
            return "Embedding配置"
        elif field_name.startswith("pageindex_"):
            return "PageIndex配置"
        elif field_name.startswith("rag_"):
            return "RAG配置"
        elif field_name.startswith("ml_"):
            return "ML评分配置"
        elif field_name.startswith("query_router_") or field_name.startswith("fusion_"):
            return "查询与融合配置"
        elif field_name.startswith("rule_metadata_"):
            return "规则元数据配置"
        elif field_name.startswith("log_"):
            return "日志配置"
        elif field_name.startswith("data_dir") or field_name.startswith("rag_storage_dir"):
            return "路径配置"
        elif field_name.startswith("rule_validation_"):
            return "校验规则配置"
        elif field_name.startswith("rule_assessment_"):
            return "评估规则配置"
        elif field_name.startswith("rule_scoring_"):
            return "评分规则配置"
        elif field_name.startswith("rule_preprocessing_"):
            return "预处理规则配置"
        elif field_name.startswith("rule_metadata_"):
            return "元数据提取规则配置"
        else:
            return "其他配置"

    def _is_hot_reloadable(self, field_name: str) -> bool:
        hot_reload_prefixes = (
            "rag_hybrid_", "rag_search_", "rag_cache_", "rag_reranker_",
            "rag_similarity_threshold", "rag_min_result_count",
            "rag_age_filter_", "query_router_", "fusion_",
            "rag_layered_content_", "bm25_scale_factor",
            "hybrid_weights", "rag_chunk_", "semantic_splitter_",
            "embedding_batch_size", "rule_",
        )
        cold_reload_prefixes = (
            "model_", "dashscope_api_key", "pageindex_",
            "rag_storage_dir", "data_dir", "log_",
            "vector_store_", "ml_scoring_model_path",
            "rag_upload_max_concurrent_tasks", "rag_temp_upload_dir",
            "rag_metadata_extraction_concurrency", "rag_vl_max_workers",
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

    def get_all_config_metadata(self) -> Dict[str, ConfigFieldMetadata]:
        metadata = {}
        for field_name, field_info in self.model_fields.items():
            category = self._infer_category(field_name)
            hot_reloadable = self._is_hot_reloadable(field_name)
            annotation = field_info.annotation
            type_name = annotation.__name__ if hasattr(annotation, '__name__') else str(annotation)
            metadata[field_name] = ConfigFieldMetadata(
                key=field_name,
                category=category,
                description=field_info.description or "",
                hot_reloadable=hot_reloadable,
                requires_restart=not hot_reloadable,
                affected_components=self._get_affected_components(field_name),
                field_type=type_name,
                default_value=field_info.default
            )
        return metadata

    @property
    def llm_models(self) -> Dict[str, str]:
        return {
            "report_generation": self.model_report_generation,
            "assessment": self.model_assessment,
            "validation": self.model_validation,
            "query_rewrite": self.model_query_rewrite,
            "metadata_extraction": self.model_metadata_extraction,
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
            }
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
                    # TODO: 集成事件总线，派发ConfigChangedEvent
                    
            return new_settings
        except Exception as e:
            logger.error(f"配置重载失败，保留原有配置: {e}")
            return _settings_instance if _settings_instance else Settings()

def compare_config_changes(old_settings: Settings, new_settings: Settings) -> Dict[str, tuple[Any, Any]]:
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
        if file_path.suffix in ('.py', '.env') and not file_path.name.startswith('__'):
            logger.info(f"检测到配置文件变更: {file_path}")
            reload_settings()

def start_config_watcher() -> Optional[Observer]:
    """启动配置文件监控
    如果watchdog库未安装，则返回None并记录警告
    """
    if not WATCHDOG_AVAILABLE:
        logger.warning("watchdog库未安装，配置热更新功能不可用，请安装后重试: pip install watchdog")
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
        logger.info("LlamaIndex嵌入模型初始化成功，使用模型: %s", settings.embedding_model_name)
    except Exception as e:
        logger.error(f"初始化嵌入模型失败: {e}")

# 自动初始化嵌入模型
init_embedding_model()


__all__ = [
    "Settings",
    "settings",
    "get_settings",
    "reload_settings",
    "start_config_watcher",
    "ConfigFieldMetadata",
]
