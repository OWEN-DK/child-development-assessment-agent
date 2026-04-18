# Phase 1 - 实体类集中管理

> **本文档包含**: Phase 1 总览、需求点清单、验收标准、实施顺序

---

## 目标

将所有 Pydantic 实体类（`BaseModel`）从 controller/service/core/model/models 统一迁移至 `backend/src/schemas/` 目录，按业务模块组织。

---

## 需求点清单

| # | 需求点名称 | 实施文件 | 预估工作量 |
|---|-----------|---------|-----------|
| 1 | schemas 目录结构创建 | `01-schemas-directory-structure.md` | 小 |
| 2 | Controller 实体迁移 | `02-migrate-controller-entities.md` | 中 |
| 3 | Service 实体迁移 | `03-migrate-service-entities.md` | 中 |
| 4 | Core 实体迁移 | `04-migrate-core-entities.md` | 小 |
| 5 | model 实体迁移 | `05-migrate-model-entities.md` | 中 |
| 6 | models 实体迁移 | `06-migrate-models-entities.md` | 小 |
| 7 | schemas __init__.py 导出 | `07-schemas-init-export.md` | 小 |
| 8 | 实体命名规范 | `08-entity-naming-convention.md` | 小 |

---

## 验收标准

- [ ] `backend/src/schemas/` 目录结构正确创建
- [ ] 所有 Pydantic 实体类迁移完成，按业务模块组织
- [ ] 0 处 `class xxx(BaseModel)` 遗留在 service/controller/core 中
- [ ] 导入规范统一：`from src.schemas import Xxx`
- [ ] 实体命名符合规范：Request DTO `{Entity}{Action}Request`，Response DTO `{Entity}Response`

---

## 实施顺序

1. 创建 `schemas/` 目录结构 → 2. 迁移各模块实体 → 3. 创建 `__init__.py` 导出 → 4. 统一命名规范

---

**下一步**: [01-schemas-directory-structure.md](./01-schemas-directory-structure.md)
