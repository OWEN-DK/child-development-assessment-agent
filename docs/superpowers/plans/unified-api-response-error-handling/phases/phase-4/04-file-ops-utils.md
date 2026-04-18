# Phase 4-4: 文件操作工具

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `5.2.4` 节
> **所属 Phase**: Phase 4

## 需求定义

提取 70+ 处重复的文件操作代码（exists/makedirs/read/write）至统一工具模块。

## 验收标准

- [ ] `utils/file_ops.py` 创建完成
- [ ] 70+ 处文件操作替换为工具函数
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/utils/file_ops.py` | 新增 | 文件操作工具 |
| 所有 Service/Core 文件 | 修改 | 替换文件操作代码 |

## 实现方案

```python
"""
文件操作工具模块

统一文件读写、目录创建、删除等操作，消除重复代码。
"""

import json
import os
from pathlib import Path
from typing import Any


def ensure_dir(path: str | Path) -> Path:
    """确保目录存在，不存在则创建
    
    使用方式：
        ensure_dir("/path/to/dir")
    
    Args:
        path: 目录路径
    
    Returns:
        Path 对象
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_remove(path: str | Path) -> bool:
    """安全删除文件，不存在则返回 False
    
    使用方式：
        if safe_remove("/path/to/file"):
            print("已删除")
    
    Args:
        path: 文件路径
    
    Returns:
        是否成功删除
    """
    p = Path(path)
    if p.exists():
        p.unlink()
        return True
    return False


def read_json(path: str | Path, default: Any = None) -> Any:
    """读取 JSON 文件，失败返回默认值
    
    使用方式：
        data = read_json("config.json", default={})
    
    Args:
        path: 文件路径
        default: 读取失败时的默认值
    
    Returns:
        JSON 解析后的数据，或默认值
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return default


def write_json(path: str | Path, data: Any, indent: int = 2) -> None:
    """写入 JSON 文件，自动创建目录
    
    使用方式：
        write_json("output.json", {"key": "value"})
    
    Args:
        path: 文件路径
        data: 要写入的数据
        indent: 缩进空格数
    """
    p = Path(path)
    ensure_dir(p.parent)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def read_text(path: str | Path, default: str = "") -> str:
    """读取文本文件，失败返回默认值
    
    Args:
        path: 文件路径
        default: 读取失败时的默认值
    
    Returns:
        文件内容，或默认值
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, PermissionError):
        return default


def write_text(path: str | Path, content: str) -> None:
    """写入文本文件，自动创建目录
    
    Args:
        path: 文件路径
        content: 要写入的内容
    """
    p = Path(path)
    ensure_dir(p.parent)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)


def file_exists(path: str | Path) -> bool:
    """检查文件是否存在
    
    Args:
        path: 文件路径
    
    Returns:
        是否存在
    """
    return Path(path).exists()


def dir_exists(path: str | Path) -> bool:
    """检查目录是否存在
    
    Args:
        path: 目录路径
    
    Returns:
        是否存在
    """
    return Path(path).is_dir()
```

## 替换对照

**替换前**（70+ 处重复）：
```python
# 重复的目录检查与创建
if not os.path.exists(dir_path):
    os.makedirs(dir_path, exist_ok=True)

# 重复的文件读取
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# 重复的文件写入
with open(file_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
```

**替换后**：
```python
from src.utils.file_ops import ensure_dir, read_json, write_json, safe_remove

ensure_dir(dir_path)
data = read_json(file_path, default={})
write_json(file_path, data)
safe_remove(file_path)
```

## 测试方案

1. `ensure_dir` 创建多级目录
2. `safe_remove` 不存在文件返回 False
3. `read_json` 文件不存在返回默认值
4. `write_json` 自动创建父目录
5. 编码统一为 utf-8

## 注意事项

- 所有路径操作使用 `pathlib.Path`，避免 `os.path` 混用
- JSON 读写统一使用 utf-8 编码
- `write_json` 设置 `ensure_ascii=False` 保留中文字符
- 文件操作失败时不抛异常，返回默认值（调用方需检查）
