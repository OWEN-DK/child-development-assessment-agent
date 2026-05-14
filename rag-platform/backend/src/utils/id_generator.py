"""ID 生成工具模块

统一 ID 生成逻辑，消除重复的 uuid.uuid4() 调用。
"""

import uuid


def generate_id() -> str:
    """生成 UUID 字符串（36 字符，含连字符）

    使用方式：
        task_id = generate_id()
        run_id = generate_id()

    Returns:
        UUID 字符串，如 "550e8400-e29b-41d4-a716-446655440000"
    """
    return str(uuid.uuid4())


def generate_short_id() -> str:
    """生成短 ID（8 字符，不含连字符）

    使用方式：
        short_id = generate_short_id()

    Returns:
        短 UUID 字符串，如 "550e8400"
    """
    return uuid.uuid4().hex[:8]


def generate_prefixed_id(prefix: str) -> str:
    """生成带前缀的 ID

    使用方式：
        task_id = generate_prefixed_id("task")  # "task_550e8400..."

    Args:
        prefix: ID 前缀

    Returns:
        带前缀的 ID 字符串
    """
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def is_valid_uuid(id_str: str) -> bool:
    """校验字符串是否为有效 UUID

    Args:
        id_str: 待校验字符串

    Returns:
        是否为有效 UUID
    """
    try:
        uuid.UUID(id_str)
        return True
    except ValueError:
        return False
