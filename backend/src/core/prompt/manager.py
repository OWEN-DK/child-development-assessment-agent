"""
向后兼容模块：PromptManager 已拆分为子服务模块。
此文件保留原有导入路径的兼容性。
"""
from src.core.prompt_impl import (ABTestManager, PromptManager, PromptStorage,
                                  prompt_manager)

__all__ = [
    "PromptManager",
    "PromptStorage",
    "ABTestManager",
    "prompt_manager",
]
