"""序列化器工具模块

统一 ORM 模型转字典逻辑，消除重复的 datetime/enum 安全转换代码。
"""

from datetime import date, datetime
from enum import Enum
from functools import lru_cache
from typing import Any, Callable, Optional


def safe_isoformat(dt: datetime | date | None) -> str | None:
    """安全转换 datetime 为 ISO 格式字符串

    使用方式：
        "created_at": safe_isoformat(item.created_at)

    Args:
        dt: datetime 或 date 对象

    Returns:
        ISO 格式字符串，None 则返回 None
    """
    if dt is None:
        return None
    return dt.isoformat()


def safe_enum_value(enum_val: Enum | None) -> str | None:
    """安全转换 enum 为字符串值

    使用方式：
        "status": safe_enum_value(item.status)

    Args:
        enum_val: Enum 对象

    Returns:
        enum 的 value，None 则返回 None
    """
    return enum_val.value if enum_val is not None else None


def safe_float(value: Any) -> float | None:
    """安全转换值为 float

    使用方式：
        "price": safe_float(item.price)

    Args:
        value: 数值或 None

    Returns:
        float 值，None 则返回 None
    """
    if value is None:
        return None
    return float(value)


def model_to_dict(
    model: Any,
    fields: Optional[dict[str, Optional[Callable]]] = None,
    exclude: Optional[set[str]] = None,
) -> dict[str, Any]:
    """ORM 模型转字典

    使用方式：
        # 方式 1：指定字段和转换器
        model_to_dict(item, fields={
            "id": None,
            "name": None,
            "created_at": safe_isoformat,
            "status": safe_enum_value,
        })

        # 方式 2：自动转换所有字段（排除内部字段）
        model_to_dict(item)

    Args:
        model: SQLAlchemy ORM 模型实例
        fields: 字段名 -> 转换函数的映射，None 则自动转换
        exclude: 需要排除的字段集合

    Returns:
        字典
    """
    if fields is not None:
        result = {}
        for field_name, converter in fields.items():
            value = getattr(model, field_name, None)
            result[field_name] = converter(value) if converter else value
        return result

    # 自动模式：排除内部字段
    exclude = exclude or {"_sa_instance_state"}
    return {
        k: v for k, v in model.__dict__.items()
        if not k.startswith("_") and k not in exclude
    }


def serialize_datetime_fields(
    data: dict[str, Any],
    field_names: list[str],
) -> dict[str, Any]:
    """批量序列化字典中的 datetime 字段

    使用方式：
        data = serialize_datetime_fields(
            {"id": 1, "created_at": dt, "updated_at": dt2},
            ["created_at", "updated_at"],
        )

    Args:
        data: 原始字典
        field_names: 需要序列化的字段名列表

    Returns:
        序列化后的字典
    """
    for field in field_names:
        if field in data:
            data[field] = safe_isoformat(data[field])
    return data


def serialize_enum_fields(
    data: dict[str, Any],
    field_names: list[str],
) -> dict[str, Any]:
    """批量序列化字典中的 enum 字段

    Args:
        data: 原始字典
        field_names: 需要序列化的字段名列表

    Returns:
        序列化后的字典
    """
    for field in field_names:
        if field in data:
            data[field] = safe_enum_value(data[field])
    return data


def create_serializer(
    model_class: Any,
    field_config: dict[str, Optional[Callable]],
) -> Callable:
    """创建序列化器工厂函数

    消除重复的手动构造字典代码。

    使用方式：
        # 定义序列化器（模块级别）
        serialize_test_case = create_serializer(
            TestCase,
            {
                "id": None,
                "query": None,
                "age": float,
                "domain": safe_enum_value,
                "created_at": safe_isoformat,
            }
        )

        # 使用
        result = serialize_test_case(test_case)

    Args:
        model_class: ORM 模型类（用于类型提示）
        field_config: 字段名 -> 转换函数的映射

    Returns:
        序列化函数
    """
    @lru_cache(maxsize=1)
    def get_field_names():
        return list(field_config.keys())

    def serialize(model: Any) -> dict[str, Any]:
        if model is None:
            return {}
        return model_to_dict(model, fields=field_config)

    return serialize


def serialize_list_field(value: list | None) -> str | None:
    """序列化列表字段为 JSON 字符串

    使用方式：
        "topics": serialize_list_field(item.topics)

    Args:
        value: 列表或 None

    Returns:
        JSON 字符串或 None
    """
    import json

    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)

