"""导出控制器

提供 PDF 异步导出、状态查询和文件下载 API。
"""

import os

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from src.service import export_service
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/rag/test", tags=["RAG Eval Export"])


@router.post("/reports/{report_id}/export")
async def create_export(report_id: str):
    """创建异步 PDF 导出任务

    提交报告 ID，后台异步生成 PDF，完成后通过 SSE 推送事件。
    """
    try:
        task_id = await export_service.create_export_task(report_id)
        return {
            "status": "accepted",
            "task_id": task_id,
            "message": "导出任务已提交，请通过 task_id 查询状态",
        }
    except Exception as e:
        logger.error(f"创建导出任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建导出任务失败: {str(e)}")


@router.get("/exports/{task_id}/status")
async def get_export_status(task_id: str):
    """获取导出任务状态

    返回任务状态：pending/processing/completed/failed
    """
    try:
        status = await export_service.get_export_status(task_id)
        if not status:
            raise HTTPException(status_code=404, detail="导出任务不存在")
        return {
            "status": "success",
            "data": status,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取导出状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取导出状态失败: {str(e)}")


@router.get("/exports/{task_id}/download")
async def download_export(task_id: str):
    """下载导出文件

    仅在任务状态为 completed 时可用，返回 PDF 文件。
    """
    try:
        file_path = await export_service.get_export_file_path(task_id)
        if not file_path:
            status = await export_service.get_export_status(task_id)
            if not status:
                raise HTTPException(status_code=404, detail="导出任务不存在")
            if status.get("status") == "failed":
                raise HTTPException(
                    status_code=500,
                    detail=f"导出失败: {status.get('error', '未知错误')}",
                )
            raise HTTPException(
                status_code=400,
                detail=f"导出尚未完成，当前状态: {status.get('status')}",
            )

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="导出文件不存在")

        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=f"rag_eval_report_{task_id[:8]}.pdf",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载导出文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载导出文件失败: {str(e)}")
