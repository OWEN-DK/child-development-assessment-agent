from typing import Tuple, List, Dict, Optional
from llama_index.llms.dashscope import DashScope
from src.config import settings
from src.utils.logger import logger
import hashlib
import os
import uuid
from functools import lru_cache
from datetime import datetime

# 全局进度存储
_task_progress: Dict[str, Dict] = {}

try:
    from summa import summarizer
    HAS_SUMMA = True
except ImportError:
    HAS_SUMMA = False
    logger.warning("summa library not installed, local summarization fallback will use simple truncation")


class LayeredContentGenerator:
    """生成分层上下文：L0(摘要)/L1(概览)/L2(详情)
    支持批量生成、降级机制、长度校验、更新检测
    """
    
    def __init__(self):
        self.llm = None
        if settings.dashscope_api_key:
            try:
                self.llm = DashScope(
                    model=settings.llm_models.get("metadata_extraction", "qwen-turbo"),
                    api_key=settings.dashscope_api_key
                )
            except Exception as e:
                logger.warning(f"Failed to initialize LLM for layered content generation: {e}")
        
        # 配置开关
        layered_config = settings.rag_config["layered_content"]
        self.enable_llm_generation = layered_config["enable_llm_generation"]
        self.enable_local_fallback = layered_config["enable_local_fallback"]
        self.l0_max_length = layered_config["l0_max_length"]
        self.l1_max_length = layered_config["l1_max_length"]
        # 批量处理配置：对于大量节点自动调整批次大小
        self.batch_size = layered_config["batch_size"]
        self.large_batch_threshold = layered_config["large_batch_threshold"]
        self.large_batch_size = layered_config["large_batch_size"]
        # 对于大量节点，使用更小的批次降低API压力
    
    async def generate_layers_batch(self, contents: List[str], task_id: Optional[str] = None) -> List[Tuple[str, str, str]]:
        """批量生成分层内容，减少LLM调用次数
        Args:
            contents: 内容列表
            task_id: 可选任务ID，用于进度跟踪
        """
        results = []
        total = len(contents)
        processed = 0
        # 根据节点总数动态调整批次大小
        batch_size = self.large_batch_size if total > self.large_batch_threshold else self.batch_size
        logger.info(f"Starting layered content generation for {total} chunks, batch size: {batch_size}")
        
        # 初始化进度
        if task_id:
            _task_progress[task_id] = {
                "total": total,
                "processed": processed,
                "progress": 0.0,
                "status": "running",
                "start_time": datetime.now().isoformat(),
                "end_time": None
            }
        # 按批次处理
        for i in range(0, total, batch_size):
            batch = contents[i:i+batch_size]
            if self.enable_llm_generation and self.llm:
                try:
                    batch_results = await self._generate_batch_llm(batch)
                    results.extend(batch_results)
                    processed += len(batch_results)
                    # 每批次记录进度
                    progress = (processed / total) * 100
                    logger.info(f"Layered content generation progress: {processed}/{total} ({progress:.1f}%)")
                    # 更新全局进度
                    if task_id and task_id in _task_progress:
                        _task_progress[task_id]["processed"] = processed
                        _task_progress[task_id]["progress"] = round(progress, 1)
                    continue
                except Exception as e:
                    logger.warning(f"Batch LLM generation failed, falling back to local: {e}")
            # 本地兜底
            batch_results_local = []
            for content in batch:
                l0, l1 = self._generate_local_summary(content)
                batch_results_local.append((l0, l1, content))
            results.extend(batch_results_local)
            processed += len(batch_results_local)
            progress = (processed / total) * 100
            logger.info(f"Layered content generation progress (local fallback): {processed}/{total} ({progress:.1f}%)")
            # 更新全局进度
            if task_id and task_id in _task_progress:
                _task_progress[task_id]["processed"] = processed
                _task_progress[task_id]["progress"] = round(progress, 1)
        logger.info(f"Completed layered content generation for {total} chunks")
        # 标记任务完成
        if task_id and task_id in _task_progress:
            _task_progress[task_id]["status"] = "completed"
            _task_progress[task_id]["end_time"] = datetime.now().isoformat()
            _task_progress[task_id]["progress"] = 100.0
        return results
    
    async def generate_layers(self, content: str, doc_hash: str = None) -> Tuple[str, str, str]:
        """
        生成三层内容，支持降级、长度校验、更新检测
        Returns: (l0_abstract, l1_overview, l2_detail)
        """
        # L2 就是原始内容
        l2_detail = content
        content_hash = doc_hash or hashlib.sha256(content.encode()).hexdigest()[:16]
        
        # 检查是否需要生成分层内容（非核心文档可配置跳过L1生成）
        layered_config = settings.rag_config["layered_content"]
        if not layered_config["enabled"]:
            return (content[:self.l0_max_length], content[:self.l1_max_length], l2_detail)
        
        if self.enable_llm_generation and self.llm:
            try:
                # L0 摘要（~100字）
                l0_prompt = f"""
                请为以下儿童发展相关内容生成{self.l0_max_length}字以内的摘要，必须包含适用年龄范围和核心主题：
                内容：{content[:1000]}
                输出仅包含摘要内容，不要其他说明。
                """
                l0_response = await self.llm.acomplete(l0_prompt, timeout=10)
                l0_abstract = l0_response.text.strip()
                # 强制长度校验
                if len(l0_abstract) > self.l0_max_length:
                    l0_abstract = l0_abstract[:self.l0_max_length] + "..."
                
                # L1 概览（~500字）
                l1_prompt = f"""
                请为以下儿童发展相关内容生成{self.l1_max_length}字以内的概览，包含核心观点、适用年龄、主要价值：
                内容：{content[:3000]}
                输出仅包含概览内容，不要其他说明。
                """
                l1_response = await self.llm.acomplete(l1_prompt, timeout=15)
                l1_overview = l1_response.text.strip()
                # 强制长度校验
                if len(l1_overview) > self.l1_max_length:
                    l1_overview = l1_overview[:self.l1_max_length] + "..."
                
                logger.debug(f"Generated layered content: L0={len(l0_abstract)}chars, L1={len(l1_overview)}chars, hash={content_hash}")
                return l0_abstract, l1_overview, l2_detail
            except Exception as e:
                logger.warning(f"LLM layered generation failed for hash {content_hash}, using local fallback: {e}")
        
        # 本地摘要兜底（TF-IDF/TextRank）
        if self.enable_local_fallback:
            l0_abstract, l1_overview = self._generate_local_summary(content)
            return l0_abstract, l1_overview, l2_detail
        
        # 最终兜底：直接截断
        return (content[:self.l0_max_length], content[:self.l1_max_length], l2_detail)
    
    def _generate_local_summary(self, content: str) -> Tuple[str, str]:
        """生成本地摘要，无LLM依赖"""
        if HAS_SUMMA:
            try:
                l0_abstract = summarizer.summarize(content, words=self.l0_max_length // 2)
                l1_overview = summarizer.summarize(content, words=self.l1_max_length // 2)
                # 补全截断
                if len(l0_abstract) < 10:
                    l0_abstract = content[:self.l0_max_length]
                if len(l1_overview) < 50:
                    l1_overview = content[:self.l1_max_length]
                return l0_abstract.strip(), l1_overview.strip()
            except:
                pass
        # 兜底方案：直接截断
        return (content[:self.l0_max_length].strip(), content[:self.l1_max_length].strip())
    
    async def _generate_batch_llm(self, contents: List[str]) -> List[Tuple[str, str, str]]:
        """批量生成LLM分层内容（真正批量调用，减少API次数）"""
        import asyncio
        # 真正的批量prompt，一次调用处理多个内容，大幅减少API调用次数
        batch_prompt = "请为以下每个儿童发展相关内容生成摘要和概览，严格按照格式输出：\n"
        batch_prompt += "格式要求：每个内容的输出用---分隔，第一行是【摘要】开头的100字以内摘要，第二行是【概览】开头的500字以内概览\n\n"
        
        for idx, content in enumerate(contents):
            batch_prompt += f"内容{idx+1}：{content[:2000]}\n\n"
        
        batch_prompt += "现在开始输出，严格按照格式，不要其他说明：\n"
        
        try:
            response = await self.llm.acomplete(batch_prompt, timeout=min(60, len(contents)*10))
            response_text = response.text.strip()
            # 解析批量结果
            items = response_text.split("---")
            final_results = []
            
            for i, content in enumerate(contents):
                if i < len(items):
                    item = items[i].strip()
                    lines = [line.strip() for line in item.split("\n") if line.strip()]
                    l0_abstract = content[:self.l0_max_length]
                    l1_overview = content[:self.l1_max_length]
                    
                    for line in lines:
                        if line.startswith("【摘要】"):
                            l0_abstract = line[4:].strip()[:self.l0_max_length]
                            if len(l0_abstract) > self.l0_max_length:
                                l0_abstract = l0_abstract[:self.l0_max_length] + "..."
                        elif line.startswith("【概览】"):
                            l1_overview = line[4:].strip()[:self.l1_max_length]
                            if len(l1_overview) > self.l1_max_length:
                                l1_overview = l1_overview[:self.l1_max_length] + "..."
                    
                    final_results.append((l0_abstract, l1_overview, content))
                else:
                    # 解析失败的内容用本地兜底
                    l0, l1 = self._generate_local_summary(content)
                    final_results.append((l0, l1, content))
            
            return final_results
            
        except Exception as e:
            logger.warning(f"Batch LLM generation failed, falling back to concurrent individual calls: {e}")
            # 降级为并发调用
            base_concurrency_limit = layered_config["concurrency_limit"]
            concurrency_limit = max(4, base_concurrency_limit)
            semaphore = asyncio.Semaphore(concurrency_limit)

            async def _generate_with_semaphore(content: str):
                async with semaphore:
                    try:
                        # 合并L0和L1到一个调用，减少一半API次数
                        combined_prompt = f"""
请为以下儿童发展相关内容同时生成摘要和概览：
【摘要要求】{self.l0_max_length}字以内，包含适用年龄范围和核心主题，开头用【摘要】标记
【概览要求】{self.l1_max_length}字以内，包含核心观点、适用年龄、主要价值，开头用【概览】标记
内容：{content[:2000]}
输出仅包含这两行内容，不要其他说明。
                        """
                        response = await self.llm.acomplete(combined_prompt, timeout=15)
                        text = response.text.strip()
                        lines = [line.strip() for line in text.split("\n") if line.strip()]
                        l0_abstract = content[:self.l0_max_length]
                        l1_overview = content[:self.l1_max_length]
                        
                        for line in lines:
                            if line.startswith("【摘要】"):
                                l0_abstract = line[4:].strip()[:self.l0_max_length]
                                if len(l0_abstract) > self.l0_max_length:
                                    l0_abstract = l0_abstract[:self.l0_max_length] + "..."
                            elif line.startswith("【概览】"):
                                l1_overview = line[4:].strip()[:self.l1_max_length]
                                if len(l1_overview) > self.l1_max_length:
                                    l1_overview = l1_overview[:self.l1_max_length] + "..."
                        
                        return l0_abstract, l1_overview, content
                    except:
                        l0, l1 = self._generate_local_summary(content)
                        return l0, l1, content

            tasks = [_generate_with_semaphore(content) for content in contents]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            final_results = []
            for content, result in zip(contents, results):
                if isinstance(result, Exception):
                    l0, l1 = self._generate_local_summary(content)
                    final_results.append((l0, l1, content))
                else:
                    final_results.append(result)
            
            return final_results


# 全局实例
@lru_cache(maxsize=1)
def get_layered_generator():
    return LayeredContentGenerator()

def get_task_progress(task_id: str) -> Optional[Dict]:
    """获取任务进度"""
    return _task_progress.get(task_id)

def list_all_tasks() -> List[Dict]:
    """获取所有任务进度"""
    return [{"task_id": tid, **progress} for tid, progress in _task_progress.items()]

def clear_task_progress(task_id: str) -> bool:
    """清除任务进度"""
    if task_id in _task_progress:
        del _task_progress[task_id]
        return True
    return False

layered_generator = get_layered_generator()
