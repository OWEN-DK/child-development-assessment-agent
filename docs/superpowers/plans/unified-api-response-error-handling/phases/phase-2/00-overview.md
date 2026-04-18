# Phase 2 - 类职责拆分

> **本文档包含**: Phase 2 总览、需求点清单、验收标准、实施顺序

---

## 目标

将 40+ 个超长类（单类 > 200 行）按单一职责原则拆分，使用门面模式（Facade）对外提供统一 API，内部协调子服务。

---

## 需求点清单

| # | 需求点名称 | 实施文件 | 原行数 | 拆分后 | 预估工作量 |
|---|-----------|---------|--------|--------|-----------|
| 1 | RagTestManager 拆分 | `01-rag-test-manager-split.md` | 1799 | 8 个子服务 + 1 门面 | 大 |
| 2 | RetrievalService 拆分 | `02-retrieval-service-split.md` | 1060 | 5 个子服务 + 1 门面 | 大 |
| 3 | MetadataProcessor 拆分 | `03-metadata-processor-split.md` | 925 | 7 个子服务 + 1 门面 | 大 |
| 4 | DocumentIngestionService 拆分 | `04-document-ingestion-split.md` | 637 | 5 个子服务 + 1 门面 | 中 |
| 5 | IndexManagerService 拆分 | `05-index-manager-split.md` | 574 | 4 个子服务 + 1 门面 | 中 |
| 6 | CacheService 拆分 | `06-cache-service-split.md` | 447 | 待拆分 | 中 |
| 7 | PromptManager 拆分 | `07-prompt-manager-split.md` | 428 | 待拆分 | 中 |

---

## 验收标准

- [ ] 所有目标类拆分完成，单类 ≤ 200 行
- [ ] 门面类对外 API 保持兼容
- [ ] 子服务通过依赖注入，不直接实例化
- [ ] 现有测试全部通过

---

## 拆分原则

| 原则 | 说明 |
|------|------|
| **单一职责** | 每个类只负责一个明确的业务职责 |
| **行数限制** | 单类不超过 200 行（含空行和注释） |
| **门面模式** | 对外通过 Facade 提供统一 API，内部协调子服务 |
| **依赖注入** | 子服务通过 DI 注入，而非直接实例化 |
| **接口兼容** | 拆分后保持现有公开 API 不变 |

---

## 实施顺序

按优先级：P0 (RagTestManager, RetrievalService) → P1 (MetadataProcessor, DocumentIngestion, IndexManager) → P2 (CacheService, PromptManager)

---

**下一步**: [01-rag-test-manager-split.md](./01-rag-test-manager-split.md)
