# 系统综合重构与能力提升设计方案

**日期**: 2026-04-10
**状态**: 已整合
**描述**: 本文档深度整合了 2026-04-09 至 2026-04-10 期间的配置系统、提示词管理、RAG 查询流水线及测试系统设计方案。旨在解决原有代码分散、耦合度高、扩展性差的问题，为系统提供统一、灵活、可监控的基础架构。

---

## 1. 方案概述

本次综合重构涵盖系统的四个核心支柱：
1. **配置系统层级重构与热更新**：彻底废除近700行的单体 `settings.py`，建立 `core/`、`modules/`、`rules/` 三层架构，实现细粒度的按域配置，并引入基于 `watchdog` 和读写锁的无感热重载机制。
2. **提示词配置管理系统**：消除业务代码中 20+ 处散落的提示词硬编码，实现基于 JSON 的持久化存储、统一加载接口（`PromptLoader`）、版本回滚及独立的独立前端工作台。
3. **RAG 查询流水线声明式编排**：废弃硬编码的检索逻辑，采用基于 YAML 的声明式配置。通过 `PipelineOrchestrator` 解耦缓存、重写、混合检索、重排序等组件。对简单查询自动跳过 LLM 增强，预计降低 50% 延迟及 60% Token 消耗。
4. **RAG 评估与测试系统增强**：全面升级 RAG 测试页面。支持大规模 JSON 测试集并发导入（含冲突检测），并新增书籍上传异步解析功能，结合 12 种考核维度和多重模板引擎实现高度多样化的测试用例自动生成（LLM驱动）。同时实现支持并发控制（`asyncio.Semaphore`）的批量执行引擎。

---

## 2. 配置系统层级重构与热更新

### 2.1 目录架构设计
为解决配置项杂乱无章的问题，后端目录与前端配置树（`/system-config`）严格映射：

```text
backend/src/config/
├── core/                          # 配置基础设施
│   ├── manager.py                 # 配置管理器（版本控制/快照）
│   ├── repository.py              # 配置存储（JSON 文件读写）
│   └── events.py                  # 配置变更事件
├── modules/                       # 领域配置模块
│   ├── app.py                     # 应用基础（名称/端口/调试等）
│   ├── logging.py                 # 日志设置
│   ├── paths.py                   # 路径（数据/存储目录）
│   ├── models/                    # AI 模型配置 (llm.py, embedding.py, ml_scoring.py)
│   └── rag/                       # RAG 知识库配置 (core.py, retrieval.py, chunking.py, vector_store.py, pageindex.py, pipeline.py)
├── rules/                         # 业务规则配置 (rules.py, rules.json)
└── __init__.py                    # 聚合入口（导出唯一的 Settings 单例）
```

### 2.2 核心重构策略
- **`rag_settings.py` 拆分**：原包含 47 个字段的文件被精准拆分。例如 `rag_hybrid_bm25_weight` 归入 `retrieval.py`；`rag_chunk_size` 归入 `chunking.py`。
- **配置聚合 (`__init__.py`)**：通过多重继承合并所有子配置类：
  ```python
  class Settings(AppSettings, LogSettings, PathSettings, ModelSettings, RagRetrievalSettings, ...):
      pass
  settings = Settings()
  ```
- **配置元数据 (`category`)**：为支持前端自动渲染，`get_all_config_metadata` 和 `ConfigController` 返回值中新增 `category` 字段（如 `rag.retrieval`, `models.llm`）。

### 2.3 热更新机制
- **文件监控**：使用 `watchdog` 监听 `.env.dev` 和 `.py`, `.yaml` 文件变更。
- **原子性重载**：在 `reload_settings()` 中使用 `threading.RLock` 保证并发安全。若新配置 Pydantic 校验失败，则安全回退至旧版本。
- **缓存同步**：重载成功后，调用 `config_manager.sync_cache_from_settings(new_settings)` 更新运行时缓存，并通过 EventBus 派发 `ConfigChangedEvent`。

### 2.4 前端独立配置页
- 废弃 RAG 评估页面的侧边栏配置面板（`ConfigTuningPanel`）。
- 新增全局 `/system-config` 路由，基于 `CATEGORY_TREE` 渲染多级分类树和动态表单，实现全局配置的一站式管理。

---

## 3. 提示词配置管理系统

### 3.1 核心架构
消除 `prompts.py` 中的静态变量，建立动态系统：
- **存储层 (`PromptRepository`)**：每个提示词存为独立 JSON 文件（如 `ASSESSMENT_SYSTEM_PROMPT.json`）。文件内联 `versions` 字段保存历史版本快照。
- **业务层 (`PromptManager`)**：单例模式，应用启动时加载所有提示词到内存缓存。提供增删改查、版本升级（自动 `v1.0.0` -> `v1.0.1`）及回滚能力。
- **加载层 (`PromptLoader`)**：统一供业务端调用的接口 `prompt_loader.load("KEY", **variables)`。内置正则表达式解析 `{{variable}}`，若内存未命中则自动降级（Fallback）至 `prompts.py`。

### 3.2 数据模型 (JSON Schema)
```json
{
  "key": "ASSESSMENT_SYSTEM_PROMPT",
  "name": "评估系统提示词",
  "category": "assessment",
  "content": "你是一个专业的儿童发展评估专家...",
  "variables": ["child_profile", "assessment_data"],
  "status": "active",
  "current_version": "v1.0.1",
  "versions": {
    "v1.0.1": {
      "content": "...",
      "change_log": "优化语气",
      "created_at": "2026-04-10T10:00:00Z"
    }
  }
}
```

### 3.3 前端工作台 (`/prompts`)
- **左侧列表**：支持按分类（assessment, scoring, retrieval 等）和状态筛选提示词。
- **右侧面板 (Tabs)**：
  1. **基础信息**：配置变量列表、分类。
  2. **提示词编辑器**：支持代码高亮，自动检测并警告文本中存在但未在 variables 中声明的 `{{未知变量}}`。
  3. **实时预览**：填入测试变量值，实时渲染最终文本并预估 Token 消耗。
  4. **版本历史**：展示变更日志，支持两版本 Diff 差异比对及一键回滚。

---

## 4. RAG 查询流水线编排

### 4.1 声明式 YAML 编排
将硬编码的 `retrieve_knowledge` 方法重构为基于 `query_pipeline.yaml` 的可配置流水线，支持 `${ENV_VAR:default}` 注入：

```yaml
pipelines:
  simple:
    - name: cache_check
    - name: hybrid_retrieval
      params: { bm25_top_k: 10, vector_top_k: 10 }
    - name: rerank
    - name: dedup
    - name: convert_to_knowledge
  complex:
    - name: cache_check
    - name: query_rewrite        # LLM 调用
    - name: synonym_expand       # LLM 调用
    - name: age_filter
    - name: hybrid_retrieval
    - name: rerank
    # ...
global:
  step_timeout: 30
  failure_strategy: "fallback_to_default"
```

### 4.2 PipelineOrchestrator 编排器
- **组件抽象**：实现 `PipelineStep` 协议。所有步骤（如 `QueryRewriteStep`, `HybridRetrievalStep`）注册到 DI 容器，按需实例化。
- **上下文传递**：使用 `PipelineContext` 记录 `query`, `query_type`, `rewritten_query`, `synonyms`, `age_filter` 以及执行日志（`execution_log`）。
- **容错与监控**：
  - 步骤超时或抛错时，根据 `fallback_to_default` 策略，自动切回默认流水线，并跳过已成功执行的步骤（基于 `context.executed_steps`）。
  - 集成 Prometheus 指标：`rag_pipeline_step_duration_seconds`, `rag_pipeline_step_total`。

### 4.3 已知 Bug 修复与优化
- **同义词 Bug**：修复 `synonym_expand` JSON 解析失败降级时引用未定义变量 `synonyms` 的错误。
- **句柄泄漏 Bug**：修复 `pageindex_wrapper.py` 中 `open()` 创建文件对象直接传给 `aiohttp` 导致句柄未关闭的问题，改用 `try...finally: file_handle.close()`。
- **统一过滤**：废弃 `retrieval_service.py` 内部的年龄逻辑，统一调用 `DynamicAgeFilter` 生成 `MetadataFilter` 供混合检索消费。

---

## 5. RAG 评估与测试系统增强

### 5.1 数据模型扩展
- **`TestCase`**：新增 `domain`, `answer_points`, `professional_terms`, `age_requirement`, `source_document_id`, `version` 字段。统一采用 `tc_{nanoid_10}` 作为主键。
- **新增实体**：
  - `SourceDocument`：记录书籍解析后的文本、哈希、结构及 `QualityReport`。
  - `TestCaseDraft`：LLM 生成的草稿状态对象，携带 `evaluation_type` 和 `generation_params`。
  - `TestSet`：测试集集合，包含关联的 `test_case_ids`。

### 5.2 测试用例批量导入
- **JSON 导入**：
  - 前端：`ImportJsonModal` 支持文件上传、解析进度条、基于 Schema 的有效/无效/重复项预览。
  - 后端：`POST /cases/batch` 实施两阶段事务写入。预校验通过后，使用 `filelock` 获取锁，写入 `.tmp` 文件后通过 `os.replace` 原子替换原 JSON，保证并发一致性。

### 5.3 书籍解析与多样化用例生成
- **文档解析 (`DocumentParser`)**：异步调用提取文本，检查文件大小、提取率、相关领域词汇，生成文档质量评估（如 "poor", "excellent"）反馈给用户。
- **大规模多样化生成 (`TestCaseDraftGenerator`)**：
  - 弃用单一 Prompt，引入 **12 种认知维度矩阵**（事实检索、概念对比、干预设计等）和 50+ 个提问角度模板。
  - 结合 `age_range`, `count`, `target_domains` 参数，按权重分配各维度生成数量。
  - 自动去重检查：计算新生成 Query 与历史 Query 的 Difflib 相似度，>0.85 即抛弃重试，单次支持最高 500 条用例的高质量生成。
- **草稿审核**：草稿列表支持人工打回或批量通过。通过后，系统自动剔除中间参数，将 `TestCaseDraft` 转换为正式 `TestCase` 入库。

### 5.4 批量并发执行引擎 (`BatchRunRequest`)
- **执行模式**：支持 `cases` (按指定ID列表)、`test_set` (按测试集)、`filter` (按领域/年龄动态过滤)。
- **并发控制**：在 `RagTestManager.run_batch_tests` 中，使用 `asyncio.Semaphore(concurrency)` 限制并发度（1~10）。单次最大执行上限为 100 条。
- **进度与异常隔离**：
  - 运行状态存储在内存字典 `_running_tasks` 中。单个用例报错仅记录至 `TestRun.errors` 数组，绝不阻断后续用例。
  - 前端轮询 `/runs/{run_id}` 获取 `progress`，展示实时通过/失败卡片及进度条。支持主动下发 `/cancel` 指令强行中断剩余队列。
- **删除与评分同步**：
  - 解决旧版删除测试报告后，全局聚合分数不更新的 Bug。
  - 修改 `DELETE /runs/{run_id}` 接口，删除 JSON 后强制调用 `recalculate_aggregate_scores()` 重新遍历计算所有版本的 Precision, Recall, F1 等数据，并将最新统计树返回给前端重绘图表。

---

## 6. 总结与兼容性保证

本设计方案秉持“**平滑演进、向后兼容**”的原则：
- 配置系统对外依然暴露 `from src.config import settings` 单例，内部调用完全透明。
- 提示词系统若出现故障，具备完善的静态文件降级保护。
- 查询流水线引入 `RAG_PIPELINE_ENABLED` 环境变量控制。若设为 `False`，请求将无缝回落至原长达 600 行的单体检索函数。
- RAG 测试数据扩展采用了 Pydantic 的 `default` / `default_factory` 机制，配合提供的 `migrate_test_cases.py` 脚本，可一键为存量数据补齐字段，绝不破坏历史评估记录。