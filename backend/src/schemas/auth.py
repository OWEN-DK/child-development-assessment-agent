"""认证模块模型

包含认证相关的 Pydantic 模型：
- User: 用户模型
"""

from typing import Optional

from pydantic import BaseModel


class User(BaseModel):
    """用户模型"""

    id: str = "1"
    username: str = "admin"
    email: Optional[str] = "admin@example.com"
    is_authenticated: bool = True
