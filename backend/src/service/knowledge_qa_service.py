"""知识问答服务层

负责：
- 并发任务限制（NFR-08）
- LangGraph 流水线执行（逐节超时，无全局硬超时）
- SSE 进度推送
- 超时降级处理
- Markdown/PDF 导出
- 权威运动清单加载（json.load，零外部依赖）
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi.encoders import jsonable_encoder

from src.core.async_task import AsyncTaskManager
from src.schemas.knowledge_qa import (
    ErrorCode,
    GenerationMetadata,
    KnowledgeQAResponse,
    KnowledgeQAState,
    MatchedBook,
    NoMatchingBooksError,
    RAGUnavailableError,
    SectionOutput,
    clear_progress_context,
    clear_prompt_manager,
    set_progress_context,
    set_prompt_manager,
)
from src.service.task_sse_publisher import TaskSsePublisher
from src.service.task_state_service import TaskStateService
from src.utils.logger import logger

# 项目根目录下的运动清单 JSON（由 xlsx 转换生成）
_EXERCISE_JSON_PATH = str(
    Path(__file__).resolve().parent.parent / "data" / "运动改变大脑_运动清单.json"
)
# 模块级缓存：首次加载后缓存为 Markdown 字符串，进程重启后自动刷新
_exercise_context_cache: str | None = None

TASK_TYPE = "knowledge_qa"


class KnowledgeQAService:
    """知识问答服务"""

    MAX_CONCURRENT_TASKS = 10

    def __init__(
        self,
        async_task_manager: AsyncTaskManager,
        task_state_service: TaskStateService,
        prompt_manager,
    ):
        from src.core.knowledge_qa.graph import knowledge_qa_graph

        self._graph = knowledge_qa_graph
        self._async = async_task_manager
        self._task_state = task_state_service
        self._prompt_manager = prompt_manager
        self._concurrent_tasks = 0
        self._task_lock = asyncio.Lock()

    # ===== 公共接口 =====

    async def ask(
        self,
        question: str,
        book_ids: Optional[List[str]] = None,
        stream: bool = True,
    ) -> str:
        """启动知识问答，返回 task_id"""
        async with self._task_lock:
            if self._concurrent_tasks >= self.MAX_CONCURRENT_TASKS:
                from src.utils.exceptions import KnowledgeQATooManyRequestsException

                raise KnowledgeQATooManyRequestsException(
                    message=f"系统繁忙，当前已有 {self._concurrent_tasks} 个任务在执行，请稍后重试"
                )
            self._concurrent_tasks += 1

        try:
            task_id = await self._async.start_task(
                task_type=TASK_TYPE,
                task_func=self._run_qa_pipeline,
                question=question,
                book_ids=book_ids or [],
                stream=stream,
            )
            return task_id
        except Exception:
            async with self._task_lock:
                self._concurrent_tasks -= 1
            raise

    async def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """查询任务状态"""
        state = await self._task_state.get(task_id, TASK_TYPE)
        if state is None:
            return None
        return state

    async def stream_progress(self, task_id: str):
        """SSE 进度流"""
        from src.api.sse import SSEPublisher

        channel = f"{TASK_TYPE}:{task_id}"
        async for event in SSEPublisher.subscribe(channel):
            yield event

    async def generate_markdown(self, task_id: str) -> str:
        """生成 Markdown 文件内容"""
        state = await self._task_state.get(task_id, TASK_TYPE)
        if not state or not state.result:
            raise ValueError("任务结果不存在或已过期")
        response = KnowledgeQAResponse(**state.result)

        parts = [f"# 知识问答报告\n\n**问题**: {response.question}\n"]

        if response.matched_books:
            parts.append("## 参考书籍\n")
            for b in response.matched_books:
                parts.append(
                    f"- **{b.title}**"
                    + (f" ({b.author})" if b.author else "")
                    + f" — {b.match_reason}\n"
                )
            parts.append("\n")

        for sec in response.sections:
            parts.append(f"{sec.content}\n\n")
            if sec.citations:
                parts.append("### 本节引用\n")
                for c in sec.citations:
                    parts.append(
                        f"- [{c.get('citation_id', '')}] {c.get('book_title', '')}, "
                        f"{c.get('chapter', '')}"
                        + (f", {c['section']}" if c.get("section") else "")
                        + f"\n  > {c.get('excerpt', '')}\n"
                    )
                parts.append("\n")

        return "".join(parts)

    async def generate_pdf(self, task_id: str) -> bytes:
        """生成 PDF 文件"""
        markdown_content = await self.generate_markdown(task_id)
        html_content = self._markdown_to_html(markdown_content)
        return await self._render_pdf(html_content)

    # ===== 内部 =====

    @staticmethod
    def _load_exercise_context() -> str:
        """加载权威运动清单 JSON → Markdown，模块级缓存。
        首次请求加载并缓存，后续请求命中缓存（零 IO）。
        失败时退化为空字符串 + log warning，不阻塞流水线。
        """
        global _exercise_context_cache
        if _exercise_context_cache is not None:
            return _exercise_context_cache

        try:
            with open(_EXERCISE_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.warning(f"运动清单 JSON 文件不存在: {_EXERCISE_JSON_PATH}，跳过运动约束")
            _exercise_context_cache = ""
            return ""
        except Exception as e:
            logger.warning(f"加载运动清单 JSON 失败: {e}，跳过运动约束")
            _exercise_context_cache = ""
            return ""

        markdown = KnowledgeQAService._build_exercise_markdown(data)
        _exercise_context_cache = markdown
        exercise_count = len(data.get("exercises", []))
        logger.info(f"运动清单已加载: {exercise_count} 项运动, {len(markdown)} 字符")
        return markdown

    @staticmethod
    def _build_exercise_markdown(data: dict) -> str:
        """将 JSON 数据格式化为三级 Markdown（全量表 + 脑区索引 + 核心原则）。"""
        lines = [
            "## 权威运动清单（来源：《运动改变大脑》）",
            "",
            "> **硬性约束**：以下清单是本次推荐的唯一权威运动来源。",
            "> 所有推荐的运动名称、运动类型、脑区说明、章节引用必须出自此清单。",
            "",
            "### 一、运动全清单",
            "",
            "| 序号 | 运动名称 | 运动类型 | 帮助修复的问题/主要益处 | 书中章节 | 强度建议 |",
            "|------|---------|---------|---------------------|---------|--------|",
        ]
        for ex in data.get("exercises", []):
            lines.append(
                f"| {ex['id']} | {ex['name']} | {ex['type']} | {ex['benefits']} | {ex['chapter']} | {ex['intensity']} |"
            )
        lines.append("")

        # 按脑区索引
        lines.append("### 二、按脑区索引")
        lines.append("")
        lines.append("| 脑区/神经机制 | 关联运动（序号） | 主要益处 |")
        lines.append("|-------------|---------------|--------|")
        for br in data.get("brain_regions", []):
            ids_str = ",".join(str(eid) for eid in br.get("exercise_ids", []))
            lines.append(f"| {br['region']} | {ids_str} | {br['benefits']} |")
        lines.append("")

        # 核心原则摘要
        lines.append("### 三、核心原则摘要")
        lines.append("")
        for i, p in enumerate(data.get("principles", []), 1):
            lines.append(f"{i}. **{p['name']}** — {p['content']}")

        return "\n".join(lines)

    async def _run_qa_pipeline(self, **ctx) -> Dict[str, Any]:
        """后台执行 LangGraph 流水线"""
        task_id = ctx["task_id"]
        task_type = ctx["task_type"]
        question = ctx["question"]
        book_ids = ctx.get("book_ids", [])
        stream = ctx.get("stream", True)

        async def push(step: str, message: str, **meta):
            if stream:
                await TaskSsePublisher.publish(
                    task_type=task_type,
                    task_id=task_id,
                    event_type="progress",
                    data={
                        "status": "running",
                        "step": step,
                        "message": message,
                        "metadata": meta,
                    },
                )
            # 同步更新 Redis 任务状态，支持页面刷新后通过 /status/{task_id} 恢复进度
            try:
                updates: Dict[str, Any] = {"stage": step, "message": message}
                # 逐节完成时，将 section 元信息写入 metadata（不存完整内容，避免 Redis 过大）
                if step.endswith("_done") and meta.get("section"):
                    sec = meta["section"]
                    updates["metadata"] = {
                        "last_section_index": sec.get("index"),
                        "last_section_title": sec.get("title"),
                    }
                await self._task_state.update(task_id, task_type, updates)
            except Exception:
                pass  # 状态更新失败不阻塞主流程

        set_progress_context(callback=push, task_id=task_id, task_type=task_type)
        set_prompt_manager(self._prompt_manager)

        from src.core.knowledge_qa.tools import clear_http_client, set_http_client
        from src.utils.http_client import RagHttpClient

        http_client = RagHttpClient()
        set_http_client(http_client)

        # 统一由 Graph 内 prefetch_context_node 处理知识上下文预取
        initial_state = KnowledgeQAState(
            question=question,
            matched_book_ids=book_ids,
            exercise_context=self._load_exercise_context(),
        )

        start_time = time.monotonic()

        try:
            # 无全局硬超时，由各节点自身 timeout 控制
            final_state = await self._graph.ainvoke(initial_state)

            # LangGraph ainvoke 返回 dict，需要包装回 KnowledgeQAState
            if isinstance(final_state, dict):
                final_state = KnowledgeQAState(**final_state)

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            response = self._build_response(final_state, elapsed_ms)
            await TaskSsePublisher.publish_complete(
                task_type=task_type,
                task_id=task_id,
                result=jsonable_encoder(response.model_dump()),
                message="完成",
            )
            return jsonable_encoder(response.model_dump())

        except (NoMatchingBooksError, RAGUnavailableError):
            raise

        except Exception as e:
            logger.exception(f"知识问答异常: task_id={task_id}")
            await TaskSsePublisher.publish_error(
                task_type=task_type,
                task_id=task_id,
                error="generation_failed",
                message="内容生成失败，请稍后重试",
            )
            raise

        finally:
            clear_progress_context()
            clear_prompt_manager()
            clear_http_client()
            if http_client and hasattr(http_client, "close"):
                await http_client.close()
            async with self._task_lock:
                self._concurrent_tasks -= 1

    def _build_response(
        self, state: KnowledgeQAState, elapsed_ms: float
    ) -> KnowledgeQAResponse:
        """从 LangGraph State 构建最终响应"""
        sections_list = sorted(
            [s for s in state.sections.values() if s],
            key=lambda s: s.index,
        )
        total_citations = sum(len(s.citations) for s in sections_list)

        return KnowledgeQAResponse(
            question=state.question,
            matched_books=state.matched_books_detail,
            sections=sections_list,
            generation_metadata=GenerationMetadata(
                total_sections=len(sections_list),
                total_citations=total_citations,
                total_time_ms=int(elapsed_ms),
                model_used="qwen3.5-27b",
                review_model_used="qwen3.5-27b",
                retries=state.retry_counts,
                partial=state.partial,
            ),
        )

    def _markdown_to_html(self, md: str) -> str:
        """Markdown → HTML (WeasyPrint 输入)"""
        import markdown

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8">
<style>
body {{ font-family: "Noto Sans SC", sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
h1, h2, h3 {{ color: #1a1a1a; }}
blockquote {{ border-left: 3px solid #ccc; padding-left: 16px; color: #666; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
</style></head>
<body>{markdown.markdown(md, extensions=['tables', 'fenced_code'])}</body>
</html>"""

    async def _render_pdf(self, html: str) -> bytes:
        """WeasyPrint 渲染 PDF（CPU 密集，放到线程池执行）"""
        from weasyprint import HTML

        return await asyncio.to_thread(lambda: HTML(string=html).write_pdf())
