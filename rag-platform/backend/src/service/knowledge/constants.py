"""知识库模块常量定义"""

# 文件限制
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
MAX_BATCH_FILES = 50
MAX_BATCH_SIZE_BYTES = 200 * 1024 * 1024  # 200MB

# 解析限制
PARSE_TIMEOUT_SECONDS = 300  # 5 分钟
PARSE_RETRY_MAX = 1

# 分块限制
CHUNK_SIZE_MIN = 128
CHUNK_SIZE_MAX = 4096

# SSE 推送
REBUILD_SSE_HEARTBEAT_SECONDS = 15
REBUILD_STALE_TIMEOUT_SECONDS = 3600

# 支持的文件类型
SUPPORTED_FILE_TYPES = {"pdf", "txt", "markdown", "html", "epub"}

# 文件类型映射
FILE_TYPE_MAP = {
    ".pdf": "pdf",
    ".txt": "txt",
    ".md": "markdown",
    ".markdown": "markdown",
    ".html": "html",
    ".htm": "html",
    ".epub": "epub",
}
