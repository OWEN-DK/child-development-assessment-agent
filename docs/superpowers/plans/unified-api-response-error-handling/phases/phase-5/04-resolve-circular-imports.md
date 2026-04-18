# Phase 5-4: 解决循环导入

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `6.3.4` 节
> **所属 Phase**: Phase 5

## 需求定义

解决 `config/__init__.py` ↔ `config/core/manager.py` 的循环导入问题，消除脆弱的延迟导入模式。

## 验收标准

- [ ] 无循环导入链
- [ ] 模块可独立 import
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/config/__init__.py` | 修改 | 移除导致循环的导入 |
| `backend/src/config/core/manager.py` | 修改 | 直接导入依赖 |

## 当前循环链

```
config/__init__.py (line 592) → from .core.manager import ConfigManager
config/core/manager.py (line 10) → from src.config import settings
```

## 实现方案

### 解决方案

1. `config/core/manager.py` 中 `from src.config import settings` 改为从 `config/modules/app.py` 直接导入
2. `config/__init__.py` 中的 `config_manager` 导入移至 `server.py` lifespan 中初始化

### 修改前

```python
# config/__init__.py
from .core.manager import ConfigManager  # ← 导致循环

# config/core/manager.py
from src.config import settings  # ← 循环引用
```

### 修改后

```python
# config/__init__.py
# 移除 ConfigManager 导入，改为在 server.py 中初始化

# config/core/manager.py
from src.config.modules.app import settings  # ← 直接导入，打破循环
```

### server.py 中初始化

```python
from src.config.core.manager import ConfigManager

def create_app() -> FastAPI:
    app = FastAPI(...)
    
    # 在 lifespan 中初始化 ConfigManager
    @app.on_event("startup")
    async def startup():
        config_manager = ConfigManager()
        await config_manager.initialize()
    
    return app
```

## 测试方案

1. `import src.config` 无循环导入错误
2. `import src.config.core.manager` 无错误
3. ConfigManager 初始化正常

## 注意事项

- 循环导入通常由模块级导入引起，改为延迟导入或直接导入可解决
- `TYPE_CHECKING` 可用于类型注解的循环引用场景
- 避免在 `__init__.py` 中导入可能产生循环依赖的模块
