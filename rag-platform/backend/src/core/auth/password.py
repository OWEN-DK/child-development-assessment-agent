"""密码哈希与验证

使用 bcrypt 算法进行密码哈希。
"""
import bcrypt


def hash_password(raw_password: str) -> str:
    """将明文密码哈希为 bcrypt hash

    Args:
        raw_password: 明文密码

    Returns:
        bcrypt hash 字符串
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(raw_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(raw_password: str, hashed_password: str) -> bool:
    """验证明文密码是否匹配 hash

    Args:
        raw_password: 明文密码
        hashed_password: bcrypt hash

    Returns:
        匹配返回 True，否则 False
    """
    return bcrypt.checkpw(
        raw_password.encode("utf-8"), hashed_password.encode("utf-8")
    )
