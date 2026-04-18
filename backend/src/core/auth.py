"""
Auth module stub - temporary implementation for development
"""

from typing import Optional

from src.schemas import User


async def get_current_user() -> User:
    """Stub dependency that returns a default admin user for development"""
    return User()
