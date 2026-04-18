# Phase 4 - 冗余代码消除

> **本文档包含**: Phase 4 总览、需求点清单、验收标准、实施顺序

---

## 目标

提取 280+ 处重复代码至 `utils/` 目录下的工具模块，消除重复，遵循 DRY 原则。

---

## 需求点清单

| # | 需求点名称 | 实施文件 | 重复次数 | 预估工作量 |
|---|-----------|---------|---------|-----------|
| 1 | 数据库 Session 工具 | `01-db-session-utils.md` | 26 处 | 小 |
| 2 | 错误处理工具 | `02-error-handler-utils.md` | 100+ 处 | 中 |
| 3 | ORM 序列化工具 | `03-orm-serializer-utils.md` | 30+ 处 | 小 |
| 4 | 文件操作工具 | `04-file-ops-utils.md` | 70+ 处 | 中 |
| 5 | 时间处理工具 | `05-time-utils.md` | 50+ 处 | 小 |
| 6 | 加密哈希工具 | `06-crypto-utils.md` | 7 处 | 小 |
| 7 | ID 生成工具 | `07-id-generator-utils.md` | 15 处 | 小 |
| 8 | 认证辅助工具 | `08-auth-helpers-utils.md` | 4 处 | 小 |

---

## 验收标准

- [ ] `utils/db.py`：`get_db_session()`, `execute_with_session()`
- [ ] `utils/response.py`：`handle_api_error()`, `not_found()`, `server_error()`
- [ ] `utils/serializers.py`：`safe_isoformat()`, `safe_enum_value()`, `model_to_dict()`
- [ ] `utils/file_ops.py`：`ensure_dir()`, `safe_remove()`, `read_json()`, `write_json()`
- [ ] `utils/time_utils.py`：`utc_now()`, `time_range()`, `safe_timestamp()`
- [ ] `utils/crypto.py`：`hash_content()`
- [ ] `utils/id_generator.py`：`generate_id()`
- [ ] `utils/auth_helpers.py`：`get_user_id()`
- [ ] 所有重复调用点替换为工具函数

---

## 新建工具模块清单

| 新文件 | 包含函数 | 可消除重复数 | 优先级 |
|--------|---------|-------------|--------|
| `utils/db.py` | `get_db_session()`, `execute_with_session()` | 26 处 | P0 |
| `utils/response.py` | `handle_api_error()`, `not_found()`, `server_error()` | 100+ 处 | P0 |
| `utils/serializers.py` | `safe_isoformat()`, `safe_enum_value()`, `model_to_dict()` | 30+ 处 | P0 |
| `utils/file_ops.py` | `ensure_dir()`, `safe_remove()`, `read_json()`, `write_json()` | 70+ 处 | P1 |
| `utils/time_utils.py` | `utc_now()`, `time_range()`, `safe_timestamp()` | 50+ 处 | P1 |
| `utils/crypto.py` | `hash_content()` | 7 处 | P2 |
| `utils/id_generator.py` | `generate_id()` | 15 处 | P2 |
| `utils/auth_helpers.py` | `get_user_id()` | 4 处 | P3 |

---

## 实施顺序

按优先级：P0 (db, response, serializers) → P1 (file_ops, time) → P2 (crypto, id_generator) → P3 (auth_helpers)

---

**下一步**: [01-db-session-utils.md](./01-db-session-utils.md)
