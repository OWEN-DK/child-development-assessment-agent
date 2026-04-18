# Phase 5-5: 函数内 import 迁移

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `6.3.5` 节
> **所属 Phase**: Phase 5

## 需求定义

将 364 处函数内 import 中非循环依赖/懒加载场景的移至文件顶部，消除冗余的函数内 import。

## 验收标准

- [ ] 非循环依赖场景的函数内 import 移至顶部
- [ ] 循环依赖/懒加载场景的函数内 import 保留
- [ ] `ruff` E402 检查通过
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| 364 处函数内 import 的文件 | 修改 | 移至文件顶部 |

## 实现方案

### 必须移至文件顶部的 import

| import | 出现位置 | 原因 |
|--------|---------|------|
| `import asyncio` | `rag_test_controller.py:261` 等 15 处 | 标准库，无循环依赖 |
| `import uuid` | `prompt_manager.py:303` 等 8 处 | 标准库，无循环依赖 |
| `import json` | 多处 | 标准库，无循环依赖 |
| `import hashlib` | 多处 | 标准库，无循环依赖 |
| `import os` | `config/__init__.py:553` 等 | 标准库，无循环依赖 |

### 允许保留函数内 import 的场景

| 场景 | 原因 |
|------|------|
| `config_manager._get_repos()` | 避免循环依赖 |
| `import weasyprint` | 重型第三方库，按需加载 |
| `import chardet` | 条件加载 |

### 修改示例

**修改前**：
```python
async def run_batch():
    import asyncio  # ← 应移至顶部
    tasks = [asyncio.create_task(run_case(c)) for c in cases]
    return await asyncio.gather(*tasks)
```

**修改后**：
```python
import asyncio  # ← 文件顶部

async def run_batch():
    tasks = [asyncio.create_task(run_case(c)) for c in cases]
    return await asyncio.gather(*tasks)
```

### 批量检查命令

```bash
# 查找函数内 import
rg "^\s+import " backend/src/ --type py | head -50

# ruff 检查
cd backend && ruff check src/ --select E402
```

## 测试方案

1. 移至顶部后 import 无错误
2. 循环依赖场景的延迟导入保留
3. `ruff E402` 检查通过

## 注意事项

- 重型第三方库（weasyprint/chardet）保留函数内 import，减少启动时间
- 循环依赖场景保留延迟导入，但需添加注释说明原因
- 标准库 import 一律移至顶部
