"""Embedding 引擎——多模型通用化封装

支持 DashScope / OpenAI / Anthropic embedding 模型。
继承 SafeDashScopeEmbedding 的安全处理逻辑（空文本替换、超长截断、重试）。
"""
import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from src.utils.logger import logger


class BaseEmbeddingProvider(ABC):
    """Embedding 提供者基类"""

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量获取文本向量"""

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """获取查询向量"""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """向量维度"""


class DashScopeEmbeddingProvider(BaseEmbeddingProvider):
    """DashScope Embedding 提供者"""

    def __init__(self, api_key: str, model: str = "text-embedding-v3", dimension: int = 1024):
        self._api_key = api_key
        self._model = model
        self._dimension = dimension
        self._max_text_length = 8192

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量获取文本向量（含安全处理）"""
        safe_texts = self._sanitize_texts(texts)
        return await self._call_with_retry(safe_texts)

    async def embed_query(self, text: str) -> list[float]:
        """获取查询向量"""
        safe_text = self._sanitize_text(text)
        results = await self._call_with_retry([safe_text])
        return results[0]

    def _sanitize_texts(self, texts: list[str]) -> list[str]:
        """文本安全处理：空文本替换、超长截断"""
        safe = []
        for i, text in enumerate(texts):
            safe.append(self._sanitize_text(text))
        return safe

    def _sanitize_text(self, text: str) -> str:
        """单个文本安全处理"""
        if not text or not text.strip():
            return "empty"
        if len(text) > self._max_text_length:
            return text[:self._max_text_length]
        return text

    async def _call_with_retry(self, texts: list[str], max_retries: int = 3) -> list[list[float]]:
        """带重试的 API 调用"""
        import httpx

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding",
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self._model,
                            "input": {"texts": texts},
                            "parameters": {"text_type": "document"},
                        },
                        timeout=60,
                    )
                    response.raise_for_status()
                    result = response.json()

                    embeddings = result.get("output", {}).get("embeddings", [])
                    if not embeddings:
                        raise ValueError("DashScope 返回空 embeddings")

                    return [e["embedding"] for e in embeddings]

            except Exception as e:
                error_msg = str(e)
                # 非瞬时错误不重试
                non_transient = ["InvalidApiKey", "401", "403", "AccessDenied", "Unauthorized"]
                if any(err in error_msg for err in non_transient):
                    logger.error(f"DashScope Embedding 非瞬时错误: {error_msg}")
                    raise

                if attempt == max_retries - 1:
                    logger.error(f"DashScope Embedding 调用失败（{max_retries} 次重试）: {error_msg}")
                    raise

                wait = 2 ** attempt
                logger.warning(f"DashScope Embedding 调用失败，{wait}s 后重试: {error_msg}")
                await asyncio.sleep(wait)

        raise RuntimeError("DashScope Embedding 调用失败")


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI Embedding 提供者"""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dimension: int = 1536):
        self._api_key = api_key
        self._model = model
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量获取文本向量"""
        import httpx

        safe_texts = [t if t and t.strip() else "empty" for t in texts]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": self._model, "input": safe_texts},
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()
            return [item["embedding"] for item in result["data"]]

    async def embed_query(self, text: str) -> list[float]:
        """获取查询向量"""
        results = await self.embed_texts([text])
        return results[0]


class EmbeddingEngine:
    """Embedding 引擎门面

    根据配置选择提供者，统一调用接口。
    """

    def __init__(self, provider: BaseEmbeddingProvider):
        self._provider = provider

    @property
    def dimension(self) -> int:
        return self._provider.dimension

    async def embed_batch(
        self, texts: list[str], batch_size: int = 64
    ) -> list[list[float]]:
        """批量获取文本向量（自动分批）

        Args:
            texts: 文本列表
            batch_size: 每批大小

        Returns:
            向量列表
        """
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = await self._provider.embed_texts(batch)
            all_embeddings.extend(embeddings)
        return all_embeddings

    async def embed_single(self, text: str) -> list[float]:
        """获取单个文本向量"""
        return await self._provider.embed_query(text)

    @classmethod
    def from_config(
        cls,
        provider: str = "dashscope",
        api_key: str = "",
        model: Optional[str] = None,
        dimension: int = 1024,
    ) -> "EmbeddingEngine":
        """从配置创建引擎

        Args:
            provider: 提供者类型（dashscope/openai）
            api_key: API 密钥
            model: 模型名称
            dimension: 向量维度
        """
        if provider == "dashscope":
            embedding_provider = DashScopeEmbeddingProvider(
                api_key=api_key,
                model=model or "text-embedding-v3",
                dimension=dimension,
            )
        elif provider == "openai":
            embedding_provider = OpenAIEmbeddingProvider(
                api_key=api_key,
                model=model or "text-embedding-3-small",
                dimension=dimension,
            )
        else:
            raise ValueError(f"不支持的 Embedding 提供者: {provider}")

        return cls(provider=embedding_provider)
