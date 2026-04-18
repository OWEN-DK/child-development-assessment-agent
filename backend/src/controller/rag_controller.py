import asyncio
import os
import shutil
import time
import uuid

from fastapi import (APIRouter, BackgroundTasks, File, Query,
                     UploadFile)

from src.config import settings
from src.schemas.common import APIResponse
from src.service.rag_service import rag_service
from src.service.task_status_service import task_status_service
from src.utils.exceptions import (ChunkNotFoundException,
                                   DocumentNotFoundException,
                                   InternalServerErrorException,
                                   InvalidParamsException,
                                   ResourceNotFoundException,
                                   TaskCancelledException,
                                   UnsupportedFileTypeException)
from src.utils.logger import logger

router = APIRouter(prefix="/rag", tags=["RAG"])

UPLOAD_DIR = settings.rag_temp_upload_dir
MAX_CONCURRENT_TASKS = settings.rag_upload_max_concurrent_tasks  # 最大并发处理任务数

# Ensure upload directory exists
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# 任务状态枚举
TASK_STATUS_PENDING = "pending"
TASK_STATUS_PROCESSING = "processing"
TASK_STATUS_SUCCESS = "success"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_CANCELLED = "cancelled"

# 全局协程信号量，限制并发数
semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)


def process_book_background(task_id: str, file_path: str, original_filename: str):
    """后台处理书籍上传和索引构建（同步包装异步任务，支持并发限制）"""

    async def run_processing():
        async with semaphore:  # 限制并发数
            try:
                # 更新任务状态为处理中
                task = await task_status_service.get_status(task_id)
                if task:
                    await task_status_service.update_status(task_id, {
                        "status": TASK_STATUS_PROCESSING,
                        "message": "文件处理中，正在解析内容",
                        "stage": "parsing",
                        "progress": 10.0,
                    })

                logger.info(
                    f"Started processing task {task_id} in background"
                )

                # 自定义进度回调函数
                def progress_callback(stage: str, progress: float, message: str):
                    logger.info(
                        f"Progress callback for {task_id}: {stage} {progress:.1f}%"
                    )
                    # 在同步函数中使用 asyncio.run 调用异步方法
                    async def update():
                        task = await task_status_service.get_status(task_id)
                        if task:
                            # 检查任务是否已被取消
                            if task["status"] == TASK_STATUS_CANCELLED:
                                raise TaskCancelledException("Task cancelled by user")

                            await task_status_service.update_status(task_id, {
                                "stage": stage,
                                "progress": progress,
                                "message": message,
                            })
                        else:
                            logger.error(
                                f"Task {task_id} not found during callback"
                            )
                    
                    asyncio.run(update())

                # 执行索引构建，传入进度回调
                await rag_service.ingest_book(
                    file_path,
                    original_filename=original_filename,
                    progress_callback=progress_callback,
                )

                # 更新任务状态为成功
                task = await task_status_service.get_status(task_id)
                if task and task.get("status") != TASK_STATUS_CANCELLED:
                    await task_status_service.update_status(task_id, {
                        "status": TASK_STATUS_SUCCESS,
                        "message": "文件上传并索引成功",
                        "stage": "completed",
                        "progress": 100.0,
                    })

                # 清理临时文件
                if os.path.exists(file_path):
                    os.remove(file_path)

                logger.info(f"Task {task_id} completed successfully")

            except TaskCancelledException:
                # 任务被取消，已在 ingest_book 中清理了文档记录
                logger.info(f"Task {task_id} cancelled by user")
                await task_status_service.update_status(task_id, {
                    "status": TASK_STATUS_CANCELLED,
                    "message": "任务已取消",
                    "progress": 0.0,
                })

                # 清理临时文件
                if os.path.exists(file_path):
                    os.remove(file_path)

            except Exception as e:
                # 更新任务状态为失败
                await task_status_service.update_status(task_id, {
                    "status": TASK_STATUS_FAILED,
                    "error": str(e),
                    "message": f"处理失败: {str(e)}",
                })

                # 清理临时文件
                if os.path.exists(file_path):
                    os.remove(file_path)

                logger.error(f"Task {task_id} failed: {str(e)}", exc_info=True)

    # 运行异步任务
    asyncio.run(run_processing())


@router.post("/upload")
async def upload_book(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    上传书籍文件（PDF/EPUB）并进行 RAG 索引（异步处理）。
    """
    if not (file.filename.endswith(".pdf") or file.filename.endswith(".epub")):
        raise UnsupportedFileTypeException(file_type=os.path.splitext(file.filename)[1])

    # Generate a unique filename to avoid collisions
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # 生成任务ID
    task_id = str(uuid.uuid4())

    try:
        # Save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 初始化任务状态
        await task_status_service.set_status(task_id, {
            "status": TASK_STATUS_PENDING,
            "filename": file.filename,
            "created_at": time.time(),
            "message": "文件已上传，正在排队处理",
            "progress": 0.0,
            "stage": "pending",  # pending, parsing, chunking, embedding, indexing, completed
        })

        logger.info(
            f"Created upload task {task_id}"
        )

        # 添加到后台任务
        background_tasks.add_task(
            process_book_background, task_id, file_path, file.filename
        )

        return APIResponse.success(data={
            "task_id": task_id,
            "filename": file.filename,
            "message": "文件已上传，正在后台处理中，可通过任务ID查询处理状态",
        })

    except Exception as e:
        # Clean up if failed
        if os.path.exists(file_path):
            os.remove(file_path)
        raise InternalServerErrorException(message=f"文件上传失败: {str(e)}")


@router.post("/tasks/{task_id}/cancel")
async def cancel_upload_task(task_id: str):
    """
    取消正在进行的上传任务
    """
    task = await task_status_service.get_status(task_id)
    if not task:
        raise ResourceNotFoundException(message="任务不存在")

    if task["status"] in [
        TASK_STATUS_SUCCESS,
        TASK_STATUS_FAILED,
        TASK_STATUS_CANCELLED,
    ]:
        return APIResponse.success(message=f"任务当前状态为 {task['status']}，无需取消")

    # 标记为已取消，后续 progress_callback 会检测到并中断
    await task_status_service.update_status(task_id, {
        "status": TASK_STATUS_CANCELLED,
        "message": "正在取消任务...",
    })

    logger.info(f"Task {task_id} marked for cancellation")
    return APIResponse.success(message="任务已标记取消")


@router.get("/tasks")
async def list_upload_tasks():
    """
    获取所有当前的上传任务（包括处理中、成功、失败的）
    """
    tasks_list = await task_status_service.list_statuses()

    # 按创建时间倒序排列
    tasks_list.sort(key=lambda x: x["created_at"], reverse=True)
    return APIResponse.success(data={"tasks": tasks_list})


@router.get("/tasks/{task_id}")
async def get_upload_task_status(task_id: str):
    """
    查询上传任务的处理状态
    """
    task = await task_status_service.get_status(task_id)
    if not task:
        logger.warning(
            f"Task {task_id} not found"
        )
        raise ResourceNotFoundException(message="任务不存在")

    logger.info(
        f"Query task {task_id}: status={task['status']}, progress={task.get('progress'):.1f}%, stage={task.get('stage')}"
    )

    response = {
        "task_id": task_id,
        "status": task["status"],
        "filename": task["filename"],
        "created_at": task["created_at"],
        "message": task.get("message", ""),
        "progress": task.get("progress", 0.0),
        "stage": task.get("stage", "pending"),
    }

    if task["status"] == TASK_STATUS_FAILED:
        response["error"] = task.get("error", "未知错误")

    return APIResponse.success(data=response)


@router.get("/status")
async def get_rag_status():
    """
    获取 RAG 服务状态
    """
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
    """
    删除指定文档及其索引
    """
    from src.service.document_ingestion_service import import_task_manager

    # 先删除文档记录
    success = rag_service.delete_document(filename)
    
    # 清理相关的任务状态
    try:
        # 查找并删除所有与该文件相关的任务
        for task_file in os.listdir(import_task_manager.task_dir):
            if not task_file.endswith(".json"):
                continue
            task_path = os.path.join(import_task_manager.task_dir, task_file)
            try:
                import json
                with open(task_path, "r", encoding="utf-8") as f:
                    task_state = json.load(f)
                if task_state.get("file_name") == filename:
                    os.remove(task_path)
                    logger.info(f"Deleted task state: {task_file}")
            except Exception as e:
                logger.warning(f"Failed to process task state {task_file}: {e}")
    except Exception as e:
        logger.error(f"Failed to cleanup task states: {e}")
    
    if not success:
        raise DocumentNotFoundException(document_id=filename)
    return APIResponse.success(message=f"Document {filename} deleted.")


@router.get("/documents")
async def list_documents():
    """
    列出所有已索引文档
    """
    from src.service.document_manager import document_manager

    docs = document_manager.list_documents()

    # Map to frontend expected format
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
    """
    搜索知识库内容，返回匹配的片段和元数据（支持分页）
    """
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
    """
    查询分层内容生成任务进度
    """
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
    """
    获取所有分层内容生成任务进度
    """
    from src.core.layered_content_generator import list_all_tasks
    
    tasks = list_all_tasks()
    return APIResponse.success(data={"tasks": tasks})


@router.get("/documents/{file_hash}/chunks")
async def get_document_chunks(file_hash: str, page: int = 1, page_size: int = 20):
    """
    获取指定文档的分块列表（支持分页）
    
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
    """
    获取指定分块的详细信息
    """
    chunk = rag_service.get_chunk_detail(chunk_id)
    if not chunk:
        raise ChunkNotFoundException(chunk_id=chunk_id)
    return APIResponse.success(data={
        "chunk": chunk
    })
