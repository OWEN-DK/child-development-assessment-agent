# Phase 4-7: ID 生成工具

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `5.2.6` 节
> **所属 Phase**: Phase 4

## 需求定义

提取 15 处重复的 `str(uuid.uuid4())` ID 生成代码至统一工具模块。

## 验收标准

- [ ] `utils/id_generator.py` 创建完成
- [ ] 15 处 ID 生成替换为 `generate_id()`
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/utils/id_generator.py` | 新增 | ID 生成工具 |
| 多个 Service/Controller 文件 | 修改 | 替换 ID 生成代码 |

## 实现方案

```python
"""
ID 生成工具模块

统一 ID 生成逻辑，消除重复的 uuid.uuid4() 调用。
"""

import uuid


def generate_id() -> str:
    """生成 UUID 字符串（36 字符，含连字符）
    
    使用方式：
        task_id = generate_id()
        run_id = generate_id()
    
    Returns:
        UUID 字符串，如 "550e8400-e29b-41d4-a716-446655440000"
    """
    return str(uuid.uuid4())


def generate_short_id() -> str:
    """生成短 ID（8 字符，不含连字符）
    
    使用方式：
        short_id = generate_short_id()
    
    Returns:
        短 UUID 字符串，如 "550e8400"
    """
    return uuid.uuid4().hex[:8]


def generate_prefixed_id(prefix: str) -> str:
    """生成带前缀的 ID
    
    使用方式：
        task_id = generate_prefixed_id("task")  # "task_550e8400..."
    
    Args:
        prefix: ID 前缀
    
    Returns:
        带前缀的 ID 字符串
    """
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def is_valid_uuid(id_str: str) -> bool:
    """校验字符串是否为有效 UUID
    
    Args:
        id_str: 待校验字符串
    
    Returns:
        是否为有效 UUID
    """
    try:
        uuid.UUID(id_str)
        return True
    except ValueError:
        return False
```

## 替换对照

**替换前**：
```python
import uuid

# 15 处重复
task_id = str(uuid.uuid4())
run_id = str(uuid.uuid4())
```

**替换后**：
```python
from src.utils.id_generator import generate_id, generate_short_id, generate_prefixed_id

task_id = generate_id()
short_id = generate_short_id()
prefixed_id = generate_prefixed_id("task")
```

## 测试方案

1. `generate_id()` 返回 36 字符 UUID
2. `generate_short_id()` 返回 8 字符
3. `generate_prefixed_id("task")` 返回 "task_xxx" 格式
4. `is_valid_uuid` 校验正确
5. 生成的 ID 全局唯一

## 注意事项

- UUID v4 是随机生成，碰撞概率极低
- 短 ID 适用于 URL 参数等需要简洁的场景
- 带前缀 ID 适用于需要区分资源类型的场景
