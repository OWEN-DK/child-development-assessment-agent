# API 接口变更参考

## Phase 2A 新增接口

| 接口 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/api/v1/rag/test/run` | POST | 统一测试执行入口（支持多测试集、自定义用例、报告格式） | ✅ 已完成 |
| `/api/v1/rag/test/reports/{run_id}/generate` | POST | 生成测试报告 | ✅ 已完成 |
| `/api/v1/rag/test/reports/{run_id}` | GET | 获取报告内容（Markdown） | ✅ 已完成 |
| `/api/v1/rag/test/reports/{run_id}/export` | GET | 导出报告（Markdown/JSON/PDF） | ✅ 已完成 |
| `/api/v1/rag/test/reports/{run_id}` | DELETE | 删除报告 | ✅ 已完成 |
| `/api/v1/rag/test/documents/{doc_id}/generate-drafts-optimized` | POST | 优化版草稿生成（按章节分块并行+去重） | ✅ 已完成 |

## Phase 2A 修改接口

| 接口 | 变更内容 | 状态 |
|------|---------|------|
| `POST /rag/test/run` | 统一执行入口，支持 test_set_ids/custom_case_ids/report_export_format | ✅ 已完成 |
| `GET /rag/test/runs` | 内部实现从 JSON 切换为 DB，接口签名不变 | ✅ 已完成 |
| `GET /rag/test/runs/{run_id}` | 内部实现从 JSON 切换为 DB，接口签名不变 | ✅ 已完成 |
| `POST /rag/test/run/legacy` | 保留旧接口向后兼容 | ✅ 已完成 |

## 其他 Phase 接口（待实施）

| 接口 | 方法 | 说明 | 所属 Phase |
|------|------|------|-----------|
| `/api/v1/rag/test/run/{run_id}/tuning-suggestions` | GET | 获取指定测试运行的调参建议 | Phase 2C |
| `/api/v1/rag/test/tuning-suggestions/preview` | POST | 预览应用某条建议后的预期指标变化 | Phase 2C |
| `/api/v1/rag/test/tuning-suggestions/apply` | POST | 一键应用建议参数到当前配置版本 | Phase 2C |
| `/api/v1/monitoring/traces` | GET | 分页查询追踪列表 | Phase 3 |
| `/api/v1/monitoring/traces/{trace_id}` | GET | 获取单次追踪的完整数据 | Phase 3 |
| `/api/v1/monitoring/traces/{trace_id}/spans/{span_id}` | GET | 获取单个 Span 的详细信息 | Phase 3 |
| `/api/v1/monitoring/cost` | GET | 成本分析接口 | Phase 3 |
| `/api/v1/monitoring/latency` | GET | 延迟分布接口 | Phase 3 |
| `/api/v1/monitoring/errors` | GET | 错误分析接口 | Phase 3 |

---

**返回索引：** [README.md](./README.md)
