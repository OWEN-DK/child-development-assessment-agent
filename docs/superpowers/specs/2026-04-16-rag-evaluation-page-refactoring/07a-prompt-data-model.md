# 07a - 提示词数据模型重构

> **本文档包含**: 提示词数据模型重构需求、新增字段定义、代码修改清单、老代码删除清单
>
> **零兼容原则**: 本文档所有变更均为直接修改/直接删除，不包含任何兼容代码、迁移脚本、@deprecated 标记、双版本并行逻辑。

---

## 1. 现有数据模型分析

### 1.1 当前 `PromptVersion` 模型字段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 主键，格式: "{prompt_key}_{version}" |
| prompt_key | string | 提示词唯一标识 |
| version | string | 版本号，如 "1.0.0" |
| content | string | 提示词内容 |
| content_hash | string | 内容 SHA256 哈希 |
| description | string\|None | 版本描述 |
| created_by | string\|None | 创建人 |
| variables | list\|None | 变量列表（JSON） |
| tags | list\|None | 标签（JSON） |
| fallback | string\|None | 降级内容 |
| created_at | datetime | 创建时间 |

### 1.2 存在的问题

| 问题 | 说明 | 影响 |
|------|------|------|
| **无中文名称** | `prompt_key` 为英文（如 `rag_query_rewrite`），用户无法直观理解 | 用户需要猜测提示词用途 |
| **无用途说明** | `description` 是版本级描述，非提示词本身的用途说明 | 用户不知道这个提示词在系统中干什么 |
| **变量声明不完整** | `variables` 仅存储变量名列表，无类型、无默认值、无说明 | 无法生成变量填写表单 |
| **无影响分析元数据** | 缺少代码引用位置、配置参数依赖等信息 | 无法实现影响分析功能 |
| **无使用状态** | 无法判断提示词是否被代码引用 | 用户可能误删正在使用的提示词 |

---

## 2. 重构方案

### 2.1 新增 `PromptMetadata` 模型

**设计决策**: 将提示词元数据与版本数据分离，因为:
- 元数据是提示词级别的（一个 prompt_key 只有一份）
- 版本数据是版本级别的（一个 prompt_key 有多个版本）
- 元数据变更频率低，版本数据变更频率高

**新增字段定义**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | CHAR(36) | 是 | 主键，UUID |
| prompt_key | VARCHAR(255) | 是 | 唯一标识，唯一索引 |
| name_zh | VARCHAR(255) | 是 | 中文名称 |
| purpose | TEXT | 是 | 用途说明 |
| category | VARCHAR(64) | 是 | 分类: rag_retrieval/rag_generation/assessment/scoring/reporting/test_case_generation |
| subcategory | VARCHAR(64) | 否 | 子分类 |
| variables_schema | JSON | 否 | 变量声明 schema（含类型、必填、默认值、说明） |
| code_references | JSON | 否 | 代码引用位置（文件路径、行号、函数名） |
| config_dependencies | JSON | 否 | 配置参数依赖（参数名、分类、说明） |
| is_active | BOOLEAN | 是 | 是否启用 |
| is_system | BOOLEAN | 是 | 是否系统内置（系统内置不可删除） |
| created_by | VARCHAR(64) | 否 | 创建人 |
| updated_by | VARCHAR(64) | 否 | 更新人 |
| created_at | DATETIME | 是 | 创建时间 |
| updated_at | DATETIME | 是 | 更新时间 |

**variables_schema 格式示例**:
```
{
  "query": {"type": "string", "required": true, "description": "用户原始查询"},
  "age": {"type": "number", "required": true, "description": "儿童年龄", "default": 0}
}
```

**code_references 格式示例**:
```
[
  {"file": "src/service/retrieval_service.py", "line": 868, "function": "rewrite_query"}
]
```

**config_dependencies 格式示例**:
```
[
  {"param": "rag_similarity_threshold", "category": "rag.retrieval", "description": "相似度阈值"}
]
```

### 2.2 `PromptVersion` 模型调整

**字段变更**:

| 字段 | 类型 | 变更 | 说明 |
|------|------|------|------|
| id | CHAR(36) | 改为 UUID | 原为 string 格式 "{prompt_key}_{version}" |
| version_label | VARCHAR(64) | 重命名 | 原字段名 `version`，改为 `version_label` 与 ConfigVersion 统一 |
| variables_extracted | JSON | 新增 | 自动提取的变量列表（保存时从 content 中提取） |
| change_impact | JSON | 新增 | 变更影响分析（variables_added/removed/modified、config_dependencies_changed、affected_code_files） |

**保留字段**: prompt_key, content, content_hash, description, created_by, created_at

### 2.3 删除 `PromptABTest` 模型

**删除原因**: A/B 测试功能不在本系统范围内，直接删除。

---

## 3. 初始化数据

### 3.1 系统内置提示词元数据

系统初始化时，必须为所有现有提示词创建元数据记录:

| prompt_key | name_zh | purpose | category |
|-----------|---------|---------|----------|
| `rag_query_rewrite` | 查询重写提示词 | 将用户原始查询重写为更适合知识库检索的形式 | rag_retrieval |
| `synonym_expansion` | 同义词扩展提示词 | 为查询词生成同义词/相关词列表，提升检索召回率 | rag_retrieval |
| `metadata_extraction` | 元数据提取提示词 | 从文档块中提取结构化元数据（主题、年龄、类型等） | rag_retrieval |
| `test_case_generation` | 测试用例生成提示词 | 根据文档内容自动生成 RAG 测试用例草稿 | test_case_generation |
| `validation` | 数据校验提示词 | 校验用户输入的儿童画像和拟定计划是否完整合理 | assessment |
| `intensity_inference` | 强度等级推断提示词 | 根据运动名称推断强度等级（low/medium/high） | assessment |
| `category_inference` | 类别推断提示词 | 根据运动名称推断类别（前庭觉/本体觉/触觉等） | assessment |
| `assessment_system` | 评估系统提示词 | 根据儿童画像进行多维度感统能力评估 | assessment |
| `scoring` | 评分提示词 | 对拟定的训练计划进行多维度打分 | scoring |
| `report_generation` | 报告生成提示词 | 生成专业、详细的儿童运动发展评估报告 | reporting |

### 3.2 变量声明示例

| prompt_key | 变量声明 |
|-----------|---------|
| `rag_query_rewrite` | query(string, required), age(number, required) |
| `synonym_expansion` | query(string, required) |
| `test_case_generation` | text(string, required), count(number, required), domains(string, required), age_range_min(number, required), age_range_max(number, required) |

---

## 4. 数据库变更

### 4.1 新建表

创建 `prompt_metadata` 表，包含上述 §2.1 定义的所有字段（主键为 UUID）。

### 4.2 修改表

在 `prompt_versions` 表中：
- 修改 `id` 字段类型：从 `VARCHAR(255)` 改为 `CHAR(36)` (UUID)
- 重命名 `version` 字段为 `version_label`
- 新增 `variables_extracted`（JSON）和 `change_impact`（JSON）两个字段

### 4.3 删除表

删除 `prompt_ab_tests` 表（A/B 测试功能不在本系统范围内，直接删除）。

---

## 5. 代码修改清单

### 5.1 必须修改的代码

| 变更 | 修改方式 | 涉及文件 |
|------|---------|---------|
| `PromptVersion.id` 格式变更 | 所有通过 ID 查询的代码改为 UUID 查询 | `backend/src/core/prompt/manager.py`、所有调用 `get_prompt_version(id)` 的位置 |
| `PromptVersion.version` 重命名 | 全局替换为 `version_label` | 所有引用 `.version` 属性的代码 |
| `PromptVersion.variables` | 删除该字段，所有读取改为 `variables_extracted` | `backend/src/core/prompt/manager.py`、前端提示词列表页 |
| `PromptABTest` 模型 | 直接删除模型类和相关 API | `backend/src/core/prompt/` 下所有 A/B 测试相关代码 |
| `PromptABTest` 前端 | 直接删除 A/B 测试页面和组件 | `frontend/src/features/prompts/` 下所有 A/B 测试相关组件 |
| `prompt_manager.get_prompt()` | 接口不变，内部逻辑适配新模型 | `backend/src/core/prompt/manager.py` |

### 5.2 必须删除的老代码

| 删除项 | 位置 | 说明 |
|--------|------|------|
| `PromptABTest` 模型类 | `backend/src/core/prompt/models.py` | 整个类删除 |
| `PromptABTest` 相关 API | `backend/src/api/v1/prompts.py` | 以下端点全部删除：`/ab-tests` (GET/POST)、`/ab-tests/{test_id}/toggle` (POST) |
| `PromptABTest` 前端页面 | `frontend/src/features/prompts/` | A/B 测试列表、创建、切换等组件全部删除 |
| `PromptVersion.variables` 字段读取逻辑 | `backend/src/core/prompt/manager.py` | 删除所有 `.variables` 属性访问 |
| `PromptVersion.fallback` 字段 | `backend/src/core/prompt/models.py` | 降级内容字段删除，降级逻辑由 `prompts_fallback.py` 文件独立处理 |
| `PromptVersion.tags` 字段 | `backend/src/core/prompt/models.py` | 标签字段删除 |

### 5.3 降级文件同步

**当前阶段**: `prompts_fallback.py` 与数据库版本保持手动同步。修改数据库中的提示词后，开发者需手动更新 `prompts_fallback.py` 中的对应内容。

**同步机制**: 在 `PromptVersion` 保存新版本时，后端自动将最新版本的提示词内容同步写入 `prompts_fallback.py` 文件（通过文件写入操作，确保数据库与 fallback 文件一致）。若文件写入失败，记录错误日志但不阻塞保存操作。

---

## 6. 验收标准

| 验收项 | 标准 |
|--------|------|
| **数据模型创建** | `prompt_metadata` 表创建成功，主键为 UUID，包含所有必填字段 |
| **ID 统一** | 所有提示词相关表（PromptMetadata/PromptVersion）主键均为 CHAR(36) UUID |
| **老字段删除** | `PromptVersion.variables`、`PromptVersion.tags`、`PromptVersion.fallback` 字段已从模型和代码中删除 |
| **A/B 测试删除** | `PromptABTest` 模型、API 端点、前端页面全部删除，代码中无残留引用 |
| **初始化数据** | 所有现有提示词都有元数据记录，中文名称和用途说明完整 |
| **变量声明** | 每个提示词的 `variables_schema` 完整准确 |
| **代码引用扫描** | `code_references` 自动扫描并填充 |
| **配置依赖检测** | `config_dependencies` 自动检测并填充 |
| **接口验证** | `prompt_manager.get_prompt()` 接口正常返回结果，内部使用新模型 |
| **降级文件同步** | 开发者手动保持 `prompts_fallback.py` 与数据库版本一致 |

---

**文档索引**: 
- 上一节: [07-prompt-management-overview.md](./07-prompt-management-overview.md) — 提示词管理重构概览
- 下一节: [07b-prompt-frontend-pages.md](./07b-prompt-frontend-pages.md) — 前端页面重构
