"""LLM 调用日志采集器 - 使用队列防止关闭时数据丢失"""

import asyncio

from src.service.monitoring_service import MonitoringService
from src.utils.logger import logger


class LLMLogCollector:
    """LLM 调用日志采集器（使用队列防止关闭时数据丢失）"""

    _queue: asyncio.Queue = None
    _worker_task: asyncio.Task = None
    _monitoring: MonitoringService = None
    _ever_started: bool = False

    @classmethod
    def start(cls):
        """启动采集器（应用启动时调用）"""
        if cls._ever_started:
            logger.debug("LLM 日志采集器已初始化过，跳过重复启动")
            return
        cls._ever_started = True
        cls._queue = asyncio.Queue(maxsize=10000)
        cls._monitoring = MonitoringService()
        cls._worker_task = asyncio.create_task(cls._worker())
        logger.info("LLM 日志采集器已启动")

    @classmethod
    async def stop(cls):
        """停止采集器（应用关闭时调用，确保数据全部写入）"""
        if cls._queue is None:
            logger.debug("LLM 日志采集器未运行，跳过停止")
            return
        if cls._worker_task:
            await cls._queue.put(None)
            await cls._worker_task
            logger.info("LLM 日志采集器已停止")

    @classmethod
    async def submit(cls, log_data: dict):
        """提交日志到队列"""
        if cls._queue is None:
            # If the queue is not initialized, we can't collect logs.
            # This happens in scripts or tests that don't start the collector.
            logger.warning("LLM 日志采集器未启动，跳过日志记录")
            return
            
        try:
            await cls._queue.put(log_data)
        except asyncio.QueueFull:
            logger.warning("LLM 日志队列已满，丢弃日志")

    @classmethod
    async def _worker(cls):
        """后台工作协程"""
        while True:
            log_data = await cls._queue.get()
            if log_data is None:
                break

            try:
                await cls._monitoring.log_llm_call(**log_data)
            except Exception as e:
                logger.error(f"LLM 日志写入失败: {e}")
