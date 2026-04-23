"""RAG 文档上传控制器（已迁移到新任务状态服务）"""

import asyncio
import os
import shutil
import uuid

from fastapi import APIRouter, BackgroundTasks, File, Query, UploadFile

from src.config import settings
from src.schemas.common import APIResponse
from src.schemas.task import TaskState, TaskStatus
from src.service.rag_service import rag_service
from src.service.task_sse_publisher import TaskSsePublisher
from src.service.task_state_service import TaskStateService
from src.utils.di import get_task_state_service
from src.utils.exceptions import (ChunkNotFoundException,
                                   DocumentNotFoundException,
                                   InternalServerErrorException,
                                   InvalidParamsException,
                                   ResourceNotFoundException,
                                   TaskCancelledException,
                                   UnsupportedFileTypeException)
from src.utils.logger import logger

TASK_TYPE = "upload"
UPLOAD_DIR = settings.rag_temp_upload_dir
MAX_CONCURRENT_TASKS = settings.rag_upload_max_concurrent_tasks

# 确保上传目录存在
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# 全局协程信号量，限制并发数（懒加载，确保绑定到正确的事件循环）
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    """获取信号量（懒加载，确保在当前事件循环中创建）"""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    return _semaphore


def _save_uploaded_file(file_obj, file_path: str):
    """保存上传文件到磁盘（同步，用于线程池执行）"""
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file_obj, buffer)


async def process_book_background(task_id: str, file_path: str, original_filename: str):
    """后台处理书籍上传和索引构建（异步任务，支持并发限制）"""
    service = get_task_state_service()
    
    async with _get_semaphore():
        try:
            # 更新状态为 running
            await service.update(task_id, TASK_TYPE, {
                "status": TaskStatus.RUNNING.value,
                "message": "文件处理中，正在解析内容",
                "stage": "parsing",
                "progress": 10.0,
            })
            
            # 推送 SSE 事件
            await TaskSsePublisher.publish_progress(
                task_type=TASK_TYPE,
                task_id=task_id,
                status=TaskStatus.RUNNING,
                progress=10.0,
                stage="parsing",
                message="文件处理中，正在解析内容",
            )

            logger.info(f"Started processing task {task_id} in background")

            # 同步进度回调（直接 await，保证顺序，消除竞态条件）
            async def progress_callback(stage: str, progress: float, message: str):
                # 检查取消信号
                if await service.check_cancellation(task_id, TASK_TYPE):
                    logger.info(f"Task {task_id} cancelled, stopping progress")
                    raise TaskCancelledException()
                
                # 更新状态
                await service.update(task_id, TASK_TYPE, {
                    "stage": stage,
                    "progress": progress,
                    "message": message,
                })
                
                # 推送 SSE 事件
                await TaskSsePublisher.publish_progress(
                    task_type=TASK_TYPE,
                    task_id=task_id,
                    progress=progress,
                    stage=stage,
                    message=message,
                )

            # 执行索引构建，传入进度回调和 task_id
            await rag_service.ingest_book(
                file_path,
                original_filename=original_filename,
                progress_callback=progress_callback,
                task_id=task_id,
            )

            # 所有进度回调已执行完毕，不会被覆盖
            # 更新任务状态为成功
            await service.update(task_id, TASK_TYPE, {
                "status": TaskStatus.COMPLETED.value,
                "message": "文件上传并索引成功",
                "stage": "completed",
                "progress": 100.0,
            })
            
            # 推送 SSE 完成事件
            await TaskSsePublisher.publish_complete(
                task_type=TASK_TYPE,
                task_id=task_id,
                message="文件上传并索引成功",
            )

            # 清理取消信号
            service.cleanup_cancellation_signal(task_id, TASK_TYPE)

            # 清理临时文件
            if os.path.exists(file_path):
                os.remove(file_path)

            logger.info(f"Task {task_id} completed successfully")

        except TaskCancelledException:
            # 任务被取消
            logger.info(f"Task {task_id} cancelled by user")
            
            await service.update(task_id, TASK_TYPE, {
                "status": TaskStatus.CANCELLED.value,
                "message": "任务已取消",
                "progress": 0.0,
            })
            
            # 推送 SSE 取消事件
            await TaskSsePublisher.publish_cancelled(
                task_type=TASK_TYPE,
                task_id=task_id,
            )
            
            # 清理取消信号
            service.cleanup_cancellation_signal(task_id, TASK_TYPE)

            # 清理临时文件
            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception as e:
            # 更新任务状态为失败
            await service.update(task_id, TASK_TYPE, {
                "status": TaskStatus.FAILED.value,
                "error": str(e),
                "message": f"处理失败: {str(e)}",
            })
            
            # 推送 SSE 错误事件
            await TaskSsePublisher.publish_error(
                task_type=TASK_TYPE,
                task_id=task_id,
                error=str(e),
                message=f"处理失败: {str(e)}",
            )
            
            # 清理取消信号
            service.cleanup_cancellation_signal(task_id, TASK_TYPE)

            # 清理临时文件
            if os.path.exists(file_path):
                os.remove(file_path)

            logger.opt(exception=True).error(f"Task {task_id} failed")


router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post("/upload")
async def upload_book(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """上传书籍文件（PDF/EPUB）并进行 RAG 索引（异步处理）"""
    if not (file.filename.endswith(".pdf") or file.filename.endswith(".epub")):
        raise UnsupportedFileTypeException(file_type=os.path.splitext(file.filename)[1])

    # 生成唯一文件名避免冲突
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # 生成任务 ID
    task_id = str(uuid.uuid4())
    service = get_task_state_service()

    try:
        # 保存上传文件
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _save_uploaded_file(file.file, file_path),
        )

        # 创建任务状态（pending）
        state = TaskState.create(
            task_id=task_id,
            task_type=TASK_TYPE,
            metadata={"filename": file.filename},
        )
        await service.create(state)
        
        # 注册取消信号
        service.get_cancellation_signal(task_id, TASK_TYPE)

        logger.info(f"Created upload task {task_id}")

        # 添加到后台任务
        background_tasks.add_task(
            process_book_background, task_id, file_path, file.filename
        )

        return APIResponse.success(data={
            "task_id": task_id,
            "filename": file.filename,
            "message": "文件已上传，正在后台处理中，可通过任务 ID 查询处理状态",
        })

    except Exception as e:
        # 失败时清理
        if os.path.exists(file_path):
            os.remove(file_path)
        raise InternalServerErrorException(message=f"文件上传失败: {str(e)}")


@router.post("/tasks/{task_id}/cancel")
async def cancel_upload_task(task_id: str):
    """取消正在进行的上传任务"""
    service = get_task_state_service()
    
    task = await service.get(task_id, TASK_TYPE)
    if not task:
        raise ResourceNotFoundException(message="任务不存在")

    if task.is_terminal:
        return APIResponse.success(message=f"任务当前状态为 {task.status.value}，无需取消")

    # 设置取消信号并更新状态
    success = await service.cancel(task_id, TASK_TYPE)
    
    if not success:
        return APIResponse.success(message=f"任务可能已进入终态，无法取消")

    # 推送 SSE 取消事件
    await TaskSsePublisher.publish_cancelled(
        task_type=TASK_TYPE,
        task_id=task_id,
    )

    logger.info(f"Task {task_id} marked for cancellation")
    return APIResponse.success(message="任务已标记取消")


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除指定任务（仅支持删除已结束的任务：成功/失败/已取消）"""
    service = get_task_state_service()
    
    task = await service.get(task_id, TASK_TYPE)
    if not task:
        raise ResourceNotFoundException(message="任务不存在")
    
    if task.is_active:
        raise InvalidParamsException(message="无法删除正在处理中的任务，请先取消")
    
    # 删除任务状态
    await service.delete(task_id, TASK_TYPE)
    
    return APIResponse.success(message="任务已删除")


@router.get("/tasks")
async def list_upload_tasks():
    """获取所有当前的上传任务（仅活跃任务：pending/running）"""
    service = get_task_state_service()
    
    # 只获取活跃任务（pending/running）
    active_tasks = await service.list_active(TASK_TYPE)
    
    # 转换为前端期望的格式
    tasks_list = []
    for task in active_tasks:
        task_data = {
            "task_id": task.task_id,
            "status": task.status.value,
            "filename": task.metadata.get("filename", ""),
            "created_at": task.created_at,
            "message": task.message or "",
            "progress": task.progress,
            "stage": task.stage or "pending",
        }
        tasks_list.append(task_data)
    
    # 按创建时间倒序排列
    tasks_list.sort(key=lambda x: x["created_at"], reverse=True)
    
    return APIResponse.success(data={"tasks": tasks_list})


@router.get("/tasks/{task_id}")
async def get_upload_task_status(task_id: str):
    """查询上传任务的处理状态"""
    service = get_task_state_service()
    
    task = await service.get(task_id, TASK_TYPE)
    if not task:
        logger.warning(f"Task {task_id} not found")
        raise ResourceNotFoundException(message="任务不存在")

    logger.info(
        f"Query task {task_id}: status={task.status.value}, "
        f"progress={task.progress:.1f}%, stage={task.stage}"
    )

    response = {
        "task_id": task.task_id,
        "status": task.status.value,
        "filename": task.metadata.get("filename", ""),
        "created_at": task.created_at,
        "message": task.message or "",
        "progress": task.progress,
        "stage": task.stage or "pending",
    }
    # 添加 completed_at 字段（如果存在）
    if task.completed_at is not None:
        response["completed_at"] = task.completed_at

    if task.status == TaskStatus.FAILED:
        response["error"] = task.error or "未知错误"

    return APIResponse.success(data=response)


@router.get("/status")
async def get_rag_status():
    """获取 RAG 服务状态"""
    from src.service.document_manager import document_manager

    # 索引就绪需要同时满足：索引存在且至少有一个已索引文档
    has_documents = len(document_manager.list_documents()) > 0
    index_ready = rag_service.index_manager.is_index_available() and has_documents

    return APIResponse.success(data={
        "index_ready": index_ready,
        "storage_dir": os.path.abspath(settings.rag_storage_dir),
        "document_count": len(document_manager.list_documents()),
    })


@router.delete("/documents/{filename}")
async def delete_document(filename: str):
    """删除指定文档及其索引"""
    # 删除文档记录
    rag_service.delete_document(filename)
    
    return APIResponse.success(message=f"Document {filename} deleted.")


@router.get("/documents")
async def list_documents():
    """列出所有已索引文档"""
    from src.service.document_manager import document_manager

    docs = document_manager.list_documents()

    # 映射到前端期望的格式
    results = []
    for doc in docs:
        results.append(
            {
                "file_hash": doc.file_hash,
                "file_name": doc.file_name,
                "uploaded_at": doc.upload_date,
                "total_pages": doc.metadata.total_pages if doc.metadata else 0,
            }
        )

    return APIResponse.success(data={"documents": results})


@router.get("/search")
async def search_knowledge_content(
    query: str, 
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """搜索知识库内容，返回匹配的片段和元数据（支持分页）"""
    if not query.strip():
        raise InvalidParamsException(message="搜索关键词不能为空")

    try:
        result = await rag_service.search_content(query.strip(), limit, offset)
        return APIResponse.success(data={
            "total": result["total"], 
            "results": result["results"]
        })
    except Exception as e:
        raise InternalServerErrorException(message=f"搜索失败: {str(e)}")


# 分层内容生成进度查询接口
@router.get("/layered-progress/{task_id}")
async def get_layered_content_progress(task_id: str):
    """查询分层内容生成任务进度"""
    from src.core.layered_content_generator import get_task_progress
    
    progress = get_task_progress(task_id)
    if not progress:
        raise ResourceNotFoundException(message="任务不存在")
    
    return APIResponse.success(data={
        "task_id": task_id,
        **progress
    })


@router.get("/layered-progress")
async def list_all_layered_tasks():
    """获取所有分层内容生成任务进度"""
    from src.core.layered_content_generator import list_all_tasks
    
    tasks = list_all_tasks()
    return APIResponse.success(data={"tasks": tasks})


@router.get("/documents/{file_hash}/chunks")
async def get_document_chunks(file_hash: str, page: int = 1, page_size: int = 20):
    """获取指定文档的分块列表（支持分页）
    
    Args:
        file_hash: 文档哈希值
        page: 页码（从 1 开始，默认 1）
        page_size: 每页数量（默认 20，最大 100）
    """
    # 限制 page_size 范围
    page_size = min(max(1, page_size), 100)
    
    logger.info(f"Getting chunks for file_hash: {file_hash}, page: {page}, page_size: {page_size}")
    result = rag_service.get_document_chunks(file_hash, page, page_size)
    logger.info(f"Found {result['total']} chunks for file_hash: {file_hash}")
    return APIResponse.success(data={
        "file_hash": file_hash,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "total_pages": result["total_pages"],
        "chunks": result["chunks"]
    })


@router.get("/chunks/{chunk_id}")
async def get_chunk_detail(chunk_id: str):
    """获取指定分块的详细信息"""
    chunk = rag_service.get_chunk_detail(chunk_id)
    if not chunk:
        raise ChunkNotFoundException(chunk_id=chunk_id)
    return APIResponse.success(data={
        "chunk": chunk
    })
