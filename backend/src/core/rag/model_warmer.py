"""
模型预热器 (Phase D-3)

服务启动时后台异步加载 Cross-Encoder 模型，消除懒加载延迟。
"""

import asyncio
import time
from typing import Optional

from src.utils.logger import logger


class ModelWarmer:
    """Cross-Encoder 模型预热器"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.model_name = model_name
        self._model = None
        self._is_warmed = False
        self._warmup_failed = False
        self._warmup_start_time: Optional[float] = None
        self._warmup_duration: Optional[float] = None

    async def warmup(self) -> bool:
        """
        后台异步预热模型

        Returns:
            bool: 是否成功
        """
        if self._is_warmed or self._warmup_failed:
            return self._is_warmed

        self._warmup_start_time = time.time()
        logger.info(f"开始预热 Cross-Encoder 模型: {self.model_name}")

        try:
            loop = asyncio.get_event_loop()
            self._model = await loop.run_in_executor(None, self._load_model_sync)

            if self._model is not None:
                self._is_warmed = True
                self._warmup_duration = time.time() - self._warmup_start_time
                logger.info(
                    f"Cross-Encoder 模型预热成功: {self.model_name}，"
                    f"耗时 {self._warmup_duration:.2f}s"
                )
                return True
            else:
                self._warmup_failed = True
                logger.error(f"Cross-Encoder 模型预热失败: {self.model_name}")
                return False

        except Exception as e:
            self._warmup_failed = True
            self._warmup_duration = time.time() - self._warmup_start_time
            logger.error(f"Cross-Encoder 模型预热异常: {self.model_name}, 错误: {e}")
            return False

    def _load_model_sync(self):
        """同步加载模型（在 executor 中运行）"""
        try:
            from sentence_transformers import CrossEncoder

            return CrossEncoder(self.model_name)
        except ImportError:
            logger.error("sentence-transformers not installed")
            return None
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            return None

    def get_model(self):
        """获取预热后的模型"""
        return self._model

    @property
    def is_warmed(self) -> bool:
        return self._is_warmed

    @property
    def warmup_failed(self) -> bool:
        return self._warmup_failed

    @property
    def warmup_duration(self) -> Optional[float]:
        return self._warmup_duration

    def get_status(self) -> dict:
        """获取预热状态"""
        return {
            "model_name": self.model_name,
            "is_warmed": self._is_warmed,
            "warmup_failed": self._warmup_failed,
            "warmup_duration": self._warmup_duration,
        }


global_warmer: Optional[ModelWarmer] = None


def get_model_warmer(model_name: str = "BAAI/bge-reranker-v2-m3") -> ModelWarmer:
    """获取全局模型预热器实例"""
    global global_warmer
    if global_warmer is None:
        global_warmer = ModelWarmer(model_name=model_name)
    return global_warmer


async def warmup_reranker(model_name: str = "BAAI/bge-reranker-v2-m3") -> bool:
    """预热重排序模型（供 FastAPI startup 调用）"""
    warmer = get_model_warmer(model_name)
    return await warmer.warmup()
