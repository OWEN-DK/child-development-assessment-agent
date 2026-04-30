import hashlib
import asyncio
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from src.config import settings
from src.core.llm.factory import LLMFramework, LLMServiceFactory, LLMServiceFactoryCompat
from src.schemas import LLMMessage, LLMRequest
from src.schemas.task import TaskStatus
from src.utils.di import get_task_state_service
from src.service.task_sse_publisher import TaskSsePublisher
from src.utils.logger import logger

try:
    from summa import summarizer

    HAS_SUMMA = True
except ImportError:
    HAS_SUMMA = False
    logger.warning(
        "summa library not installed, local summarization fallback will use simple truncation"
    )


class LayeredContentGenerator:
    """生成分层上下文：L0(摘要)/L1(概览)/L2(详情)
    支持批量生成、降级机制、长度校验、更新检测
    """

    def __init__(self):
        self.llm_available = bool(settings.dashscope_api_key)

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

    async def generate_layers_batch(
        self, 
        contents: List[str], 
        task_id: Optional[str] = None,
        cancellation_event: Optional[asyncio.Event] = None
    ) -> List[Tuple[str, str, str]]:
        """批量生成分层内容，减少LLM调用次数
        Args:
            contents: 内容列表
            task_id: 可选任务ID，用于进度跟踪
            cancellation_event: 可选取消事件，用于终止任务
        """
        results = []
        total = len(contents)
        processed = 0
        TASK_TYPE = "layered_generation"
        task_state_service = get_task_state_service()
        
        # 根据节点总数动态调整批次大小
        batch_size = (
            self.large_batch_size
            if total > self.large_batch_threshold
            else self.batch_size
        )
        logger.info(
            f"Starting layered content generation for {total} chunks, batch size: {batch_size}"
        )

        # 初始化任务状态
        if task_id:
            await task_state_service.update(
                task_id=task_id,
                task_type=TASK_TYPE,
                updates={
                    "status": TaskStatus.RUNNING,
                    "progress": 0.0,
                    "message": "生成分层内容中",
                    "metadata": {"total": total, "processed": processed}
                }
            )
        # 按批次处理
        for i in range(0, total, batch_size):
            # 检查是否取消
            if cancellation_event and cancellation_event.is_set():
                raise asyncio.CancelledError("任务已取消")
                
            batch = contents[i : i + batch_size]
            if self.enable_llm_generation and self.llm_available:
                try:
                    batch_results = await self._generate_batch_llm(batch)
                    results.extend(batch_results)
                    processed += len(batch_results)
                    # 每批次记录进度
                    progress = (processed / total) * 100
                    logger.info(
                        f"Layered content generation progress: {processed}/{total} ({progress:.1f}%)"
                    )
                    # 更新任务状态
                    if task_id:
                        await task_state_service.update(
                            task_id=task_id,
                            task_type=TASK_TYPE,
                            updates={
                                "progress": round(progress, 1),
                                "metadata": {"total": total, "processed": processed}
                            }
                        )
                        # 推送进度事件
                        await TaskSsePublisher.publish_progress(
                            task_type=TASK_TYPE,
                            task_id=task_id,
                            progress=round(progress, 1),
                            message=f"已处理 {processed}/{total} 个内容块"
                        )
                    continue
                except Exception as e:
                    logger.warning(
                        f"Batch LLM generation failed, falling back to local: {e}"
                    )
            # 本地兜底
            batch_results_local = []
            for content in batch:
                l0, l1 = self._generate_local_summary(content)
                batch_results_local.append((l0, l1, content))
            results.extend(batch_results_local)
            processed += len(batch_results_local)
            progress = (processed / total) * 100
            logger.info(
                f"Layered content generation progress (local fallback): {processed}/{total} ({progress:.1f}%)"
            )
            # 更新任务状态
            if task_id:
                await task_state_service.update(
                    task_id=task_id,
                    task_type=TASK_TYPE,
                    updates={
                        "progress": round(progress, 1),
                        "metadata": {"total": total, "processed": processed}
                    }
                )
                # 推送进度事件
                await TaskSsePublisher.publish_progress(
                    task_type=TASK_TYPE,
                    task_id=task_id,
                    progress=round(progress, 1),
                    message=f"已处理 {processed}/{total} 个内容块"
                )
        logger.info(f"Completed layered content generation for {total} chunks")
        # 标记任务完成
        if task_id:
            await task_state_service.update(
                task_id=task_id,
                task_type=TASK_TYPE,
                updates={
                    "status": TaskStatus.COMPLETED,
                    "progress": 100.0,
                    "message": "分层内容生成完成",
                    "result": {"total_chunks": total}
                }
            )
            # 推送完成事件
            await TaskSsePublisher.publish_complete(
                task_type=TASK_TYPE,
                task_id=task_id,
                result={"total_chunks": total}
            )
        return results

    async def generate_layers(
        self, content: str, doc_hash: str = None
    ) -> Tuple[str, str, str]:
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
            return (
                content[: self.l0_max_length],
                content[: self.l1_max_length],
                l2_detail,
            )

        if self.enable_llm_generation and self.llm_available:
            try:
                # 使用工厂创建 LLM 实例
                llm = LLMServiceFactoryCompat.create(
                    framework=LLMFramework.LLAMAINDEX,
                    model_name=settings.llm_models.get(
                        "metadata_extraction", "qwen-turbo"
                    ),
                    scenario="layered_content_generation",
                    temperature=0.4,
                )

                # L0 摘要（~100字）
                l0_prompt = f"""
                请为以下儿童发展相关内容生成{self.l0_max_length}字以内的摘要，必须包含适用年龄范围和核心主题：
                内容：{content[:1000]}
                输出仅包含摘要内容，不要其他说明。
                """

                l0_messages = [
                    LLMMessage(
                        role="system",
                        content="你是一个内容摘要专家，擅长提取核心要点。",
                    ),
                    LLMMessage(role="user", content=l0_prompt),
                ]

                l0_response = await llm.chat(
                    LLMRequest(
                        messages=l0_messages,
                        model_name=settings.llm_models.get(
                            "metadata_extraction", "qwen-turbo"
                        ),
                        temperature=0.4,
                        max_tokens=256,
                        scenario="layered_content_generation",
                        prompt_key="layered_l0_summary",
                    )
                )
                l0_abstract = l0_response.content.strip()
                # 强制长度校验
                if len(l0_abstract) > self.l0_max_length:
                    l0_abstract = l0_abstract[: self.l0_max_length] + "..."

                # L1 概览（~500字）
                l1_prompt = f"""
                请为以下儿童发展相关内容生成{self.l1_max_length}字以内的概览，包含核心观点、适用年龄、主要价值：
                内容：{content[:3000]}
                输出仅包含概览内容，不要其他说明。
                """

                l1_messages = [
                    LLMMessage(
                        role="system",
                        content="你是一个内容概览专家，擅长生成全面的概述。",
                    ),
                    LLMMessage(role="user", content=l1_prompt),
                ]

                l1_response = await llm.chat(
                    LLMRequest(
                        messages=l1_messages,
                        model_name=settings.llm_models.get(
                            "metadata_extraction", "qwen-turbo"
                        ),
                        temperature=0.4,
                        max_tokens=1024,
                        scenario="layered_content_generation",
                        prompt_key="layered_l1_overview",
                    )
                )
                l1_overview = l1_response.content.strip()
                # 强制长度校验
                if len(l1_overview) > self.l1_max_length:
                    l1_overview = l1_overview[: self.l1_max_length] + "..."

                logger.debug(
                    f"Generated layered content: L0={len(l0_abstract)}chars, L1={len(l1_overview)}chars, hash={content_hash}"
                )
                return l0_abstract, l1_overview, l2_detail
            except Exception as e:
                logger.warning(
                    f"LLM layered generation failed for hash {content_hash}, using local fallback: {e}"
                )

        # 本地摘要兜底（TF-IDF/TextRank）
        if self.enable_local_fallback:
            l0_abstract, l1_overview = self._generate_local_summary(content)
            return l0_abstract, l1_overview, l2_detail

        # 最终兜底：直接截断
        return (content[: self.l0_max_length], content[: self.l1_max_length], l2_detail)

    def _generate_local_summary(self, content: str) -> Tuple[str, str]:
        """生成本地摘要，无LLM依赖"""
        if HAS_SUMMA:
            try:
                l0_abstract = summarizer.summarize(
                    content, words=self.l0_max_length // 2
                )
                l1_overview = summarizer.summarize(
                    content, words=self.l1_max_length // 2
                )
                # 补全截断
                if len(l0_abstract) < 10:
                    l0_abstract = content[: self.l0_max_length]
                if len(l1_overview) < 50:
                    l1_overview = content[: self.l1_max_length]
                return l0_abstract.strip(), l1_overview.strip()
            except:
                pass
        # 兜底方案：直接截断
        return (
            content[: self.l0_max_length].strip(),
            content[: self.l1_max_length].strip(),
        )

    async def _generate_batch_llm(
        self, contents: List[str]
    ) -> List[Tuple[str, str, str]]:
        """批量生成LLM分层内容（真正批量调用，减少API次数）"""
        import asyncio

        # 真正的批量prompt，一次调用处理多个内容，大幅减少API调用次数
        batch_prompt = (
            "请为以下每个儿童发展相关内容生成摘要和概览，严格按照格式输出：\n"
        )
        batch_prompt += "格式要求：每个内容的输出用---分隔，第一行是【摘要】开头的100字以内摘要，第二行是【概览】开头的500字以内概览\n\n"

        for idx, content in enumerate(contents):
            batch_prompt += f"内容{idx + 1}：{content[:2000]}\n\n"

        batch_prompt += "现在开始输出，严格按照格式，不要其他说明：\n"

        try:
            # 使用工厂创建 LLM 实例
            llm = LLMServiceFactoryCompat.create(
                framework=LLMFramework.LLAMAINDEX,
                model_name=settings.llm_models.get("metadata_extraction", "qwen-turbo"),
                scenario="layered_content_batch",
                temperature=0.4,
            )

            messages = [
                LLMMessage(role="system", content="你是一个批量内容摘要生成专家。"),
                LLMMessage(role="user", content=batch_prompt),
            ]

            response = await llm.chat(
                LLMRequest(
                    messages=messages,
                    model_name=settings.llm_models.get(
                        "metadata_extraction", "qwen-turbo"
                    ),
                    temperature=0.4,
                    max_tokens=4096,
                    scenario="layered_content_batch",
                    prompt_key="layered_batch_generation",
                )
            )
            response_text = response.content.strip()
            # 解析批量结果
            items = response_text.split("---")
            final_results = []

            for i, content in enumerate(contents):
                if i < len(items):
                    item = items[i].strip()
                    lines = [line.strip() for line in item.split("\n") if line.strip()]
                    l0_abstract = content[: self.l0_max_length]
                    l1_overview = content[: self.l1_max_length]

                    for line in lines:
                        if line.startswith("【摘要】"):
                            l0_abstract = line[4:].strip()[: self.l0_max_length]
                            if len(l0_abstract) > self.l0_max_length:
                                l0_abstract = l0_abstract[: self.l0_max_length] + "..."
                        elif line.startswith("【概览】"):
                            l1_overview = line[4:].strip()[: self.l1_max_length]
                            if len(l1_overview) > self.l1_max_length:
                                l1_overview = l1_overview[: self.l1_max_length] + "..."

                    final_results.append((l0_abstract, l1_overview, content))
                else:
                    # 解析失败的内容用本地兜底
                    l0, l1 = self._generate_local_summary(content)
                    final_results.append((l0, l1, content))

            return final_results

        except Exception as e:
            logger.warning(
                f"Batch LLM generation failed, falling back to concurrent individual calls: {e}"
            )
            # 降级为并发调用
            base_concurrency_limit = layered_config.get("concurrency_limit", 4)
            concurrency_limit = max(4, base_concurrency_limit)
            semaphore = asyncio.Semaphore(concurrency_limit)

            async def _generate_with_semaphore(content: str):
                async with semaphore:
                    try:
                        # 使用工厂创建 LLM 实例
                        llm = LLMServiceFactoryCompat.create(
                            framework=LLMFramework.LLAMAINDEX,
                            model_name=settings.llm_models.get(
                                "metadata_extraction", "qwen-turbo"
                            ),
                            scenario="layered_content_concurrent",
                            temperature=0.4,
                        )

                        # 合并L0和L1到一个调用，减少一半API次数
                        combined_prompt = f"""
请为以下儿童发展相关内容同时生成摘要和概览：
【摘要要求】{self.l0_max_length}字以内，包含适用年龄范围和核心主题，开头用【摘要】标记
【概览要求】{self.l1_max_length}字以内，包含核心观点、适用年龄、主要价值，开头用【概览】标记
内容：{content[:2000]}
输出仅包含这两行内容，不要其他说明。
                        """

                        messages = [
                            LLMMessage(
                                role="system",
                                content="你是一个内容摘要和概览生成专家。",
                            ),
                            LLMMessage(role="user", content=combined_prompt),
                        ]

                        response = await llm.chat(
                            LLMRequest(
                                messages=messages,
                                model_name=settings.llm_models.get(
                                    "metadata_extraction", "qwen-turbo"
                                ),
                                temperature=0.4,
                                max_tokens=1024,
                                scenario="layered_content_concurrent",
                                prompt_key="layered_combined_generation",
                            )
                        )
                        text = response.content.strip()
                        lines = [
                            line.strip() for line in text.split("\n") if line.strip()
                        ]
                        l0_abstract = content[: self.l0_max_length]
                        l1_overview = content[: self.l1_max_length]

                        for line in lines:
                            if line.startswith("【摘要】"):
                                l0_abstract = line[4:].strip()[: self.l0_max_length]
                                if len(l0_abstract) > self.l0_max_length:
                                    l0_abstract = (
                                        l0_abstract[: self.l0_max_length] + "..."
                                    )
                            elif line.startswith("【概览】"):
                                l1_overview = line[4:].strip()[: self.l1_max_length]
                                if len(l1_overview) > self.l1_max_length:
                                    l1_overview = (
                                        l1_overview[: self.l1_max_length] + "..."
                                    )

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


async def get_task_progress(task_id: str) -> Optional[Dict]:
    """获取任务进度"""
    task_state_service = get_task_state_service()
    TASK_TYPE = "layered_generation"
    
    task_state = await task_state_service.get(task_id, TASK_TYPE)
    if not task_state:
        return None
        
    return {
        "task_id": task_state.task_id,
        "total": task_state.metadata.get("total", 0),
        "processed": task_state.metadata.get("processed", 0),
        "progress": task_state.progress,
        "status": task_state.status.value,
        "start_time": task_state.started_at.isoformat() if task_state.started_at else None,
        "end_time": task_state.completed_at.isoformat() if task_state.completed_at else None
    }


async def list_all_tasks() -> List[Dict]:
    """获取所有任务进度"""
    task_state_service = get_task_state_service()
    
    tasks = await task_state_service.list_active(task_type="layered_generation")
    
    return [
        {
            "task_id": task.task_id,
            "total": task.metadata.get("total", 0),
            "processed": task.metadata.get("processed", 0),
            "progress": task.progress,
            "status": task.status.value,
            "start_time": task.started_at.isoformat() if task.started_at else None
        } 
        for task in tasks
    ]


async def clear_task_progress(task_id: str) -> bool:
    """清除任务进度"""
    task_state_service = get_task_state_service()
    TASK_TYPE = "layered_generation"
    
    success = await task_state_service.delete(task_id, TASK_TYPE)
    return success


layered_generator = get_layered_generator()
