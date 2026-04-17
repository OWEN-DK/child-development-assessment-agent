# Phase 3: 前端页面实现 — 总览

> **需求来源**: spec 文档 `04-frontend-pages.md`
> **需求点数量**: 10 个
> **优先级**: P1

## 目标

实现 `/rag-eval/*` 全部前端页面，删除旧路由与组件。

## 需求点清单

| # | 需求点 | 实施文件 | 路由 | 说明 |
|---|--------|---------|------|------|
| 1 | `/rag-eval/*` 路由配置 | `01-routes-rag-eval.md` | - | React Router 7 路由配置 |
| 2 | 测试集列表页 | `02-page-testset-list.md` | `/rag-eval/test-sets` | 列表展示、搜索、筛选、创建 |
| 3 | 测试集详情页 | `03-page-testset-detail.md` | `/rag-eval/test-sets/{id}` | 用例列表、运行测试、添加用例 |
| 4 | 草稿审核页 | `04-page-draft-review.md` | `/rag-eval/test-sets/{id}/drafts` | 草稿列表、通过/拒绝、批量归入 |
| 5 | 运行历史列表页 | `05-page-run-list.md` | `/rag-eval/runs` | 列表展示、筛选（状态/测试集） |
| 6 | 运行详情页 | `06-page-run-detail.md` | `/rag-eval/runs/{id}` | 汇总指标、用例执行结果、SSE 进度 |
| 7 | 评估报告页 | `07-page-report.md` | `/rag-eval/reports/{id}` | 指标总览、6 层校验、推荐面板、趋势图 |
| 8 | 删除旧路由 `/rag-evaluation` | `08-delete-old-routes.md` | - | 直接删除，不保留兼容 |
| 9 | 删除 OneClickOptimize 组件 | `09-delete-oneclickoptimize.md` | - | 违反"禁止替用户决策"原则 |
| 10 | SPA 回退路由 | `10-spa-fallback-route.md` | - | 后端配置非 API 路径 404 返回 index.html |

## 验收标准

- [ ] 前端路由 `/rag-eval/*` 全部可用
- [ ] 评估报告页展示 6 层校验结果
- [ ] 测试集管理（列表/详情/用例管理）
- [ ] 草稿审核页功能正常
- [ ] 运行历史列表与详情页
- [ ] 旧路由 `/rag-evaluation` 直接删除
- [ ] `OneClickOptimize` 组件直接删除
- [ ] 后端配置 SPA 回退路由

## 删除清单

| 文件/路由 | 说明 |
|-----------|------|
| `frontend/src/features/rag-evaluation/` | 旧评估页面目录，直接删除 |
| `frontend/src/components/rag/OneClickOptimize.tsx` | 违反"禁止替用户决策"原则 |
| `/rag-evaluation` 路由 | 旧路由，不保留兼容 |
| `backend/src/controller/rag_test_controller.py` 中 `/rag/test/run/{run_id}/stream` 路由注册 | 旧 SSE 端点，Phase-2 已由 `/api/runs/{run_id}/sse` 替代 |
| `backend/src/router/` 或 `backend/src/server.py` 中旧路由注册代码 | 删除 `app.include_router(rag_evaluation_router)` 或类似注册语句 |

---

**文档索引**: 
- 上一节: [Phase 2 总览](../phase-2/00-overview.md)
- 下一节: [01-routes-rag-eval.md](./01-routes-rag-eval.md) — 需求点 1
