import sys
from pathlib import Path
from loguru import logger
from src.config.settings import settings as log_config

# 确保日志目录存在
LOG_PATH = Path(log_config.LOG_FILE).parent
LOG_PATH.mkdir(parents=True, exist_ok=True)

# 移除默认的控制台处理器（避免重复输出）
logger.remove()

# 重新添加控制台日志（开发环境使用，带颜色）
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=log_config.LOG_LEVEL,
    colorize=True,
)

# 添加文件日志（按天切割 + 保留7天 + 压缩）
logger.add(
    LOG_PATH.joinpath("{time:YYYY-MM-DD}.log"),
    level=log_config.LOG_LEVEL,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    rotation="00:00",  # 每天零点切割
    retention="7 days",  # 保留7天
    compression="gz",  # 压缩旧日志
    enqueue=True,  # 异步写入（避免阻塞请求）
    backtrace=True,  # 记录异常回溯
    diagnose=True,  # 诊断信息（如变量值）
)

# 导出 logger
__all__ = ["logger"]
