"""SQLAlchemy 声明式基类

所有 Model 共享同一个 Base，避免注册表冲突。
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass
