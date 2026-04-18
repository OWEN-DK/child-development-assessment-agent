"""加密哈希工具模块

统一内容哈希计算，消除重复的 hashlib.sha256() 调用。
"""

import hashlib
import secrets


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
    return secrets.token_hex(length)
