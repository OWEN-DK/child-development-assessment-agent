"""ORM 模型 → Pydantic Schema 统一映射工具

职责：
1. 处理 Enum 值转换（ORM Enum → Python str）
2. 处理 JSON 字段序列化/反序列化（MySQL JSON → Python dict/list）
3. 处理时间格式转换（datetime → ISO 8601 str）
4. 处理 None 值默认化
"""

from datetime import datetime
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase

T = TypeVar("T", bound=BaseModel)


class OrmMapper:
    """ORM 模型 → Pydantic Schema 统一映射工具"""

    _EXCLUDE_ATTRS = {"_sa_instance_state", "_sa_class_manager"}

    @staticmethod
    def safe_enum_value(val: Any) -> Any:
        """Enum 安全取值，非 Enum 原样返回"""
        if val is None:
            return None
        if isinstance(val, Enum):
            return val.value
        return val

    @staticmethod
    def safe_isoformat(val: datetime | None) -> str | None:
        """datetime 安全转 ISO 字符串"""
        if val is None:
            return None
        return val.isoformat()

    @staticmethod
    def _extract_orm_attrs(orm_obj: DeclarativeBase) -> dict[str, Any]:
        """提取 ORM 对象的列属性，跳过 SQLAlchemy 内部属性"""
        result = {}
        for key in dir(orm_obj):
            if key in OrmMapper._EXCLUDE_ATTRS:
                continue
            if key.startswith("_"):
                continue
            value = getattr(orm_obj, key, None)
            result[key] = value
        return result

    @staticmethod
    def _transform_value(value: Any) -> Any:
        """转换单个值：Enum→value, datetime→ISO"""
        if value is None:
            return None
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    @staticmethod
    def to_read(orm_obj: DeclarativeBase, schema_cls: type[T]) -> T:
        """通用 ORM→Pydantic 转换

        自动提取 ORM 列属性，跳过 SQLAlchemy 内部属性。
        Enum 字段自动取 .value。
        datetime 字段自动转 ISO 格式字符串。

        Args:
            orm_obj: ORM 模型实例
            schema_cls: 目标 Pydantic Schema 类

        Returns:
            Pydantic Schema 实例
        """
        attrs = OrmMapper._extract_orm_attrs(orm_obj)
        transformed = {
            k: OrmMapper._transform_value(v) for k, v in attrs.items()
        }
        return schema_cls.model_validate(transformed)

    @staticmethod
    def to_read_list(
        orm_objs: list[DeclarativeBase], schema_cls: type[T]
    ) -> list[T]:
        """批量转换 ORM 列表为 Pydantic Schema 列表"""
        return [OrmMapper.to_read(obj, schema_cls) for obj in orm_objs]
