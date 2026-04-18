import json

from src.core.redis_client import RedisClient
from src.utils.logger import logger


class TaskStatusService:
    """任务状态管理服务（基于Redis）"""
    
    def __init__(self, prefix: str = "upload:"):
        self.prefix = prefix
        self.redis_client = RedisClient.get_client()
    
    def _build_key(self, task_id: str) -> str:
        """构建Redis键名"""
        return f"{self.prefix}{task_id}"
    
    async def set_status(self, task_id: str, status: dict, ttl: int = 3600):
        """设置任务状态"""
        key = self._build_key(task_id)
        try:
            await self.redis_client.setex(key, ttl, json.dumps(status, ensure_ascii=False))
            logger.info(f"任务状态已设置: {task_id}")
        except Exception as e:
            logger.error(f"设置任务状态失败: {task_id}, 错误: {e}")
            raise
    
    async def get_status(self, task_id: str) -> dict | None:
        """获取任务状态"""
        key = self._build_key(task_id)
        try:
            value = await self.redis_client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            logger.error(f"获取任务状态失败: {task_id}, 错误: {e}")
            return None
    
    async def update_status(self, task_id: str, updates: dict):
        """更新任务状态的部分字段"""
        key = self._build_key(task_id)
        try:
            value = await self.redis_client.get(key)
            if value is None:
                logger.warning(f"任务不存在，无法更新: {task_id}")
                return
            
            status = json.loads(value)
            status.update(updates)
            
            # 保持原有的TTL
            ttl = await self.redis_client.ttl(key)
            if ttl < 0:
                ttl = 3600
            
            await self.redis_client.setex(key, ttl, json.dumps(status, ensure_ascii=False))
            logger.info(f"任务状态已更新: {task_id}")
        except Exception as e:
            logger.error(f"更新任务状态失败: {task_id}, 错误: {e}")
            raise
    
    async def delete_status(self, task_id: str):
        """删除任务状态"""
        key = self._build_key(task_id)
        try:
            await self.redis_client.delete(key)
            logger.info(f"任务状态已删除: {task_id}")
        except Exception as e:
            logger.error(f"删除任务状态失败: {task_id}, 错误: {e}")
            raise
    
    async def list_statuses(self, prefix: str | None = None) -> list[dict]:
        """列出所有任务状态"""
        pattern = f"{self.prefix}{prefix or ''}*"
        try:
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            statuses = []
            for key in keys:
                value = await self.redis_client.get(key)
                if value:
                    status = json.loads(value)
                    # 从key中提取task_id
                    task_id = key.replace(self.prefix, "", 1)
                    status["task_id"] = task_id
                    statuses.append(status)
            
            return statuses
        except Exception as e:
            logger.error(f"列出任务状态失败: {e}")
            return []


# 全局单例
task_status_service = TaskStatusService()
