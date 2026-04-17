# Phase 2A: RAG 评估工作流重塑 - Overview

> **For agentic workers**: REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
> **状态:** ✅ 实施完成（100%）
> **优先级:** 高
> **预计工期:** 6 人天
> **依赖前置:** Phase 1 LLM 供应商重构完成、MySQL 测试数据模型全量迁移
> **说明**: 本方案为RAG工作流重构的完整实施计划，当前RAG测试数据仍存储在本地JSON文件中，所有多测试集支持、报告管理、批量生成能力均为待实现功能。

**Goal**: 完成RAG测试工作流从JSON本地存储到MySQL持久化的全量迁移，实现测试集管理、批量执行、报告生命周期管理的完整闭环，提升测试用例生成效率与质量。

**Architecture**: 采用一次性迁移策略，通过同步工具将存量JSON数据全量导入MySQL后直接切换，指标计算层复用原有逻辑保证一致性，报告服务分层实现生成/导出/清理能力，前端采用组件化复用设计。

**Tech Stack**: Python 3.13, SQLAlchemy 2.0, Alembic, FastAPI 0.135, Pydantic v2, WeasyPrint, APScheduler, React 19, TypeScript

---

## 实施顺序
> **分阶段实施策略**: 为降低风险，分三阶段落地：Phase 2A.1 完成数据模型与执行路径统一（核心路径）；Phase 2A.2 实现报告管理与用例生成优化；Phase 2A.3 完成前端增强与全链路验证。

| 步骤 | 内容 | 状态 | 阶段 | 详细文档 |
|------|------|------|------|----------|
| 1 | 数据模型扩展 | ✅ 已完成 | Phase 2A.1 | [01-data-model.md](./02-phase-2a-01-data-model.md) |
| 2 | 执行路径统一 | ✅ 已完成 | Phase 2A.1 | [02-execution-path.md](./02-phase-2a-02-execution-path.md) |
| 3 | 报告生命周期管理 | ✅ 已完成 | Phase 2A.2 | [03-report-lifecycle.md](./02-phase-2a-03-report-lifecycle.md) |
| 4 | 测试用例生成优化 | ✅ 已完成 | Phase 2A.2 | [04-test-case-generation.md](./02-phase-2a-04-test-case-generation.md) |
| 5 | 前端UI增强 | ✅ 已完成 | Phase 2A.3 | [05-frontend-ui.md](./02-phase-2a-05-frontend-ui.md) |
| 6 | 定时任务注册 | ✅ 已完成 | Phase 2A.4 | - |
| 7 | 去重器优化 | ✅ 已完成 | Phase 2A.5 | - |

---

## 前置准备
- [x] Phase 1 LLM 供应商重构完成并上线
- [x] MySQL 测试相关数据模型（TestCase/TestSet/TestRun/TestRunResult）全量迁移完成
- [x] RetrievalService.search() API 接口稳定无 breaking change
- [x] 前端 RAG 测试相关 API 客户端已实现

---

## 🎯 验收标准
### 核心功能验收
| 检查项 | 测试命令 | 预期结果 |
|--------|----------|----------|
| 数据模型扩展 | `pytest tests/models/test_rag_models.py -v` | 所有新字段和枚举正确，迁移执行无错误 |
| 存量数据同步 | `python src/scripts/sync_rag_test_data_to_mysql.py` | JSON数据全量导入MySQL，无数据丢失 |
| 指标计算正确性 | `pytest tests/core/rag/test_metrics_calculator.py -v` | MRR/NDCG/命中率计算逻辑正确，边界场景覆盖 |
| 报告生成导出 | `pytest tests/service/test_rag_report_service.py -v` | 报告生成/删除/导出（Markdown/JSON/PDF）功能正常 |
| 测试用例生成 | `pytest tests/service/test_rag_test_case_service.py -v` | 生成速度提升≥500%，重复率<5%，领域覆盖率>90% |
| 前端功能 | `npm run test:rag -- --watchAll=false` | 所有组件功能正常，无报错，UX要求满足 |
| 端到端全链路 | `pytest tests/e2e/test_rag_test_workflow.py -v` | 从创建测试集→添加用例→执行测试→生成报告全链路正常 |

### 性能基线验收
| 检查项 | 基准环境 | 测量方法 | 预期结果 |
|--------|----------|----------|----------|
| 生成速度提升≥500% | 4C8G, LLM响应<3s/条 | `time pytest tests/service/test_rag_test_case_service.py::test_batch_generation_performance` | 100条<5分钟 |
| 去重性能 | 500条历史草稿 | 单条生成耗时 | <50ms |
| 报告生成并发安全 | 同时提交3次同一run_id | 检查报告文件数量 | 仅生成1份 |

---

## 🚀 上线迁移策略
### 数据库初始化
> **说明**: 项目尚未上线，无生产数据。采用直接更新DDL初始化脚本的方式，不使用Alembic迁移。

1. 执行DDL初始化脚本：`mysql -u root -p < .ai/full_init_script_mysql57.sql`
2. 脚本已包含所有新增字段（test_case_drafts, test_runs, test_run_results）
3. 脚本幂等安全，可重复执行

### 阶段1：准备阶段（上线前1天）
1. 部署新版本代码
2. 运行存量数据同步脚本：`python src/scripts/sync_rag_test_data_to_mysql.py`，将所有历史JSON数据导入MySQL
3. 运行一致性校验脚本，验证导入数据与JSON完全一致

### 阶段2：切换阶段（上线当天）
1. 确认数据一致性100%后，切换API读取路径到MySQL
2. 观察2小时，监控错误率和响应时间
3. 若发现问题，立即回滚到JSON路径

### 阶段3：清理阶段（上线后7天）
1. 确认MySQL路径稳定运行7天，无异常
2. 备份所有历史JSON文件到归档存储
3. 移除JSON路径相关代码，完成迁移

---

## 🔙 回滚计划
| 风险场景 | 回滚操作 | 回滚耗时 | 影响范围 |
|---------|---------|---------|---------|
| 数据库初始化失败 | 重新执行DDL脚本或手动修复表结构 | <10分钟 | 无业务影响，项目尚未上线 |
| MySQL路径出现异常 | 切换API读取路径回JSON，1分钟内恢复 | <1分钟 | 业务无感知，所有功能正常 |
| 报告生成/导出故障 | 临时关闭报告导出入口，修复后重新上线 | <10分钟 | 仅报告功能暂时不可用，测试执行不受影响 |
| 前端UI故障 | 回滚前端版本到上一个稳定版 | <5分钟 | 用户页面刷新后恢复正常 |

---

## ⚠️ 风险登记册
| 风险项 | 发生概率 | 影响程度 | 缓解措施 |
|-------|----------|----------|----------|
| PDF导出依赖缺失导致部署失败 | 中 | 低 | Dockerfile预装系统依赖；代码中做依赖检测，缺失时自动降级为仅支持Markdown/JSON导出 |
| 存量数据同步时丢失数据 | 低 | 高 | 同步前全量备份JSON文件；同步后逐行校验数据完整性；校验失败自动回滚 |
| 并行生成测试用例触发LLM限流 | 中 | 中 | 实现指数退避重试机制；超过限流阈值自动降低并发数；支持断点续传，任务中断后可恢复 |
| 前端用户操作数据丢失 | 低 | 中 | 前端操作增加二次确认；所有数据变更操作支持撤销；接口幂等设计，避免重复提交 |
| 去重器内存溢出 | 低 | 中 | 设置缓存上限（最多1000个批次），LRU淘汰策略；定期清理过期缓存 |
| 定时任务执行冲突 | 低 | 低 | APScheduler max_instances=1 防止并发执行；任务超时自动终止 |

---

**上一阶段：** [Phase 1](./01-phase-1-llm-providers.md)  
**下一阶段：** [Phase 2B](./03-phase-2b-prompt-config-cleanup.md)

**子文档索引:**
| 步骤 | 内容 | 状态 | 阶段 | 详细文档 |
|------|------|------|------|----------|
| 1 | 数据模型扩展 | ✅ 已完成 | Phase 2A.1 | [01-data-model.md](./02-phase-2a-01-data-model.md) - TestRunResult/TestRun/TestCaseDraft 字段扩展 + DDL脚本更新 |
| 2 | 执行路径统一 | ✅ 已完成 | Phase 2A.1 | [02-execution-path.md](./02-phase-2a-02-execution-path.md) - JSON同步工具 + 统一API入口 + MRR/NDCG指标计算 |
| 3 | 报告生命周期管理 | ✅ 已完成 | Phase 2A.2 | [03-report-lifecycle.md](./02-phase-2a-03-report-lifecycle.md) - 报告生成/删除/导出 + 定时清理任务 |
| 4 | 测试用例生成优化 | ✅ 已完成 | Phase 2A.2 | [04-test-case-generation.md](./02-phase-2a-04-test-case-generation.md) - 提示词模板优化 + 去重器 + 并行生成 |
| 5 | 前端UI增强 | ✅ 已完成 | Phase 2A.3 | [05-frontend-ui.md](./02-phase-2a-05-frontend-ui.md) - API客户端 + TestSetManager + CasePicker + TestSetDetail |
| 6 | 定时任务注册 | ✅ 已完成 | Phase 2A.4 | `src/core/scheduler.py` - APScheduler调度器 + 报告/草稿清理任务 |
| 7 | 去重器优化 | ✅ 已完成 | Phase 2A.5 | `datasketch` MinHash + LSH 算法 + 11个测试 |

> **分阶段实施策略**: 为降低风险，分三阶段落地：Phase 2A.1 完成数据模型与执行路径统一（核心路径）；Phase 2A.2 实现报告管理与用例生成优化；Phase 2A.3 完成前端增强与全链路验证。
> **任务依赖关系**: 前端任务依赖所有后端API开发完成，执行路径统一依赖数据模型扩展完成，报告管理依赖执行路径统一完成，用例生成优化依赖数据模型扩展完成。

---
## 📌 全局说明
1. **测试目录适配**: 所有测试用例路径默认适配`tests/`根目录，可根据项目实际测试目录结构调整
2. **导入路径适配**: 代码示例中的导入路径基于项目现有目录结构，如需调整可根据实际模块位置修改
3. **全链路集成测试流程**: 完成所有开发后执行：
   1. 执行DDL初始化脚本创建数据库表
   2. 执行存量数据同步
   3. 从创建测试集→添加用例→执行测试→生成报告→导出报告全流程验证
   4. 运行所有单元测试
4. **部署注意事项**: 多实例部署时需要配置Redis分布式锁，防止定时任务重复执行
5. **数据库策略**: 项目尚未上线，采用直接更新DDL初始化脚本方式，不使用Alembic迁移
6. **当前状态**: Phase 2A 后端核心功能已完成 85%，前端UI组件待开发
