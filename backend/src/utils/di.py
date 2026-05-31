"""DI 辅助函数

提供便捷的依赖获取方法
"""

def get_task_state_service():
    """获取 TaskStateService 实例"""
    from src.core.di_container import injector
    from src.service.task_state_service import TaskStateService
    
    return injector.get(TaskStateService)


def get_embedding_helper():
    """获取 EmbeddingHelper 实例"""
    from src.core.di_container import injector
    from src.utils.embedding_helper import EmbeddingHelper

    return injector.get(EmbeddingHelper)
