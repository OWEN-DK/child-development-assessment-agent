"""导出控制器

提供 PDF 异步导出、状态查询和文件下载 API。
"""

import os

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from src.service import export_service
from src.schemas.common import APIResponse
from src.utils.exceptions import (InternalServerErrorException,
                                    InvalidParamsException,
                                    ResourceNotFoundException)
from src.utils.response import api_handler

router = APIRouter(prefix="/api/v1/rag/test", tags=["RAG Eval Export"])


@router.post("/reports/{report_id}/export")
@api_handler("创建导出任务")
async def create_export(report_id: str):
    """创建异步 PDF 导出任务

    提交报告 ID，后台异步生成 PDF，完成后通过 SSE 推送事件。
    """
    task_id = await export_service.create_export_task(report_id)
    return APIResponse.success(data={
        "task_id": task_id,
        "message": "导出任务已提交，请通过 task_id 查询状态",
    })


@router.get("/exports/{task_id}/status")
@api_handler("获取导出状态")
async def get_export_status(task_id: str):
    """获取导出任务状态

    返回任务状态：pending/processing/completed/failed
    """
    status = await export_service.get_export_status(task_id)
    if not status:
        raise ResourceNotFoundException(message="导出任务不存在")
    return APIResponse.success(data=status)


@router.get("/exports/{task_id}/download")
@api_handler("下载导出文件")
async def download_export(task_id: str):
    """下载导出文件

    仅在任务状态为 completed 时可用，返回 PDF 文件。
    """
    file_path = await export_service.get_export_file_path(task_id)
    if not file_path:
        status = await export_service.get_export_status(task_id)
        if not status:
            raise ResourceNotFoundException(message="导出任务不存在")
        if status.get("status") == "failed":
            raise InternalServerErrorException(
                message=f"导出失败: {status.get('error', '未知错误')}",
            )
        raise InvalidParamsException(
            message=f"导出尚未完成，当前状态: {status.get('status')}",
        )

    if not os.path.exists(file_path):
        raise ResourceNotFoundException(message="导出文件不存在")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"rag_eval_report_{task_id[:8]}.pdf",
    )
