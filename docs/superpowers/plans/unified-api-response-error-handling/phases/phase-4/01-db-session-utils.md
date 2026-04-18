# Phase 4-1: 数据库 Session 工具

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `5.2.1` 节
> **所属 Phase**: Phase 4

## 需求定义

提取 26 处重复的 SQLAlchemy Session 获取代码至统一工具模块。

## 验收标准

- [ ] `utils/db.py` 创建完成
- [ ] 26 处 `async with async_session_factory()` 替换为 `async with get_db_session()`
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/utils/db.py` | 新增 | 数据库 Session 工具 |
| 所有 Controller 文件 | 修改 | 替换 Session 获取方式 |

## 实现方案

```python
"""
数据库工具模块

统一管理数据库 Session 生命周期，消除重复代码。
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable, Any

from src.core.database import async_session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator:
    """统一数据库会话获取
    
    使用方式：
        async with get_db_session() as session:
            result = await session.execute(select(User))
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def execute_with_session(
    func: Callable, *args: Any, **kwargs: Any
) -> Any:
    """自动管理 session 生命周期的执行器
    
    使用方式：
        result = await execute_with_session(my_service_method, arg1, arg2)
    """
    async with async_session_factory() as session:
        try:
            result = await func(session, *args, **kwargs)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise


async def execute_readonly(
    func: Callable, *args: Any, **kwargs: Any
) -> Any:
    """只读查询执行器（不提交）
    
    使用方式：
        result = await execute_readonly(my_query_method, arg1)
    """
    async with async_session_factory() as session:
        return await func(session, *args, **kwargs)
```

## 替换对照

**替换前**（每个 Controller 重复）：
```python
from src.core.database import async_session_factory

async def some_endpoint():
    async with async_session_factory() as session:
        try:
            # 业务逻辑
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

**替换后**：
```python
from src.utils.db import get_db_session

async def some_endpoint():
    async with get_db_session() as session:
        # 业务逻辑（自动 commit/rollback）
```

## 测试方案

1. Session 自动提交成功
2. 异常时自动回滚
3. 只读查询不提交
4. 并发请求 Session 隔离

## 注意事项

- `get_db_session()` 自动处理 commit/rollback，业务代码无需手动调用
- 只读查询使用 `execute_readonly()` 避免不必要的提交
- 事务边界由调用方控制，工具只负责生命周期管理
