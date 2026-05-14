"""统一内容哈希工具 — 全项目使用 SHA-256 全长，strip 后计算"""
import hashlib


def content_hash(text: str) -> str:
    """统一内容哈希：SHA-256 全长，strip 后计算"""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
