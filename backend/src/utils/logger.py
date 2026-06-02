import logging
import sys
import uuid
from contextvars import ContextVar
from pathlib import Path

from loguru import logger

from src.config import settings as log_config

# TRACE_ID 上下文变量
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")

def get_trace_id() -> str:
    """获取当前请求的TRACE_ID"""
    return trace_id_var.get()

def set_trace_id(trace_id: str = None) -> str:
    """设置TRACE_ID，不传则自动生成"""
    if not trace_id:
        trace_id = str(uuid.uuid4()).replace("-", "")[:16]  # 16位短UUID
    trace_id_var.set(trace_id)
    return trace_id


class InterceptHandler(logging.Handler):
    """
    拦截标准 logging 模块的日志，重定向到 loguru
    """
    def emit(self, record):
        # 获取对应的 loguru 等级
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 查找日志消息的来源帧
        frame, depth = logging.currentframe(), 2
        while frame and (
            frame.f_code.co_filename == logging.__file__
            or frame.f_code.co_filename.endswith(("logging/__init__.py", "logging\\__init__.py"))
        ):
            frame = frame.f_back
            depth += 1

        logger.bind(
            name=record.name,
            function=record.funcName,
            line=record.lineno
        ).opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

# 确保日志目录存在
LOG_PATH = Path(log_config.log_file).parent
LOG_PATH.mkdir(parents=True, exist_ok=True)

# 移除默认的控制台处理器（避免重复输出）
logger.remove()

# 重新添加控制台日志（开发环境使用，带颜色）
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <magenta>{extra[trace_id]:<16}</magenta> | <level>{level: <8}</level> | <cyan>{extra[name]}</cyan>:<cyan>{extra[function]}</cyan>:<cyan>{extra[line]}</cyan> - <level>{message}</level>",
    level=log_config.log_level,
    colorize=True,
    filter=lambda record: "name" in record["extra"],
)
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <magenta>{extra[trace_id]:<16}</magenta> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=log_config.log_level,
    colorize=True,
    filter=lambda record: "name" not in record["extra"],
)

# 添加文件日志（按天切割 + 保留7天 + 压缩）
logger.add(
    LOG_PATH.joinpath("{time:YYYY-MM-DD}.log"),
    level=log_config.log_level,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {extra[trace_id]:<16} | {level: <8} | {extra[name]}:{extra[function]}:{extra[line]} - {message}",
    rotation="00:00",  # 每天零点切割
    retention="7 days",  # 保留7天
    compression="gz",  # 压缩旧日志
    enqueue=False,  # 同步写入（避免 macOS 信号量限制）
    backtrace=True,  # 记录异常回溯
    diagnose=True,  # 诊断信息（如变量值）
    filter=lambda record: "name" in record["extra"],
)
logger.add(
    LOG_PATH.joinpath("{time:YYYY-MM-DD}.log"),
    level=log_config.log_level,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {extra[trace_id]:<16} | {level: <8} | {name}:{function}:{line} - {message}",
    rotation="00:00",  # 每天零点切割
    retention="7 days",  # 保留7天
    compression="gz",  # 压缩旧日志
    enqueue=False,  # 同步写入（避免 macOS 信号量限制）
    backtrace=True,  # 记录异常回溯
    diagnose=True,  # 诊断信息（如变量值）
    filter=lambda record: "name" not in record["extra"],
)

# 全局绑定TRACE_ID到日志上下文
logger = logger.patch(lambda record: record["extra"].setdefault("trace_id", get_trace_id() or "-"))

# 拦截常见的标准日志，重定向到 loguru
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

# 清理现有的 handlers 并禁用 propagate
for logger_name in logging.root.manager.loggerDict.keys():
    logging_logger = logging.getLogger(logger_name)
    logging_logger.handlers = [InterceptHandler()]
    logging_logger.propagate = False

# 导出 logger
__all__ = ["logger"]

