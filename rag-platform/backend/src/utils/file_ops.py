"""文件操作工具模块

统一文件读写、目录创建、删除等操作，消除重复代码。
"""

import json
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
