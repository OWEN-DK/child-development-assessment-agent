# Phase 5-6: 拆分 config/__init__.py

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `6.3.6` 节
> **所属 Phase**: Phase 5

## 需求定义

将 614 行的 `config/__init__.py` 按单一职责拆分为 4 个文件，消除混合的配置定义、单例管理、启动初始化等职责。

## 验收标准

- [ ] `config/__init__.py` 拆分为 4 个文件
- [ ] 拆分后 `config/__init__.py` 行数 < 50
- [ ] 所有引用更新为新路径
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/config/__init__.py` | 修改 | 纯聚合导出，< 50 行 |
| `backend/src/config/modules/app.py` | 已存在 | Settings 类定义 |
| `backend/src/config/core/singleton.py` | 新增 | 单例管理 |
| `backend/src/config/core/init.py` | 新增 | 启动初始化 |

## 拆分方案

| 新文件 | 职责 | 预估行数 |
|--------|------|---------|
| `config/modules/app.py` | `Settings` 类定义 | ~200 |
| `config/core/singleton.py` | 单例管理（`get_settings`, `reload_settings`） | ~50 |
| `config/core/init.py` | 应用启动初始化（embedding init, watcher） | ~100 |
| `config/__init__.py` | 纯聚合导出 | ~30 |

## 实现方案

### config/__init__.py（拆分后）

```python
"""
配置模块入口

纯聚合导出，不实现业务逻辑。
"""

from src.config.modules.app import Settings, settings
from src.config.core.singleton import get_settings, reload_settings

__all__ = [
    "Settings",
    "settings",
    "get_settings",
    "reload_settings",
]
```

### config/core/singleton.py

```python
"""
配置单例管理

提供全局配置实例的获取和重载功能。
"""

from src.config.modules.app import Settings

_settings: Settings | None = None


def get_settings() -> Settings:
    """获取全局配置实例"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """重新加载配置"""
    global _settings
    _settings = Settings()
    return _settings
```

### config/core/init.py

```python
"""
应用启动初始化

负责 embedding 初始化、配置监听器等启动时任务。
"""

import asyncio

from src.config.core.singleton import get_settings


async def init_on_startup():
    """应用启动时初始化"""
    settings = get_settings()
    
    # 初始化 embedding
    await _init_embedding(settings)
    
    # 启动配置监听器
    _start_config_watcher(settings)


async def _init_embedding(settings):
    """初始化 Embedding 模型"""
    # embedding 初始化逻辑
    pass


def _start_config_watcher(settings):
    """启动配置变更监听器"""
    # 监听器逻辑
    pass
```

## 测试方案

1. `from src.config import settings` 导入无错误
2. `get_settings()` 返回正确实例
3. `reload_settings()` 重新加载成功
4. `init_on_startup()` 执行正常

## 注意事项

- 拆分后 `config/__init__.py` 仅负责导出
- 单例管理使用模块级变量，避免全局变量污染
- 启动初始化移至 `server.py` lifespan 中调用
