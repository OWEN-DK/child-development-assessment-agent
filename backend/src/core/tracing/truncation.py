"""内容截断存储策略

prompt_messages 和 completion_message 默认截断至前 8000 字符，
完整内容可存储于可选的本地文件。
"""

import json
import os
from typing import Tuple

from src.config import settings

DEFAULT_TRUNCATE_LENGTH = 8000
FULL_CONTENT_DIR = "storage/traces"


def _get_truncate_config() -> tuple[int, bool, str]:
    """从配置获取截断参数，若无则使用默认值"""
    try:
        truncate_length = getattr(
            settings, "trace_truncate_length", DEFAULT_TRUNCATE_LENGTH
        )
        full_content_enabled = getattr(settings, "trace_full_content_enabled", False)
        full_content_dir = getattr(settings, "trace_full_content_dir", FULL_CONTENT_DIR)
        return truncate_length, full_content_enabled, full_content_dir
    except Exception:
        return DEFAULT_TRUNCATE_LENGTH, False, FULL_CONTENT_DIR


def truncate_content(content: str, max_length: int | None = None) -> Tuple[str, bool]:
    """截断文本内容，返回 (截断后内容, 是否被截断)"""
    if max_length is None:
        max_length, _, _ = _get_truncate_config()
    if len(content) <= max_length:
        return content, False
    return content[:max_length], True


def truncate_messages(
    messages: list[dict], max_length: int | None = None
) -> list[dict]:
    """截断消息数组中每个消息的 content 字段"""
    if max_length is None:
        max_length, _, _ = _get_truncate_config()
    result = []
    for msg in messages:
        truncated_msg = msg.copy()
        if "content" in truncated_msg and isinstance(truncated_msg["content"], str):
            truncated_msg["content"], _ = truncate_content(
                truncated_msg["content"], max_length
            )
        result.append(truncated_msg)
    return result


def save_full_content(
    content: str, trace_id: str, span_id: str, field_name: str
) -> str:
    """保存完整内容到本地文件，返回文件路径

    Args:
        content: 完整内容
        trace_id: 追踪 ID
        span_id: Span ID
        field_name: 字段名 ("prompt" 或 "completion")

    Returns:
        文件绝对路径
    """
    _, enabled, content_dir = _get_truncate_config()
    if not enabled:
        return ""

    os.makedirs(content_dir, exist_ok=True)
    filename = f"{trace_id}_{span_id}_{field_name}.json"
    filepath = os.path.join(content_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(
            {
                "trace_id": trace_id,
                "span_id": span_id,
                "field": field_name,
                "content": content,
            },
            f,
        )

    return filepath
