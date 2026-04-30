# 草稿生成质量全面翻新 — 总览

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 移除 age/domain 组合机制，简化草稿生成为"每 chunk 直接生成 N 个忠实于原文的 QA 对"，同时接入 PromptManager、修复忠实度评分逻辑，使草稿生成真正服务于 RAG 能力测试。

**Architecture:** 将当前的"age×domain 笛卡尔积 + 硬编码 prompt + embedding(query vs source)"管道替换为"每 chunk 独立生成 + PromptManager 动态模板 + embedding(answer_points vs source)"。BookMetadataAnalyzer 简化为仅提取 topic_summary，生成逻辑从 `_generate_for_chunk_all_combos` 简化为 `_generate_for_chunk`。

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy 2.0 / Pydantic / React 19 / TypeScript 5.3 / Ant Design 6

**Contradiction Analysis:** [draft_generation_contradiction_analysis.md](../../draft_generation_contradiction_analysis.md)

**数据库重建策略:** 项目未上线，直接 DROP + CREATE，无需数据迁移（零迁移原则）。

---

## 文件索引

| 文件 | 内容 | 任务数 |
|------|------|--------|
| [01-phase1-schema.md](01-phase1-schema.md) | 阶段 1：DDL + Pydantic Schema + ORM 改造 | 3 |
| [02-phase2-backend-logic.md](02-phase2-backend-logic.md) | 阶段 2：后端核心逻辑重构（含 PromptManager 接入） | 5 |
| [03-phase3-di-and-cleanup.md](03-phase3-di-and-cleanup.md) | 阶段 3：旧模板清理 + 单例验证 | 1 |
| [04-phase4-frontend.md](04-phase4-frontend.md) | 阶段 4：前端适配 | 3 |
| [05-phase5-e2e-verification.md](05-phase5-e2e-verification.md) | 阶段 5：TDD 验证 + 端到端集成 | 3 |
| [06-downstream-fixes.md](06-downstream-fixes.md) | 下游模块连锁修复（测试用例/报告/前端展示） | 4 |

## 阶段依赖

```
阶段 1 (Schema)
    ↓
阶段 2 (后端逻辑 + PromptManager 接入) ← PromptManager 与 generator 重写合并，一步到位
    ↓
阶段 3 (旧模板清理 + 单例验证)
    ↓
阶段 4 (前端)
    ↓
阶段 5 (TDD 验证 + 端到端)
    ↓
06-downstream-fixes (下游修复)
```

## 矛盾解决映射

| 矛盾 | 方案如何解决 | 文件 |
|------|-------------|------|
| 矛盾 5 — 目标错位 | 移除 age×domain 组合机制 | phase 1-4 |
| 矛盾 1 — 调用模式 | 每 chunk 直接生成 N 个 QA | 02-phase2 Task 4 |
| 矛盾 4 — 元数据推断 | BookMetadataAnalyzer 简化 | 02-phase2 Task 5 |
| 矛盾 3 — 忠实度评分 | embedding 对比改 answer_points vs source | 02-phase2 Task 6 |
| 矛盾 2 — 架构合规 | PromptManager 动态加载（与 generator 重写合并） | 02-phase2 Task 4 |
| 下游连锁问题 | test_case/report 适配 Optional age/domain | 06-downstream-fixes |

## 已修改文件清单

| 文件 | 变更类型 | 任务 |
|------|----------|------|
| `.ai/full_init_script_mysql57.sql` | Modify | Phase 1 Task 1 |
| `backend/src/schemas/rag_eval/draft.py` | Modify | Phase 1 Task 2 |
| `backend/src/schemas/rag_eval/test_case.py` | Modify | Phase 1 Task 3 |
| `backend/src/models/rag_eval/draft.py` | Modify | Phase 1 Task 3 |
| `backend/src/models/rag_eval/test_case.py` | Modify | Phase 1 Task 3 |
| `backend/src/service/rag_eval/draft/generator.py` | Rewrite | Phase 2 Task 4 |
| `backend/src/service/rag_eval/draft/book_analyzer.py` | Rewrite | Phase 2 Task 5 |
| `backend/src/service/rag_eval/draft/faithfulness_checker.py` | Modify | Phase 2 Task 6 |
| `backend/src/service/rag_eval/draft/facade.py` | Modify | Phase 2 Task 7 |
| `backend/src/controller/rag_eval/draft_controller.py` | Modify | Phase 2 Task 8 |
| `backend/src/core/prompts_fallback.py` | Modify | Phase 2 Task 4 |
| `backend/src/core/prompt_impl/initializer.py` | Modify | Phase 2 Task 4 |
| `frontend/src/entities/rag-eval/types.ts` | Modify | Phase 4 Task 11 |
| `frontend/src/api/rag-eval/drafts.ts` | Modify | Phase 4 Task 12 |
| `frontend/src/features/rag-eval/hooks/useDrafts.ts` | Modify | Phase 4 Task 12 |
| `frontend/src/features/rag-eval/hooks/useDraftGenerationProgress.ts` | Verify | Phase 4 Task 12 |
| `frontend/src/features/rag-eval/components/draft/DraftGenerationForm.tsx` | Modify | Phase 4 Task 12 |
| `frontend/src/features/rag-eval/components/draft/DraftTable.tsx` | Modify | Phase 4 Task 12 |
| `frontend/src/features/rag-eval/pages/DraftPage.tsx` | Modify | Phase 4 Task 13 |
| `backend/tests/service/rag_eval/draft/test_generator_simplified.py` | Create | Phase 5 Task 14 |
| `backend/tests/service/rag_eval/draft/test_faithfulness_checker.py` | Create | Phase 5 Task 14 |
