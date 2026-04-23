# 提示词表统一设计文档

**日期**: 2026-04-19  
**状态**: 待实施  
**作者**: AI Assistant

---

## 1. 问题描述

当前系统存在两套独立的提示词存储系统，数据不互通：

| 系统 | 表名 | 用途 | 使用者 |
|------|------|------|--------|
| **旧版** | `prompt_versions` | 业务代码运行时读取提示词内容 | Agent Nodes、RAG QueryRewriter、MetadataExtractor 等 15+ 处 |
| **新版** | `rag_eval_prompt_metadata` + `rag_eval_prompt_versions` | 提示词管理页面 CRUD | PromptManagementController、前端 PromptListPage |

**核心矛盾**：业务代码通过 `prompt_manager.get_prompt()` 写入旧表，但前端管理界面查询新表，导致管理页面搜索不到任何内容。

---

## 2. 设计方案

### 2.1 目标

- **一套表服务所有场景**：业务运行时 + 管理界面统一数据源
- **去掉 `rag_eval_` 前缀**：体现提示词作为全局基础设施的定位
- **零数据迁移**：项目未上线，直接删除旧表旧代码
- **业务代码零改动**：`prompt_manager.get_prompt()` 接口保持不变

### 2.2 新表结构

#### `prompt_metadata`（提示词元数据表）

一个 prompt_key 一条记录，作为提示词的"身份证"。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键 UUID |
| prompt_key | VARCHAR(255) | 唯一标识，UNIQUE |
| name_zh | VARCHAR(255) | 中文名称 |
| purpose | TEXT | 用途说明 |
| category | ENUM | 分类（rag_retrieval, rag_generation, assessment, scoring, reporting, test_case_generation） |
| subcategory | VARCHAR(64) | 子分类（可选） |
| variables_schema | JSON | 变量声明 schema（可选） |
| code_references | JSON | 代码引用位置（可选） |
| config_dependencies | JSON | 配置参数依赖（可选） |
| is_active | BOOLEAN | 是否启用 |
| is_system | BOOLEAN | 是否系统内置 |
| created_by | VARCHAR(64) | 创建人 |
| updated_by | VARCHAR(64) | 更新人 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

#### `prompt_versions`（提示词版本表）

一个 prompt_key 多条记录，作为提示词的"版本历史"。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键 UUID |
| prompt_key | VARCHAR(255) | 关联 prompt_metadata.prompt_key |
| version_label | VARCHAR(36) | 展示用版本号，如 v1, v2 |
| version_number | INT | 自增序号，用于排序 |
| content | TEXT | 提示词完整内容 |
| content_hash | VARCHAR(64) | 内容 SHA256 哈希，用于去重 |
| variables_extracted | JSON | 自动提取的变量列表 |
| change_impact | JSON | 变更影响分析 |
| change_summary | TEXT | 变更摘要 |
| created_by | VARCHAR(36) | 创建人 |
| created_at | DATETIME | 创建时间 |
| tags | JSON | 标签列表（从旧表保留） |
| fallback | TEXT | 降级备用内容（从旧表保留） |

### 2.3 文件变更清单

#### 删除的文件

| 文件 | 原因 |
|------|------|
| `backend/src/models/prompt.py` | 旧模型（PromptVersion、PromptABTest）废弃 |
| `backend/src/controller/prompt_controller.py` | 旧版提示词 API 控制器，功能被 prompt_management_controller 覆盖 |
| `backend/src/repository/prompt_repository.py` | 旧 Repository，将被新实现替代 |
| `backend/scripts/migrate_json_to_mysql.py` | 旧迁移脚本，针对旧表结构 |

#### 移动/重命名的文件

| 原文件 | 新文件 | 变更 |
|--------|--------|------|
| `backend/src/models/rag_eval/prompt_metadata.py` | `backend/src/models/prompt_metadata.py` | 类名 RagEvalPromptMetadata → PromptMetadata，表名 rag_eval_prompt_metadata → prompt_metadata |
| `backend/src/models/rag_eval/prompt_version.py` | `backend/src/models/prompt_version.py` | 类名 RagEvalPromptVersion → PromptVersion，表名 rag_eval_prompt_versions → prompt_versions，合并 content_hash/tags/fallback 字段 |

#### 修改的文件

| 文件 | 变更内容 |
|------|----------|
| `backend/src/models/__init__.py` | 更新 import：删除旧模型，添加新模型 |
| `backend/src/models/rag_eval/__init__.py` | 删除 RagEvalPromptMetadata 和 RagEvalPromptVersion 导出 |
| `backend/src/core/prompt_impl/prompt_storage.py` | 改用新模型 PromptMetadata + PromptVersion，更新字段映射 |
| `backend/src/controller/prompt_management_controller.py` | 改用新模型 import |
| `backend/src/core/prompt_impl/initializer.py` | 增强逻辑：同时写入 prompt_metadata 和 prompt_versions |
| `backend/src/service/config_change_set_service.py` | 更新 import RagEvalPromptVersion → PromptVersion |
| `backend/src/service/config_rollback_service.py` | 更新 import RagEvalPromptVersion → PromptVersion |
| `backend/src/models/rag_eval/prompt_suggestion.py` | 更新 relationship 引用 |
| `backend/src/models/rag_eval/config_change_set_prompt.py` | 更新 relationship 引用 |
| `backend/src/schemas/prompt.py` | 无需改动（Pydantic 模型，不依赖 ORM） |
| `backend/src/utils/exceptions.py` | 无需改动（异常类独立） |

#### 无需改动的文件

业务代码通过 `prompt_manager.get_prompt()` 接口读取提示词，该接口由 `PromptStorage` 封装，内部适配新模型后对外接口不变：

- `backend/src/core/nodes/validation.py`
- `backend/src/core/nodes/assessment.py`
- `backend/src/core/nodes/retrieval.py`
- `backend/src/core/nodes/reporting.py`
- `backend/src/service/retrieval/query_rewriter.py`
- `backend/src/core/metadata_extractor.py`
- `backend/src/service/rag_test_case_service.py`
- `backend/src/service/rag_test/draft_service.py`
- `backend/src/service/config_health_service.py`
- `backend/src/controller/prompt_management_controller.py`（test_prompt 端点）
- 所有测试文件

---

## 3. 实施步骤

### Step 1: 创建新模型文件

1. 创建 `backend/src/models/prompt_metadata.py`，从 `rag_eval/prompt_metadata.py` 复制并重命名类、表名
2. 创建 `backend/src/models/prompt_version.py`，从 `rag_eval/prompt_version.py` 复制，合并旧表的 content_hash/tags/fallback 字段

### Step 2: 更新模型导出

1. 更新 `backend/src/models/__init__.py`，导出 PromptMetadata、PromptVersion
2. 更新 `backend/src/models/rag_eval/__init__.py`，删除相关导出

### Step 3: 更新 PromptStorage

修改 `backend/src/core/prompt_impl/prompt_storage.py`：
- import 改为新模型
- 所有 ORM 操作使用新模型字段
- 适配 content_hash、tags、fallback 字段

### Step 4: 更新 Controller

修改 `backend/src/controller/prompt_management_controller.py`：
- import 改为新模型

### Step 5: 更新初始化器

修改 `backend/src/core/prompt_impl/initializer.py`：
- 创建提示词时同时写入 prompt_metadata 和 prompt_versions
- 根据 prompt_key 映射到正确的 category 和 name_zh

### Step 6: 更新依赖引用

批量更新所有引用旧模型的文件：
- `config_change_set_service.py`
- `config_rollback_service.py`
- `prompt_suggestion.py`
- `config_change_set_prompt.py`

### Step 7: 清理旧代码

删除以下文件：
- `backend/src/models/prompt.py`
- `backend/src/controller/prompt_controller.py`
- `backend/src/repository/prompt_repository.py`
- `backend/scripts/migrate_json_to_mysql.py`

更新相关 import 和注册逻辑。

### Step 8: 更新 DDL

更新 `.ai/full_init_script_mysql57.sql`，删除旧表 DDL，添加新表 DDL。

---

## 4. 验收标准

1. ✅ 后端启动无报错
2. ✅ `init_default_prompts()` 成功写入 11 个默认提示词到 prompt_metadata 和 prompt_versions
3. ✅ `GET /api/v1/rag/prompts` 返回 11 条提示词数据
4. ✅ 前端提示词管理页面能正常显示、搜索、筛选
5. ✅ 业务代码（Agent Nodes、RAG 等）能正常通过 `prompt_manager.get_prompt()` 读取提示词
6. ✅ 提示词更新、版本对比、影响分析等管理功能正常
7. ✅ 前端类型检查通过（`npm run typecheck`）
8. ✅ 前端测试通过（`npm run test`）

---

## 5. 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 新表字段与旧代码不兼容 | PromptStorage 内部适配，对外接口不变 |
| 初始化器写入失败 | 保留 fallback 机制，数据库不可用时从 Python 常量读取 |
| 枚举值不匹配 | 初始化器中硬编码 prompt_key → category 映射 |

---

## 6. 附录：prompt_key → category 映射表

| prompt_key | category | name_zh | purpose |
|------------|----------|---------|---------|
| rag_query_rewrite | rag_retrieval | 查询重写 | 优化用户查询以提高检索准确率 |
| synonym_expansion | rag_retrieval | 同义词扩展 | 扩展查询的相关术语 |
| rag_query_template | rag_retrieval | RAG 查询模板 | RAG 查询模板 |
| metadata_extraction | rag_generation | 元数据提取 | 从文档块中提取结构化元数据 |
| test_case_generation | test_case_generation | 测试用例生成 | 从文档中自动生成 RAG 测试用例 |
| validation | assessment | 数据校验 | 校验用户输入数据的完整性和合理性 |
| intensity_inference | assessment | 运动强度推断 | 根据运动名称和年龄推断运动强度 |
| category_inference | assessment | 运动类别推断 | 根据运动名称和年龄推断运动类别 |
| child_assessment | assessment | 儿童发展评估 | 评估儿童的发展状态 |
| scoring | scoring | 评分 | 对训练计划进行多维度打分 |
| report_generation | reporting | 报告生成 | 生成最终的儿童发展评估报告 |
