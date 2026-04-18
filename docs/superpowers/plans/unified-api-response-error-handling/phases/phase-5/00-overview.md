# Phase 5 - 代码引用规范

> **本文档包含**: Phase 5 总览、需求点清单、验收标准、实施顺序

---

## 目标

规范 Python 代码引用（import），解决 model/models 命名冲突，补充缺失的 `__init__.py`，统一 import 分组格式，解决循环导入。

---

## 需求点清单

| # | 需求点名称 | 实施文件 | 影响范围 | 预估工作量 |
|---|-----------|---------|---------|-----------|
| 1 | 重命名 model → schemas | `01-rename-model-to-schemas.md` | 31 处引用 | 中 |
| 2 | 补充 __init__.py | `02-add-init-files.md` | 4 个目录 | 小 |
| 3 | Import 分组格式 | `03-import-grouping-format.md` | 170+ 文件 | 大 |
| 4 | 解决循环导入 | `04-resolve-circular-imports.md` | config 模块 | 中 |
| 5 | 函数内 import 迁移 | `05-move-function-imports.md` | 364 处 | 中 |
| 6 | 拆分 config/__init__.py | `06-split-config-init.md` | 614 行 | 中 |

---

## 验收标准

- [ ] `src/model/` 重命名为 `src/schemas/`，31 处引用全部更新
- [ ] `controller/`, `service/`, `core/`, `utils/` 补充 `__init__.py`
- [ ] Import 分组：stdlib → third-party → local，每组空行分隔，字母排序
- [ ] 循环导入解决（config/__init__.py ↔ config/core/manager.py）
- [ ] 非循环依赖场景的函数内 import 移至文件顶部
- [ ] `config/__init__.py` 拆分为 4 个文件（app.py, singleton.py, init.py, __init__.py）

---

## Import 分组格式

```python
# 1. 标准库（按字母排序）
import asyncio
import json
from datetime import datetime, timezone, timedelta

# 2. 第三方库（按字母排序）
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# 3. 本地应用（from src.xxx，按字母排序）
from src.config import settings
from src.schemas.assessment import UserInput
from src.utils.logger import logger
```

---

## 实施顺序

1. 重命名 model → schemas → 2. 补充 __init__.py → 3. 统一 import 分组 → 4. 解决循环导入 → 5. 函数内 import 迁移 → 6. 拆分 config

---

**下一步**: [01-rename-model-to-schemas.md](./01-rename-model-to-schemas.md)
