# 项目兼容历史版本代码完整影响分析报告

> **生成日期:** 2026-04-16
> **分析范围:** 全项目代码库（后端 + 前端）
> **分析目标:** 识别所有兼容历史版本、降级、回滚、向后兼容的代码

---

## 📊 统计总览

| 类别 | 文件数 | 代码行数（约） | 删除风险 | 建议操作 |
|------|--------|----------------|----------|----------|
| 1. RAG 回滚开关 | 5 | ~50 | **低** | ✅ 可安全删除 |
| 2. LLM 工厂兼容层 | 4 | ~150 | **高** | ⚠️ 需评估迁移状态 |
| 3. Prompt 降级文件 | 2 | ~330 | **中** | ⚠️ 需确认 PromptManager 稳定 |
| 4. RAG 测试旧接口 | 1 | ~30 | **低** | ✅ 可安全删除 |
| 5. 检索降级策略 | 9 | ~100 | **高** | ❌ 不应删除（运行时容错） |
| 6. 配置版本回滚 | 4 | ~100 | **高** | ❌ 不应删除（系统功能） |
| 7. 其他降级机制 | 5 | ~50 | **中** | ⚠️ 视情况保留 |
| **合计** | **30** | **~810** | - | - |

---

## 类别 1：RAG 搜索优化回滚开关

> **风险等级：低** — 这些是 Phase A/B/C/D 实施时为平滑过渡保留的回滚开关，现已全部验收通过，可安全删除。

### 1.1 固定权重回滚

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/core/hybrid_retrieval.py` |
| **行号** | 149-155 |
| **代码** | `get_dynamic_weights()` 中 `if strategy == "fixed"` 分支 |
| **说明** | 当 `strategy="fixed"` 时绕过 QueryAnalyzer，返回旧版固定权重 `settings.rag_hybrid_bm25_weight` |
| **注释** | `# 回滚开关：固定权重模式` |

### 1.2 权重策略配置项

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/config/modules/rag/retrieval.py` |
| **行号** | 82-86 |
| **代码** | `rag_weight_strategy: str = Field(default="dynamic")` |
| **说明** | 支持 `"dynamic"` 或 `"fixed"` 两种策略，`"fixed"` 为回滚路径 |

### 1.3 权重策略传递

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/service/retrieval_service.py` |
| **行号** | 428-434 |
| **代码** | `HybridRetrievalMerger.get_dynamic_weights(..., strategy=settings.rag_weight_strategy)` |
| **说明** | 调用动态权重时传入回滚开关参数 |

### 1.4 固定权重回滚测试

| 项目 | 详情 |
|------|------|
| **文件** | `backend/tests/test_weight_decision.py` |
| **行号** | 48-56 |
| **代码** | `test_fixed_weight_fallback()` 测试函数 |
| **说明** | 显式测试固定权重回滚路径 |

### 1.5 DynamicAgeFilter 兼容类

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/core/age_filter.py` |
| **行号** | 162-271（整个类，110 行） |
| **代码** | `class DynamicAgeFilter` |
| **说明** | 旧版动态年龄过滤器，按发展阶段（婴儿/幼儿/学龄前/学龄期）调整容忍度。已被新版 `AgeFilter`（严格/宽松模式）替代 |
| **注释** | `"""动态年龄过滤器（保留向后兼容）"""` |

### 1.6 旧版年龄过滤配置项

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/config/modules/rag/retrieval.py` |
| **行号** | 195-204 |
| **代码** | `rag_age_filter_strictness`, `rag_age_filter_tolerance` |
| **说明** | 旧版年龄过滤配置项，描述中标注"向后兼容" |

### 1.7 分数分离向后兼容测试

| 项目 | 详情 |
|------|------|
| **文件** | `backend/tests/test_score_separation.py` |
| **行号** | 165-182 |
| **代码** | `test_backward_compatibility()` 测试函数 |
| **说明** | 验证旧版 API 响应（无 `age_fit_score` 字段）不会导致前端崩溃 |

### 1.8 A/B 测试变体选择

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/service/retrieval_service.py` |
| **行号** | 173-179, 417-426 |
| **代码** | `retrieval_variant` 选择逻辑（`control`/`variant1`/`variant2`） |
| **说明** | A/B 测试框架选择不同权重策略。**若 A/B 测试仍在运行则不能删除** |

---

## 类别 2：LLM 工厂兼容层

> **风险等级：高** — 这些代码提供旧的同步类方法接口，绕过新的异步 DI 工厂。删除前需确认所有调用方已迁移。

### 2.1 LLMServiceFactoryCompat 兼容类

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/core/llm/factory.py` |
| **行号** | 387-501（115 行） |
| **代码** | `LLMServiceFactoryCompat` 类 + `_legacy_factory` 全局变量 + `_get_legacy_factory()` 函数 |
| **说明** | 提供旧的同步 `create()` 类方法接口，绕过新的异步 DI 工厂。内部直接使用 `ChatTongyi`/`DashScope` 实例化 |
| **注释** | `# ===== 向后兼容：保留旧的类方法接口 =====` |

### 2.2 RetrievalService 使用兼容层

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/service/retrieval_service.py` |
| **行号** | 23-26（导入）, 859-865（查询重写）, 985-991（同义词扩展） |
| **代码** | `from src.core.llm.factory import LLMServiceFactoryCompat` + `LLMServiceFactoryCompat.create(...)` |
| **说明** | 查询重写和同义词扩展方法中使用兼容层创建 LLM 实例 |
| **注释** | `# 使用工厂创建 LLM 实例（使用兼容层保持向后兼容）` |

### 2.3 LLM 旧配置字段

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/config/modules/models/llm.py` |
| **行号** | 1-8（模块说明）, 46-61（API Key 字段）, 97-137（旧字符串字段）, 140-180（`llm_scene_configs` 属性） |
| **代码** | `model_report_generation`, `model_assessment`, `model_validation`, `model_query_rewrite`, `model_metadata_extraction`, `model_vl_parsing`, `model_query_classification`, `ml_scoring_qwen_model` |
| **说明** | 保留旧的字符串字段从 `.env` 读取模型名称，通过 `llm_scene_configs` 属性自动构建新格式 `LLMSceneConfig` 对象 |
| **注释** | `"""LLM 多提供商统一配置（向后兼容）"""`, `# ===== 保留：向后兼容的 API Key 字段 =====`, `# ===== 保留：旧的字符串字段（向后兼容）=====` |

### 2.4 llm_models 兼容属性

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/config/__init__.py` |
| **行号** | 374-402 |
| **代码** | `llm_models` 属性 |
| **说明** | 提供旧版 dict-based 模型名称访问方式（`settings.llm_models["query_rewrite"]`） |
| **注释** | `"""获取各场景的模型名称（向后兼容）"""` |

---

## 类别 3：Prompt 降级文件

> **风险等级：中** — 当 PromptManager（数据库驱动的 Prompt 管理）不可用时的降级备用。删除前需确认 PromptManager 已完全稳定且无异常场景。

### 3.1 prompts_fallback.py

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/core/prompts_fallback.py` |
| **行号** | 全部（322 行） |
| **代码** | 硬编码的 Prompt 副本，包括：`RAG_QUERY_TEMPLATE`, `QUERY_REWRITE_PROMPT`, `SYNONYM_EXPANSION_PROMPT`, 元数据提取 Prompt, 测试用例生成 Prompt, 系统 Prompt 等 |
| **说明** | 仅作为 PromptManager 不可用时的降级备用。提示词的唯一真实来源是 MySQL 数据库（`prompt_versions` 表） |
| **注释** | `"""本文件仅作为 PromptManager 不可用时的降级备用，不作为主要维护目标"""` |

### 3.2 rag_test_manager 导入 fallback Prompt

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/service/rag_test_manager.py` |
| **行号** | 39 |
| **代码** | `from src.core.prompts_fallback import TEST_CASE_DRAFT_GENERATION_PROMPT` |
| **说明** | 从 prompts_fallback 导入测试用例生成 Prompt |

---

## 类别 4：RAG 测试旧接口

> **风险等级：低** — 已迁移到新接口的旧版 API 端点，若前端已完全迁移则可安全删除。

### 4.1 /run/legacy 端点

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/controller/rag_test_controller.py` |
| **行号** | 284-310（27 行） |
| **代码** | `RunTestsRequestLegacy` Pydantic 模型 + `@router.post("/run/legacy")` 端点 + `run_tests_legacy()` 处理器 |
| **说明** | 旧版测试运行 API 端点，已迁移到文件开头的统一入口 |
| **注释** | `# 保留旧接口向后兼容`, `"""运行测试用例（旧接口，向后兼容）"""` |

---

## 类别 5：检索降级策略（运行时容错）

> **风险等级：高** — 这些是**运行时容错设计**，不是历史版本兼容代码。当外部服务（BM25、DashScope、Redis 等）不可用时提供降级路径，**不应删除**。

### 5.1 Vector/BM25 初始化降级

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/service/retrieval_service.py` |
| **行号** | 104-137 |
| **代码** | Vector retriever try/except fallback to `None`；BM25 retriever 检查 `docstore` 可用性，空时降级为纯向量检索 |
| **说明** | BM25 不可用时降级为纯向量检索 |
| **类型** | **运行时容错**，非版本兼容 |

### 5.2 search_content 降级

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/service/retrieval_service.py` |
| **行号** | 327-334, 453-460 |
| **代码** | `use_hybrid=False` 时执行单一向量检索 |
| **说明** | 混合检索不可用时降级为单一向量检索 |
| **类型** | **运行时容错**，非版本兼容 |

### 5.3 查询重写本地降级

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/service/retrieval_service.py` |
| **行号** | 849-850, 893-909 |
| **代码** | `if not self.dashscope_available: return self._local_rewrite_query(...)` + `_local_rewrite_query()` 方法 |
| **说明** | DashScope API 不可用时使用规则-based 本地重写（按年龄添加关键词） |
| **类型** | **运行时容错**，非版本兼容 |

### 5.4 同义词扩展本地降级

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/service/retrieval_service.py` |
| **行号** | 949-950, 1053-1073 |
| **代码** | `if not self.dashscope_available: return self._local_expand_synonyms(...)` + 多处 `return self._local_expand_synonyms(query)` |
| **说明** | LLM 失败或验证未通过时使用本地词典扩展 |
| **类型** | **运行时容错**，非版本兼容 |

### 5.5 同义词词典三级降级加载

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/core/rag/local_synonym_expander.py` |
| **行号** | 98-125 |
| **代码** | `_load_synonyms()` 方法 |
| **说明** | 数据库 → 本地 JSON → 空词典 |
| **类型** | **配置降级加载**，非版本兼容 |

### 5.6 专业术语三级降级加载

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/core/rag/query_analyzer.py` |
| **行号** | 51-101 |
| **代码** | `_load_terminology()` 方法 |
| **说明** | 数据库 → 本地 JSON → 空集合 |
| **类型** | **配置降级加载**，非版本兼容 |

### 5.7 同义词验证规则三级降级加载

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/core/rag/synonym_validator.py` |
| **行号** | 157 |
| **代码** | `_load_validation_rules()` 方法 |
| **说明** | 数据库 → 本地 JSON → 空词典 |
| **类型** | **配置降级加载**，非版本兼容 |

### 5.8 重排序降级

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/core/reranker.py` |
| **行号** | 173-176, 194-195 |
| **代码** | `except` 返回 `nodes[:self.final_k]`；模型为 `None` 时返回 `nodes[:self.final_k]` |
| **说明** | Cross-Encoder 模型不可用或异常时返回原始排序 |
| **类型** | **运行时容错**，非版本兼容 |

### 5.9 边界场景三级降级策略

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/core/rag/boundary_handler.py` |
| **行号** | 156-192 |
| **代码** | `apply_fallback_strategy()` 方法 |
| **说明** | 降级 1：放宽年龄过滤；降级 2：降低分数阈值；降级 3：返回通用内容 |
| **类型** | **运行时容错**，非版本兼容 |

---

## 类别 6：配置版本回滚系统

> **风险等级：高** — 这是**系统功能**，不是历史版本兼容代码。提供配置版本管理和回滚能力，**不应删除**。

### 6.1 ConfigManager rollback_to_version

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/config/core/manager.py` |
| **行号** | 258-322 |
| **代码** | `rollback_to_version()` 方法 |
| **说明** | 完整的配置版本回滚机制，创建新版本快照并记录审计日志 |
| **类型** | **系统功能**，非版本兼容 |

### 6.2 ConfigController 回滚端点

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/controller/config_controller.py` |
| **行号** | 31-35, 201-223 |
| **代码** | `ConfigRollbackRequest` Pydantic 模型 + `POST /api/v1/config/rollback` 端点 |
| **说明** | 配置回滚 API 端点 |
| **类型** | **系统功能**，非版本兼容 |

### 6.3 前端配置回滚状态

| 项目 | 详情 |
|------|------|
| **文件** | `frontend/src/store/configStore.ts` |
| **行号** | 65, 245-251 |
| **代码** | `rollbackToVersion()` action |
| **说明** | 前端 Zustand store 中的配置回滚状态管理 |
| **类型** | **系统功能**，非版本兼容 |

### 6.4 前端配置回滚 API 客户端

| 项目 | 详情 |
|------|------|
| **文件** | `frontend/src/api/config/index.ts` |
| **行号** | 30-34 |
| **代码** | `rollbackToVersion()` API 客户端方法 |
| **说明** | 调用 `/api/v1/config/rollback` |
| **类型** | **系统功能**，非版本兼容 |

---

## 类别 7：其他降级机制

> **风险等级：中** — 这些是运行时或配置降级机制，部分可视为容错设计，部分可视为历史兼容。

### 7.1 reload_settings 降级

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/config/__init__.py` |
| **行号** | 457-469 |
| **代码** | `reload_settings()` 函数 |
| **说明** | 重载失败时返回原有配置实例 |
| **注释** | `重载失败时返回原有配置实例` |
| **类型** | **运行时容错** |

### 7.2 分层内容本地降级开关

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/config/__init__.py` |
| **行号** | 427 |
| **代码** | `"enable_local_fallback": self.rag_layered_content_enable_local_fallback` |
| **说明** | 分层内容本地降级开关 |
| **类型** | **配置开关** |

### 7.3 语义分块降级

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/core/metadata_processor.py` |
| **行号** | 610-629 |
| **代码** | 语义分块失败时 fallback 到 `SentenceSplitter` |
| **说明** | 语义分块 token 过多时使用规则-based 分块 |
| **类型** | **运行时容错** |

### 7.4 LLM 健康诊断降级

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/service/config_health_service.py` |
| **行号** | 58-64 |
| **代码** | LLM 诊断失败时使用本地规则评分 |
| **说明** | LLM 不可用时使用本地规则评分 |
| **类型** | **运行时容错** |

### 7.5 Redis 缓存降级

| 项目 | 详情 |
|------|------|
| **文件** | `backend/src/service/cache_service.py` |
| **行号** | 253 |
| **代码** | Redis 读取失败时降级 |
| **说明** | Redis 不可用时降级处理 |
| **类型** | **运行时容错** |

---

## 📋 删除建议汇总

### ✅ 可安全删除（类别 1 + 4）

| 文件 | 行号 | 说明 |
|------|------|------|
| `backend/src/core/hybrid_retrieval.py` | 149-155 | fixed weight 回滚分支 |
| `backend/src/config/modules/rag/retrieval.py` | 82-86 | `rag_weight_strategy` 配置项 |
| `backend/src/service/retrieval_service.py` | 428-434 | strategy 参数传递 |
| `backend/tests/test_weight_decision.py` | 48-56 | `test_fixed_weight_fallback()` |
| `backend/src/core/age_filter.py` | 162-271 | `DynamicAgeFilter` 整个类 |
| `backend/src/config/modules/rag/retrieval.py` | 195-204 | 旧版年龄过滤配置项 |
| `backend/tests/test_score_separation.py` | 165-182 | `test_backward_compatibility()` |
| `backend/src/controller/rag_test_controller.py` | 284-310 | `/run/legacy` 端点 |

**预估影响：** ~200 行代码，5 个文件，风险极低。

### ⚠️ 需评估后删除（类别 2 + 3）

| 文件 | 行号 | 说明 | 前置条件 |
|------|------|------|----------|
| `backend/src/core/llm/factory.py` | 387-501 | `LLMServiceFactoryCompat` | 确认所有调用方已迁移到 DI 工厂 |
| `backend/src/service/retrieval_service.py` | 23-26, 859-865, 985-991 | 使用兼容层创建 LLM | 同上 |
| `backend/src/config/modules/models/llm.py` | 1-8, 46-61, 97-180 | 旧配置字段 + `llm_scene_configs` | 确认无代码依赖旧字段 |
| `backend/src/config/__init__.py` | 374-402 | `llm_models` 属性 | 确认无代码使用 `settings.llm_models["xxx"]` |
| `backend/src/core/prompts_fallback.py` | 全部（322 行） | Prompt 降级文件 | 确认 PromptManager 完全稳定 |
| `backend/src/service/rag_test_manager.py` | 39 | 导入 fallback Prompt | 确认有替代来源 |

**预估影响：** ~550 行代码，6 个文件，风险中高。

### ❌ 不应删除（类别 5 + 6 + 7）

这些是**运行时容错设计**或**系统功能**，不是历史版本兼容代码：

- 类别 5：检索降级策略（9 处）— 外部服务不可用时的容错路径
- 类别 6：配置版本回滚（4 处）— 系统配置管理功能
- 类别 7：其他降级机制（5 处）— 运行时容错

**删除这些会导致系统在异常场景下直接崩溃。**

---

## 🔍 删除前检查清单

### 类别 1 + 4 删除前

- [ ] 确认 A/B 测试已关闭或迁移（检查 `retrieval_variant` 逻辑）
- [ ] 确认前端未调用 `/run/legacy` 端点
- [ ] 确认无外部系统依赖旧版 API 响应格式

### 类别 2 删除前

- [ ] 搜索全项目 `LLMServiceFactoryCompat` 的所有引用
- [ ] 确认所有引用已迁移到新的 DI 工厂（`LLMServiceFactory`）
- [ ] 确认 `.env` 中旧字段（`MODEL_REPORT_GENERATION` 等）不再使用
- [ ] 确认 `settings.llm_models["xxx"]` 模式已替换

### 类别 3 删除前

- [ ] 确认 PromptManager 在所有启动场景下均可用
- [ ] 确认无代码直接导入 `prompts_fallback`
- [ ] 考虑保留文件但添加 `@deprecated` 标记，观察一段时间后再删除

---

## 📝 备注

1. **降级 vs 兼容**：本报告严格区分"历史版本兼容代码"和"运行时降级/容错机制"。前者是为旧版逻辑保留的回滚路径，应删除；后者是系统在异常场景下的自我保护，应保留。

2. **A/B 测试特殊处理**：类别 1.8 的 A/B 测试变体选择逻辑若仍在运行，需先关闭 A/B 测试或迁移到新的实验框架后再删除。

3. **LLM 兼容层迁移成本**：类别 2 的 `LLMServiceFactoryCompat` 被 `retrieval_service.py` 中的查询重写和同义词扩展方法使用。迁移需要将这两处改为使用 DI 注入的 LLM 实例，并确保异步上下文正确处理。

4. **Prompt 降级文件**：`prompts_fallback.py` 包含 322 行硬编码 Prompt，若 PromptManager 稳定运行，此文件可安全删除。但建议在删除前添加监控，确认无 fallback 触发日志。

---

**报告生成完成。** 请确认要删除的类别范围，我将据此制定详细的实施计划。
