import os
import shutil
import uuid
import time
import asyncio
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Query
from src.service.rag_service import rag_service
from src.utils.logger import logger
from src.config.settings import settings

router = APIRouter(prefix="/rag", tags=["RAG"])

UPLOAD_DIR = settings.rag_temp_upload_dir
MAX_CONCURRENT_TASKS = settings.rag_upload_max_concurrent_tasks  # 最大并发处理任务数

# Ensure upload directory exists
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# 任务状态跟踪
upload_tasks = {}
# 任务状态枚举
TASK_STATUS_PENDING = "pending"
TASK_STATUS_PROCESSING = "processing"
TASK_STATUS_SUCCESS = "success"
TASK_STATUS_FAILED = "failed"

# 全局协程信号量，限制并发数
semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)


def process_book_background(task_id: str, file_path: str, original_filename: str):
    """后台处理书籍上传和索引构建（同步包装异步任务，支持并发限制）"""
    async def run_processing():
        async with semaphore:  # 限制并发数
            try:
                # 更新任务状态为处理中
                upload_tasks[task_id]["status"] = TASK_STATUS_PROCESSING
                upload_tasks[task_id]["message"] = "文件处理中，正在解析内容"
                upload_tasks[task_id]["stage"] = "parsing"
                upload_tasks[task_id]["progress"] = 10.0
                
                # 自定义进度回调函数
                def progress_callback(stage: str, progress: float, message: str):
                    upload_tasks[task_id]["stage"] = stage
                    upload_tasks[task_id]["progress"] = progress
                    upload_tasks[task_id]["message"] = message
                
                # 执行索引构建，传入进度回调
                await rag_service.ingest_book(
                    file_path, 
                    original_filename=original_filename,
                    progress_callback=progress_callback
                )
                
                # 更新任务状态为成功
                upload_tasks[task_id]["status"] = TASK_STATUS_SUCCESS
                upload_tasks[task_id]["message"] = "文件上传并索引成功"
                upload_tasks[task_id]["stage"] = "completed"
                upload_tasks[task_id]["progress"] = 100.0
                
                # 清理临时文件
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
                logger.info(f"Task {task_id} completed successfully for file {original_filename}")
                
            except Exception as e:
                # 更新任务状态为失败
                upload_tasks[task_id]["status"] = TASK_STATUS_FAILED
                upload_tasks[task_id]["error"] = str(e)
                upload_tasks[task_id]["message"] = f"处理失败: {str(e)}"
                
                # 清理临时文件
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
                logger.error(f"Task {task_id} failed for file {original_filename}: {str(e)}")
    
    # 运行异步任务
    asyncio.run(run_processing())


@router.post("/upload")
async def upload_book(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    上传书籍文件（PDF/EPUB）并进行 RAG 索引（异步处理）。
    """
    if not (file.filename.endswith(".pdf") or file.filename.endswith(".epub")):
        raise HTTPException(
            status_code=400, detail="Only PDF and EPUB files are supported currently."
        )

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
        upload_tasks[task_id] = {
            "status": TASK_STATUS_PENDING,
            "filename": file.filename,
            "created_at": time.time(),
            "message": "文件已上传，正在排队处理",
            "progress": 0.0,
            "stage": "pending"  # pending, parsing, chunking, embedding, indexing, completed
        }
        
        # 添加到后台任务
        background_tasks.add_task(process_book_background, task_id, file_path, file.filename)

        return {
            "status": "accepted",
            "task_id": task_id,
            "filename": file.filename,
            "message": "文件已上传，正在后台处理中，可通过任务ID查询处理状态",
        }

    except Exception as e:
        # Clean up if failed
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@router.get("/tasks/{task_id}")
async def get_upload_task_status(task_id: str):
    """
    查询上传任务的处理状态
    """
    if task_id not in upload_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = upload_tasks[task_id]
    response = {
        "task_id": task_id,
        "status": task["status"],
        "filename": task["filename"],
        "created_at": task["created_at"],
        "message": task.get("message", ""),
        "progress": task.get("progress", 0.0),
        "stage": task.get("stage", "pending")
    }
    
    if task["status"] == TASK_STATUS_FAILED:
        response["error"] = task.get("error", "未知错误")
        
    return response


@router.get("/status")
async def get_rag_status():
    """
    获取 RAG 服务状态
    """
    from src.service.document_manager import document_manager
    
    # 索引就绪需要同时满足：索引存在且至少有一个已索引文档
    has_documents = len(document_manager.list_documents()) > 0
    index_ready = rag_service.index is not None and has_documents
    
    return {
        "index_ready": index_ready,
        "storage_dir": os.path.abspath("./storage"),
        "document_count": len(document_manager.list_documents())
    }


@router.delete("/documents/{filename}")
async def delete_document(filename: str):
    """
    删除指定文档及其索引
    """
    success = rag_service.delete_document(filename)
    if not success:
        raise HTTPException(
            status_code=404, detail="Document not found or deletion failed."
        )
    return {"status": "success", "message": f"Document {filename} deleted."}


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
        results.append({
            "file_hash": doc.file_hash,
            "file_name": doc.file_name,
            "uploaded_at": doc.upload_date,
            "total_pages": doc.metadata.total_pages if doc.metadata else 0,
        })
        
    return {"documents": results}


@router.get("/search")
async def search_knowledge_content(query: str, limit: int = Query(20, ge=1, le=100)):
    """
    搜索知识库内容，返回匹配的片段和元数据
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="搜索关键词不能为空")

    try:
        results = await rag_service.search_content(query.strip(), limit)
        return {"status": "success", "total": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")
