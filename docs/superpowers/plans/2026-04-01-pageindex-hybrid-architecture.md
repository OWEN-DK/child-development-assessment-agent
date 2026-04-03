# PageIndex Hybrid Architecture Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate PageIndex to implement a hybrid reasoning architecture, enabling complex multi-step queries while retaining fast hybrid retrieval for simple queries.

**Architecture:** A QueryRouter classifies queries as simple or complex. Simple queries use the existing hybrid retrieval (BM25 + Vector). Complex queries invoke PageIndex for multi-step reasoning, and ResultFusion combines results from both engines. RagService acts as the orchestrator.

**Tech Stack:** Python, FastAPI, LlamaIndex, PageIndex

---

## Chunk 1: Setup and Basic Integration

### Task 1: Configure Settings

**Files:**
- Modify: `backend/src/config/settings.py`

- [ ] **Step 1: Add PageIndex configurations to Settings**
Open `backend/src/config/settings.py` and append:
```python
    # PageIndex 配置
    pageindex_enabled: bool = Field(True, validation_alias="PAGEINDEX_ENABLED")
    pageindex_api_key: str = Field("", validation_alias="PAGEINDEX_API_KEY")
    pageindex_max_concurrency: int = Field(5, validation_alias="PAGEINDEX_MAX_CONCURRENCY")
    pageindex_max_tree_depth: int = Field(3, validation_alias="PAGEINDEX_MAX_TREE_DEPTH")
    pageindex_timeout_seconds: int = Field(10, validation_alias="PAGEINDEX_TIMEOUT_SECONDS")
    
    # 查询分类器配置
    query_router_llm_enabled: bool = Field(True, validation_alias="QUERY_ROUTER_LLM_ENABLED")
    query_router_confidence_threshold: float = Field(0.8, validation_alias="QUERY_ROUTER_CONFIDENCE_THRESHOLD")
    
    # 结果融合配置
    fusion_hybrid_supplement_limit: int = Field(5, validation_alias="FUSION_HYBRID_SUPPLEMENT_LIMIT")
    fusion_score_boost_for_pageindex: float = Field(1.2, validation_alias="FUSION_SCORE_BOOST_FOR_PAGEINDEX")
```

- [ ] **Step 2: Commit changes**
```bash
git add backend/src/config/settings.py
git commit -m "feat: add pageindex configurations"
```

## Chunk 2: Core Components Implementation

### Task 2: Implement QueryRouter

**Files:**
- Create: `backend/src/core/query_router.py`

- [ ] **Step 1: Create QueryRouter module**
Create `backend/src/core/query_router.py` implementing `QueryType`, `QueryClassification` and `QueryRouter` with regex-based and LLM-assisted classification (as described in the spec).

- [ ] **Step 2: Commit changes**
```bash
git add backend/src/core/query_router.py
git commit -m "feat: implement QueryRouter for simple/complex query classification"
```

### Task 3: Implement PageIndexWrapper

**Files:**
- Create: `backend/src/core/pageindex_wrapper.py`

- [ ] **Step 1: Create PageIndexWrapper module**
Create `backend/src/core/pageindex_wrapper.py` implementing the `PageIndexWrapper` class, mocking `PageIndexClient` if the `pageindex` package is not available on pip, and exposing `query` and `index_document` methods (as described in the spec).

- [ ] **Step 2: Commit changes**
```bash
git add backend/src/core/pageindex_wrapper.py
git commit -m "feat: implement PageIndexWrapper for PageIndex engine integration"
```

### Task 4: Implement ResultFusion

**Files:**
- Create: `backend/src/core/result_fusion.py`

- [ ] **Step 1: Create ResultFusion module**
Create `backend/src/core/result_fusion.py` implementing `ResultFusion` class that merges hybrid and PageIndex results based on the query type (simple, complex, default) as specified in the spec.

- [ ] **Step 2: Commit changes**
```bash
git add backend/src/core/result_fusion.py
git commit -m "feat: implement ResultFusion to combine hybrid and PageIndex results"
```

## Chunk 3: Service Integration

### Task 5: Update RagService

**Files:**
- Modify: `backend/src/service/rag_service.py`

- [ ] **Step 1: Integrate QueryRouter, PageIndexWrapper, and ResultFusion into RagService**
Modify `RagService` to initialize these three components. Update `retrieve_knowledge` to:
1. Call `query_router.classify(query)`.
2. If simple: use `retrieval_service`.
3. If complex: use `asyncio.gather` for `retrieval_service` and `pageindex_wrapper.query`.
4. Fuse results using `result_fusion.fuse`.
5. Return truncated results up to `limit`.

- [ ] **Step 2: Commit changes**
```bash
git add backend/src/service/rag_service.py
git commit -m "feat: integrate QueryRouter, PageIndexWrapper, and ResultFusion into RagService"
```
