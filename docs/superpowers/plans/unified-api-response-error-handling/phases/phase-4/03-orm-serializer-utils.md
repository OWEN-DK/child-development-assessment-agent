# Phase 4-3: ORM 序列化工具

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `5.2.3` 节
> **所属 Phase**: Phase 4

## 需求定义

提取 30+ 处重复的 ORM 模型转字典代码（datetime/enum 安全转换）至统一工具模块。

## 验收标准

- [ ] `utils/serializers.py` 创建完成
- [ ] 30+ 处 ORM 序列化替换为工具函数
- [ ] 无 `datetime.utcnow()` 残留
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/utils/serializers.py` | 新增 | ORM 序列化工具 |
| 所有 Controller/Service 文件 | 修改 | 替换 ORM 序列化代码 |

## 实现方案

```python
"""
序列化器工具模块

统一 ORM 模型转字典逻辑，消除重复的 datetime/enum 安全转换代码。
"""

from datetime import datetime, date
from enum import Enum
from typing import Any, Optional, Callable


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
    if isinstance(dt, datetime):
        return dt.isoformat()
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
```

## 替换对照

**替换前**（重复的 datetime/enum 转换）：
```python
# 重复的 datetime 安全转换
"created_at": item.created_at.isoformat() if item.created_at else None,
"updated_at": item.updated_at.isoformat() if item.updated_at else None,

# 重复的 enum 安全转换
"status": item.status.value if item.status else None,
"source_type": item.source_type.value if item.source_type else None,
```

**替换后**：
```python
from src.utils.serializers import safe_isoformat, safe_enum_value, model_to_dict

# 方式 1：手动转换
{
    "created_at": safe_isoformat(item.created_at),
    "status": safe_enum_value(item.status),
}

# 方式 2：使用 model_to_dict
model_to_dict(item, fields={
    "id": None,
    "name": None,
    "created_at": safe_isoformat,
    "status": safe_enum_value,
})
```

## 测试方案

1. `safe_isoformat(None)` 返回 None
2. `safe_isoformat(datetime(2024, 1, 1))` 返回 "2024-01-01T00:00:00"
3. `safe_enum_value(None)` 返回 None
4. `model_to_dict` 正确排除内部字段
5. 批量序列化函数正确

## 注意事项

- datetime 转换需处理时区信息（带时区的 datetime 也支持）
- enum 转换使用 `.value` 属性，确保所有 Enum 有 value
- `model_to_dict` 自动排除 `_sa_instance_state` 等 SQLAlchemy 内部字段
