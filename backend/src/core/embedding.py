from typing import List, Any, Optional
import time
import asyncio
from llama_index.embeddings.dashscope import DashScopeEmbedding
from src.utils.logger import logger

# 延迟导入 settings 以避免循环引用
# from src.config import settings


class SafeDashScopeEmbedding(DashScopeEmbedding):
    """
    A wrapper around DashScopeEmbedding that safely handles:
    1. Text too long (truncates to 2048 characters as a safe approximation for 2048 tokens)
    2. Text empty (replaces with placeholder)
    3. Logging of modifications
    4. Timeout and retry for API calls
    """

    # Safe limit for text length (chars).
    # DashScope limit is 2048 tokens.
    # Conservative estimate: 1 token >= 0.5 chars (very conservative),
    # but usually 1 token ~ 1 char for Chinese, ~3-4 chars for English.
    # To be safe and avoid 400 errors, we use settings.embedding_max_text_length chars.

    @property
    def max_text_length(self) -> int:
        from src.config import settings

        return settings.embedding_max_text_length

    def get_text_embedding_batch(
        self, texts: List[str], show_progress: bool = False, **kwargs: Any
    ) -> List[List[float]]:
        safe_texts = []
        modified = False

        for i, text in enumerate(texts):
            # Handle empty or whitespace only
            if not text or not text.strip():
                logger.warning(
                    f"Empty text encountered at index {i}, replacing with placeholder."
                )
                safe_texts.append("empty")
                modified = True
                continue

            # Handle too long
            if len(text) > self.max_text_length:
                # Log only once per batch to avoid spam if many are long
                if not modified:
                    logger.warning(
                        f"Text too long ({len(text)} chars) at index {i}, truncating to {self.max_text_length} chars."
                    )
                safe_texts.append(text[: self.max_text_length])
                modified = True
            else:
                safe_texts.append(text)

        # 添加重试机制以应对网络波动
        max_retries = 3
        retry_delay = 2.0  # 秒
        
        for attempt in range(max_retries):
            try:
                return super().get_text_embedding_batch(safe_texts, show_progress, **kwargs)
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Embedding API call failed (attempt {attempt + 1}/{max_retries}): {error_msg}")
                
                # 非瞬时错误不重试：无效API密钥、权限错误等
                non_transient_errors = ["InvalidApiKey", "401", "403", "AccessDenied", "Unauthorized", "Forbidden"]
                if any(err in error_msg for err in non_transient_errors):
                    logger.error(f"Non-transient error detected, aborting retries: {error_msg}")
                    raise
                
                # 如果是最后一次尝试，抛出异常
                if attempt == max_retries - 1:
                    logger.error(f"Embedding API call failed after {max_retries} retries")
                    raise
                
                # 指数退避
                wait_time = retry_delay * (2 ** attempt)
                logger.info(f"Retrying in {wait_time:.1f} seconds...")
                time.sleep(wait_time)

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings = super()._get_text_embeddings(texts)
        if any(e is None or len(e) == 0 for e in embeddings):
            raise ValueError(
                "DashScope API returned empty embeddings. This is often caused by an invalid API key, "
                "rate limiting, or account arrears (e.g. out of balance). "
                "Please check the console logs for the exact DashScope error message."
            )
        return embeddings

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings = await super()._aget_text_embeddings(texts)
        if any(e is None or len(e) == 0 for e in embeddings):
            raise ValueError(
                "DashScope API returned empty embeddings. This is often caused by an invalid API key, "
                "rate limiting, or account arrears (e.g. out of balance). "
                "Please check the console logs for the exact DashScope error message."
            )
        return embeddings

    def _get_text_embedding(self, text: str) -> List[float]:
        embedding = super()._get_text_embedding(text)
        if embedding is None or len(embedding) == 0:
            raise ValueError(
                "DashScope API returned empty embedding. This is often caused by an invalid API key, "
                "rate limiting, or account arrears (e.g. out of balance). "
                "Please check the console logs for the exact DashScope error message."
            )
        return embedding

    async def _aget_text_embedding(self, text: str) -> List[float]:
        embedding = await super()._aget_text_embedding(text)
        if embedding is None or len(embedding) == 0:
            raise ValueError(
                "DashScope API returned empty embedding. This is often caused by an invalid API key, "
                "rate limiting, or account arrears (e.g. out of balance). "
                "Please check the console logs for the exact DashScope error message."
            )
        return embedding

    def _get_query_embedding(self, query: str) -> List[float]:
        embedding = super()._get_query_embedding(query)
        if embedding is None or len(embedding) == 0:
            raise ValueError(
                "DashScope API returned empty embedding for query. This is often caused by an invalid API key, "
                "rate limiting, or account arrears (e.g. out of balance)."
            )
        return embedding

    async def _aget_query_embedding(self, query: str) -> List[float]:
        embedding = await super()._aget_query_embedding(query)
        if embedding is None or len(embedding) == 0:
            raise ValueError(
                "DashScope API returned empty embedding for query. This is often caused by an invalid API key, "
                "rate limiting, or account arrears (e.g. out of balance)."
            )
        return embedding

    def get_query_embedding(self, query: str) -> List[float]:
        if not query or not query.strip():
            logger.warning("Empty query encountered, replacing with placeholder.")
            query = "empty"
        elif len(query) > self.max_text_length:
            logger.warning(f"Query too long ({len(query)} chars), truncating.")
            query = query[: self.max_text_length]
        return super().get_query_embedding(query)

    async def aget_text_embedding_batch(
        self, texts: List[str], show_progress: bool = False, **kwargs: Any
    ) -> List[List[float]]:
        # Async version
        safe_texts = []
        modified = False

        for i, text in enumerate(texts):
            if not text or not text.strip():
                safe_texts.append("empty")
                modified = True
                continue

            if len(text) > self.max_text_length:
                if not modified:
                    logger.warning(
                        f"Text too long ({len(text)} chars) at index {i}, truncating to {self.max_text_length} chars."
                    )
                safe_texts.append(text[: self.max_text_length])
                modified = True
            else:
                safe_texts.append(text)

        # 添加重试机制以应对网络波动
        max_retries = 3
        retry_delay = 2.0  # 秒
        
        for attempt in range(max_retries):
            try:
                return await super().aget_text_embedding_batch(
                    safe_texts, show_progress, **kwargs
                )
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Async embedding API call failed (attempt {attempt + 1}/{max_retries}): {error_msg}")
                
                # 非瞬时错误不重试：无效API密钥、权限错误等
                non_transient_errors = ["InvalidApiKey", "401", "403", "AccessDenied", "Unauthorized", "Forbidden"]
                if any(err in error_msg for err in non_transient_errors):
                    logger.error(f"Non-transient error detected, aborting retries: {error_msg}")
                    raise
                
                # 如果是最后一次尝试，抛出异常
                if attempt == max_retries - 1:
                    logger.error(f"Async embedding API call failed after {max_retries} retries")
                    raise
                
                # 指数退避
                wait_time = retry_delay * (2 ** attempt)
                logger.info(f"Retrying in {wait_time:.1f} seconds...")
                await asyncio.sleep(wait_time)

    async def aget_query_embedding(self, query: str) -> List[float]:
        if not query or not query.strip():
            logger.warning("Empty query encountered, replacing with placeholder.")
            query = "empty"
        elif len(query) > self.max_text_length:
            logger.warning(f"Query too long ({len(query)} chars), truncating.")
            query = query[: self.max_text_length]
        return await super().aget_query_embedding(query)
