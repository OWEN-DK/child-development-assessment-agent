# Phase 1: LLM 多提供商 + 热配置 - Overview

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
> **状态:** ✅ 方案已审查并修正（评分 9.5/10，已修复 25 个问题）
> **说明:** 本方案为RAG-LLM重构的前瞻性技术规划，目前尚未在项目中落地实施。当前项目实际仅支持Dashscope单提供商，文档中描述的多提供商能力、热更新机制等均为待实现功能。

**Goal:** 实现LLM服务从单一DashScope扩展到5+主流提供商支持，并实现全量参数零停机热更新能力，业务代码无感知。

**Architecture:** 采用Provider Registry层抽象不同厂商适配器，工厂类根据配置动态加载对应实例，结合EventBus监听配置变更事件，实现安全的实例重建与热切换。

**Tech Stack:** Python 3.13, LangChain, LlamaIndex, Pydantic v2, Injector, asyncio, uv (包管理器)

---

## 实施顺序

> **分阶段实施策略**: 为降低风险，建议分两阶段落地。Phase 1.1 先完成配置结构化与工厂重构（核心路径）；Phase 1.2 再接入热更新与多提供商扩展（优化路径）。

| 步骤 | 内容 | 状态 | 阶段 | 详细文档 |
|------|------|------|------|----------|
| 1 | 配置层改造 | ⏳ 待实现 | Phase 1.1 | [01-config-layer.md](./01-phase-1-01-config-layer.md) |
| 2 | 配置校验层 | ⏳ 待实现 | Phase 1.1 | [03-hot-reload.md](./01-phase-1-03-hot-reload.md) |
| 3 | 核心工厂类重构 | ⚠️ 部分实现 | Phase 1.1 | [02-factory-refactor.md](./01-phase-1-02-factory-refactor.md) |
| 4 | 热更新机制开发 | ⏳ 待实现 | Phase 1.2 | [03-hot-reload.md](./01-phase-1-03-hot-reload.md) |
| 5 | 批量改造调用点 | ⏳ 待实现 | Phase 1.1 | [04-call-sites.md](./01-phase-1-04-call-sites.md) |
| 6 | 安装依赖并测试 | ⏳ 待实现 | Phase 1.2 | [05-dependencies.md](./01-phase-1-05-dependencies.md) |

> **⚠️ 实施顺序修正**: 配置校验层 (Task 1.3.1) 必须在工厂类重构 (Task 1.2.2) 之前实现，因为工厂依赖校验器。

---

## 概述

本 Phase 实现 LLM 服务从单一 DashScope 扩展到多提供商支持，并实现全量参数的零停机热更新能力。

### 核心架构

```
配置层 (Config) → 校验层 (Validator) → 工厂层 (Factory) → 调用点 (Call Sites)
       ↓                  ↓                    ↓                  ↓
   LLMSceneConfig    Pydantic validate    ProviderRegistry    Nodes/Services
   LLMProviderConfig  model_validate()    LLMServiceFactory   Parsers/Scorers
   EmbeddingConfig                         EmbeddingFactory
   RetrievalConfig                         RerankerFactory
```

### 关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 配置访问 | `get_full_config()` + 解析嵌套键 | `ConfigManager` 无 `get("llm")` 方法 |
| 事件签名 | `ConfigChangedEvent(version_id, changed_keys)` | 使用 `event_bus.py` 版本，非 `events.py` |
| 锁设计 | 双锁 (`_cache_lock` + `_config_lock`) | 避免死锁，缓存操作与配置变更隔离 |
| 热更新 | 引用计数 + 代际追踪 | 零停机，活跃请求完成后才清理旧实例 |
| 校验 | 复用 `LLMSceneConfig.model_validate()` | 避免双重校验规则 diverge |
| 测试 | pytest fixtures (`conftest.py`) | 避免修改全局状态，测试隔离 |

---

## 验收标准

### Phase 1 验收 Checklist

- [ ] **Provider支持验证**
  Run: `pytest tests/core/llm/test_provider_registry.py -v`
  Expected: PASS - 支持DashScope/OpenAI/Anthropic/Ollama 4大提供商

- [ ] **配置分离验证**
  Run: `pytest tests/config/test_llm_config.py -v`
  Expected: PASS - 全局凭证与场景参数完全分离，无硬编码密钥

- [ ] **热更新验证**
  Run: `pytest tests/core/llm/test_hot_reload.py -v`
  Expected: PASS - 配置变更后自动生效，零停机，旧实例在引用计数归零后立即清理

- [ ] **配置校验验证**
  Run: `pytest tests/core/llm/test_config_validator.py -v`
  Expected: PASS - 所有参数校验规则生效，无效配置被拒绝

- [ ] **调用点改造验证**
  Run: `pytest tests/core/nodes/ tests/core/ tests/service/ -v --no-header`
  Expected: All 100+ tests pass - 所有文件改造完成，无功能退化

- [ ] **端到端验证**
  Run: `pytest tests/e2e/test_rag_pipeline.py -v`
  Expected: PASS - 完整RAG链路运行正常，输出结果符合预期

---

## 上线要求
1. 所有单元测试通过（覆盖率≥90%）
2. 集成测试通过
3. 端到端测试通过
4. 性能测试无明显下降（响应时间波动≤10%）
5. 日志监控正常，无错误日志

---

## 🔙 回滚计划
| 风险场景 | 回滚操作 | 回滚耗时 | 影响范围 |
|---------|---------|---------|---------|
| 配置层改造导致启动失败 | 回退 `pyproject.toml` 和配置模块到上一版本 | <5分钟 | 服务启动失败，无业务影响 |
| 工厂重构导致实例创建失败 | 临时切换回硬编码 DashScope 调用，后续修复 | <10分钟 | 部分功能降级，核心链路可用 |
| 热更新机制触发频繁重建 | 关闭 EventBus 订阅，改为手动重启 | <5分钟 | 配置变更需重启生效 |
| 多提供商依赖安装冲突 | 使用 `uv` 回滚依赖版本 | <15分钟 | 依赖安装失败，不影响运行中服务 |

---

## 📊 性能基准
| 检查项 | 基准环境 | 测量方法 | 预期结果 |
|--------|----------|----------|----------|
| 实例创建耗时 | 4C8G, 本地缓存 | `time pytest tests/core/llm/test_llm_factory.py::test_llm_service_factory_create -v` | 首次创建<500ms, 缓存命中<5ms |
| 热更新实例重建 | 配置变更触发 | 记录 `_on_config_changed` 到首次 `create` 返回耗时 | <1s (不含模型加载) |
| 响应时间波动 | 端到端 RAG 链路 | `pytest tests/e2e/test_rag_pipeline.py -v` 对比改造前后 | 波动≤10% |
| 并发安全验证 | 10 并发请求 | `pytest tests/core/llm/test_hot_reload.py::test_hot_reload_concurrent_requests -v` | 无重复实例创建，无死锁 |

---

## 当前实现状态对比
| 功能模块 | 现状 | 规划目标 |
|----------|------|----------|
| LLM提供商支持 | ✅ 已实现：仅支持Dashscope单提供商 | ⏳ 待实现：支持Dashscope/OpenAI/Anthropic/Ollama等多提供商 |
| 工厂模式 | ✅ 已实现：基础LLMServiceFactory，支持按场景创建实例 | ⏳ 待实现：支持多提供商动态选择、配置变更热更新、引用计数安全释放 |
| 配置结构 | ✅ 已实现：按场景定义模型参数 | ⏳ 待实现：LLM提供商统一配置、模型定价配置、场景provider选择字段、env_nested_delimiter支持 |
| Embedding管理 | ✅ 已实现：Dashscope Embedding基础支持 | ⏳ 待实现：多提供商EmbeddingFactory、热更新能力 |
| Reranker管理 | ✅ 已实现：本地bge-reranker基础支持 | ⏳ 待实现：RerankerFactory、多提供商支持 |
| 事件总线集成 | ❌ 未实现 | ⏳ 待实现：配置变更事件监听、自动实例重建 |
| 配置校验层 | ❌ 未实现 | ⏳ 待实现：复用 Pydantic LLMSceneConfig.model_validate() 校验 |
| 并发安全 | ⚠️ 部分实现：有基础缓存，无锁保护 | ⏳ 待实现：双锁设计（缓存锁+配置锁）、引用计数追踪、锁超时 |
| 优雅关闭 | ❌ 未实现 | ⏳ 待实现：shutdown() 方法，等待活跃请求完成后清理 |
| 配置回滚 | ❌ 未实现 | ⏳ 待实现：实例创建失败时保留旧实例 |

## 已修复问题清单 (25个)

| 编号 | 严重级 | 问题 | 修复方案 | 所在文档 |
|------|--------|------|----------|----------|
| C1 | 🔴 | EventBus 异步回调不执行 | `publish()` 中使用 `asyncio.iscoroutinefunction()` 检测，异步回调用 `asyncio.create_task()` 调度 | 02-factory |
| C2 | 🔴 | ConfigChangedEvent 签名不匹配 | 使用 `event_bus.py` 实际签名 `(version_id, changed_keys)`，通过 `changed_keys` 判断热更新 | 01-config |
| C3 | 🔴 | asyncio.Lock 死锁风险 | 双锁设计：`_cache_lock` 保护缓存操作，`_config_lock` 保护配置变更 | 02-factory |
| C4 | 🔴 | `config_manager.get("llm")` 不存在 | 使用 `get_full_config()` + 解析嵌套键（如 `llm_report_generation`） | 01-config |
| C5 | 🔴 | 引用计数竞态条件 | 引入 `_current_generation` 代际计数，旧实例标记代际，清理时检查 | 02-factory |
| H1 | 🟠 | `env_nested_delimiter` 映射问题 | 文档修正：说明需使用统一 Settings 类嵌套结构 | 01-config |
| H2 | 🟠 | 导入顺序错误 | 实施顺序表调整：配置校验层 (1.3.1) 在工厂重构 (1.2.2) 之前 | overview |
| H3 | 🟠 | 配置路径不存在 | 使用 `get_full_config()` 解析扁平化键，非 `settings.llm.report_generation` | 01-config |
| H4 | 🟠 | bare except ImportError | 每个提供商独立 try/except，避免单个缺失导致全部失败 | 02-factory |
| H5 | 🟠 | EmbeddingFactory 重复读配置 | 方法内缓存 `full_config` 和 `llm_providers`，避免多次调用 | 02-factory |
| H6 | 🟠 | 无优雅关闭机制 | 所有工厂添加 `shutdown()` 方法，等待活跃请求后清理 | 02-factory |
| H7 | 🟠 | EventBus 回调不 await | 同 C1，`publish()` 中异步回调使用 `asyncio.create_task()` | 02-factory |
| M1 | 🟡 | ConfigChangedEvent 双定义 | 文档说明：使用 `event_bus.py` 版本，`events.py` 版本由 ConfigManager 内部使用 | 01-config |
| M2 | 🟡 | @inject 装饰器冗余 | 移除所有工厂的 `@inject`，`@singleton` 已处理注入 | 02-factory |
| M3 | 🟡 | 校验器重复 Pydantic 验证 | 使用 `LLMSceneConfig.model_validate()` 替代手动校验规则 | 03-hot-reload |
| M4 | 🟡 | 测试引用未定义单例 | 使用 pytest fixtures (`conftest.py`) 注入工厂实例 | 05-dependencies |
| M5 | 🟡 | EmbeddingFactory 不清理 dispose | `_try_cleanup_deprecated()` 中添加 `dispose()` 调用 | 02-factory |
| M6 | 🟡 | 实例创建失败无回滚 | `create()` 中捕获异常，若有旧实例则保留并返回 | 02-factory |
| M7 | 🟡 | CrossEncoder 加载阻塞事件循环 | 使用 `asyncio.to_thread()` 在独立线程加载模型 | 02-factory |
| M8 | 🟡 | 集成测试修改全局状态 | 使用 mock ConfigManager fixture，不修改 `settings` 对象 | 05-dependencies |
| L1 | 🟢 | 模型名称不一致 | 修正为项目实际的 `qwen3.5-plus` / `qwen3.5-turbo` / `qwen3-omni-flash` | 01-config |
| L2 | 🟢 | 缺少 `__init__.py` 导出 | 新增 Task 1.2.5 更新导出 | 02-factory |
| L3 | 🟢 | provider 大小写归一化 | `register()` 和 `get()` 中统一使用 `.lower()` | 02-factory |
| L4 | 🟢 | Lock 无超时 | 添加 `LOCK_TIMEOUT = 10.0`，使用 `asyncio.wait_for()` | 02-factory |
| L5 | 🟢 | model_dump fallback | `event_bus.py` 已处理，文档说明 | 02-factory |

---

**上一阶段：** [00-overview.md](./00-overview.md)  
**下一阶段：** [Phase 2A](./02-phase-2a-rag-workflow.md)

**子文档索引:**
- [01: 配置层改造](./01-phase-1-01-config-layer.md) - Task 1.1
- [02: 工厂类重构](./01-phase-1-02-factory-refactor.md) - Task 1.2
- [03: 热更新机制](./01-phase-1-03-hot-reload.md) - Task 1.3
- [04: 调用点改造](./01-phase-1-04-call-sites.md) - Task 1.4
- [05: 依赖与测试](./01-phase-1-05-dependencies.md) - Task 1.5
