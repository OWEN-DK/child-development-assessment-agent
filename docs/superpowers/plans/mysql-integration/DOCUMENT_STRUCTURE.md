# 文档结构说明

## 📁 文件组织

本文档已将原始的单一实施方案文件拆分为多个独立的模块，便于管理和维护。

### 核心文档结构

```
mysql-integration/
├── README.md                          # 主索引文件（入口）
├── 00-overview.md                     # 项目概览与文件结构变更
│
├── 01-phase-0-infrastructure.md       # Phase 0: MySQL + Redis 基础设施搭建
├── 02-phase-1-config-migration.md     # Phase 1: 配置系统 MySQL 迁移
├── 03-phase-2-llm-factory.md          # Phase 2: LLM 服务工厂重构
├── 04-phase-3-rag-pipeline.md         # Phase 3: RAG 查询流水线重构
├── 05-phase-4-test-framework.md       # Phase 4: RAG 测试框架迁移
├── 06-phase-5-monitoring.md           # Phase 5: LLM 监控系统
├── 07-phase-6-prompt-management.md    # Phase 6: 提示词管理系统
├── 08-phase-7-frontend-integration.md # Phase 7: 前端集成测试
├── 09-phase-8-deployment.md           # Phase 8: 部署与上线
├── 10-remaining-phases-overview.md    # 剩余阶段概览 (Phase 2-8 快速参考)
│
├── appendix-a-design-decisions.md     # 附录 A: 关键设计决策（新增）
├── appendix-b-performance-benchmarks.md  # 性能基准测试
├── appendix-c-troubleshooting.md         # 风险缓解与故障排查
├── appendix-d-migration-checklist.md     # 数据迁移检查清单（新增）
│
└── DOCUMENT_STRUCTURE.md            # 本文档
```

### 文档拆分策略

| 原始文档部分 | 拆分后文件 | 说明 |
|-------------|-----------|------|
| 文件结构变更总览 | `00-overview.md` | 包含新增/修改/删除文件清单、架构图、依赖管理 |
| Phase 0 (详细) | `01-phase-0-infrastructure.md` | Task 0.1-0.13 的完整实施步骤 |
| Phase 1 (详细) | `02-phase-1-config-migration.md` | Task 1.1-1.4 的完整实施步骤 |
| Phase 2 (详细) | `03-phase-2-llm-factory.md` | Task 2.1-2.5: LLM 服务工厂、9 大场景、双框架适配 |
| Phase 3 (详细) | `04-phase-3-rag-pipeline.md` | Task 3.1-3.5: YAML 编排器、查询路由、失败降级 |
| Phase 4 (详细) | `05-phase-4-test-framework.md` | Task 4.1-4.4: MySQL 迁移、分布式锁、SSE 推送 |
| Phase 5 (详细) | `06-phase-5-monitoring.md` | Task 5.1-5.3: LLM 日志采集、监控 API、指标聚合 |
| Phase 6 (详细) | `07-phase-6-prompt-management.md` | Task 6.1-6.2: 提示词版本控制、A/B 测试、API |
| Phase 7 (详细) | `08-phase-7-frontend-integration.md` | Task 7.1-7.4: 系统配置、提示词管理、监控仪表板 |
| Phase 8 (详细) | `09-phase-8-deployment.md` | Task 8.1-8.4: 生产配置、数据库迁移、压力测试 |
| Phase 2-8 (概览) | `10-remaining-phases-overview.md` | Phase 2-8 的高层次概览（快速参考） |
| 性能预期指标 | `appendix-b-performance-benchmarks.md` | 性能对比表格 |
| 风险缓解措施 | `appendix-c-troubleshooting.md` | 风险缓解策略和实施建议 |
| 关键设计决策 | `appendix-a-design-decisions.md` | 架构决策记录、技术选型原因（新增） |
| 数据迁移检查 | `appendix-d-migration-checklist.md` | 数据清理、迁移验证清单（新增） |

---

## 📖 使用指南

### 阅读顺序

1. **入口**：从 [`README.md`](./README.md) 开始，了解项目整体
2. **概览**：阅读 [`00-overview.md`](./00-overview.md)，了解文件结构和架构
3. **实施**：按顺序执行各个 Phase：
   - [`Phase 0`](./01-phase-0-infrastructure.md) - 基础设施搭建
   - [`Phase 1`](./02-phase-1-config-migration.md) - 配置系统迁移
   - [`Phase 2-8`](./10-remaining-phases-overview.md) - 剩余阶段（概览）
4. **参考**：查阅附录文档获取性能指标和故障排查指南

### 任务追踪

每个 Phase 文档都使用 checkbox (`- [ ]`) 语法，方便追踪进度：

```markdown
- [ ] **Step 1: 任务描述**
```

实施时，将已完成的步骤标记为：

```markdown
- [x] **Step 1: 任务描述**
```

---

## 🔧 文档维护

### 添加新内容

如需补充 Phase 2-8 的详细任务，可以：

1. 创建新的文件，如 `03-phase-2-llm-factory.md`
2. 在 `README.md` 中更新链接
3. 在 `10-remaining-phases-overview.md` 中标记为"已完成"

### 更新现有内容

直接编辑对应的 Phase 文件即可。所有修改应：
- 保持代码示例的完整性
- 包含必要的导入语句
- 提供测试步骤和预期结果

---

## 📊 修复历史

本文档已应用以下修复：

- ✅ **Batch 1**: 移除所有 git 操作步骤（31 处）
- ✅ **Batch 1**: 修复包管理器配置（poetry → uv）
- ✅ **Batch 2**: 修复缺失的依赖和类型定义
  - 添加 `db_session_factory` 导出说明
  - 创建 `entities.py` 配置实体定义
  - 修复所有 JSON 字段类型

### 已完成修复

- ✅ **Batch 3**: 补充缺失的代码和说明
  - Redis 客户端懒加载说明
  - EVENT_CLASSES 定义
  - Pydantic v2 兼容性处理
  - time 模块导入说明
- ✅ **Batch 4**: 完善 Phase 2-8 的详细任务
  - Phase 2: LLM 服务工厂（9 大场景、双框架适配）
  - Phase 3: RAG 流水线（YAML 编排、失败降级）
  - Phase 4: RAG 测试框架（MySQL 迁移、SSE 推送）
  - Phase 5: LLM 监控系统（日志采集、指标聚合）
  - Phase 6: 提示词管理系统（版本控制、A/B 测试）
  - Phase 7: 前端集成（系统配置、监控仪表板）
  - Phase 8: 部署与上线（生产配置、压力测试）

---

## 🔗 相关文档

- [设计文档](../specs/2026-04-12-mysql-integration-redesign.md) - 原始设计文档
- [原始实施方案](../plans/2026-04-12-mysql-integration-implementation.md) - 拆分前的完整文档
- [RAG 系统完整文档](../../RAG_SYSTEM_COMPLETE_DOCUMENTATION.md) - RAG 系统技术文档

---

**最后更新：** 2026-04-12  
**文档版本：** 1.0 (拆分版)  
**维护者：** AI Assistant
