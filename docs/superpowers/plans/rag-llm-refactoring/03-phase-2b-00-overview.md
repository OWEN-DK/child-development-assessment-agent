# Phase 2B: 提示词/配置收拢 - Overview

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
> **状态:** ✅ 方案已完成
> **优先级:** 高
> **预计工期:** 5 人天
> **依赖前置:** Phase 1 LLM 供应商重构完成、PromptManager 与 ConfigManager 基础设施稳定运行

**Goal:** 全面清查并收拢散落在代码中的硬编码提示词 (Prompts) 与业务配置 (Configs/魔法值)，统一接入 PromptManager 和 ConfigManager 进行版本控制、热更新与 A/B 测试分发。

**Architecture:** 采用分阶段迁移策略 (P0/P1/P2 三批次)，提示词提取至 MySQL 数据库通过 PromptManager 管理，魔法值提升至 ConfigManager 配置模块（MySQL 存储），每迁移 2-3 个即执行回归测试确保功能一致性。

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, MySQL 5.7, Redis 7.0, PromptManager, ConfigManager

---

## 实施顺序

> **分阶段实施策略**: 为降低风险，分三批次落地：Phase 2B.1 完成提示词扫描与迁移 (P0/P1/P2)；Phase 2B.2 实现业务配置与魔法值迁移；Phase 2B.3 完成兼容性验证与回归测试。

| 步骤 | 内容 | 状态 | 阶段 | 详细文档 |
|------|------|------|------|----------|
| 1 | 提示词扫描与盘点 | ⏳ 待实现 | Phase 2B.1 | [01-prompt-scan.md](./03-phase-2b-01-prompt-scan.md) |
| 2 | 提示词迁移与接入 | ⏳ 待实现 | Phase 2B.1 | [02-prompt-migration.md](./03-phase-2b-02-prompt-migration.md) |
| 3 | 提示词校验与测试 | ⏳ 待实现 | Phase 2B.1 | [03-prompt-validation.md](./03-phase-2b-03-prompt-validation.md) |
| 4 | 配置扫描与盘点 | ⏳ 待实现 | Phase 2B.2 | [04-config-scan.md](./03-phase-2b-04-config-scan.md) |
| 5 | 配置迁移与接入 | ⏳ 待实现 | Phase 2B.2 | [05-config-migration.md](./03-phase-2b-05-config-migration.md) |
| 6 | 魔法值清理与重构 | ⏳ 待实现 | Phase 2B.2 | [06-magic-value-cleanup.md](./03-phase-2b-06-magic-value-cleanup.md) |
| 7 | 兼容性与降级处理 | ⏳ 待实现 | Phase 2B.3 | [07-compatibility.md](./03-phase-2b-07-compatibility.md) |

---

## 前置准备

- [x] Phase 1 LLM 供应商重构完成并上线
- [x] PromptManager 基础设施稳定运行 (版本管理、A/B 测试、缓存失效)
- [x] ConfigManager 热更新机制正常工作
- [ ] 业务规则 Pydantic 模型定义完成 (`src/config/modules/rag/rules.py`)
- [x] 数据库 `prompt_versions` 表结构支持扩展 variables 字段

---

## 当前实现状态对比

| 功能模块 | 现状 | 规划目标 |
|----------|------|----------|
| 提示词管理 | ⚠️ 部分实现：`src/core/prompts.py` 集中管理部分提示词，但 nodes/ 目录下仍有硬编码 | ⏳ 待实现：全部迁移至 PromptManager (MySQL + Redis 缓存)，代码仅保留 `get_prompt()` 调用 |
| PromptManager | ✅ 已实现：基础版本管理、缓存、A/B 测试分发 | ⏳ 待增强：补充占位符校验器、Fallback 机制完善、初始数据迁移脚本 |
| 配置管理 | ⚠️ 部分实现：部分 RAG 参数已定义在 `config/modules/rag/` 模块中 | ⏳ 待实现：魔法值全部提升至 ConfigManager，业务规则分离到 rules.json |
| ConfigManager | ✅ 已实现：热更新机制、EventBus 事件驱动 | ⏳ 待增强：新增 LLM 场景参数/RAG 评分/去重/元数据等配置模块 |
| 降级机制 | ❌ 未实现 | ⏳ 待实现：PromptManager 不可用时降级到内嵌 fallback，ConfigManager 不可用时使用 Pydantic 默认值 |
| 业务规则 | ❌ 未分离：年龄段划分、年龄边界等硬编码在 `age_filter.py` 和 `child_development_engine.py` | ⏳ 待实现：提取到 ConfigManager（MySQL 存储），支持热更新 |

---

## 🎯 验收标准

### 核心功能验收

| 检查项 | 测试命令 | 预期结果 |
|--------|----------|----------|
| 提示词迁移完整性 | `pytest tests/core/prompts/test_prompt_migration.py -v` | 所有 P0/P1/P2 提示词迁移完成，代码中无硬编码提示词 |
| 提示词 Fallback 验证 | `pytest tests/core/prompts/test_prompt_fallback.py -v` | PromptManager 不可用时降级到内嵌 fallback 提示词 |
| 配置迁移完整性 | `pytest tests/config/test_config_migration.py -v` | 所有 P0/P1/P2 魔法值迁移完成，代码中无硬编码阈值 |
| 业务规则分离验证 | `pytest tests/config/test_rules_json.py -v` | 年龄段划分、年龄边界等规则正确提取到 rules.json |
| 热更新验证 | `pytest tests/config/test_hot_reload_prompts_configs.py -v` | 提示词和配置变更自动生效，无需重启服务 |
| 回归测试 | `pytest tests/e2e/test_assessment_workflow.py -v` | 核心评估流程功能正常，输出结果与迁移前一致 |

### 性能基线验收

| 检查项 | 基准环境 | 测量方法 | 预期结果 |
|--------|----------|----------|----------|
| 提示词加载延迟 | 4C8G, Redis 本地, MySQL 本地, 缓存命中 | `pytest tests/core/prompts/test_prompt_manager_perf.py::test_prompt_load_latency` | 缓存命中 <5ms, 数据库查询 <50ms |
| 配置读取延迟 | 4C8G, Redis 本地, 缓存命中 | `pytest tests/config/test_config_perf.py::test_config_read_latency` | <2ms |
| 回归测试通过率 | 全量测试集, 4C8G | `pytest tests/ -v --no-header -q` | 100% 通过，无功能退化 |

---

## 🚀 上线迁移策略

### 阶段 1：提示词迁移 (上线前 3 天)

1. 按 P0 → P1 → P2 顺序分批迁移提示词
2. 每迁移 2-3 个提示词即执行回归测试
3. 确认功能正常后提交代码

### 阶段 2：配置迁移 (上线前 2 天)

1. 按 P0 (LLM 参数) → P1 (RAG 阈值) → P2 (文档处理) 顺序迁移
2. 魔法值迁移后通过单元测试验证算法行为一致性
3. 业务规则提取到 rules.json 后验证配置加载

### 阶段 3：切换与验证 (上线当天)

1. 部署新版本代码，所有提示词和配置从管理系统读取
2. 观察 2 小时，监控错误率和响应时间
3. 若发现异常，立即回滚到上一版本

### 阶段 4：清理 (上线后 7 天)

1. 确认系统稳定运行 7 天
2. 移除代码中遗留的 fallback 提示词和硬编码配置
3. 更新 AGENTS.md 和 CLAUDE.md 文档

---

## 🔙 回滚计划

| 风险场景 | 回滚操作 | 回滚耗时 | 影响范围 |
|---------|---------|---------|---------|
| 提示词迁移后 LLM 输出异常 | 回退代码到迁移前版本，或 PromptManager 切换回旧版本 | <5 分钟 | 部分功能降级，核心链路可用 |
| 配置迁移后算法行为改变 | 回退配置模块到上一版本，恢复硬编码阈值 | <10 分钟 | 检索/评分精度波动，功能可用 |
| PromptManager 不可用 | 自动降级到 fallback 提示词，无需人工干预 | 自动 | 提示词版本控制失效，功能降级可用 |
| ConfigManager 热更新失败 | 重启服务加载最新配置，或回退到硬编码 | <5 分钟 | 配置变更需重启生效 |

---

## ⚠️ 风险登记册

| 风险项 | 发生概率 | 影响程度 | 缓解措施 | 责任人 |
|-------|----------|----------|----------|--------|
| 提示词占位符 (Variables) 不匹配导致渲染失败 | 中 | 高 | 迁移时严格校验占位符对应关系；单元测试覆盖所有提示词渲染 | 实施工程师 |
| 魔法值迁移后算法精度下降 | 中 | 高 | 迁移前后对比测试，确保输出结果一致性；保留原阈值作为 fallback | 实施工程师 |
| 批量迁移导致回归测试范围遗漏 | 低 | 高 | 每迁移 2-3 个即执行回归测试；建立完整的提示词/配置映射清单 | QA 工程师 |
| rules.json 业务规则与代码逻辑不同步 | 低 | 中 | 规则变更后自动校验；单元测试验证规则加载正确性 | 实施工程师 |
| 热更新触发频繁导致性能抖动 | 低 | 中 | 配置变更事件去重；Redis 缓存加速读取 | 架构师 |

---

**上一阶段:** [Phase 2A](./02-phase-2a-rag-workflow.md)  
**下一阶段:** [Phase 2C](./04-phase-2c-tuning-engine.md)

**子文档索引:**

| 步骤 | 内容 | 状态 | 阶段 | 详细文档 |
|------|------|------|------|----------|
| 1 | 提示词扫描与盘点 | ⏳ 待实现 | Phase 2B.1 | [01-prompt-scan.md](./03-phase-2b-01-prompt-scan.md) - 全代码扫描、提示词清单、优先级分级 |
| 2 | 提示词迁移与接入 | ⏳ 待实现 | Phase 2B.1 | [02-prompt-migration.md](./03-phase-2b-02-prompt-migration.md) - P0/P1/P2 分批迁移、代码替换、Fallback 配置 |
| 3 | 提示词校验与测试 | ⏳ 待实现 | Phase 2B.1 | [03-prompt-validation.md](./03-phase-2b-03-prompt-validation.md) - 占位符校验、渲染测试、回归测试 |
| 4 | 配置扫描与盘点 | ⏳ 待实现 | Phase 2B.2 | [04-config-scan.md](./03-phase-2b-04-config-scan.md) - 魔法值扫描、配置清单、目标配置键映射 |
| 5 | 配置迁移与接入 | ⏳ 待实现 | Phase 2B.2 | [05-config-migration.md](./03-phase-2b-05-config-migration.md) - P0/P1/P2 分批迁移、ConfigManager 接入 |
| 6 | 魔法值清理与重构 | ⏳ 待实现 | Phase 2B.2 | [06-magic-value-cleanup.md](./03-phase-2b-06-magic-value-cleanup.md) - 代码重构、规则分离、单元测试 |
| 7 | 兼容性与降级处理 | ⏳ 待实现 | Phase 2B.3 | [07-compatibility.md](./03-phase-2b-07-compatibility.md) - Fallback 机制、热更新验证、文档更新 |

> **分阶段实施策略**: 为降低风险，分三批次落地：Phase 2B.1 完成提示词扫描与迁移 (P0/P1/P2)；Phase 2B.2 实现业务配置与魔法值迁移；Phase 2B.3 完成兼容性验证与回归测试。
> **任务依赖关系**: 提示词迁移依赖扫描盘点完成，配置迁移依赖扫描盘点完成，兼容性验证依赖所有迁移完成。

---

## 📌 全局说明

1. **测试目录适配**: 所有测试用例路径默认适配 `tests/` 根目录，可根据项目实际测试目录结构调整
2. **测试路径适配**: 文档中 `tests/core/prompts/` 为示意路径，实施时需根据项目实际测试目录结构调整 (如 `tests/unit/core/prompt/`)
3. **导入路径适配**: 代码示例中的导入路径基于项目现有目录结构，如需调整可根据实际模块位置修改
4. **全链路集成测试流程**: 完成所有开发后执行：
   1. 运行数据库迁移 `alembic upgrade head`
   2. 执行提示词迁移验证脚本
   3. 从用户输入→预处理→校验→评估→检索→评分→报告生成全流程验证
   4. 运行所有单元测试和回归测试
5. **部署注意事项**: 提示词和配置迁移后需确保 PromptManager 和 ConfigManager 服务正常运行，Redis 缓存已预热
