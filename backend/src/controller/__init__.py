"""Controller 模块，导出所有路由路由器"""

from .config_controller import router as config_router
from .config_health_controller import router as config_health_router
from .config_management_controller import router as config_mgmt_router
from .export_controller import router as export_router
from .health_controller import router as health_router
from .monitoring_controller import router as monitoring_router
from .prompt_controller import router as prompt_router
from .prompt_management_controller import router as prompt_mgmt_router
from .rag_controller import router as rag_router
from .rag_test_controller import router as rag_test_router
from .rollback_controller import router as rollback_router
from .task_controller import router as task_router
from .trend_controller import router as trend_router
from .tuning_controller import router as tuning_router

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
