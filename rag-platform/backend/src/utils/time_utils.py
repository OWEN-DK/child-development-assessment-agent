"""时间处理工具模块

统一时间获取、范围计算、格式化等操作，消除 utcnow/now 混用问题。
"""

from datetime import datetime, timedelta, timezone


def utc_now() -> datetime:
    """获取当前 UTC 时间（带时区信息）

    使用方式：
        now = utc_now()

    Returns:
        带时区信息的当前 UTC 时间
    """
    return datetime.now(timezone.utc)


def time_range(
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
) -> tuple[datetime, datetime]:
    """获取从 N 天前到现在的时间范围

    使用方式：
        start, end = time_range(days=7)  # 7 天前到现在

    Args:
        days: 天数
        hours: 小时数
        minutes: 分钟数

    Returns:
        (start_time, end_time) 元组
    """
    end = utc_now()
    start = end - timedelta(days=days, hours=hours, minutes=minutes)
    return start, end


def safe_timestamp(dt: datetime | None) -> str | None:
    """安全转换 datetime 为 ISO 格式时间戳字符串

    使用方式：
        "created_at": safe_timestamp(item.created_at)

    Args:
        dt: datetime 对象

    Returns:
        ISO 格式字符串，None 则返回 None
    """
    return dt.isoformat() if dt is not None else None


def add_time(
    dt: datetime,
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    seconds: int = 0,
) -> datetime:
    """在指定时间上增加时间段

    Args:
        dt: 基准时间
        days: 天数
        hours: 小时数
        minutes: 分钟数
        seconds: 秒数

    Returns:
        增加后的时间
    """
    return dt + timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


def is_expired(dt: datetime, ttl_seconds: int) -> bool:
    """检查时间是否已过期

    使用方式：
        if is_expired(cache_time, ttl_seconds=300):
            # 缓存已过期

    Args:
        dt: 基准时间
        ttl_seconds: 过期时间（秒）

    Returns:
        是否已过期
    """
    return utc_now() > add_time(dt, seconds=ttl_seconds)


def format_duration(seconds: float) -> str:
    """格式化时间间隔为可读字符串

    使用方式：
        format_duration(3661)  # "1h 1m 1s"

    Args:
        seconds: 秒数

    Returns:
        可读字符串
    """
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m {s}s"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m}m"
