"""
PageIndex 包装器 - 封装 PageIndex 推理检索能力（增强：熔断、重试、降级）
"""
import asyncio
import aiohttp
import logging
import time
from enum import Enum
from typing import List, Dict, Any, Optional
from src.config.settings import settings

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态（试探恢复）


class CircuitBreaker:
    """
    熔断器实现
    
    功能:
    1. 连续失败达到阈值时触发熔断
    2. 熔断后自动定时尝试恢复
    3. 半开状态试探性放行请求
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: int = 60
    ):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    def record_success(self):
        """记录成功"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def record_failure(self):
        """记录失败"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"熔断器触发：连续失败{self.failure_count}次")
    
    def can_execute(self) -> bool:
        """判断是否可以执行请求"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # 检查是否过了恢复时间
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("熔断器进入半开状态，尝试恢复")
                return True
            return False
        
        # HALF_OPEN 状态允许一个请求通过
        return True


class PageIndexWrapper:
    """
    PageIndex 引擎包装器（增强版）
    
    功能:
    1. 封装 PageIndex API 调用
    2. 熔断器保护（防雪崩）
    3. 指数退避重试（防抖动）
    4. 降级到混合检索
    """
    
    def __init__(self):
        self.api_key = settings.pageindex_api_key
        self.base_url = settings.pageindex_base_url
        self.max_tree_depth = settings.pageindex_max_tree_depth
        self.timeout_seconds = settings.pageindex_timeout_seconds
        self.max_concurrency = settings.pageindex_max_concurrency
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        
        # 熔断器
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=settings.pageindex_circuit_breaker_failure_threshold,
            reset_timeout=settings.pageindex_circuit_breaker_reset_timeout
        )
        
        # 降级开关
        self.fallback_enabled = settings.pageindex_fallback_to_hybrid
    
    async def query(
        self, 
        query: str, 
        context: Optional[List[str]] = None,
        max_depth: Optional[int] = None,
        use_fallback: bool = True
    ) -> List[Dict[str, Any]]:
        """
        使用 PageIndex 进行推理检索（增强：熔断 + 重试 + 降级）
        
        Args:
            query: 查询字符串
            context: 额外上下文（可选）
            max_depth: 最大推理深度（可选）
            use_fallback: 是否启用降级（默认 True）
            
        Returns:
            List[Dict]: 检索结果列表
        """
        # 1. 检查熔断器
        if not self.circuit_breaker.can_execute():
            logger.warning(f"熔断器开启，降级到混合检索：{query[:50]}...")
            if use_fallback and self.fallback_enabled:
                return []  # 返回空列表，由调用方降级到混合检索
            else:
                raise Exception("熔断器开启且降级未启用")
        
        async with self._semaphore:
            # 2. 指数退避重试
            last_error = None
            for attempt in range(settings.pageindex_max_retries):
                try:
                    result = await self._execute_query(
                        query=query,
                        context=context,
                        max_depth=max_depth or self.max_tree_depth
                    )
                    # 成功：重置熔断器
                    self.circuit_breaker.record_success()
                    return result
                    
                except asyncio.TimeoutError as e:
                    last_error = e
                    logger.warning(f"PageIndex 查询超时（第{attempt+1}次）: {query[:50]}...")
                except aiohttp.ClientError as e:
                    last_error = e
                    logger.warning(f"PageIndex 网络错误（第{attempt+1}次）: {e}")
                except Exception as e:
                    last_error = e
                    logger.warning(f"PageIndex 查询异常（第{attempt+1}次）: {e}")
                
                # 3. 指数退避延迟（带抖动）
                if attempt < settings.pageindex_max_retries - 1:
                    delay = min(
                        settings.pageindex_retry_base_delay * (2 ** attempt),
                        settings.pageindex_retry_max_delay
                    )
                    # 添加 10% 抖动
                    import random
                    jitter = delay * 0.1 * random.random()
                    await asyncio.sleep(delay + jitter)
            
            # 4. 所有重试失败
            self.circuit_breaker.record_failure()
            logger.error(f"PageIndex 查询所有重试失败：{query[:50]}...")
            
            # 5. 降级处理
            if use_fallback and self.fallback_enabled:
                logger.info("降级到混合检索")
                return []  # 返回空列表，由调用方处理降级
            else:
                raise last_error
    
    async def _execute_query(
        self, 
        query: str, 
        context: Optional[List[str]],
        max_depth: int
    ) -> List[Dict[str, Any]]:
        """执行 PageIndex 查询"""
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        
        payload = {
            "query": query,
            "max_tree_depth": max_depth,
            "include_reasoning_trace": True,  # 包含推理路径
            "context": context or []
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{self.base_url}/api/v1/reasoning_query",
                json=payload,
                headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"PageIndex API 错误：{response.status} - {error_text}")
                
                result = await response.json()
                return self._parse_response(result)
    
    async def index_document(
        self, 
        file_path: str, 
        document_id: str
    ) -> bool:
        """
        将文档索引到 PageIndex
        :param file_path: 文件路径
        :param document_id: 文档 ID
        :return: 是否成功
        """
        if not settings.pageindex_enabled:
            return False
            
        if not self.api_key:
            logger.warning("PageIndex is enabled but no API key provided, skipping ingestion")
            return False
            
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds * 3) # Uploading might take longer
            
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # Using aiohttp FormData for file upload
            data = aiohttp.FormData()
            data.add_field('document_id', document_id)
            
            import os
            if not os.path.exists(file_path):
                logger.error(f"File not found for PageIndex ingestion: {file_path}")
                return False
                
            with open(file_path, 'rb') as f:
                # We need to read the file content to upload it, or pass the file object
                # For large files, passing the file object directly is better, but since it's async we should be careful.
                # Since we're in an async function, we can just let aiohttp handle the file reading.
                # However, aiohttp expects the file object to remain open during the request.
                pass
                
            # Better approach:
            data.add_field('file',
                          open(file_path, 'rb'),
                          filename=os.path.basename(file_path))
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.base_url}/api/v1/documents",
                    data=data,
                    headers=headers
                ) as response:
                    if response.status not in (200, 201):
                        error_text = await response.text()
                        logger.error(f"PageIndex document ingestion failed: {response.status} - {error_text}")
                        return False
                        
                    logger.info(f"Successfully ingested document {document_id} to PageIndex")
                    return True
                    
        except Exception as e:
            logger.error(f"PageIndex index document failed: {e}")
            return False

    def _parse_response(self, response: Dict) -> List[Dict[str, Any]]:
        """解析 PageIndex API 响应"""
        results = []
        
        for node in response.get("nodes", []):
            results.append({
                "content": node.get("content", ""),
                "source": node.get("source_document", "Unknown"),
                "section": node.get("section_path", ""),
                "reasoning_path": node.get("reasoning_trace", ""),  # 推理路径
                "confidence": node.get("confidence_score", 0.0),
                "metadata": node.get("metadata", {})
            })
        
        # 按置信度排序
        results.sort(key=lambda x: x["confidence"], reverse=True)
        
        return results
