"""截断存储策略单元测试"""

import pytest


def test_truncate_short_content():
    from src.core.tracing.truncation import truncate_content

    content = "short content"
    result, truncated = truncate_content(content, max_length=8000)
    assert result == content
    assert truncated is False


def test_truncate_long_content():
    from src.core.tracing.truncation import truncate_content

    content = "a" * 10000
    result, truncated = truncate_content(content, max_length=8000)
    assert len(result) == 8000
    assert truncated is True


def test_truncate_json_messages():
    from src.core.tracing.truncation import truncate_messages

    messages = [{"role": "user", "content": "a" * 10000}]
    result = truncate_messages(messages, max_length=8000)
    assert len(result[0]["content"]) == 8000


def test_truncate_multiple_messages():
    from src.core.tracing.truncation import truncate_messages

    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "a" * 10000},
        {"role": "assistant", "content": "b" * 5000},
    ]
    result = truncate_messages(messages, max_length=8000)
    assert len(result[0]["content"]) == 13
    assert len(result[1]["content"]) == 8000
    assert len(result[2]["content"]) == 5000
