# Phase 5-3: Import 分组格式

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `6.3.3` 节
> **所属 Phase**: Phase 5

## 需求定义

统一所有 Python 文件的 import 分组格式，按 stdlib → third-party → local 分组，每组空行分隔，字母排序。

## 验收标准

- [ ] 170+ 文件 import 分组符合规范
- [ ] 使用 `isort` 自动格式化
- [ ] `isort --check` 通过
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `pyproject.toml` | 修改 | 添加 isort 配置 |
| 所有 .py 文件 | 修改 | import 分组格式化 |

## 实现方案

### 统一 Import 分组格式

```python
# 1. 标准库（按字母排序）
import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

# 2. 第三方库（按字母排序）
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

# 3. 本地应用（from src.xxx，按字母排序）
from src.config import settings
from src.schemas.assessment import UserInput, AgentState
from src.service.rag_test_manager import rag_test_manager
from src.utils.logger import logger
```

### 规则

| 规则 | 说明 |
|------|------|
| 分组顺序 | stdlib → third-party → local |
| 组内排序 | 字母顺序 |
| 组间分隔 | 一个空行 |
| 导入方式 | 跨模块统一使用 `from src.xxx` 绝对导入 |
| 相对导入 | 仅限 `__init__.py` 中的聚合导出 |
| 函数内 import | 仅允许循环依赖/懒加载场景 |

### pyproject.toml 配置

```toml
[tool.isort]
profile = "black"
line_length = 88
sections = ["FUTURE", "STDLIB", "THIRDPARTY", "FIRSTPARTY", "LOCALFOLDER"]
known_first_party = ["src"]
force_single_line = false
combine_as_imports = true
```

### 执行命令

```bash
# 检查
cd backend && isort src/ --check --diff

# 格式化
cd backend && isort src/

# 验证
cd backend && isort src/ --check
```

## 测试方案

1. `isort --check` 通过
2. 格式化后 import 无错误
3. 循环依赖场景的延迟导入保留

## 注意事项

- `isort` 配置 `profile = "black"` 与项目代码风格一致
- 循环依赖场景的函数内 import 需人工审查，不可自动移动
- `from __future__ import annotations` 始终在最顶部
