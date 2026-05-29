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
from typing import Any, Dict, List, Optional

from fastapi.encoders import jsonable_encoder

from src.core.async_task import AsyncTaskManager
from src.core.knowledge_qa.nodes.base import get_exercise_json_path
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
_EXERCISE_JSON_PATH = get_exercise_json_path()
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
        """生成 Markdown 文件内容 — 结构化、美观的报告"""
        state = await self._task_state.get(task_id, TASK_TYPE)
        if not state or not state.result:
            raise ValueError("任务结果不存在或已过期")
        response = KnowledgeQAResponse(**state.result)

        lines = []

        # ═══════════ 标题 ═══════════
        lines.append("# 🧒 儿童发展评估报告")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ═══════════ 问题概述 ═══════════
        lines.append("## 📋 评估问题")
        lines.append("")
        lines.append(f"> **{response.question}**")
        lines.append("")

        # ═══════════ 报告元信息 ═══════════
        total_time = response.generation_metadata.total_time_ms / 1000
        lines.append(f"📊 **共 {response.generation_metadata.total_sections} 节** · "
                     f"**{response.generation_metadata.total_citations} 条引用** · "
                     f"**耗时 {total_time:.0f}s**")
        if response.generation_metadata.partial:
            lines.append("")
            lines.append("> ⚠️ **注意**：此结果为部分生成（存在超时或降级处理），内容可能不完整。")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ═══════════ 参考书籍 ═══════════
        if response.matched_books:
            lines.append("## 📚 参考书籍")
            lines.append("")
            for i, b in enumerate(response.matched_books):
                primary_tag = " ⭐ 主要参考" if b.is_primary else ""
                author_str = f" — {b.author}" if b.author else ""
                lines.append(f"### {i + 1}. {b.title}{author_str}{primary_tag}")
                lines.append(f"> {b.match_reason}")
                lines.append("")
            lines.append("---")
            lines.append("")

        # ═══════════ 跨书籍观点差异 ═══════════
        if response.contradictions:
            lines.append("## ⚠️ 跨书籍观点差异")
            lines.append("")
            for i, c in enumerate(response.contradictions):
                lines.append(f"### 差异 {i + 1}：{c.get('topic', '')}")
                lines.append(f"- **观点 A**：{c.get('view_a', '')}")
                lines.append(f"- **观点 B**：{c.get('view_b', '')}")
                lines.append(f"- **💡 调和建议**：{c.get('resolution', '请根据实际情况判断')}")
                lines.append("")
            lines.append("---")
            lines.append("")

        # ═══════════ 目录 ═══════════
        lines.append("## 📑 报告目录")
        lines.append("")
        for sec in response.sections:
            icon = {1: "🔍", 2: "🔬", 3: "💪", 4: "📅", 5: "🎯"}.get(sec.index, "📄")
            lines.append(f"- [{icon} S{sec.index}：{sec.title}](#s{sec.index}-{sec.title.replace(' ', '-').replace('：', '-')})")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ═══════════ 各节内容 ═══════════
        for sec in response.sections:
            icon = {1: "🔍", 2: "🔬", 3: "💪", 4: "📅", 5: "🎯"}.get(sec.index, "📄")
            color_hex = {1: "#1890ff", 2: "#fa8c16", 3: "#f5222d", 4: "#52c41a", 5: "#722ed1"}.get(sec.index, "#666")

            lines.append(f'<span id="s{sec.index}-{sec.title.replace(" ", "-").replace("：", "-")}"></span>')
            lines.append("")
            lines.append(f"## {icon} S{sec.index}：{sec.title}")
            lines.append("")

            if sec.index in (3, 4):
                # S3/S4: 从 structured_data 渲染
                if sec.index == 3:
                    lines.append(_render_s3_markdown(sec.structured_data) + "\n")
                else:
                    from src.core.knowledge_qa.nodes.plan_assemble import _render_s4_markdown
                    lines.append(_render_s4_markdown(sec.structured_data) + "\n")
            else:
                # S1/S2/S5: 直接使用 content（LLM 生成的 Markdown）
                if sec.content:
                    # 确保 content 中的标题级别正确（二级标题 → 三级标题）
                    content = sec.content.strip()
                    lines.append(content)
                    lines.append("")
                else:
                    lines.append("> *本节内容为空*")
                    lines.append("")

            # 引用
            if sec.citations:
                lines.append(f"#### 📖 本节参考来源")
                lines.append("")
                for c in sec.citations:
                    cid = c.get('citation_id', '')
                    book = c.get('book_title', '未知书籍')
                    chapter = c.get('chapter', '')
                    excerpt = c.get('excerpt', '')
                    lines.append(f"- **[{cid}]** *{book}* — {chapter}")
                    if excerpt:
                        lines.append(f"  > {excerpt}")
                lines.append("")

            lines.append("---")
            lines.append("")

        # ═══════════ 页脚 ═══════════
        lines.append("---")
        lines.append("")
        lines.append("*本报告由 AI 儿童发展评估系统自动生成，仅供参考。*")
        lines.append("*如有疑虑，请咨询专业儿科医生或儿童发展专家。*")
        lines.append("")

        return "\n".join(lines)

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

    @staticmethod
    async def _save_history_to_db(
        task_id: str,
        question: str,
        result_dict: dict,
        status: str = "completed",
    ) -> None:
        """保存问答结果到历史记录 DB
        status: completed / partial / cancelled / timeout / error
        """
        from src.repository.knowledge_qa_history_repository import (
            KnowledgeQAHistoryRepository,
        )
        from src.models.knowledge_qa_history import KnowledgeQAHistory
        import uuid

        try:
            # 标记部分结果
            if status != "completed":
                result_dict.setdefault("generation_metadata", {})
                result_dict["generation_metadata"]["partial"] = True

            repo = KnowledgeQAHistoryRepository()
            history = KnowledgeQAHistory(
                id=str(uuid.uuid4()),
                task_id=task_id,
                question=question,
                status=status,
                result_json=result_dict,
                matched_books_json=result_dict.get("matched_books"),
            )
            await repo.save(history)
            await repo.delete_oldest(keep_count=200)
        except Exception as e:
            logger.error(f"保存历史记录失败: {e}")

    async def _run_qa_pipeline(self, **ctx) -> Dict[str, Any]:
        """后台执行 LangGraph 流水线"""
        task_id = ctx["task_id"]
        task_type = ctx["task_type"]
        question = ctx["question"]
        book_ids = ctx.get("book_ids", [])
        stream = ctx.get("stream", True)
        cancellation_event = ctx.get("cancellation_event")

        async def _check_cancelled() -> None:
            """检查取消信号，如果已取消则抛出 CancelledError"""
            if cancellation_event and cancellation_event.is_set():
                raise asyncio.CancelledError("任务已被取消")

        # 跟踪部分结果，用于中断/超时时保存到历史记录
        partial_data: Dict[str, Any] = {
            "sections": {},
            "matched_books": [],
        }

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
                    # 收集部分结果
                    partial_data["sections"][sec.get("index")] = sec
                # 保存匹配书籍
                if step == "qa_books_matched" and meta.get("books"):
                    partial_data["matched_books"] = meta["books"]
                await self._task_state.update(task_id, task_type, updates)
            except Exception:
                pass  # 状态更新失败不阻塞主流程

        set_progress_context(callback=push, task_id=task_id, task_type=task_type, cancellation_event=cancellation_event)
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
            # 执行前检查取消信号
            await _check_cancelled()

            # 全局硬超时 900s（15分钟），防止 LLM 卡死
            final_state = await asyncio.wait_for(
                self._graph.ainvoke(initial_state),
                timeout=900.0,
            )

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
            # 保存到历史记录 DB
            result_dict = jsonable_encoder(response.model_dump())
            status = "partial" if final_state.partial else "completed"
            await self._save_history_to_db(task_id, question, result_dict, status=status)
            return jsonable_encoder(response.model_dump())

        except asyncio.CancelledError:
            logger.info(f"知识问答被取消: task_id={task_id}")
            await TaskSsePublisher.publish_cancelled(
                task_type=task_type,
                task_id=task_id,
            )
            # 保存部分结果到历史记录
            try:
                partial_response = self._build_partial_response(
                    question, partial_data, task_id, task_type
                )
                if partial_response:
                    result_dict = jsonable_encoder(partial_response.model_dump())
                    await self._save_history_to_db(
                        task_id, question, result_dict, status="cancelled"
                    )
                    logger.info(f"已保存中断时的部分结果: task_id={task_id}")
            except Exception as e:
                logger.error(f"保存部分结果失败: {e}")
            raise

        except (NoMatchingBooksError, RAGUnavailableError):
            raise

        except asyncio.TimeoutError:
            logger.error(f"知识问答全局超时 (900s): task_id={task_id}")
            await TaskSsePublisher.publish_error(
                task_type=task_type,
                task_id=task_id,
                error="timeout",
                message="处理超时，请简化问题后重试",
            )
            # 保存部分结果到历史记录
            try:
                partial_response = self._build_partial_response(
                    question, partial_data, task_id, task_type
                )
                if partial_response:
                    result_dict = jsonable_encoder(partial_response.model_dump())
                    await self._save_history_to_db(
                        task_id, question, result_dict, status="cancelled"
                    )
            except Exception as e:
                logger.error(f"保存超时部分结果失败: {e}")
            raise

        except Exception as e:
            logger.exception(f"知识问答异常: task_id={task_id}")
            await TaskSsePublisher.publish_error(
                task_type=task_type,
                task_id=task_id,
                error="generation_failed",
                message="内容生成失败，请稍后重试",
            )
            # 保存部分结果到历史记录
            try:
                partial_response = self._build_partial_response(
                    question, partial_data, task_id, task_type
                )
                if partial_response:
                    result_dict = jsonable_encoder(partial_response.model_dump())
                    await self._save_history_to_db(
                        task_id, question, result_dict, status="cancelled"
                    )
            except Exception as save_err:
                logger.error(f"保存异常部分结果失败: {save_err}")
            raise

        finally:
            clear_progress_context()
            clear_prompt_manager()
            clear_http_client()
            if http_client and hasattr(http_client, "close"):
                await http_client.close()
            async with self._task_lock:
                self._concurrent_tasks -= 1

    @staticmethod
    def _build_partial_response(
        question: str,
        partial_data: Dict[str, Any],
        task_id: str,
        task_type: str,
    ) -> KnowledgeQAResponse | None:
        """从部分数据构建中断/超时时的部分响应"""
        sections_dict = partial_data.get("sections", {})
        matched_books = partial_data.get("matched_books", [])

        if not sections_dict and not matched_books:
            return None  # 没有任何数据，不保存

        # 按 index 排序 sections
        sorted_sections = sorted(
            sections_dict.values(),
            key=lambda s: s.get("index", 0),
        )

        # 转为 SectionOutput 列表
        section_outputs = [
            SectionOutput(
                index=s.get("index", i + 1),
                title=s.get("title", f"第{i + 1}节"),
                content=s.get("content", ""),
                citations=s.get("citations", []),
                structured_data=s.get("structured_data", {}),
            )
            for i, s in enumerate(sorted_sections)
        ]

        return KnowledgeQAResponse(
            question=question,
            matched_books=matched_books if matched_books else [],
            sections=section_outputs,
            generation_metadata=GenerationMetadata(
                total_sections=len(section_outputs),
                total_citations=sum(len(s.citations) for s in section_outputs),
                total_time_ms=0,
                model_used="unknown",
                review_model_used="unknown",
                retries={},
                partial=True,
            ),
        )

    def _build_response(
        self, state: KnowledgeQAState, elapsed_ms: float
    ) -> KnowledgeQAResponse:
        """从 LangGraph State 构建最终响应"""
        sections_list = sorted(
            [s for s in state.sections.values() if s],
            key=lambda s: s.index,
        )
        total_citations = sum(len(s.citations) for s in sections_list)

        # 从 S2/S3 structured_data 的 source_books 统计覆盖率
        search_coverage: dict[str, int] = {}
        for sec in sections_list:
            sd = sec.structured_data or {}
            for key in ("problems", "exercise_types"):
                for item in sd.get(key) or []:
                    for book in item.get("source_books") or []:
                        if book:
                            search_coverage[book] = search_coverage.get(book, 0) + 1

        return KnowledgeQAResponse(
            question=state.question,
            matched_books=state.matched_books_detail,
            sections=sections_list,
            contradictions=getattr(state, "contradictions", []),
            generation_metadata=GenerationMetadata(
                total_sections=len(sections_list),
                total_citations=total_citations,
                total_time_ms=int(elapsed_ms),
                model_used="qwen3.5-27b",
                review_model_used="qwen3.5-27b",
                retries=state.retry_counts,
                partial=state.partial,
                search_coverage=search_coverage,
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


def _render_s3_markdown(structured_data: dict) -> str:
    """从 S3 structured_data 渲染运动类型推荐 Markdown（美化版）。"""
    sd = structured_data
    if not isinstance(sd, dict):
        return ""

    lines = []

    ets = sd.get("exercise_types", [])
    if not ets:
        return "> *暂无运动类型推荐数据*"

    child_age = sd.get("child_age_group", "")
    if child_age:
        lines.append(f"> 🧒 **适用年龄段**：{child_age}")
        lines.append("")

    # 按 tier 分组
    tier_order = ["primary", "secondary", "supplementary"]
    tier_config = {
        "primary": {"emoji": "🔴", "label": "核心推荐", "desc": "最针对性、解决首要问题的运动"},
        "secondary": {"emoji": "🟡", "label": "辅助推荐", "desc": "补充性运动，增强干预效果"},
        "supplementary": {"emoji": "🟢", "label": "补充推荐", "desc": "可选运动，丰富方案"},
    }

    grouped = {}
    for et in ets:
        tier = et.get("tier", "secondary")
        if tier not in grouped:
            grouped[tier] = []
        grouped[tier].append(et)

    for tier in tier_order:
        items = grouped.get(tier, [])
        if not items:
            continue
        
        cfg = tier_config.get(tier, {"emoji": "⚪", "label": tier, "desc": ""})
        lines.append(f"### {cfg['emoji']} {cfg['label']}")
        if cfg['desc']:
            lines.append(f"> {cfg['desc']}")
        lines.append("")

        # 表格
        lines.append("| 运动名称 | 类型ID | 分类 | 训练目标 | 推荐理由 |")
        lines.append("|---------|--------|------|---------|--------|")

        for et in items:
            name = et.get("name", "")
            type_id = et.get("type_id", "")
            category = (et.get("category", "") or "")[:12]
            skills = "、".join(et.get("target_skills", [])[:3])
            rationale = (et.get("recommendation_rationale", "") or "")[:80]

            lines.append(f"| **{name}** | {type_id} | {category} | {skills} | {rationale} |")

        lines.append("")

    return "\n".join(lines)
