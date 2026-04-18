# Phase 4-2: 错误处理工具

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `5.2.2` 节
> **所属 Phase**: Phase 4

## 需求定义

提取 100+ 处重复的 try/except + logger + HTTPException 模板至统一工具模块。

## 验收标准

- [ ] `utils/response.py` 创建完成
- [ ] 100+ 处错误处理模板替换为工具函数
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/utils/response.py` | 新增 | 错误处理工具 |
| 所有 Controller/Service 文件 | 修改 | 替换错误处理模板 |

## 实现方案

```python
"""
响应与错误处理工具模块

统一错误处理模式，消除重复的 try/except + logger + HTTPException 模板。
"""

from typing import Optional, Any

from src.utils.logger import logger
from src.utils.exceptions import (
    AppException,
    InternalServerErrorException,
    ResourceNotFoundException,
)


def handle_api_error(e: Exception, action: str, include_detail: bool = True) -> None:
    """统一错误处理
    
    使用方式：
        try:
            result = do_something()
        except Exception as e:
            handle_api_error(e, "获取数据")
    
    Args:
        e: 捕获的异常
        action: 操作描述（如"获取数据"、"创建测试用例"）
        include_detail: 是否在错误信息中包含异常详情
    """
    logger.error(f"{action}失败: {e}", exc_info=True)
    if include_detail:
        raise InternalServerErrorException(f"{action}失败: {str(e)}")
    raise InternalServerErrorException(f"{action}失败")


def not_found(resource: str, detail: Optional[dict] = None) -> None:
    """资源不存在快捷函数
    
    使用方式：
        if not item:
            not_found("测试用例", {"id": case_id})
    
    Args:
        resource: 资源名称（如"测试用例"、"文档"）
        detail: 额外上下文信息
    """
    raise ResourceNotFoundException(
        error_code=f"{resource.upper()}_NOT_FOUND",
        message=f"{resource}不存在",
        details=detail,
    )


def server_error(message: str = "系统内部异常，请稍后重试", details: Optional[dict] = None) -> None:
    """系统错误快捷函数
    
    Args:
        message: 错误信息
        details: 额外上下文信息
    """
    raise InternalServerErrorException(message=message)


def require(condition: bool, exception: AppException) -> None:
    """条件校验快捷函数
    
    使用方式：
        require(user is not None, UnauthorizedException())
        require(item.owner == current_user, ForbiddenException())
    
    Args:
        condition: 校验条件
        exception: 条件不满足时抛出的异常
    """
    if not condition:
        raise exception
```

## 替换对照

**替换前**（三种风格混用）：
```python
# 风格 1：带详情
except Exception as e:
    logger.error(f"获取数据失败: {e}")
    raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")

# 风格 2：不带详情
except Exception as e:
    logger.error("获取数据失败")
    raise HTTPException(status_code=500, detail="获取数据失败")

# 风格 3：裸错误
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

**替换后**（统一风格）：
```python
from src.utils.response import handle_api_error, not_found, require

try:
    result = do_something()
except Exception as e:
    handle_api_error(e, "获取数据")

# 或直接抛出
if not item:
    not_found("测试用例", {"id": case_id})

# 条件校验
require(user is not None, UnauthorizedException())
```

## 测试方案

1. `handle_api_error` 记录日志并抛出 InternalServerErrorException
2. `not_found` 抛出 ResourceNotFoundException 且 error_code 正确
3. `require` 条件不满足时抛出指定异常
4. 日志格式统一

## 注意事项

- `handle_api_error` 默认包含异常详情，生产环境可配置关闭
- `not_found` 的 resource 参数会自动转为大写作为 error_code 后缀
- 所有函数抛出 AppException 子类，确保被全局异常处理器捕获
