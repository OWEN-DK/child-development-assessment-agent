# RAG 文档管理与语义切分实施计划 (修正版)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现基于本地 JSON 的文档管理，并利用 LLM 进行高精度的语义切分和元数据提取，支持物理删除和结构化检索。

**Architecture:**
1.  **Storage Layer**: `document_store.json` 管理文件元数据；`VectorStoreIndex` 存储向量和文本。
2.  **Ingestion Pipeline**: Upload -> MD5 Check -> Parser (PDF/EPUB) -> Semantic Chunking (LLM) -> Metadata Injection -> Indexing.
3.  **Service Layer**: 封装 `DocumentManager` 和增强版 `RagService`。

**Tech Stack:** Python 3.12+, LlamaIndex, PyMuPDF, EbookLib, Pydantic

---

## Chunk 1: 基础架构与文档管理 (Infrastructure & Document Management)

### Task 1.1: 引入依赖与数据模型

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/src/model/document.py` (文档注册表模型)
- Modify: `backend/src/model/schemas.py` (扩展 KnowledgeItem)

- [ ] **Step 1: 添加 PyMuPDF 依赖**
  - Run: `uv add pymupdf`
  - Verify: `import fitz` 成功。

- [ ] **Step 2: 定义 DocumentRegistry Schema**
  - Create `backend/src/model/document.py`:
    ```python
    from typing import Dict, List, Optional
    from pydantic import BaseModel, Field
    from datetime import datetime

    class DocumentMetadata(BaseModel):
        title: str
        category: str = "Uncategorized"
        total_pages: int = 0

    class DocumentRecord(BaseModel):
        file_hash: str
        file_name: str
        upload_date: datetime = Field(default_factory=datetime.now)
        ref_doc_ids: List[str] = Field(default_factory=list) # 对应 LlamaIndex 的 ref_doc_id
        metadata: DocumentMetadata
        status: str = "indexed"

    class DocumentStore(BaseModel):
        docs: Dict[str, DocumentRecord] = Field(default_factory=dict) # Key: file_hash
    ```

- [ ] **Step 3: 扩展 KnowledgeItem**
  - Modify `backend/src/model/schemas.py`:
    - 增加 `target_age_min`, `target_age_max`, `brain_regions`, `topics` 等字段 (已存在则确认类型一致)。

### Task 1.2: 实现 DocumentManager

**Files:**
- Create: `backend/src/service/document_manager.py`
- Test: `backend/tests/test_document_manager.py`

- [ ] **Step 1: 实现 DocumentManager 类**
  - 功能：加载/保存 `storage/document_store.json`，提供 `add_document`, `get_document`, `delete_document`, `exists` 方法。
  - 逻辑：使用文件锁或原子写入保证并发安全（虽低并发，但习惯要好）。

- [ ] **Step 2: 编写测试用例**
  - Test: `test_add_and_get`, `test_persistence`, `test_delete`.
  - Verify: 确保存储文件正确生成和读取。

---

## Chunk 2: 智能解析与语义切分 (Smart Parsing & Chunking)

### Task 2.1: 实现 PDF/EPUB 解析器

**Files:**
- Create: `backend/src/core/parsers.py`
- Test: `backend/tests/test_parsers.py`

- [ ] **Step 1: 实现 PDFParser**
  - 使用 `pymupdf` 提取文本。
  - *高级*: 尝试按页提取，并保留页码信息 `(text, page_num)`。

- [ ] **Step 2: 实现 EPUBParser**
  - 使用 `ebooklib` 和 `html2text` 提取章节文本。
  - **关键**: 确保支持 EPUB 格式解析，提取章节标题作为 metadata。
  - 返回 `List[Document]` (LlamaIndex Document)，包含 `file_name`, `page_label` (或章节名) metadata。

### Task 2.2: 实现 LLM 语义元数据提取

**Files:**
- Create: `backend/src/core/metadata_extractor.py`
- Modify: `backend/src/core/prompts.py` (新增提取 Prompt)

- [ ] **Step 1: 定义提取 Prompt**
  - Prompt: "阅读以下文本片段，提取：摘要、主题列表、适用年龄范围、涉及脑区。返回 JSON。"

- [ ] **Step 2: 实现 MetadataExtractor**
  - 输入: 文本块 (Text Chunk)。
  - 输出: `ExtractedMetadata` (Pydantic Model)。
  - 逻辑: 调用 LLM (使用 `Settings.llm`) 进行提取。

---

## Chunk 3: 摄入流程重构 (Ingestion Pipeline Refactoring)

### Task 3.1: 重构 RagService.ingest_book

**Files:**
- Modify: `backend/src/service/rag_service.py`

- [ ] **Step 1: 集成 DocumentManager**
  - 在 `ingest_book` 开头计算 hash，调用 `doc_manager.exists(hash)` 查重。

- [ ] **Step 2: 实现语义切分与 Metadata 注入**
  - 遍历 Parser 解析出的文档。
  - 对每个文档/章节进行切分 (SentenceSplitter)。
  - **关键**: 对每个 Node 调用 `MetadataExtractor`。
  - 将提取的 Metadata + 原始 Text + `file_name` 写入 `node.metadata`。
  - 确保 `node.text` 是完整原文。

- [ ] **Step 3: 索引与注册**
  - `index.insert_nodes(nodes)`.
  - `doc_manager.add_document(...)`.
  - 持久化索引。

---

## Chunk 4: 高级检索与删除 (Advanced Retrieval & Deletion)

### Task 4.1: 实现混合检索

**Files:**
- Modify: `backend/src/service/rag_service.py`

- [ ] **Step 1: 实现 Query Rewriter (可选/简单版)**
  - 简单版：直接使用 Query，但在 `retrieve_knowledge` 参数中接收 `age` 等过滤条件。
  - 构造 `MetadataFilters`:
    ```python
    filters = MetadataFilters(
        filters=[
            MetadataFilter(key="target_age_min", operator="<=", value=age),
            MetadataFilter(key="target_age_max", operator=">=", value=age),
        ]
    )
    ```

- [ ] **Step 2: 升级 retrieve_knowledge**
  - 使用 `index.as_retriever(filters=filters)`.
  - 将返回的 Node 映射回 `KnowledgeItem`，确保包含 `content` (原文) 和所有 Metadata。

### Task 4.2: 实现文档删除接口

**Files:**
- Modify: `backend/src/service/rag_service.py`
- Modify: `backend/src/controller/rag_controller.py`

- [ ] **Step 1: 实现 delete_document 服务方法**
  - `doc = doc_manager.get_document_by_name(filename)`
  - `for ref_id in doc.ref_doc_ids: index.delete_ref_doc(ref_id, delete_from_docstore=True)`
  - `doc_manager.delete_document(hash)`
  - `index.storage_context.persist()`

- [ ] **Step 2: 暴露 API**
  - `DELETE /rag/documents/{filename}`
  - `GET /rag/documents`

---

## Chunk 5: 验证与测试 (Verification)

### Task 5.1: 集成测试

**Files:**
- Create: `backend/tests/test_rag_flow.py`

- [ ] **Step 1: 测试完整流程**
  - Upload PDF & EPUB -> Verify indexed & registered.
  - Retrieve (check metadata filtering) -> Verify correct results.
  - Delete -> Verify removed from index & doc_store.
