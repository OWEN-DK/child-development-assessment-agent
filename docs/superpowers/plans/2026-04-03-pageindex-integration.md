# PageIndex Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate PageIndex into the document ingestion and retrieval pipelines to complete the hybrid reasoning architecture.

**Architecture:** 
1. `PageIndexWrapper` is extended to support document ingestion via `index_document` method using `aiohttp`.
2. `DocumentIngestionService` triggers `index_document` after a document is fully indexed in LlamaIndex.
3. `RagService` serves as the orchestrator for hybrid queries: it uses `QueryRouter` to classify queries; simple queries go to `RetrievalService`, complex queries go to both `RetrievalService` and `PageIndexWrapper`, and the results are combined via `ResultFusion`.

**Tech Stack:** Python, FastAPI, LlamaIndex, PageIndex API

---

## Chunk 1: Extend PageIndexWrapper

### Task 1: Add Ingestion API to PageIndexWrapper

**Files:**
- Modify: `backend/src/core/pageindex_wrapper.py`

- [ ] **Step 1: Write a mock test for `index_document`**
Write a failing test in a new file `backend/tests/test_pageindex_wrapper.py` that mocks `aiohttp.ClientSession.post` and asserts `index_document(file_path, file_hash)` makes the correct API call.

- [ ] **Step 2: Run the test to verify it fails**
Run: `pytest backend/tests/test_pageindex_wrapper.py -v`
Expected: FAIL (method not found or NotImplemented)

- [ ] **Step 3: Implement `index_document` in `pageindex_wrapper.py`**
Add an async `index_document(self, file_path: str, document_id: str) -> bool` method. It should check `settings.pageindex_enabled`. If enabled, use `aiohttp` and `FormData` to POST the file to `{self.base_url}/api/v1/documents`. Catch exceptions and return `True` on success, `False` on failure. Add a mock fallback if the API key is not configured or in testing mode.

- [ ] **Step 4: Run the test to verify it passes**
Run: `pytest backend/tests/test_pageindex_wrapper.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/src/core/pageindex_wrapper.py backend/tests/test_pageindex_wrapper.py
git commit -m "feat: add index_document to PageIndexWrapper for document ingestion"
```

## Chunk 2: Integrate Ingestion Pipeline

### Task 2: Modify DocumentIngestionService

**Files:**
- Modify: `backend/src/service/document_ingestion_service.py`

- [ ] **Step 1: Write a mock test for ingestion integration**
Write a test in `backend/tests/test_rag_ingest.py` (or a new file) that mocks `PageIndexWrapper.index_document` and verifies it gets called at the end of `_ingest_book_with_state` with the correct file path and file hash.

- [ ] **Step 2: Run the test to verify it fails**
Run: `pytest backend/tests/test_rag_ingest.py -v`
Expected: FAIL (mock not called)

- [ ] **Step 3: Implement the integration in `document_ingestion_service.py`**
Import `PageIndexWrapper`. Initialize it in `DocumentIngestionService.__init__` (e.g., `self.pageindex_wrapper = PageIndexWrapper()`).
At the end of `_ingest_book_with_state` (around the "7. 标记为已完成" step), add a call:
```python
if settings.pageindex_enabled:
    asyncio.create_task(self.pageindex_wrapper.index_document(file_path, file_hash))
```

- [ ] **Step 4: Run the test to verify it passes**
Run: `pytest backend/tests/test_rag_ingest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/src/service/document_ingestion_service.py
git commit -m "feat: integrate PageIndex document ingestion in DocumentIngestionService"
```

## Chunk 3: Integrate Retrieval Pipeline

### Task 3: Refactor RagService

**Files:**
- Modify: `backend/src/service/rag_service.py`

- [ ] **Step 1: Write a mock test for RagService hybrid retrieval**
Write a test in `backend/tests/test_rag_service.py` (or `test_rag_hybrid.py`) that mocks `QueryRouter.classify`, `RetrievalService.retrieve_knowledge`, and `PageIndexWrapper.query`. Verify that for a complex query, both services are called and `ResultFusion.fuse` is used.

- [ ] **Step 2: Run the test to verify it fails**
Run: `pytest backend/tests/test_rag_hybrid.py -v`
Expected: FAIL (RagService does not use PageIndexWrapper)

- [ ] **Step 3: Implement the integration in `rag_service.py`**
In `RagService.__init__`, initialize:
```python
from src.core.query_router import QueryRouter
from src.core.pageindex_wrapper import PageIndexWrapper
from src.core.result_fusion import ResultFusion

self.query_router = QueryRouter()
self.pageindex_wrapper = PageIndexWrapper()
self.result_fusion = ResultFusion()
```
Modify `retrieve_knowledge(self, query: str, age: int, limit: int = 3, user_id: str = None)` to:
1. Classify query using `self.query_router.classify(query)`.
2. Retrieve hybrid results via `self.retrieval_service.retrieve_knowledge(...)`.
3. If `classification.query_type == QueryType.COMPLEX` and `settings.pageindex_enabled`:
   - Get pageindex results via `await self.pageindex_wrapper.query(query)`.
   - Fuse results: `fused_results = self.result_fusion.fuse(hybrid_results, pageindex_results, query_type="complex", limit=limit)`
   - Return fused results.
4. Else, return hybrid results.

- [ ] **Step 4: Run the test to verify it passes**
Run: `pytest backend/tests/test_rag_hybrid.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/src/service/rag_service.py
git commit -m "feat: integrate PageIndex hybrid architecture into RagService"
```
