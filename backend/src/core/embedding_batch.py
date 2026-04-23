import asyncio
import csv
import tempfile
from typing import List, Dict, Any

import dashscope
from dashscope.api_entities.dashscope_response import DashScopeAPIResponse

from src.config import settings
from src.utils.logger import logger

# 初始化DashScope API密钥
dashscope.api_key = settings.dashscope_api_key

# 常量定义
MAX_BATCH_SIZE = 100000  # DashScope单批最大支持10万行
MAX_RETRIES = 10  # 最大轮询重试次数
INITIAL_POLL_DELAY = 5  # 初始轮询延迟（秒）
TEXT_EMBEDDING_ASYNC_MODEL = "text-embedding-async-v2"


async def batch_embed_texts(texts: List[str]) -> List[List[float]]:
    """
    批量异步生成文本嵌入，使用DashScope text-embedding-async-v2 API
    适用于大规模文本嵌入场景（>50条文本）
    
    Args:
        texts: 待嵌入的文本列表
        
    Returns:
        与输入顺序对应的嵌入向量列表
        
    Raises:
        ValueError: 输入参数无效
        RuntimeError: 任务执行失败、超时或API错误
    """
    # 输入校验
    if not texts:
        raise ValueError("待嵌入文本列表不能为空")
    
    if len(texts) > MAX_BATCH_SIZE:
        raise ValueError(f"单批文本数量不能超过{MAX_BATCH_SIZE}条，当前输入{len(texts)}条")
    
    # 预处理文本，与SafeDashScopeEmbedding保持一致的处理逻辑
    from src.core.embedding import SafeDashScopeEmbedding
    safe_embedding = SafeDashScopeEmbedding()
    safe_texts = []
    
    for i, text in enumerate(texts):
        # 处理空文本
        if not text or not text.strip():
            logger.warning(f"Empty text encountered at index {i}, replacing with placeholder.")
            safe_texts.append("empty")
            continue
        
        # 处理过长文本
        if len(text) > safe_embedding.max_text_length:
            logger.warning(
                f"Text too long ({len(text)} chars) at index {i}, truncating to {safe_embedding.max_text_length} chars."
            )
            safe_texts.append(text[: safe_embedding.max_text_length])
        else:
            safe_texts.append(text)
    
    # 创建临时CSV文件，每行一个文本
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["text"])  # 表头
        for text in safe_texts:
            writer.writerow([text])
        temp_file_path = f.name
    
    try:
        # 上传文件到DashScope
        logger.info(f"Uploading batch file with {len(safe_texts)} texts to DashScope...")
        upload_response: DashScopeAPIResponse = dashscope.File.upload(file_path=temp_file_path)
        
        if upload_response.status_code != 200:
            raise RuntimeError(f"文件上传失败: {upload_response.message} (code: {upload_response.status_code})")
        
        file_id = upload_response.output["file_id"]
        logger.info(f"File uploaded successfully, file_id: {file_id}")
        
        # 提交异步嵌入任务
        logger.info(f"Submitting async embedding job for model {TEXT_EMBEDDING_ASYNC_MODEL}...")
        job_response: DashScopeAPIResponse = dashscope.AsyncTextEmbedding.async_call(
            model=TEXT_EMBEDDING_ASYNC_MODEL,
            file_id=file_id,
            text_field="text"  # 指定文本所在列名
        )
        
        if job_response.status_code != 200:
            raise RuntimeError(f"任务提交失败: {job_response.message} (code: {job_response.status_code})")
        
        job_id = job_response.output["job_id"]
        logger.info(f"Async embedding job submitted successfully, job_id: {job_id}")
        
        # 轮询任务状态，指数退避
        poll_delay = INITIAL_POLL_DELAY
        for attempt in range(MAX_RETRIES):
            logger.info(f"Polling job status (attempt {attempt + 1}/{MAX_RETRIES}), next poll in {poll_delay}s...")
            await asyncio.sleep(poll_delay)
            
            status_response: DashScopeAPIResponse = dashscope.AsyncTextEmbedding.fetch(
                job_id=job_id
            )
            
            if status_response.status_code != 200:
                raise RuntimeError(f"获取任务状态失败: {status_response.message} (code: {status_response.status_code})")
            
            job_status = status_response.output["status"]
            
            if job_status == "SUCCEEDED":
                logger.info(f"Job {job_id} completed successfully!")
                break
            elif job_status == "FAILED":
                error_msg = status_response.output.get("error_msg", "未知错误")
                raise RuntimeError(f"嵌入任务失败: {error_msg}")
            elif job_status in ["PENDING", "RUNNING"]:
                # 指数退避，最大延迟不超过60秒
                poll_delay = min(poll_delay * 2, 60)
                continue
            else:
                logger.warning(f"未知任务状态: {job_status}, 继续轮询...")
        else:
            # 所有重试都用完了
            raise RuntimeError(f"任务轮询超时，已超过{MAX_RETRIES}次重试，最后状态: {job_status}")
        
        # 下载结果文件
        logger.info(f"Downloading embedding results for job {job_id}...")
        download_url = status_response.output["url"]
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(download_url)
            response.raise_for_status()
        
        # 解析结果CSV，分批处理避免内存溢出
        import gc
        response_text = response.text
        lines = response_text.strip().split('\n')
        reader = csv.DictReader(lines)
        
        # 预分配列表，避免动态扩容
        embeddings: List[List[float]] = [None] * len(texts)
        count = 0
        
        for row in reader:
            # 解析embedding字段，格式为字符串化的列表
            embedding_str = row["embedding"]
            # 直接解析为元组再转列表，减少中间对象
            embedding = tuple(map(float, embedding_str.strip('[]').split(',')))
            embeddings[count] = list(embedding)
            count += 1
            
            # 每处理1000条清理一次内存
            if count % 1000 == 0:
                gc.collect()
        
        # 清理响应文本，释放大对象
        del response_text
        del lines
        gc.collect()
        
        # 校验结果数量是否匹配
        if count != len(texts):
            raise RuntimeError(
                f"结果数量与输入不匹配: 输入{len(texts)}条，返回{count}条"
            )
        
        logger.info(f"Successfully generated {count} embeddings")
        return embeddings
        
    finally:
        # 清理临时文件
        import os
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
            logger.debug(f"Temporary file {temp_file_path} cleaned up")


async def batch_embed_texts_smart(texts: List[str], threshold: int = 50) -> List[List[float]]:
    """
    智能批量嵌入：根据文本数量自动选择同步或异步API
    文本数量 <= threshold 时使用SafeDashScopeEmbedding的同步批量API
    文本数量 > threshold 时使用异步批量API
    
    Args:
        texts: 待嵌入的文本列表
        threshold: 选择异步API的阈值，默认50条
        
    Returns:
        与输入顺序对应的嵌入向量列表
    """
    from src.core.embedding import SafeDashScopeEmbedding
    
    if len(texts) <= threshold:
        logger.info(f"Using sync embedding API for {len(texts)} texts (threshold: {threshold})")
        safe_embedding = SafeDashScopeEmbedding()
        return await safe_embedding.aget_text_embedding_batch(texts)
    else:
        logger.info(f"Using async batch embedding API for {len(texts)} texts (threshold: {threshold})")
        return await batch_embed_texts(texts)
