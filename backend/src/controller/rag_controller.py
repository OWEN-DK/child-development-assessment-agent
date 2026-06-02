"""RAG 文档上传控制器（已迁移到新任务状态服务）"""

import asyncio
import hashlib
import os
import shutil
import uuid
from typing import Optional

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



async def _update_source_file_path(file_hash: str, new_path: str) -> None:
    """更新 source_documents 表中的 file_path 字段"""
    from src.models.document import SourceDocument
    from src.core.database import async_session_factory
    from sqlalchemy import update as sa_update

    async with async_session_factory() as session:
        stmt = (
            sa_update(SourceDocument)
            .where(SourceDocument.file_hash == file_hash)
            .values(file_path=new_path)
        )
        await session.execute(stmt)
        await session.commit()


async def _delete_source_document_by_title(title: str) -> bool:
    """从 source_documents 表中按标题删除文档（回退方案）"""
    from src.models.document import SourceDocument
    from src.core.database import async_session_factory
    from sqlalchemy import select, delete as sa_delete

    async with async_session_factory() as session:
        # 先查找匹配的记录
        result = await session.execute(
            select(SourceDocument).where(SourceDocument.title == title)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return False

        # 删除记录
        await session.execute(
            sa_delete(SourceDocument).where(SourceDocument.id == doc.id)
        )
        await session.commit()
        return True

TASK_TYPE = "upload"
UPLOAD_DIR = settings.rag_temp_upload_dir
BOOKS_DIR = settings.rag_books_dir
MAX_CONCURRENT_TASKS = settings.rag_upload_max_concurrent_tasks

# 确保上传目录和永久存储目录存在
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)
if not os.path.exists(BOOKS_DIR):
    os.makedirs(BOOKS_DIR)

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
            # 等待 SSE 订阅者就绪，避免竞态条件导致早期进度事件丢失
            # 前端上传完成后需要时间建立 EventSource 连接
            await TaskSsePublisher.wait_for_subscriber(TASK_TYPE, task_id)

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

            # 移动文件到永久存储（而非删除），供后续 D2G 等流程使用
            if os.path.exists(file_path):
                file_ext = os.path.splitext(original_filename)[1]
                permanent_name = f"{uuid.uuid4()}{file_ext}"
                permanent_path = os.path.join(BOOKS_DIR, permanent_name)
                shutil.move(file_path, permanent_path)
                # 更新 source_documents 的 file_path 为永久路径
                try:
                    file_hash = hashlib.md5(open(permanent_path, 'rb').read()).hexdigest()
                    await _update_source_file_path(file_hash, permanent_path)
                except Exception as e:
                    logger.warning("更新 source_documents.file_path 失败: %s", e)
                logger.info("文件已移至永久存储: %s", permanent_path)

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
    from src.repository.document_repository import SourceDocumentRepository
    from src.core.database import async_session_factory

    repo = SourceDocumentRepository(async_session_factory)
    all_docs = await repo.get_all(limit=1000)
    document_count = len(all_docs)
    has_documents = document_count > 0
    index_ready = rag_service.index_manager.is_index_available() and has_documents

    return APIResponse.success(data={
        "index_ready": index_ready,
        "storage_dir": os.path.abspath(settings.rag_storage_dir),
        "document_count": document_count,
    })


@router.get("/documents/{filename}/bindings")
async def get_document_bindings(filename: str):
    """查询文档的知识图谱绑定信息"""
    from src.repository.document_repository import DocumentRecordRepository
    from src.repository.graph_repository import (
        GraphEntityRepository, GraphRelationRepository, GraphCommunityRepository,
    )
    from src.core.database import async_session_factory

    doc_repo = DocumentRecordRepository(async_session_factory)
    doc = await doc_repo.get_by_file_name(filename)
    if not doc:
        raise ResourceNotFoundException(message=f"文档 {filename} 未找到")

    book_id = doc.id
    entity_repo = GraphEntityRepository(async_session_factory)
    relation_repo = GraphRelationRepository(async_session_factory)
    community_repo = GraphCommunityRepository(async_session_factory)

    entity_count = await entity_repo.count_by_book(book_id)
    relation_count = await relation_repo.count_by_book(book_id)
    community_count = await community_repo.count_by_book(book_id)
    total = entity_count + relation_count + community_count

    return APIResponse.success(data={
        "book_id": book_id,
        "graph_ready": bool(doc.graph_ready),
        "bindings": {
            "entities": entity_count,
            "relations": relation_count,
            "communities": community_count,
            "total": total,
        },
        "has_bindings": total > 0,
    })


@router.delete("/documents/{filename}")
async def delete_document(filename: str, cascade: bool = Query(False, description="是否同时删除知识图谱绑定")):
    """删除指定文档及其索引。

    如果文档存在知识图谱绑定（实体/关系/社区节点），默认拒绝删除。
    传入 cascade=true 可同时删除文档和所有绑定数据。
    """
    from src.repository.document_repository import DocumentRecordRepository
    from src.repository.graph_repository import (
        GraphEntityRepository, GraphRelationRepository, GraphCommunityRepository,
    )
    from src.core.database import async_session_factory

    # 检查绑定
    doc_repo = DocumentRecordRepository(async_session_factory)
    doc = await doc_repo.get_by_file_name(filename)
    if doc:
        book_id = doc.id
        entity_repo = GraphEntityRepository(async_session_factory)
        relation_repo = GraphRelationRepository(async_session_factory)
        community_repo = GraphCommunityRepository(async_session_factory)

        entity_count = await entity_repo.count_by_book(book_id)
        relation_count = await relation_repo.count_by_book(book_id)
        community_count = await community_repo.count_by_book(book_id)
        total_bindings = entity_count + relation_count + community_count

        if total_bindings > 0 and not cascade:
            raise InvalidParamsException(
                message=f'文档 "{filename}" 已绑定知识图谱（{entity_count} 个实体、{relation_count} 条关系、{community_count} 个社区节点），无法直接删除。请先在知识管理中解除绑定，或使用 cascade=true 同时删除。',
                code=409,
            )

    # 执行删除（index_operations.delete_document 已包含图谱级联删除）
    success = await rag_service.delete_document(filename)
    if not success:
        fallback_success = await _delete_source_document_by_title(filename)
        if not fallback_success:
            raise ResourceNotFoundException(message=f"文档 {filename} 未找到或删除失败")

    msg = f"Document {filename} deleted."
    if cascade:
        msg = f"Document {filename} and all graph bindings deleted."
    return APIResponse.success(message=msg)


@router.get("/documents")
async def list_documents():
    """列出所有已索引文档"""
    from src.repository.document_repository import SourceDocumentRepository
    from src.core.database import async_session_factory

    repo = SourceDocumentRepository(async_session_factory)
    orms = await repo.get_all(limit=1000)
    results = []
    for o in orms:
        results.append({
            "file_hash": o.file_hash,
            "file_name": o.title,
            "uploaded_at": o.created_at,
            "total_pages": o.page_count or 0,
        })
    return APIResponse.success(data={"documents": results})


# ===== 书籍批量解析端点（供 knowledge-qa 通过 HTTP 调用，避免直接 DB 访问） =====


# ===== 知识图谱社区树端点（供 knowledge-qa 通过 HTTP 调用，避免直接 DB 访问） =====



@router.get("/graph/nodes/{node_id}")
async def get_graph_node(node_id: str):
    """获取单个社区节点的详细信息。

    供 knowledge-qa 的社区树遍历通过 HTTP 调用。
    """
    from src.repository.graph_repository import GraphCommunityRepository
    from src.core.database import async_session_factory

    repo = GraphCommunityRepository(async_session_factory)
    node = await repo.get_node(node_id)
    if not node:
        from src.utils.exceptions import ResourceNotFoundException
        raise ResourceNotFoundException(message=f"社区节点 {node_id} 不存在")

    return APIResponse.success(data={
        "node": {
            "node_id": node.node_id,
            "parent_id": node.parent_id,
            "label": node.label,
            "entity_names": node.entity_names or [],
            "chunk_ids": node.chunk_ids or [],
            "is_leaf": node.is_leaf,
            "scope": node.scope,
            "book_id": node.book_id,
        }
    })


@router.get("/graph/children-batch")
async def get_graph_children_batch(
    parent_ids: str = Query(..., description="逗号分隔的父节点 ID 列表"),
):
    """批量查询多个父节点的直接子节点（单次 HTTP 请求）。

    供 knowledge-qa 的社区树遍历通过 HTTP 调用。
    """
    from src.repository.graph_repository import GraphCommunityRepository
    from src.core.database import async_session_factory

    id_list = [pid.strip() for pid in parent_ids.split(",") if pid.strip()]
    if not id_list:
        return APIResponse.success(data={"children_map": {}})

    repo = GraphCommunityRepository(async_session_factory)
    children_map = await repo.get_children_batch(id_list)

    result: dict[str, list[dict]] = {}
    for pid, children in children_map.items():
        result[pid] = [
            {
                "node_id": c.node_id,
                "parent_id": c.parent_id,
                "label": c.label,
                "entity_names": c.entity_names or [],
                "chunk_ids": c.chunk_ids or [],
                "is_leaf": c.is_leaf,
                "scope": c.scope,
                "book_id": c.book_id,
            }
            for c in children
        ]

    return APIResponse.success(data={"children_map": result})



@router.post("/graph/global-rebuild")
async def trigger_global_graph_rebuild():
    """触发全局知识图谱重建（跨书实体去重 + 全局社区检测 + 层级树存储）。

    供 knowledge-qa 和调度器通过 HTTP 调用，
    避免直接传递 async_session_factory 访问数据库。
    """
    from src.core.database import async_session_factory
    from src.core.knowledge_qa.graph.global_rebuild import rebuild_global_graph

    result = await rebuild_global_graph(async_session_factory)
    if result.get("error"):
        return APIResponse.error(
            code=500,
            error_code="global_rebuild_failed",
            message=f"全局图谱重建失败: {result['error']}",
        )
    return APIResponse.success(result)


@router.get("/graph/roots")
async def get_graph_roots(
    scope: str = Query("book", description="社区作用域: book 或 global"),
    book_id: str | None = Query(None, description="书籍 ID（scope=book 时必填）"),
):
    """获取社区树的根节点列表。

    供 knowledge-qa 的 prefetch_context 通过 HTTP 调用。
    """
    from src.repository.graph_repository import GraphCommunityRepository
    from src.core.database import async_session_factory

    if scope not in ("book", "global"):
        from src.utils.exceptions import InvalidParamsException
        raise InvalidParamsException(message="scope 必须是 book 或 global")

    repo = GraphCommunityRepository(async_session_factory)
    roots = await repo.get_roots(scope=scope, book_id=book_id)

    return APIResponse.success(data={
        "roots": [
            {
                "node_id": r.node_id,
                "label": r.label,
                "entity_names": r.entity_names or [],
                "chunk_ids": r.chunk_ids or [],
                "is_leaf": r.is_leaf,
                "scope": r.scope,
                "book_id": r.book_id,
            }
            for r in roots
        ]
    })


@router.get("/graph/children/{node_id}")
async def get_graph_children(node_id: str):
    """获取社区节点的直接子节点列表。

    供 knowledge-qa 的社区树遍历通过 HTTP 调用。
    """
    from src.repository.graph_repository import GraphCommunityRepository
    from src.core.database import async_session_factory

    repo = GraphCommunityRepository(async_session_factory)
    children = await repo.get_children(node_id)

    return APIResponse.success(data={
        "children": [
            {
                "node_id": c.node_id,
                "label": c.label,
                "entity_names": c.entity_names or [],
                "chunk_ids": c.chunk_ids or [],
                "is_leaf": c.is_leaf,
                "scope": c.scope,
                "book_id": c.book_id,
            }
            for c in children
        ]
    })



# ===== 知识图谱写入端点（供 knowledge-qa 通过 HTTP 调用图谱构建操作） =====

@router.post("/graph/entities/upsert")
async def upsert_graph_entities(
    entities: list[dict],
    book_id: str = Query(...),
):
    """批量 upsert 图谱实体。

    供 knowledge-qa 的图谱构建流水线通过 HTTP 调用。
    接收实体 JSON 列表，服务端处理 ORM 创建和持久化。
    """
    from src.models.graph import EntityType, GraphEntity
    from src.repository.graph_repository import GraphEntityRepository
    from src.core.database import async_session_factory

    repo = GraphEntityRepository(async_session_factory)
    entity_orms = []
    for e in entities:
        try:
            etype = EntityType(e.get("entity_type", "development_concept"))
        except ValueError:
            etype = EntityType.DEVELOPMENT_CONCEPT
        entity_orms.append(GraphEntity(
            name=e["name"],
            entity_type=etype,
            description=e.get("description") or "",
            aliases=e.get("aliases") or None,
            book_id=book_id,
            chunk_ids=e.get("chunk_ids") or None,
        ))

    count = await repo.batch_upsert(entity_orms)
    return APIResponse.success(data={"count": count})


@router.post("/graph/relations/insert")
async def insert_graph_relations(
    relations: list[dict],
    book_id: str = Query(...),
):
    """批量插入图谱关系（通过实体名称关联，服务端解析 source/target 实体 ID）。

    供 knowledge-qa 的图谱构建流水线通过 HTTP 调用。
    """
    from src.models.graph import GraphRelation, RelationType
    from src.repository.graph_repository import GraphEntityRepository, GraphRelationRepository
    from src.core.database import async_session_factory

    entity_repo = GraphEntityRepository(async_session_factory)
    relation_repo = GraphRelationRepository(async_session_factory)

    # 查询所有实体，构建 name → id 映射
    all_entities = await entity_repo.find_by_book(book_id)
    name_to_ids: dict[str, list[int]] = {}
    for ent in all_entities:
        name_to_ids.setdefault(ent.name, []).append(ent.id)

    rel_orms = []
    for r in relations:
        source_ids = name_to_ids.get(r["source_entity_name"], [])
        target_ids = name_to_ids.get(r["target_entity_name"], [])
        if not source_ids or not target_ids:
            continue
        try:
            rtype = RelationType(r.get("relation_type", "related_to"))
        except ValueError:
            rtype = RelationType.RELATED_TO
        rel_orms.append(GraphRelation(
            source_entity_id=source_ids[0],
            target_entity_id=target_ids[0],
            relation_type=rtype,
            description=r.get("description") or "",
            confidence=r.get("confidence", 0.5),
            book_id=book_id,
        ))

    count = 0
    if rel_orms:
        count = await relation_repo.batch_insert(rel_orms)
    return APIResponse.success(data={"count": count})


@router.post("/graph/communities/store")
async def store_community_tree_endpoint(
    tree_nodes: list[dict],
    tree_edges: list[dict] | None = None,
    book_id: str | None = Query(None),
    scope: str = Query("book"),
):
    """存储层级社区树。

    供 knowledge-qa 的图谱构建流水线通过 HTTP 调用。
    服务端处理 ORM 创建、旧数据清理和批量写入。
    """
    from src.models.graph import CommunityScope, GraphCommunityNode
    from src.repository.graph_repository import GraphCommunityRepository
    from src.core.database import async_session_factory

    repo = GraphCommunityRepository(async_session_factory)

    if scope == "global":
        await repo.delete_by_scope("global")
    elif book_id:
        await repo.delete_by_book(book_id)

    # 建立 parent_id 映射
    node_parents: dict[str, str | None] = {}
    for n in tree_nodes:
        node_parents[n["node_id"]] = n.get("parent_id")
    if tree_edges:
        for edge in tree_edges:
            node_parents[edge["child"]] = edge["parent"]

    orm_nodes = []
    for n in tree_nodes:
        pid = n.get("parent_id") or node_parents.get(n["node_id"])
        try:
            cs = CommunityScope(scope)
        except ValueError:
            cs = CommunityScope.BOOK
        orm_nodes.append(GraphCommunityNode(
            node_id=n["node_id"],
            parent_id=pid,
            label=n.get("label", ""),
            entity_names=n.get("entity_names") or [],
            chunk_ids=n.get("chunk_ids") or [],
            is_leaf=n.get("is_leaf", False),
            scope=cs,
            book_id=book_id or "",
        ))

    count = await repo.batch_insert(orm_nodes)
    return APIResponse.success(data={"count": count})


@router.delete("/graph/entities/book/{book_id}")
async def delete_graph_entities_by_book(book_id: str):
    """删除指定书籍的所有图谱实体。"""
    from src.repository.graph_repository import GraphEntityRepository
    from src.core.database import async_session_factory

    repo = GraphEntityRepository(async_session_factory)
    count = await repo.delete_by_book(book_id)
    return APIResponse.success(data={"count": count})


@router.delete("/graph/relations/book/{book_id}")
async def delete_graph_relations_by_book(book_id: str):
    """删除指定书籍的所有图谱关系。"""
    from src.repository.graph_repository import GraphRelationRepository
    from src.core.database import async_session_factory

    repo = GraphRelationRepository(async_session_factory)
    count = await repo.delete_by_book(book_id)
    return APIResponse.success(data={"count": count})


@router.delete("/graph/communities/book/{book_id}")
async def delete_graph_communities_by_book(book_id: str):
    """删除指定书籍的所有社区节点。"""
    from src.repository.graph_repository import GraphCommunityRepository
    from src.core.database import async_session_factory

    repo = GraphCommunityRepository(async_session_factory)
    count = await repo.delete_by_book(book_id)
    return APIResponse.success(data={"count": count})


@router.delete("/graph/communities/scope/{scope}")
async def delete_graph_communities_by_scope(scope: str):
    """删除指定作用域的所有社区节点（全局图重建前清理）。"""
    from src.repository.graph_repository import GraphCommunityRepository
    from src.core.database import async_session_factory

    repo = GraphCommunityRepository(async_session_factory)
    count = await repo.delete_by_scope(scope)
    return APIResponse.success(data={"count": count})


@router.get("/books/batch-resolve")
async def batch_resolve_books(
    ids: str = Query(..., description="逗号分隔的书籍标识符列表（ID、文件名或文件哈希）"),
):
    """批量解析书籍标识符为 {id, file_name, file_hash} 映射。

    供 knowledge-qa 模块通过 HTTP 调用，避免直接访问知识库数据库。
    后续知识库独立部署时只需迁移此端点。
    """
    from src.models.document import DocumentRecord
    from src.repository.document_repository import DocumentRecordRepository
    from src.core.database import async_session_factory
    from sqlalchemy import select, or_

    id_list = [rid.strip() for rid in ids.split(",") if rid.strip()]
    if not id_list:
        from src.utils.exceptions import InvalidParamsException
        raise InvalidParamsException(message="ids 参数不能为空")

    repo = DocumentRecordRepository(async_session_factory)
    async with async_session_factory() as session:
        result = await session.execute(
            select(DocumentRecord.id, DocumentRecord.file_name, DocumentRecord.file_hash)
            .where(
                or_(
                    DocumentRecord.id.in_(id_list),
                    DocumentRecord.file_name.in_(id_list),
                    DocumentRecord.file_hash.in_(id_list),
                )
            )
        )
        rows = result.all()

    books = []
    for row in rows:
        books.append({
            "id": str(row.id),
            "file_name": row.file_name,
            "file_hash": row.file_hash,
        })
    return APIResponse.success(data={"books": books})


@router.get("/books/graph-ready")
async def filter_graph_ready_books(
    book_ids: str = Query(..., description="逗号分隔的文件哈希列表"),
):
    """过滤出 graph_ready=True 的书籍 UUID 列表。

    供 knowledge-qa 的 prefetch_context 通过 HTTP 调用。
    """
    from src.models.document import DocumentRecord
    from src.core.database import async_session_factory
    from sqlalchemy import select

    id_list = [bid.strip() for bid in book_ids.split(",") if bid.strip()]
    if not id_list:
        return APIResponse.success(data={"ready_ids": []})

    async with async_session_factory() as session:
        result = await session.execute(
            select(DocumentRecord.id)
            .where(
                DocumentRecord.file_hash.in_(id_list),
                DocumentRecord.graph_ready == True,  # noqa: E712
            )
        )
        ready_ids = [str(row.id) for row in result.all()]

    return APIResponse.success(data={"ready_ids": ready_ids})



@router.get("/search")
async def search_knowledge_content(
    query: str,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    book_ids: Optional[str] = Query(
        None,
        description="按书籍 ID 过滤，逗号分隔。不传则检索全部书籍",
    ),
):
    """搜索知识库内容，返回匹配的片段和元数据（支持分页）"""
    if not query.strip():
        raise InvalidParamsException(message="搜索关键词不能为空")

    book_id_list = None
    if book_ids:
        book_id_list = [bid.strip() for bid in book_ids.split(",") if bid.strip()]

    try:
        result = await rag_service.search_content(query.strip(), limit, offset, book_ids=book_id_list)
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
