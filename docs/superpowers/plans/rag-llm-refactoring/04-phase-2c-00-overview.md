# Phase 2C: 智能调参建议引擎 - Overview

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
> **状态:** 📋 方案构建完成，待实施
> **优先级:** 中
> **预计工期:** 5 人天
> **依赖前置:** Phase 2A (RAG 评估工作流重塑，需测试报告数据就绪)、PromptManager 与 ConfigManager 基础设施稳定运行

**Goal:** 构建 RAG 智能调参建议引擎，基于测试结果自动诊断问题根因，给出可操作、可解释、可验证的参数优化建议，形成"测试 → 诊断 → 调参 → 复测"的闭环。

**Architecture:** 采用三层递进式架构：规则引擎 (Rule Engine) 指标驱动毫秒级响应、历史对比 (History Analysis) 从历史运行提取经验、LLM 诊断 (LLM-as-Judge) 对 Bad Case 语义深度分析。规则配置通过 ConfigManager 存入 MySQL，诊断 Prompt 通过 PromptManager 管理。

**Tech Stack:** Python 3.13, FastAPI 0.135, SQLAlchemy 2.0, Pydantic v2, Injector, json-repair, React 19, TypeScript

---

## 实施顺序

> **分阶段实施策略**: 为降低风险，分三阶段落地：Phase 2C.1 完成规则引擎与冲突检测（核心路径，无 LLM 成本）；Phase 2C.2 实现历史对比与 LLM 诊断；Phase 2C.3 完成 API、前端集成与全链路验证。

| 步骤 | 内容 | 状态 | 阶段 | 详细文档 |
|------|------|------|------|----------|
| 1 | 规则引擎 (配置化 + 核心 + 冲突检测) | ⏳ 待实现 | Phase 2C.1 | [01-rule-engine.md](./04-phase-2c-01-rule-engine.md) |
| 2 | 历史对比分析 | ⏳ 待实现 | Phase 2C.2 | [02-history-analyzer.md](./04-phase-2c-02-history-analyzer.md) |
| 3 | LLM 诊断 | ⏳ 待实现 | Phase 2C.2 | [03-llm-diagnoser.md](./04-phase-2c-03-llm-diagnoser.md) |
| 4 | 统一引擎 + API 实现 | ⏳ 待实现 | Phase 2C.3 | [04-engine-api.md](./04-phase-2c-04-engine-api.md) |
| 5 | 前端集成 (MVP) | ⏳ 待实现 | Phase 2C.3 | [05-frontend-mvp.md](./04-phase-2c-05-frontend-mvp.md) |
| 6 | TDD 测试策略 | ⏳ 待实现 | Phase 2C.3 | [06-testing.md](./04-phase-2c-06-testing.md) |

---

## 前置准备

- [x] Phase 1 LLM 供应商重构完成并上线
- [x] Phase 2A RAG 评估工作流重塑完成，TestRun/TestRunResult 数据在 MySQL 中可用
- [x] PromptManager 基础设施稳定运行 (版本管理、缓存、A/B 测试)
- [x] ConfigManager 热更新机制正常工作
- [x] `json-repair` 库已安装 (Phase 1 依赖)

---

## 核心架构

```
┌─────────────────────────────────────────────────┐
│              TuningSuggestionEngine               │
│  (统一入口，协调三层诊断)                          │
└──────────┬──────────────┬──────────────┬─────────┘
           ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ RuleEngine   │ │ HistoryAnalyzer│ │ LLMDiagnoser │
│ (规则引擎)    │ │ (历史对比)    │ │ (LLM诊断)    │
└──────────────┘ └──────────────┘ └──────────────┘
       │                  │                  │
       ▼                  ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ ConfigManager│ │ TestRun DB   │ │ PromptManager│
│ (MySQL存储)   │ │ ConfigVersion│ │ LLM Factory  │
└──────────────┘ └──────────────┘ └──────────────┘
```

### 关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 规则存储 | MySQL `config_versions` 表 | 禁止本地 JSON 文件，支持多实例共享和热更新 |
| 冲突检测 | 按参数名分组 + 动作方向判断 | 简单高效，避免矛盾建议 |
| LLM 触发条件 | Bad Case ≥ 3 | 控制成本，少量失败案例无需深度诊断 |
| LLM 输出解析 | `json-repair` 库 | 防止 LLM 截断或格式错误导致解析失败 |
| 历史匹配算法 | 指标短板向量余弦相似度 | 轻量级，无需额外训练模型 |
| 缓存策略 | 建议结果缓存 5 分钟 | 避免重复计算，用户频繁查看同一报告时命中缓存 |

---

## 🎯 验收标准

### 核心功能验收

| 检查项 | 测试命令 | 预期结果 |
|--------|----------|----------|
| 规则引擎触发 | `pytest tests/unit/tuning/test_rule_engine.py -v` | 指标低于阈值时正确触发建议，高于阈值时不触发 |
| 冲突检测 | `pytest tests/unit/tuning/test_conflict_detector.py -v` | 矛盾建议被正确过滤，保留高优先级 |
| 历史对比 | `pytest tests/unit/tuning/test_history_analyzer.py -v` | 正确提取配置变更和指标变化，<2 次历史时返回空 |
| LLM 诊断 | `pytest tests/unit/tuning/test_llm_diagnoser.py -v` | Bad Case ≥ 3 时触发诊断，输出结构化 JSON |
| 统一引擎 | `pytest tests/unit/tuning/test_engine.py -v` | 三层诊断结果正确合并，冲突检测生效 |
| API 接口 | `pytest tests/integration/tuning/test_tuning_api.py -v` | 3 个 API 接口功能正常，请求/响应格式正确 |
| 配置应用 | `pytest tests/integration/tuning/test_config_apply.py -v` | 建议参数正确应用到 ConfigManager，生成新版本 |
| 端到端全链路 | `pytest tests/e2e/test_tuning_workflow.py -v` | 从测试完成→获取建议→应用参数→复测全流程正常 |

### 性能基线验收

| 检查项 | 基准环境 | 测量方法 | 预期结果 |
|--------|----------|----------|----------|
| 规则引擎响应时间 | 4C8G, MySQL 本地 | `pytest tests/unit/tuning/test_rule_engine.py::test_evaluate_latency` | <50ms |
| 历史对比响应时间 | ≥5 次历史运行 | `pytest tests/unit/tuning/test_history_analyzer.py::test_analyze_latency` | <100ms |
| LLM 诊断响应时间 | Bad Case 10 条 | `pytest tests/unit/tuning/test_llm_diagnoser.py::test_diagnose_latency` | 1-3s |
| 缓存命中率 | 同一 run_id 连续请求 5 次 | 检查 Redis 缓存命中日志 | ≥80% |

---

## 🔙 回滚计划

| 风险场景 | 回滚操作 | 回滚耗时 | 影响范围 |
|---------|---------|---------|---------|
| 规则引擎加载失败 | 返回空建议列表 + 错误日志，不影响其他功能 | 自动降级 | 仅调参建议不可用 |
| LLM 诊断调用异常 | 跳过 LLM 层，仅返回规则引擎和历史对比结果 | 自动降级 | 深度诊断不可用 |
| 配置应用后检索异常 | 通过 ConfigManager 回滚到上一配置版本 | <1 分钟 | 检索参数恢复为旧值 |
| 前端组件报错 | 隐藏调参建议面板，不影响报告展示 | 前端条件渲染 | 仅面板不展示 |

---

## ⚠️ 风险登记册

| 风险项 | 发生概率 | 影响程度 | 缓解措施 |
|-------|----------|----------|----------|
| 规则建议值超出安全范围导致检索质量下降 | 低 | 高 | 所有建议值必须在 `safe_range` 内，应用前二次校验 |
| 历史对比数据不准确导致误导 | 中 | 中 | 历史参考仅作为参考，标注置信度 |
| LLM 诊断输出格式不稳定 | 中 | 中 | 使用 `json-repair` 修复，解析失败时返回降级结果 |
| 冲突检测算法误过滤有效建议 | 低 | 中 | 冲突检测仅针对同一参数的矛盾动作，不同参数不冲突 |
| 配置应用后未自动生效 | 低 | 高 | 应用后触发 ConfigManager 热更新事件，验证新配置已激活 |

---

**上一阶段:** [Phase 2B](./03-phase-2b-prompt-config-cleanup.md)  
**下一阶段:** [Phase 3](./05-phase-3-llm-tracing.md)

**子文档索引:**

| 步骤 | 内容 | 状态 | 阶段 | 详细文档 |
|------|------|------|------|----------|
| 1 | 规则引擎 | ⏳ 待实现 | Phase 2C.1 | [01-rule-engine.md](./04-phase-2c-01-rule-engine.md) - 规则配置化 (MySQL) + 核心实现 + 冲突检测 |
| 2 | 历史对比分析 | ⏳ 待实现 | Phase 2C.2 | [02-history-analyzer.md](./04-phase-2c-02-history-analyzer.md) - 数据关联链路 + 相似匹配 + 效果追踪 |
| 3 | LLM 诊断 | ⏳ 待实现 | Phase 2C.2 | [03-llm-diagnoser.md](./04-phase-2c-03-llm-diagnoser.md) - Prompt 设计 + Bad Case 聚合 + 输出解析 |
| 4 | 统一引擎 + API | ⏳ 待实现 | Phase 2C.3 | [04-engine-api.md](./04-phase-2c-04-engine-api.md) - 引擎入口 + 3 个 API 接口 |
| 5 | 前端集成 (MVP) | ⏳ 待实现 | Phase 2C.3 | [05-frontend-mvp.md](./04-phase-2c-05-frontend-mvp.md) - 建议面板 + 一键优化组件 |
| 6 | TDD 测试策略 | ⏳ 待实现 | Phase 2C.3 | [06-testing.md](./04-phase-2c-06-testing.md) - 测试文件清单 + 红绿重构步骤 |

> **分阶段实施策略**: 为降低风险，分三阶段落地：Phase 2C.1 完成规则引擎与冲突检测（核心路径，无 LLM 成本）；Phase 2C.2 实现历史对比与 LLM 诊断；Phase 2C.3 完成 API、前端集成与全链路验证。
> **任务依赖关系**: 历史对比和 LLM 诊断依赖规则引擎完成，统一引擎依赖所有三层组件完成，API 依赖引擎完成，前端依赖 API 完成。

---

## 📌 全局说明

1. **测试目录适配**: 所有测试用例路径默认适配 `tests/` 根目录，可根据项目实际测试目录结构调整
2. **导入路径适配**: 代码示例中的导入路径基于项目现有目录结构，如需调整可根据实际模块位置修改
3. **全链路集成测试流程**: 完成所有开发后执行：
   1. 运行一次完整测试集执行 (`POST /rag/test/run`)
   2. 获取调参建议 (`GET /run/{run_id}/tuning-suggestions`)
   3. 应用建议参数 (`POST /tuning-suggestions/apply`)
   4. 重新执行测试集，验证指标变化
   5. 运行所有单元测试
4. **部署注意事项**: 规则配置需通过 ConfigManager 首次写入 MySQL，诊断 Prompt 需通过 PromptManager 首次写入
