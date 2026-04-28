# DocumentManager MySQL 迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 DocumentManager 从 JSON 文件存储迁移到 MySQL，document_records 跟踪导入进度，source_documents 存储索引完成的可用文档。

**Architecture:** DocumentManager 改为异步类，通过 DocumentRecordRepository 读写 document_records 表。文档索引成功后同步 upsert 到 source_documents 表。所有消费方（controller、service）适配新的异步接口。废弃 document_store.json 文件。

**数据迁移说明：** 项目未上线，无需迁移历史数据。迁移完成后删除 `storage/rag/document_store.json` 即可（如存在）。

**Tech Stack:** Python 3.13, SQLAlchemy 2.0 (async), Pydantic, MySQL 5.7

---

## 变更文件清单

| 文件 | 动作 | 职责 |
|------|------|------|
| `backend/src/service/document_manager.py` | **重写** | 从 JSON 存储改为 MySQL document_records + source_documents |
| `backend/src/schemas/rag.py` | **修改** | DocumentRecord Pydantic 模型增加 id 字段 |
| `backend/src/models/document.py` | **修改** | DocumentRecord ORM 模型字段对齐 |
| `backend/src/repository/document_repository.py` | **修改** | DocumentRecordRepository 增加必要查询方法 |
| `backend/src/service/document_ingestion/book_ingestor.py` | **修改** | 适配新的 DocumentManager 异步接口 |
| `backend/src/service/document_ingestion/chunking_indexing.py` | **修改** | 适配新的 DocumentManager 异步接口 |
| `backend/src/service/index_manager/index_operations.py` | **修改** | 适配新的 DocumentManager 异步接口 |
| `backend/src/core/interfaces.py` | **修改** | IIndexManager.delete_document 改为 async |
| `backend/src/service/index_manager/facade.py` | **修改** | IndexManagerService.delete_document 改为 async |
| `backend/src/service/rag_service.py` | **修改** | RAGService.delete_document 改为 async |
| `backend/src/controller/rag_controller.py` | **修改** | list_documents / get_rag_status 改用 source_documents |
| `backend/src/controller/rag_eval/draft_controller.py` | **修改** | list_source_docs 改用 source_documents |
| `backend/src/service/retrieval/result_processor.py` | **修改** | 查询源文档名改为异步 |
| `backend/src/service/retrieval/facade.py` | **修改** | 调用点加 await |
| `backend/src/service/rag_eval/run/snapshot_manager.py` | **修改** | 脱离 document_store.json 依赖 |
| `backend/src/service/index_manager/storage_manager.py` | **修改** | 移除 dead import |
| `.ai/full_init_script_mysql57.sql` | **修改** | document_records 表增加 file_name 索引 |
| `frontend/src/entities/rag-eval/types.ts` | **已修改** | SourceDocument 类型（上一步已完成） |

---

## 依赖顺序

```
Task 1 (Schema + ORM + DDL)
  → Task 2 (Repository 方法)
    → Task 3 (DocumentManager 重写)
      → Task 4 (book_ingestor 适配)
      → Task 5 (chunking_indexing 适配)
      → Task 6 (index_operations + 接口链 async 改造)
      → Task 7 (rag_controller 适配)
      → Task 8 (draft_controller 适配)
      → Task 9 (result_processor + retrieval facade async 改造)
      → Task 10 (snapshot_manager 适配)
      → Task 11 (storage_manager 清理)
        → Task 12 (端到端验证)
```

---

### Task 1: Schema / ORM / DDL 对齐

**Files:**
- Modify: `backend/src/schemas/rag.py`
- Modify: `backend/src/models/document.py`
- Modify: `.ai/full_init_script_mysql57.sql`

- [ ] **Step 1: 给 Pydantic DocumentRecord 增加 id 和 file_type 字段**

在 `backend/src/schemas/rag.py` 的 `DocumentRecord` 类中增加 `id` 和 `file_type` 字段，使其与 ORM 模型对齐：

```python
class DocumentRecord(BaseModel):
    """文档记录"""

    id: str = ""
    file_hash: str
    file_name: str
    file_type: str = ""
    upload_date: datetime = Field(default_factory=datetime.now)
    ref_doc_ids: List[str] = Field(default_factory=list)
    metadata: DocumentMetadata
    status: str = "indexed"
    progress: float = 0.0
```

- [ ] **Step 2: 检查 ORM DocumentRecord 模型是否有 file_name 列**

读取 `backend/src/models/document.py` 的 `DocumentRecord(Base)` 类（lines 64-90），确认已有以下列：
- `id` (String 64, PK)
- `file_hash` (String 64)
- `file_name` (String 500)
- `upload_date` (DateTime)
- `total_pages` (Integer, nullable)
- `indexed_chunks` (Integer, default 0)
- `category` (String 100, nullable)
- `metadata` (JSON)
- `ref_doc_ids` (JSON)
- `status` (Enum: pending/processing/indexed/failed)
- `progress` (Integer, default 0)
- `created_at` / `updated_at`

ORM 模型已有这些字段，无需修改。

- [ ] **Step 3: 更新 DDL — 给 document_records 增加 file_name 索引**

在 `.ai/full_init_script_mysql57.sql` 的 `document_records` 建表语句中确认是否已有 `idx_doc_records_file_name` 索引。如果已有则跳过。

- [ ] **Step 4: Commit**

```bash
git add backend/src/schemas/rag.py .ai/full_init_script_mysql57.sql
git commit -m "refactor: DocumentRecord Pydantic 增加 id/file_type 字段，对齐 ORM 模型"
```

---

### Task 2: Repository 增加必要查询方法

**Files:**
- Modify: `backend/src/repository/document_repository.py`

- [ ] **Step 1: 给 DocumentRecordRepository 增加方法**

当前只有 `get_by_file_hash`。需要增加：

```python
class DocumentRecordRepository(BaseRepository[DocumentRecord]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(DocumentRecord, db_session_factory)

    async def get_by_file_hash(self, file_hash: str) -> Optional[DocumentRecord]:
        """根据文件哈希查询文档记录"""
        return await self.get_one_by_filter(file_hash=file_hash)

    async def get_by_file_name(self, file_name: str) -> Optional[DocumentRecord]:
        """根据文件名查询文档记录"""
        return await self.get_one_by_filter(file_name=file_name)

    async def get_indexed(self, skip: int = 0, limit: int = 100) -> List[DocumentRecord]:
        """查询所有已索引的文档记录"""
        from src.models.document import ImportStatus
        return await self.get_by_filter(skip=skip, limit=limit, status=ImportStatus.INDEXED)

    async def count_indexed(self) -> int:
        """统计已索引文档数量"""
        from src.models.document import ImportStatus
        return await self.count_by_filter(status=ImportStatus.INDEXED)

    async def upsert_by_file_hash(self, data: dict) -> DocumentRecord:
        """根据 file_hash 执行 upsert（存在则更新，不存在则创建）"""
        existing = await self.get_by_file_hash(data["file_hash"])
        if existing:
            return await self.update(existing.id, data)
        if "id" not in data:
            from src.utils.id_generator import generate_id
            data["id"] = generate_id()
        return await self.create(data)
```

- [ ] **Step 2: 给 SourceDocumentRepository 增加 upsert 和查询方法**

```python
class SourceDocumentRepository(BaseRepository[SourceDocument]):
    def __init__(self, db_session_factory: async_sessionmaker):
        super().__init__(SourceDocument, db_session_factory)

    async def get_by_file_hash(self, file_hash: str) -> Optional[SourceDocument]:
        """根据文件哈希查询文档"""
        return await self.get_one_by_filter(file_hash=file_hash)

    async def get_by_status(
        self, status: str, skip: int = 0, limit: int = 50
    ) -> List[SourceDocument]:
        """根据状态查询文档"""
        return await self.get_by_filter(skip=skip, limit=limit, status=status)

    async def upsert_by_file_hash(self, data: dict) -> SourceDocument:
        """根据 file_hash 执行 upsert"""
        existing = await self.get_by_file_hash(data["file_hash"])
        if existing:
            return await self.update(existing.id, data)
        if "id" not in data:
            from src.utils.id_generator import generate_id
            data["id"] = generate_id()
        return await self.create(data)

    async def get_indexed(self, skip: int = 0, limit: int = 100) -> List[SourceDocument]:
        """查询所有就绪的源文档"""
        from src.models.document import DocumentStatus
        return await self.get_by_filter(skip=skip, limit=limit, status=DocumentStatus.READY)

    async def count_indexed(self) -> int:
        """统计就绪源文档数量"""
        from src.models.document import DocumentStatus
        return await self.count_by_filter(status=DocumentStatus.READY)
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/repository/document_repository.py
git commit -m "refactor: Repository 增加 upsert 和索引文档查询方法"
```

---

### Task 3: DocumentManager 重写

**Files:**
- Rewrite: `backend/src/service/document_manager.py`

- [ ] **Step 1: 重写 DocumentManager 为异步 MySQL 实现**

将整个文件重写为以下内容：

```python
"""文档管理器（MySQL 存储）

职责：
- 通过 document_records 表跟踪文档导入进度/状态
- 文档索引成功后同步 upsert 到 source_documents 表
- 废弃原 JSON 文件存储方式
"""

from typing import List, Optional

from src.utils.logger import logger


class DocumentManager:
    """文档管理器（MySQL 存储，异步）

    保持单例语义：模块级 document_manager 实例在首次 import 时创建，
    所有消费方通过 from src.service.document_manager import document_manager 使用同一实例。
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._doc_repo = None
            cls._instance._source_repo = None
        return cls._instance

    def _get_doc_repo(self):
        from src.repository.document_repository import DocumentRecordRepository
        from src.core.database import async_session_factory
        if self._doc_repo is None:
            self._doc_repo = DocumentRecordRepository(async_session_factory)
        return self._doc_repo

    def _get_source_repo(self):
        from src.repository.document_repository import SourceDocumentRepository
        from src.core.database import async_session_factory
        if self._source_repo is None:
            self._source_repo = SourceDocumentRepository(async_session_factory)
        return self._source_repo

    async def add_document(self, doc_dict: dict) -> None:
        """新增或更新文档记录（document_records），索引成功时同步 source_documents

        Args:
            doc_dict: 包含 file_hash, file_name, status 等字段的字典
        """
        from src.models.document import ImportStatus

        status_str = doc_dict.get("status", "pending")
        try:
            status_enum = ImportStatus(status_str)
        except ValueError:
            status_enum = ImportStatus.PENDING

        data = {
            "file_hash": doc_dict["file_hash"],
            "file_name": doc_dict["file_name"],
            "upload_date": doc_dict.get("upload_date"),
            "status": status_enum,
            "progress": int(doc_dict.get("progress", 0)),
            "total_pages": doc_dict.get("metadata", {}).get("total_pages") if isinstance(doc_dict.get("metadata"), dict) else None,
            "category": doc_dict.get("metadata", {}).get("category") if isinstance(doc_dict.get("metadata"), dict) else None,
            "ref_doc_ids": doc_dict.get("ref_doc_ids", []),
            "extra_metadata": doc_dict.get("metadata"),
        }
        if data["upload_date"] is None:
            from datetime import datetime
            data["upload_date"] = datetime.now()

        try:
            repo = self._get_doc_repo()
            await repo.upsert_by_file_hash(data)
        except Exception as e:
            logger.error(f"写入 document_records 失败: {e}")
            return

        if status_enum == ImportStatus.INDEXED:
            await self._sync_to_source_documents(doc_dict)

    async def _sync_to_source_documents(self, doc_dict: dict) -> None:
        """将已索引文档同步到 source_documents 表"""
        import os
        from src.models.document import DocumentStatus

        file_name = doc_dict["file_name"]
        file_hash = doc_dict["file_hash"]
        ext = os.path.splitext(file_name)[1].lstrip(".").lower() or "txt"
        metadata = doc_dict.get("metadata", {}) or {}
        if not isinstance(metadata, dict):
            metadata = {}

        source_data = {
            "file_hash": file_hash,
            "title": metadata.get("title", file_name),
            "file_type": ext,
            "file_path": file_name,
            "page_count": metadata.get("total_pages"),
            "chapter_count": metadata.get("chapter_count"),
            "status": DocumentStatus.READY,
        }
        try:
            source_repo = self._get_source_repo()
            await source_repo.upsert_by_file_hash(source_data)
            logger.info(f"已同步文档到 source_documents: {file_name}")
        except Exception as e:
            logger.error(f"同步 source_documents 失败: {e}")

    async def get_document(self, file_hash: str) -> Optional[dict]:
        """根据 file_hash 获取文档记录"""
        repo = self._get_doc_repo()
        orm = await repo.get_by_file_hash(file_hash)
        if not orm:
            return None
        return self._orm_to_dict(orm)

    async def get_document_by_name(self, file_name: str) -> Optional[dict]:
        """根据 file_name 获取文档记录"""
        repo = self._get_doc_repo()
        orm = await repo.get_by_file_name(file_name)
        if not orm:
            return None
        return self._orm_to_dict(orm)

    async def delete_document(self, file_hash: str) -> bool:
        """删除文档记录（同时删除 document_records 和 source_documents）"""
        repo = self._get_doc_repo()
        orm = await repo.get_by_file_hash(file_hash)
        if not orm:
            return False

        deleted = await repo.delete(orm.id)

        source_repo = self._get_source_repo()
        source = await source_repo.get_by_file_hash(file_hash)
        if source:
            await source_repo.delete(source.id)

        return deleted

    async def exists(self, file_hash: str) -> bool:
        """检查文档是否存在"""
        repo = self._get_doc_repo()
        orm = await repo.get_by_file_hash(file_hash)
        return orm is not None

    async def list_documents(self) -> List[dict]:
        """列出所有文档记录"""
        repo = self._get_doc_repo()
        orms = await repo.get_all(limit=10000)
        return [self._orm_to_dict(o) for o in orms]

    @staticmethod
    def _orm_to_dict(orm) -> dict:
        """ORM 对象转字典，保持与原 Pydantic DocumentRecord 兼容的格式"""
        metadata = {}
        if hasattr(orm, "extra_metadata") and orm.extra_metadata:
            if isinstance(orm.extra_metadata, dict):
                metadata = orm.extra_metadata

        return {
            "id": orm.id,
            "file_hash": orm.file_hash,
            "file_name": orm.file_name,
            "upload_date": orm.upload_date,
            "ref_doc_ids": orm.ref_doc_ids or [],
            "metadata": metadata,
            "status": orm.status.value if hasattr(orm.status, "value") else str(orm.status),
            "progress": float(orm.progress or 0),
        }


document_manager = DocumentManager()
```

- [ ] **Step 2: 验证导入无误**

```bash
cd backend && uv run python -c "from src.service.document_manager import document_manager; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/service/document_manager.py
git commit -m "refactor: DocumentManager 重写为异步 MySQL 实现，废弃 JSON 存储"
```

---

### Task 4: book_ingestor 适配

**Files:**
- Modify: `backend/src/service/document_ingestion/book_ingestor.py`

**关键变化：** `document_manager.add_document()` 和 `document_manager.exists()` 等方法现在是异步的。`book_ingestor` 本身在异步上下文中运行，可以直接 `await`。但 `add_document` 的参数从 Pydantic `DocumentRecord` 对象改为 dict。

- [ ] **Step 1: 修改 import 和所有调用点**

将 `DocumentRecord` Pydantic 的构造改为 dict 构造，并 await 所有 document_manager 调用：

1. **Line 36**: `document_manager.exists(file_hash)` → `await document_manager.exists(file_hash)` （已在 async 上下文中）
2. **Lines 168-171**: 构造 `DocumentRecord(...)` 改为 dict，`document_manager.add_document(...)` 改为 `await`
3. **Lines 183-184**: `document_manager.exists()` 和 `delete_document()` 加 `await`
4. **Lines 189-192**: 构造 `DocumentRecord(...)` 改为 dict，`add_document` 加 `await`

Line 168-171 的变更示例：
```python
# 旧：
# doc_record = DocumentRecord(file_hash=file_hash, file_name=file_name, ...)
# await loop.run_in_executor(None, document_manager.add_document, doc_record)

# 新：
doc_record = {
    "file_hash": file_hash,
    "file_name": file_name,
    "ref_doc_ids": [file_hash],
    "metadata": {
        "title": file_name,
        "total_pages": actual_total_pages if actual_total_pages is not None else doc_count,
        "chapter_count": chapter_count,
    },
    "status": "indexed",
    "progress": 100.0,
}
await document_manager.add_document(doc_record)
```

Line 189-192（失败记录）同理改为 dict：
```python
failed_doc = {
    "file_hash": file_hash,
    "file_name": file_name,
    "ref_doc_ids": [file_hash],
    "metadata": {"title": file_name, "total_pages": 0},
    "status": "failed",
    "progress": 0.0,
}
await document_manager.add_document(failed_doc)
```

移除 `from src.schemas import DocumentMetadata, DocumentRecord` 导入（如果不再需要）。

- [ ] **Step 2: Commit**

```bash
git add backend/src/service/document_ingestion/book_ingestor.py
git commit -m "refactor: book_ingestor 适配异步 DocumentManager"
```

---

### Task 5: chunking_indexing 适配

**Files:**
- Modify: `backend/src/service/document_ingestion/chunking_indexing.py`

- [ ] **Step 1: 修改 import 和调用点**

1. **移除** `from src.schemas import DocumentMetadata, DocumentRecord`
2. **Line 39-45**: `DocumentRecord(...)` 构造改为 dict，`document_manager.add_document` 加 `await`
3. **Line 59-60**: 同步回调中的 `document_manager.add_document` → 需要通过 `asyncio.run_coroutine_threadsafe` 调用
4. **Line 88-89**: 同上处理

Line 39-45 变更：
```python
pending_doc = {
    "file_hash": file_hash,
    "file_name": file_name,
    "ref_doc_ids": [file_hash],
    "metadata": {"title": file_name, "total_pages": len(documents)},
    "status": "processing",
    "progress": 30.0,
}
await document_manager.add_document(pending_doc)
```

Line 59-60（同步回调 chunking_progress 中）变更：
```python
def chunking_progress(stage: str, progress: float, message: str):
    nonlocal pending_doc
    if progress_callback:
        overall_progress = 30.0 + (progress / 100.0 * 20.0)
        pending_doc["progress"] = overall_progress
        asyncio.run_coroutine_threadsafe(
            document_manager.add_document(pending_doc), loop
        )
        res = progress_callback(stage, overall_progress, message)
        if asyncio.iscoroutine(res):
            asyncio.run_coroutine_threadsafe(res, loop)
```

Line 84-92（wrapped_progress）同理用 `asyncio.run_coroutine_threadsafe`。

- [ ] **Step 2: Commit**

```bash
git add backend/src/service/document_ingestion/chunking_indexing.py
git commit -m "refactor: chunking_indexing 适配异步 DocumentManager"
```

---

### Task 6: index_operations 适配

**Files:**
- Modify: `backend/src/service/index_manager/index_operations.py`

- [ ] **Step 1: 将 delete_document 改为异步，适配新接口**

`delete_document` 方法需要改为 `async def`：

```python
async def delete_document(self, file_name: str) -> bool:
    doc = await document_manager.get_document_by_name(file_name)
    if not doc:
        logger.warning(f"Document {file_name} not found in registry.")
        return False
    logger.info(f"Deleting document: {file_name} (hash: {doc['file_hash']}, status: {doc['status']})")

    try:
        await document_manager.delete_document(doc["file_hash"])
    except Exception as e:
        logger.error(f"Failed to delete document record: {e}")
        return False

    if not self.storage_manager.index:
        logger.warning("Index not initialized, document record deleted successfully.")
        return True

    try:
        if doc["status"] != "failed":
            for ref_id in doc["ref_doc_ids"]:
                self.storage_manager.index.delete_ref_doc(ref_id, delete_from_docstore=True)
            self.storage_manager._persist_index()
            self.storage_manager._dirty = False

            remaining_docs = await document_manager.list_documents()
            if not remaining_docs:
                self.storage_manager._clear_index()

        logger.info(f"Successfully deleted {file_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete document from index: {e}, but document record was deleted")
        return True
```

- [ ] **Step 2: 修改 IIndexManager 接口签名**（`backend/src/core/interfaces.py:24`）

将 `delete_document` 改为 `async def`：

```python
@abstractmethod
async def delete_document(self, file_name: str) -> bool:
    pass
```

- [ ] **Step 3: 修改 IndexManagerService 门面**（`backend/src/service/index_manager/facade.py:27`）

```python
async def delete_document(self, file_name: str) -> bool:
    return await self.index_operations.delete_document(file_name)
```

- [ ] **Step 4: 修改 RAGService**（`backend/src/service/rag_service.py:117`）

```python
async def delete_document(self, file_name: str) -> bool:
    """删除文档（原有接口）"""
    success = await self.index_manager.delete_document(file_name)
    if success:
        self.retrieval_service.reload_retrievers()
    return success
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/service/index_manager/index_operations.py backend/src/core/interfaces.py backend/src/service/index_manager/facade.py backend/src/service/rag_service.py
git commit -m "refactor: delete_document 全链路改为 async，适配异步 DocumentManager"
```

---

### Task 7: rag_controller 适配

**Files:**
- Modify: `backend/src/controller/rag_controller.py`

- [ ] **Step 1: 修改 list_documents 端点（约 line 372-391）**

改为从 source_documents 表查询（通过 SourceDocumentRepository），而非 document_manager.list_documents()：

```python
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
```

- [ ] **Step 2: 修改 get_rag_status 端点（约 line 347-360）**

同样改为查 source_documents：

```python
@router.get("/status")
async def get_rag_status():
    """获取 RAG 系统状态"""
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
```

- [ ] **Step 3: 修改 delete_document 端点调用**

确保 `rag_service.delete_document(file_name)` 用 `await` 调用（因为 Task 6 已将 RAGService.delete_document 改为 async）：

```python
# 旧：
# rag_service.delete_document(filename)

# 新：
await rag_service.delete_document(filename)
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/controller/rag_controller.py
git commit -m "refactor: rag_controller 改用 source_documents 查询文档列表"
```

---

### Task 8: draft_controller 适配

**Files:**
- Modify: `backend/src/controller/rag_eval/draft_controller.py`

- [ ] **Step 1: 修改 list_source_docs 方法**

上一步已经改为从 document_manager 获取数据，现在改为直接查 source_documents 表（通过已有的 self._doc_repo）：

```python
async def list_source_docs(
    self,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出源文档（从 source_documents 表查询就绪文档）"""
    skip = (page - 1) * page_size
    orms = await self._doc_repo.get_indexed(skip=skip, limit=page_size)
    total = await self._doc_repo.count_indexed()
    items = []
    for o in orms:
        items.append({
            "id": o.id,
            "name": o.title,
            "file_hash": o.file_hash,
            "status": o.status.value if hasattr(o.status, "value") else str(o.status),
            "page_count": o.page_count,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "updated_at": o.updated_at.isoformat() if o.updated_at else None,
        })
    return APIResponse.success({"items": items, "total": total, "page": page, "page_size": page_size})
```

注意：需要在 Task 2 中给 SourceDocumentRepository 增加 `get_indexed` 和 `count_indexed` 方法，查询 `status=DocumentStatus.READY` 的记录。source_documents 表的 status enum 值为 uploaded/parsing/ready/archived，索引完成的文档会被 DocumentManager._sync_to_source_documents 标记为 `DocumentStatus.READY`。

- [ ] **Step 2: Commit**

```bash
git add backend/src/controller/rag_eval/draft_controller.py
git commit -m "refactor: draft_controller 改用 source_documents 表查询就绪文档"
```

---

### Task 9: result_processor 适配

**Files:**
- Modify: `backend/src/service/retrieval/result_processor.py`
- Modify: `backend/src/service/retrieval/facade.py`

- [ ] **Step 1: 将 `_process_search_results` 改为 `async def`**

> **注意：** `_process_search_results` 当前是**同步方法**（`result_processor.py:60`），不能直接使用 `await`。
> 需要先改为 `async def`，然后追溯所有调用方加 `await`。

在 `result_processor.py` 中：
1. 将 `def _process_search_results(` 改为 `async def _process_search_results(`
2. **Line 228-230**: 将 `document_manager.get_document(file_hash)` 改为 `await`：

```python
# 旧：
# doc = document_manager.get_document(file_hash)
# if doc:
#     source_book = doc.file_name

# 新：
doc = await document_manager.get_document(file_hash)
if doc:
    source_book = doc["file_name"]
```

在 `facade.py` 中：
1. **Line 107**: 将 `def _process_search_results(` 改为 `async def _process_search_results(`
2. **Line 108**: 加 `await`：`return await self.result_processor._process_search_results(...)`
3. **Line 239**: 加 `await`：`processed_results = await self.result_processor._process_search_results(...)`

- [ ] **Step 2: Commit**

```bash
git add backend/src/service/retrieval/result_processor.py backend/src/service/retrieval/facade.py
git commit -m "refactor: result_processor 和 retrieval facade 适配异步 DocumentManager"
```

---

### Task 10: snapshot_manager 适配

**Files:**
- Modify: `backend/src/service/rag_eval/run/snapshot_manager.py`

- [ ] **Step 1: 修改 create_snapshot 方法**

移除对 `document_store.json` 的依赖，改为从数据库查 document_count：

```python
async def create_snapshot(
    self,
    name: str | None = None,
    description: str = "",
) -> SnapshotRead:
    snapshot_id = generate_id()
    snapshot_dir = self._get_snapshot_dir(snapshot_id)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    work_dir = self._get_work_dir()
    index_src = work_dir / "index"

    document_count = 0
    chunk_count = 0

    if index_src.exists():
        shutil.copytree(index_src, snapshot_dir / "index", dirs_exist_ok=True)
        chunk_count = self._count_index_entries(snapshot_dir / "index")

    from src.repository.document_repository import DocumentRecordRepository
    from src.core.database import async_session_factory
    from src.models.document import ImportStatus
    doc_repo = DocumentRecordRepository(async_session_factory)
    document_count = await doc_repo.count_by_filter(status=ImportStatus.INDEXED)

    snapshot_name = name or f"snapshot_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    orm_obj = await self._snapshot_repo.create({
        "id": snapshot_id,
        "name": snapshot_name,
        "description": description,
        "vector_store_path": str(snapshot_dir),
        "document_count": document_count,
        "chunk_count": chunk_count,
    })

    from src.utils.orm_mapper import OrmMapper
    return OrmMapper.to_read(orm_obj, SnapshotRead)
```

- [ ] **Step 2: 修改 restore_snapshot 方法**

移除 `document_store.json` 的备份/恢复逻辑，只保留 index 目录的备份/恢复：

在 restore_snapshot 方法中，删除所有 `docstore_path` / `document_store.json` 相关的行（约 lines 112-118, 123-124, 128-132, 142-143）。只保留 index 目录的备份和恢复逻辑。

- [ ] **Step 3: Commit**

```bash
git add backend/src/service/rag_eval/run/snapshot_manager.py
git commit -m "refactor: snapshot_manager 脱离 document_store.json 依赖"
```

---

### Task 11: storage_manager 清理 dead import

**Files:**
- Modify: `backend/src/service/index_manager/storage_manager.py`

- [ ] **Step 1: 移除未使用的 document_manager import**

```python
# 删除这行：
# from src.service.document_manager import document_manager
```

确认文件中没有其他地方使用 `document_manager`（已确认是 dead import）。

- [ ] **Step 2: Commit**

```bash
git add backend/src/service/index_manager/storage_manager.py
git commit -m "refactor: storage_manager 移除未使用的 document_manager import"
```

---

### Task 12: 端到端验证

- [ ] **Step 0: 清理 document_store.json**

迁移完成后，旧文件不再需要。如文件存在则删除：

```bash
rm -f storage/rag/document_store.json
```

- [ ] **Step 1: 后端导入检查**

```bash
cd backend && uv run python -c "
from src.service.document_manager import document_manager
from src.repository.document_repository import DocumentRecordRepository, SourceDocumentRepository
from src.controller.rag_controller import router
from src.controller.rag_eval.draft_controller import DraftController
from src.service.rag_eval.run.snapshot_manager import SnapshotManager
from src.service.retrieval.result_processor import ResultProcessor
from src.service.retrieval.facade import RetrievalFacade
from src.service.index_manager.index_operations import IndexOperations
from src.service.index_manager.facade import IndexManagerService
from src.service.index_manager.storage_manager import StorageManager
from src.service.rag_service import rag_service
from src.core.interfaces import IIndexManager
from src.service.document_ingestion.book_ingestor import BookIngestor
from src.service.document_ingestion.chunking_indexing import ChunkingAndIndexing
print('所有模块导入成功')
"
```

- [ ] **Step 2: 前端类型检查**

```bash
cd frontend && npm run typecheck
```

确认无新增类型错误（已有的测试文件类型错误可忽略）。

- [ ] **Step 3: 启动后端验证 API**

```bash
cd backend && uv run start
```

验证以下端点：
- `GET /rag/documents` → 返回文档列表（从 source_documents 查询）
- `GET /rag/status` → 返回 RAG 状态
- `GET /api/v1/rag/eval/source-documents` → 返回源文档列表（草稿下拉框数据源）

- [ ] **Step 4: Final Commit**

```bash
git add -A
git commit -m "refactor: DocumentManager MySQL 迁移完成，废弃 JSON 存储"
```
