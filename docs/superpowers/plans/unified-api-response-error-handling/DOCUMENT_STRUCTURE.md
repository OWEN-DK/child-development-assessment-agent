# 文档结构说明

## 📁 文件组织

本文档将统一接口返回与异常处理重构实施计划拆分为多个独立模块，**一个文件只对应一个需求点**，不得合并。

### 核心文档结构

```
unified-api-response-error-handling/
├── README.md                              # 主索引文件（入口）+ 核心实施规则
├── PROGRESS.md                            # 进度追踪（按需求点 checkbox）
├── DOCUMENT_STRUCTURE.md                  # 本文档：需求点与实施文件映射表
├── 00-overview.md                         # 项目概览：背景目标、验收标准、架构
│
├── phases/
│   ├── phase-1/                           # Phase 1: 实体类集中管理 (8 个需求点)
│   │   ├── 00-overview.md                 # Phase 1 总览
│   │   ├── 01-schemas-directory-structure.md
│   │   ├── 02-migrate-controller-entities.md
│   │   ├── 03-migrate-service-entities.md
│   │   ├── 04-migrate-core-entities.md
│   │   ├── 05-migrate-model-entities.md
│   │   ├── 06-migrate-models-entities.md
│   │   ├── 07-schemas-init-export.md
│   │   └── 08-entity-naming-convention.md
│   │
│   ├── phase-2/                           # Phase 2: 类职责拆分 (7 个需求点)
│   │   ├── 00-overview.md                 # Phase 2 总览
│   │   ├── 01-rag-test-manager-split.md
│   │   ├── 02-retrieval-service-split.md
│   │   ├── 03-metadata-processor-split.md
│   │   ├── 04-document-ingestion-split.md
│   │   ├── 05-index-manager-split.md
│   │   ├── 06-cache-service-split.md
│   │   └── 07-prompt-manager-split.md
│   │
│   ├── phase-3/                           # Phase 3: 统一响应格式 (5 个需求点)
│   │   ├── 00-overview.md                 # Phase 3 总览
│   │   ├── 01-api-response-model.md
│   │   ├── 02-success-response-format.md
│   │   ├── 03-error-response-format.md
│   │   ├── 04-pagination-format.md
│   │   └── 05-http-status-mapping.md
│   │
│   ├── phase-4/                           # Phase 4: 冗余代码消除 (8 个需求点)
│   │   ├── 00-overview.md                 # Phase 4 总览
│   │   ├── 01-db-session-utils.md
│   │   ├── 02-error-handler-utils.md
│   │   ├── 03-orm-serializer-utils.md
│   │   ├── 04-file-ops-utils.md
│   │   ├── 05-time-utils.md
│   │   ├── 06-crypto-utils.md
│   │   ├── 07-id-generator-utils.md
│   │   └── 08-auth-helpers-utils.md
│   │
│   ├── phase-5/                           # Phase 5: 代码引用规范 (6 个需求点)
│   │   ├── 00-overview.md                 # Phase 5 总览
│   │   ├── 01-rename-model-to-schemas.md
│   │   ├── 02-add-init-files.md
│   │   ├── 03-import-grouping-format.md
│   │   ├── 04-resolve-circular-imports.md
│   │   ├── 05-move-function-imports.md
│   │   └── 06-split-config-init.md
│   │
│   ├── phase-6/                           # Phase 6: 前端架构重构 (8 个需求点)
│   │   ├── 00-overview.md                 # Phase 6 总览
│   │   ├── 01-fsd-lite-directory-structure.md
│   │   ├── 02-page-logic-separation.md
│   │   ├── 03-split-config-store.md
│   │   ├── 04-unify-api-call-pattern.md
│   │   ├── 05-eliminate-notification-dup.md
│   │   ├── 06-unify-sse-implementation.md
│   │   ├── 07-unify-type-definitions.md
│   │   └── 08-eslint-path-alias-config.md
│   │
│   └── phase-7/                           # Phase 7: 错误码与后端实现 (6 个需求点)
│       ├── 00-overview.md                 # Phase 7 总览
│       ├── 01-error-code-segmentation.md
│       ├── 02-common-error-codes.md
│       ├── 03-module-error-codes.md
│       ├── 04-app-exception-hierarchy.md
│       ├── 05-global-exception-handler.md
│       └── 06-response-wrapper-middleware.md
```

---

## 📋 需求点与实施文件映射表

> **每个需求点对应一个实施文件，不得遗漏和跳过。**

### Phase 1: 实体类集中管理 (8 个需求点)

| 需求点序号 | 需求点名称 | 实施文件 | spec 来源 |
|-----------|-----------|---------|----------|
| 1 | schemas 目录结构创建 | `01-schemas-directory-structure.md` | 2.2 目标目录结构 |
| 2 | Controller 实体迁移 | `02-migrate-controller-entities.md` | 2.4 迁移清单 |
| 3 | Service 实体迁移 | `03-migrate-service-entities.md` | 2.4 迁移清单 |
| 4 | Core 实体迁移 | `04-migrate-core-entities.md` | 2.4 迁移清单 |
| 5 | model 实体迁移 | `05-migrate-model-entities.md` | 2.4 迁移清单 |
| 6 | models 实体迁移 | `06-migrate-models-entities.md` | 2.4 迁移清单 |
| 7 | schemas __init__.py 导出 | `07-schemas-init-export.md` | 2.5 导入规范 |
| 8 | 实体命名规范 | `08-entity-naming-convention.md` | 2.3 分类规则 |

### Phase 2: 类职责拆分 (7 个需求点)

| 需求点序号 | 需求点名称 | 实施文件 | spec 来源 |
|-----------|-----------|---------|----------|
| 1 | RagTestManager 拆分 | `01-rag-test-manager-split.md` | 3.3.1 (1799 行 → 8 个类) |
| 2 | RetrievalService 拆分 | `02-retrieval-service-split.md` | 3.3.2 (1060 行 → 5 个类) |
| 3 | MetadataProcessor 拆分 | `03-metadata-processor-split.md` | 3.3.3 (925 行 → 7 个类) |
| 4 | DocumentIngestionService 拆分 | `04-document-ingestion-split.md` | 3.3.4 (637 行 → 5 个类) |
| 5 | IndexManagerService 拆分 | `05-index-manager-split.md` | 3.3.5 (574 行 → 4 个类) |
| 6 | CacheService 拆分 | `06-cache-service-split.md` | 3.4 P2 (447 行) |
| 7 | PromptManager 拆分 | `07-prompt-manager-split.md` | 3.4 P2 (428 行) |

### Phase 3: 统一响应格式 (5 个需求点)

| 需求点序号 | 需求点名称 | 实施文件 | spec 来源 |
|-----------|-----------|---------|----------|
| 1 | APIResponse 模型定义 | `01-api-response-model.md` | 4.1-4.3 |
| 2 | 成功响应格式 | `02-success-response-format.md` | 4.2 |
| 3 | 错误响应格式 | `03-error-response-format.md` | 4.3 |
| 4 | 分页数据格式 | `04-pagination-format.md` | 4.2 分页扩展 |
| 5 | HTTP 状态码映射 | `05-http-status-mapping.md` | 4.4 |

### Phase 4: 冗余代码消除 (8 个需求点)

| 需求点序号 | 需求点名称 | 实施文件 | spec 来源 |
|-----------|-----------|---------|----------|
| 1 | 数据库 Session 工具 | `01-db-session-utils.md` | 5.2.1 (26 处) |
| 2 | 错误处理工具 | `02-error-handler-utils.md` | 5.2.2 (100+ 处) |
| 3 | ORM 序列化工具 | `03-orm-serializer-utils.md` | 5.2.3 (30+ 处) |
| 4 | 文件操作工具 | `04-file-ops-utils.md` | 5.2.4 (70+ 处) |
| 5 | 时间处理工具 | `05-time-utils.md` | 5.2.5 (50+ 处) |
| 6 | 加密哈希工具 | `06-crypto-utils.md` | 5.2.6 (7 处) |
| 7 | ID 生成工具 | `07-id-generator-utils.md` | 5.2.6 (15 处) |
| 8 | 认证辅助工具 | `08-auth-helpers-utils.md` | 5.2.6 (4 处) |

### Phase 5: 代码引用规范 (6 个需求点)

| 需求点序号 | 需求点名称 | 实施文件 | spec 来源 |
|-----------|-----------|---------|----------|
| 1 | 重命名 model → schemas | `01-rename-model-to-schemas.md` | 6.3.1 (31 处引用) |
| 2 | 补充 __init__.py | `02-add-init-files.md` | 6.3.2 |
| 3 | Import 分组格式 | `03-import-grouping-format.md` | 6.3.3 |
| 4 | 解决循环导入 | `04-resolve-circular-imports.md` | 6.3.4 |
| 5 | 函数内 import 迁移 | `05-move-function-imports.md` | 6.3.5 |
| 6 | 拆分 config/__init__.py | `06-split-config-init.md` | 6.3.6 (614 行) |

### Phase 6: 前端架构重构 (8 个需求点)

| 需求点序号 | 需求点名称 | 实施文件 | spec 来源 |
|-----------|-----------|---------|----------|
| 1 | FSD Lite 目录结构 | `01-fsd-lite-directory-structure.md` | 7.3 目标目录结构 |
| 2 | 页面与逻辑分离 | `02-page-logic-separation.md` | 7.5.1 |
| 3 | 拆分 configStore | `03-split-config-store.md` | 7.5.2 (369 行) |
| 4 | 统一 API 调用模式 | `04-unify-api-call-pattern.md` | 7.5.3 |
| 5 | 消除通知重复 | `05-eliminate-notification-dup.md` | 7.5.4 (95+ 处) |
| 6 | 统一 SSE 实现 | `06-unify-sse-implementation.md` | 7.5.4 |
| 7 | 统一类型定义 | `07-unify-type-definitions.md` | 7.5.5 |
| 8 | ESLint 与路径别名 | `08-eslint-path-alias-config.md` | 7.6 |

### Phase 7: 错误码与后端实现 (6 个需求点)

| 需求点序号 | 需求点名称 | 实施文件 | spec 来源 |
|-----------|-----------|---------|----------|
| 1 | 错误码分段定义 | `01-error-code-segmentation.md` | 8.1 |
| 2 | 通用错误码 | `02-common-error-codes.md` | 8.2 (10 个) |
| 3 | 模块错误码 | `03-module-error-codes.md` | 8.3 |
| 4 | AppException 层级 | `04-app-exception-hierarchy.md` | 9.1.2 |
| 5 | 全局异常处理器 | `05-global-exception-handler.md` | 9.1.3-9.1.4 |
| 6 | 响应包装中间件 | `06-response-wrapper-middleware.md` | 9.2 |

---

## 📖 使用指南

### 阅读顺序

1. **入口**：从 [`README.md`](./README.md) 开始，了解项目整体与核心规则
2. **概览**：阅读 [`00-overview.md`](./00-overview.md)，了解背景目标、验收标准、架构
3. **映射表**：阅读本文档，了解需求点与实施文件的对应关系
4. **按 Phase 执行**：按 Phase 1→7 顺序，每个 Phase 先读 `00-overview.md`，再按序号逐个实施

### 实施文件模板

每个实施文件必须包含以下结构：

```markdown
# {需求点名称}

> **需求来源**: spec 文档 `{spec_file}` 中 `{section}` 节
> **所属 Phase**: Phase {N}

## 需求定义

{来自 spec 文档的完整需求描述}

## 验收标准

- [ ] {验收标准 1}
- [ ] {验收标准 2}

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/...` | 新增/修改/删除 | {说明} |

## 实现方案

### 后端实现

{完整的 Python 代码实现}

### 前端实现（如适用）

{完整的 TypeScript/React 代码实现}

### 数据库变更（如适用）

{完整的 DDL 语句或 SQLAlchemy 模型定义}

## 测试方案

{测试用例定义，TDD-Red 阶段必须先写测试}

## 注意事项

{CLAUDE.md 相关规则、踩坑提醒}
```

---

## 🔧 文档维护

### 添加新内容

如需补充某个需求点的详细实施，直接编辑对应的实施文件即可。

### 更新现有内容

直接编辑对应的实施文件。所有修改应：
- 保持代码示例的完整性
- 包含必要的导入语句
- 提供测试步骤和预期结果
- 遵守"一个文件只对应一个需求点"的原则

---

**最后更新：** 2026-04-18
**文档版本：** 0.1 (初始框架)
**维护者：** AI Assistant
