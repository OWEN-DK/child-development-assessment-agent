# Phase 4-8: 认证辅助工具

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `5.2.6` 节
> **所属 Phase**: Phase 4

## 需求定义

提取 4 处重复的用户获取代码（`current_user.username if current_user else "system"`）至统一工具模块。

## 验收标准

- [ ] `utils/auth_helpers.py` 创建完成
- [ ] 4 处用户获取替换为 `get_user_id()`
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/utils/auth_helpers.py` | 新增 | 认证辅助工具 |
| 多个 Controller/Service 文件 | 修改 | 替换用户获取代码 |

## 实现方案

```python
"""
认证辅助工具模块

统一用户信息获取逻辑，消除重复的 current_user 判断代码。
"""

from typing import Optional, Any


def get_user_id(current_user: Any | None) -> str:
    """获取当前用户 ID
    
    使用方式：
        user_id = get_user_id(current_user)
    
    Args:
        current_user: 当前用户对象（可能为 None）
    
    Returns:
        用户 ID，未登录返回 "system"
    """
    if current_user is None:
        return "system"
    return getattr(current_user, "id", None) or getattr(current_user, "username", "system")


def get_username(current_user: Any | None) -> str:
    """获取当前用户名
    
    Args:
        current_user: 当前用户对象
    
    Returns:
        用户名，未登录返回 "system"
    """
    if current_user is None:
        return "system"
    return getattr(current_user, "username", "system")


def is_authenticated(current_user: Any | None) -> bool:
    """检查用户是否已认证
    
    Args:
        current_user: 当前用户对象
    
    Returns:
        是否已认证
    """
    return current_user is not None


def require_auth(current_user: Any | None) -> None:
    """要求用户已认证，否则抛出异常
    
    使用方式：
        require_auth(current_user)
    
    Raises:
        UnauthorizedException: 用户未认证
    """
    from src.utils.exceptions import UnauthorizedException
    
    if current_user is None:
        raise UnauthorizedException()
```

## 替换对照

**替换前**：
```python
# 4 处重复
created_by = current_user.username if current_user else "system"
updated_by = current_user.username if current_user else "system"
```

**替换后**：
```python
from src.utils.auth_helpers import get_user_id, get_username, require_auth

created_by = get_username(current_user)
updated_by = get_username(current_user)

# 或要求认证
require_auth(current_user)
```

## 测试方案

1. 已登录用户返回正确 ID/用户名
2. 未登录返回 "system"
3. `is_authenticated` 判断正确
4. `require_auth` 未登录抛出 UnauthorizedException

## 注意事项

- 用户对象可能没有 `id` 字段，fallback 到 `username`
- "system" 是默认值，用于后台任务或匿名操作
- `require_auth` 应在 Controller 层调用，Service 层使用 `get_user_id`
