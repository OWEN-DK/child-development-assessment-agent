# Phase 4-6: 加密哈希工具

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `5.2.6` 节
> **所属 Phase**: Phase 4

## 需求定义

提取 7 处重复的 `hashlib.sha256()` 内容哈希计算代码至统一工具模块。

## 验收标准

- [ ] `utils/crypto.py` 创建完成
- [ ] 7 处内容哈希计算替换为 `hash_content()`
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/utils/crypto.py` | 新增 | 加密哈希工具 |
| 多个 Service 文件 | 修改 | 替换哈希计算代码 |

## 实现方案

```python
"""
加密哈希工具模块

统一内容哈希计算，消除重复的 hashlib.sha256() 调用。
"""

import hashlib


def hash_content(content: str | bytes, algorithm: str = "sha256") -> str:
    """计算内容哈希值
    
    使用方式：
        doc_hash = hash_content(document_content)
        file_hash = hash_content(file_bytes)
    
    Args:
        content: 字符串或字节内容
        algorithm: 哈希算法（默认 sha256）
    
    Returns:
        十六进制哈希字符串
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.new(algorithm, content).hexdigest()


def hash_file(file_path: str, algorithm: str = "sha256", chunk_size: int = 8192) -> str:
    """计算文件哈希值（分块读取，适合大文件）
    
    使用方式：
        file_hash = hash_file("/path/to/large/file.pdf")
    
    Args:
        file_path: 文件路径
        algorithm: 哈希算法
        chunk_size: 每次读取的字节数
    
    Returns:
        十六进制哈希字符串
    """
    h = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def generate_token(length: int = 32) -> str:
    """生成随机 Token
    
    Args:
        length: Token 长度
    
    Returns:
        十六进制随机字符串
    """
    import secrets
    return secrets.token_hex(length)
```

## 替换对照

**替换前**：
```python
import hashlib

# 7 处重复
doc_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
file_hash = hashlib.sha256(file_bytes).hexdigest()
```

**替换后**：
```python
from src.utils.crypto import hash_content, hash_file

doc_hash = hash_content(document_content)
file_hash = hash_file("/path/to/file.pdf")
```

## 测试方案

1. 相同内容生成相同哈希
2. 不同内容生成不同哈希
3. 字符串和字节输入结果一致
4. 大文件分块哈希正确

## 注意事项

- 默认使用 SHA-256，满足内容去重需求
- 大文件使用 `hash_file` 分块读取，避免内存溢出
- Token 生成使用 `secrets` 模块（密码学安全）
