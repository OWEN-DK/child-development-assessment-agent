"""配置初始化模块

负责嵌入模型初始化、配置监听器等启动时任务。
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    Observer = None
    FileSystemEventHandler = object
    WATCHDOG_AVAILABLE = False


def init_embedding_model() -> None:
    """初始化嵌入模型，配置LlamaIndex使用通义千问嵌入模型"""
    try:
        from llama_index.core import Settings as LlamaSettings

        from src.config import settings
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

    from src.config import settings

    missing = []

    settings_key = getattr(settings, "dashscope_api_key", None)
    env_key = os.environ.get("DASHSCOPE_API_KEY")
    if not settings_key and not env_key:
        missing.append("DASHSCOPE_API_KEY")

    return missing


class ConfigFileChangeHandler(FileSystemEventHandler):
    """配置文件变更处理器"""

    def on_modified(self, event):
        if event.is_directory:
            return
        file_path = Path(event.src_path)
        if file_path.suffix in (".py", ".env") and not file_path.name.startswith("__"):
            logger.info(f"检测到配置文件变更: {file_path}")
            from src.config import reload_settings

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

    from src.config import BASE_DIR

    event_handler = ConfigFileChangeHandler()
    observer = Observer()
    config_dir = Path(__file__).parent.parent
    observer.schedule(event_handler, str(config_dir), recursive=False)
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        observer.schedule(event_handler, str(env_file), recursive=False)
    observer.start()
    logger.info("配置文件监控已启动")
    return observer
