"""导出服务

负责异步生成 PDF 报告，使用 Redis 存储任务状态，通过 SSE 推送完成事件。
支持并发限制（最多 2 个任务同时执行）。
"""

import asyncio
import os
import uuid
from typing import Optional

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select

try:
    from weasyprint import HTML
except (ImportError, OSError):
    HTML = None

from src.schemas.task import TaskState, TaskStatus
from src.service.task_sse_publisher import TaskSsePublisher
from src.utils.di import get_task_state_service
from src.core.database import db_session_factory
from src.utils.logger import logger

# 导出任务并发限制
EXPORT_CONCURRENCY_LIMIT = 2
# 任务 TTL（24小时）
EXPORT_TASK_TTL = 24 * 60 * 60
# 单个任务超时时间（60秒）
EXPORT_TASK_TIMEOUT = 60

# 信号量控制并发
_export_semaphore = asyncio.Semaphore(EXPORT_CONCURRENCY_LIMIT)
# 任务队列
_export_queue: asyncio.Queue = asyncio.Queue()
# 队列处理是否已启动
_queue_started = False


async def _ensure_queue_processor():
    """确保队列处理器已启动"""
    global _queue_started
    if not _queue_started:
        _queue_started = True
        asyncio.create_task(_process_queue())


async def _process_queue():
    """处理导出任务队列（后台持续运行）"""
    logger.info("导出任务队列处理器已启动")
    task_state_service = get_task_state_service()
    TASK_TYPE = "export"
    
    while True:
        try:
            task_id = await _export_queue.get()
            async with _export_semaphore:
                try:
                    # 获取取消信号
                    cancellation_event = task_state_service.get_cancellation_signal(task_id, TASK_TYPE)
                    
                    await asyncio.wait_for(
                        _generate_pdf(task_id, cancellation_event=cancellation_event),
                        timeout=EXPORT_TASK_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    # 更新状态为 failed
                    await task_state_service.update(
                        task_id=task_id,
                        task_type=TASK_TYPE,
                        updates={"status": TaskStatus.FAILED, "error": "任务执行超时", "message": "执行超时"}
                    )
                    # 推送错误事件
                    await TaskSsePublisher.publish_error(
                        task_type=TASK_TYPE,
                        task_id=task_id,
                        error="任务执行超时"
                    )
                    logger.error(f"导出任务超时: {task_id}")
                except asyncio.CancelledError:
                    # 任务已取消，状态已经在 cancel 方法中更新
                    logger.info(f"导出任务已取消: {task_id}")
                except Exception as e:
                    # 更新状态为 failed
                    await task_state_service.update(
                        task_id=task_id,
                        task_type=TASK_TYPE,
                        updates={"status": TaskStatus.FAILED, "error": str(e), "message": "执行失败"}
                    )
                    # 推送错误事件
                    await TaskSsePublisher.publish_error(
                        task_type=TASK_TYPE,
                        task_id=task_id,
                        error=str(e)
                    )
                    logger.error(f"导出任务执行失败: {task_id}, error={e}")
                finally:
                    _export_queue.task_done()
        except Exception as e:
            logger.error(f"导出队列处理异常: {e}")
            await asyncio.sleep(1)





async def _get_report_data(report_id: str) -> dict:
    """从数据库获取报告数据"""
    from src.models.rag_eval.test_report import RagEvalTestReport
    from src.models.rag_eval.test_run import RagEvalTestRun
    from src.models.rag_eval.test_run_result import RagEvalTestRunResult

    async with db_session_factory() as session:
        # 获取报告
        stmt = select(RagEvalTestReport).where(RagEvalTestReport.id == report_id)
        result = await session.execute(stmt)
        report = result.scalar_one_or_none()
        if not report:
            raise ValueError(f"报告不存在: {report_id}")

        # 获取运行数据
        run_stmt = select(RagEvalTestRun).where(RagEvalTestRun.id == report.run_id)
        run_result = await session.execute(run_stmt)
        run = run_result.scalar_one_or_none()

        # 获取运行结果详情
        results_stmt = select(RagEvalTestRunResult).where(
            RagEvalTestRunResult.run_id == report.run_id
        )
        results_result = await session.execute(results_stmt)
        results = results_result.scalars().all()

        return {
            "report": report,
            "run": run,
            "results": results,
        }


async def _generate_pdf(task_id: str, cancellation_event: Optional[asyncio.Event] = None):
    """生成 PDF 报告

    使用 Jinja2 模板渲染 HTML，再通过 WeasyPrint 转换为 PDF。
    """
    task_state_service = get_task_state_service()
    TASK_TYPE = "export"
    
    # 更新状态为 running
    await task_state_service.update(
        task_id=task_id,
        task_type=TASK_TYPE,
        updates={"status": TaskStatus.RUNNING, "message": "生成PDF中"}
    )

    # 获取任务信息
    task_state = await task_state_service.get(task_id, TASK_TYPE)
    if not task_state:
        raise ValueError(f"任务不存在: {task_id}")

    report_id = task_state.metadata.get("report_id")
    user_id = task_state.metadata.get("user_id", "anonymous")
    if not report_id:
        raise ValueError("任务缺少 report_id")

    # 获取报告数据
    report_data = await _get_report_data(report_id)
    run = report_data["run"]
    results = report_data["results"]

    # 渲染模板
    template_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "templates", "reports"
    )
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("report_summary.html")

    # 准备模板数据
    bad_cases = [r for r in results if r.status == "failed"]
    html_content = template.render(
        report_id=report_id,
        run=run,
        results=results,
        bad_cases=bad_cases,
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
        total_cases=len(results),
        passed_cases=len([r for r in results if r.status == "passed"]),
        failed_cases=len(bad_cases),
        precision=run.overall_precision or 0,
        recall=run.overall_recall or 0,
        f1=run.overall_f1 or 0,
        mrr=run.overall_mrr or 0,
        ndcg=run.overall_ndcg or 0,
    )

    # 生成 PDF
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "..", "..", "storage", "exports"
    )
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, f"report_{report_id}.pdf")

    if HTML is None:
        raise RuntimeError("WeasyPrint 未正确安装，无法生成 PDF")
        
    # 检查是否取消
    if cancellation_event and cancellation_event.is_set():
        raise asyncio.CancelledError("任务已取消")

    HTML(string=html_content).write_pdf(file_path)

    # 更新任务状态为 completed
    await task_state_service.update(
        task_id=task_id,
        task_type=TASK_TYPE,
        updates={
            "status": TaskStatus.COMPLETED,
            "progress": 100.0,
            "message": "导出完成",
            "result": {"file_path": file_path, "report_id": report_id}
        }
    )

    # 发布 SSE 事件
    await TaskSsePublisher.publish_complete(
        task_type=TASK_TYPE,
        task_id=task_id,
        result={"file_path": file_path, "report_id": report_id, "user_id": user_id}
    )

    logger.info(f"PDF 导出完成: task_id={task_id}, report_id={report_id}")


async def create_export_task(report_id: str, user_id: str = "anonymous") -> str:
    """创建异步 PDF 导出任务

    Args:
        report_id: 报告ID
        user_id: 用户ID（用于 SSE 推送）

    Returns:
        任务ID
    """
    task_id = str(uuid.uuid4())
    TASK_TYPE = "export"
    task_state_service = get_task_state_service()

    # 创建初始任务状态
    initial_state = TaskState.create(
        task_id=task_id,
        task_type=TASK_TYPE,
        metadata={"report_id": report_id, "user_id": user_id},
    )
    initial_state.message = "等待导出"
    await task_state_service.create(initial_state)

    # 加入队列
    await _export_queue.put(task_id)

    # 确保队列处理器已启动
    await _ensure_queue_processor()

    logger.info(f"导出任务已创建: task_id={task_id}, report_id={report_id}")
    return task_id


async def get_export_status(task_id: str) -> Optional[dict]:
    """获取导出任务状态

    Args:
        task_id: 任务ID

    Returns:
        任务状态信息，不存在则返回 None
    """
    task_state_service = get_task_state_service()
    TASK_TYPE = "export"
    
    task_state = await task_state_service.get(task_id, TASK_TYPE)
    if not task_state:
        return None
        
    return {
        "task_id": task_state.task_id,
        "status": task_state.status.value,
        "progress": task_state.progress,
        "message": task_state.message,
        "error": task_state.error,
        "result": task_state.result,
        "metadata": task_state.metadata,
        "created_at": task_state.created_at.isoformat() if task_state.created_at else None,
        "started_at": task_state.started_at.isoformat() if task_state.started_at else None,
        "completed_at": task_state.completed_at.isoformat() if task_state.completed_at else None
    }


async def get_export_file_path(task_id: str) -> Optional[str]:
    """获取导出文件路径

    Args:
        task_id: 任务ID

    Returns:
        文件路径，任务未完成或不存在则返回 None
    """
    task_state_service = get_task_state_service()
    TASK_TYPE = "export"
    
    task_state = await task_state_service.get(task_id, TASK_TYPE)
    if task_state and task_state.status == TaskStatus.COMPLETED:
        return task_state.result.get("file_path") if task_state.result else None
    return None
