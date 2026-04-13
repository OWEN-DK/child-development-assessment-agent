"""
Auth module stub - temporary implementation for development
"""

from typing import Optional
from pydantic import BaseModel


class User(BaseModel):
    """Stub user model"""

    id: str = "1"
    username: str = "admin"
    email: Optional[str] = "admin@example.com"
    is_authenticated: bool = True


async def get_current_user() -> User:
    """Stub dependency that returns a default admin user for development"""
    return User()
