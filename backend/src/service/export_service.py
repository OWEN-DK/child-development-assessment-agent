"""导出服务

负责异步生成 PDF 报告，使用 Redis 存储任务状态，通过 SSE 推送完成事件。
支持并发限制（最多 2 个任务同时执行）。
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Optional

from jinja2 import Environment, FileSystemLoader

try:
    from weasyprint import HTML
except (ImportError, OSError):
    HTML = None

from src.core.database import db_session_factory
from src.core.redis_client import RedisClient
from src.api.sse import SSEPublisher
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
    while True:
        try:
            task_id = await _export_queue.get()
            async with _export_semaphore:
                try:
                    await asyncio.wait_for(
                        _generate_pdf(task_id),
                        timeout=EXPORT_TASK_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    await _update_task_status(task_id, "failed", error="任务执行超时")
                    logger.error(f"导出任务超时: {task_id}")
                except Exception as e:
                    await _update_task_status(task_id, "failed", error=str(e))
                    logger.error(f"导出任务执行失败: {task_id}, error={e}")
                finally:
                    _export_queue.task_done()
        except Exception as e:
            logger.error(f"导出队列处理异常: {e}")
            await asyncio.sleep(1)


async def _update_task_status(
    task_id: str,
    status: str,
    file_path: Optional[str] = None,
    error: Optional[str] = None,
):
    """更新任务状态到 Redis"""
    redis_client = RedisClient.get_client()
    task_data = {
        "task_id": task_id,
        "status": status,
        "file_path": file_path,
        "error": error,
        "updated_at": datetime.utcnow().isoformat(),
    }
    await redis_client.set(
        f"rag_eval:export:{task_id}",
        json.dumps(task_data),
        ex=EXPORT_TASK_TTL,
    )


async def _get_task_status(task_id: str) -> Optional[dict]:
    """从 Redis 获取任务状态"""
    redis_client = RedisClient.get_client()
    data = await redis_client.get(f"rag_eval:export:{task_id}")
    if data:
        return json.loads(data)
    return None


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


async def _generate_pdf(task_id: str):
    """生成 PDF 报告

    使用 Jinja2 模板渲染 HTML，再通过 WeasyPrint 转换为 PDF。
    """
    await _update_task_status(task_id, "processing")

    # 获取任务信息
    task_info = await _get_task_status(task_id)
    if not task_info:
        raise ValueError(f"任务不存在: {task_id}")

    report_id = task_info.get("report_id")
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

    HTML(string=html_content).write_pdf(file_path)

    # 更新任务状态
    await _update_task_status(task_id, "completed", file_path=file_path)

    # 发布 SSE 事件
    user_id = task_info.get("user_id", "anonymous")
    await SSEPublisher.publish(
        f"exports:{user_id}",
        {
            "type": "export_complete",
            "task_id": task_id,
            "report_id": report_id,
            "file_path": file_path,
            "status": "completed",
        },
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

    # 保存任务信息到 Redis
    redis_client = RedisClient.get_client()
    task_data = {
        "task_id": task_id,
        "report_id": report_id,
        "user_id": user_id,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "file_path": None,
        "error": None,
    }
    await redis_client.set(
        f"rag_eval:export:{task_id}",
        json.dumps(task_data),
        ex=EXPORT_TASK_TTL,
    )

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
    return await _get_task_status(task_id)


async def get_export_file_path(task_id: str) -> Optional[str]:
    """获取导出文件路径

    Args:
        task_id: 任务ID

    Returns:
        文件路径，任务未完成或不存在则返回 None
    """
    task_info = await _get_task_status(task_id)
    if task_info and task_info.get("status") == "completed":
        return task_info.get("file_path")
    return None
