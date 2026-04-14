# Architecture Update Design Spec
Date: 2026-04-14
Topic: Sync AGENTS.md and CLAUDE.md with Current Codebase

## 1. Overview
The current documentation (`AGENTS.md` and `CLAUDE.md`) does not fully reflect the latest structural changes and new components in the `backend/src` directory. This update will bring the documentation into alignment with the existing codebase.

## 2. Changes to Mermaid Diagrams
- **System Architecture**:
  - Add `SSEPublisher` and `AsyncTaskManager` to the Gateway/Services layer.
  - Add `PrometheusMetrics` and `AlertService` to the Infrastructure layer.
  - Add `DraftDeduplicator` to the RAG Services layer.
- **RAG Pipeline Architecture**:
  - Update `PipelineOrchestrator` to reflect the extracted `pipeline/steps` modules (`age_filter`, `cache_check`, `deduplication`, `hybrid_retrieval`, `pageindex_enhancement`, `query_rewrite`, `query_router`, `reranking`, `result_fusion`, `synonym_expansion`).
- **Evaluation Workflow**:
  - Update Node4 (Scoring) to explicitly reference `qwen_scorer` for Level 2/3 ML Scoring.

## 3. Directory Structure Updates
- Replace the outdated `repository/` file list with the consolidated repositories (`config_repository.py`, `document_repository.py`, `monitor_repository.py`, `prompt_repository.py`, `test_case_repository.py`).
- Add the `core/pipeline/steps/` directory and its contents.
- Add `api/sse.py`, `core/async_task.py`, `core/prometheus_metrics.py`.
- Add `service/alert_service.py` and `service/draft_deduplicator.py`.
- Add `core/ml/qwen_scorer.py`.

## 4. Core Infrastructure Additions (Section 6)
- **6.10 Data Access Layer (Repository Layer)**: Update to list the 5 consolidated repositories instead of the previous 14 separate files.
- **6.13 Async Tasks & SSE (New)**: Describe `AsyncTaskManager` for background task queueing and `SSEPublisher` for streaming progress updates. Mention Starlette's `StreamingResponse` and the `ExceptionGroup` serialization fix.
- **6.14 Metrics & Alerting (New)**: Describe `PrometheusMetrics` for system observability and `AlertService` for anomaly notification.

## 5. Agent Workflow & RAG Updates
- **RAG Evaluation**: Describe the role of `draft_deduplicator` in merging and managing test case drafts to prevent duplicates.
- **Node4 (Scoring Agent)**: Detail the integration of `qwen_scorer` for ML-based evaluation and scoring, expanding beyond the Level 1 AHP baseline.
