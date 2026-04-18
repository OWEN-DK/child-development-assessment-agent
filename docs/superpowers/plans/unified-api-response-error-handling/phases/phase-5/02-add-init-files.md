# Phase 5-2: 补充 __init__.py

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `6.3.2` 节
> **所属 Phase**: Phase 5

## 需求定义

为缺失 `__init__.py` 的目录创建初始化文件，显式导出公共 API，使其成为正规 Python 包。

## 验收标准

- [ ] `controller/__init__.py` 创建完成
- [ ] `service/__init__.py` 创建完成
- [ ] `utils/__init__.py` 创建完成
- [ ] `core/__init__.py` 创建完成
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/controller/__init__.py` | 新增 | 导出所有路由路由器 |
| `backend/src/service/__init__.py` | 新增 | 导出所有服务单例 |
| `backend/src/utils/__init__.py` | 新增 | 导出常用工具 |
| `backend/src/core/__init__.py` | 新增 | 导出核心模块 |

## 实现方案

### controller/__init__.py

```python
"""Controller 模块，导出所有路由路由器"""

from .task_controller import router as task_router
from .rag_controller import router as rag_router
from .rag_test_controller import router as rag_test_router
from .config_controller import router as config_router
from .monitoring_controller import router as monitoring_router
from .prompt_controller import router as prompt_router
from .health_controller import router as health_router
from .config_management_controller import router as config_mgmt_router
from .prompt_management_controller import router as prompt_mgmt_router
from .rollback_controller import router as rollback_router
from .trend_controller import router as trend_router
from .export_controller import router as export_router
from .tuning_controller import router as tuning_router
from .config_health_controller import router as config_health_router

__all__ = [
    "task_router",
    "rag_router",
    "rag_test_router",
    "config_router",
    "monitoring_router",
    "prompt_router",
    "health_router",
    "config_mgmt_router",
    "prompt_mgmt_router",
    "rollback_router",
    "trend_router",
    "export_router",
    "tuning_router",
    "config_health_router",
]
```

### service/__init__.py

```python
"""Service 模块，导出所有服务单例"""

from .rag_service import rag_service
from .rag_test_manager import rag_test_manager
from .cache_service import cache_service

__all__ = [
    "rag_service",
    "rag_test_manager",
    "cache_service",
]
```

### utils/__init__.py

```python
"""工具模块，导出常用工具"""

from .logger import logger

__all__ = ["logger"]
```

### core/__init__.py

```python
"""核心模块，导出核心组件"""

from .di_container import di_container
from .graph import graph

__all__ = [
    "di_container",
    "graph",
]
```

## 测试方案

1. `from src.controller import rag_router` 导入无错误
2. `from src.service import rag_service` 导入无错误
3. `__all__` 列表与实际导出一致
4. server.py 路由注册正常

## 注意事项

- `__init__.py` 只负责导出，不实现业务逻辑
- 使用 `as` 别名避免命名冲突（如多个 router）
- 延迟导入（函数内 import）仅用于解决循环依赖
