"""清理旧服务写入的 Redis Key

迁移到统一任务状态管理后，旧服务写入的 Redis Key 不再使用。
此脚本用于清理这些旧 Key，释放 Redis 内存。

旧 Key 模式：
- upload:* - 旧上传任务 Key
- rag_eval:export:* - 旧导出任务 Key

新 Key 模式：
- task:upload:{task_id}
- task:export:{task_id}
- task:draft_generation:{task_id}
- task:test_run:{task_id}
- task:active:{task_type}
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "src"))

from src.core.redis_client import RedisClient
from src.utils.logger import logger

# 旧 Key 模式列表
OLD_KEY_PATTERNS = [
    "upload:*",           # 旧上传任务 Key
    "rag_eval:export:*",  # 旧导出任务 Key
]


async def cleanup_old_keys():
    """清理旧服务写入的 Redis Key"""
    redis_client = RedisClient.get_client()
    total_cleaned = 0

    for pattern in OLD_KEY_PATTERNS:
        count = 0
        async for key in redis_client.scan_iter(match=pattern):
            await redis_client.delete(key)
            count += 1
        logger.info(f"Cleaned up {count} keys matching {pattern}")
        total_cleaned += count

    logger.info(f"Total cleaned: {total_cleaned} old Redis keys")
    return total_cleaned


if __name__ == "__main__":
    result = asyncio.run(cleanup_old_keys())
    print(f"清理完成，共删除 {result} 个旧 Redis Key")
