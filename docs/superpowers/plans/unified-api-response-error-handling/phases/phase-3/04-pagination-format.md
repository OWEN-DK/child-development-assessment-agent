# Phase 3-4: 分页数据格式

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `4.2 分页扩展` 节
> **所属 Phase**: Phase 3

## 需求定义

定义统一的分页数据格式，嵌套在 `APIResponse.data` 中。

## 验收标准

- [ ] 分页数据包含 `items`, `total`, `page`, `page_size` 四个字段
- [ ] 嵌套在 `APIResponse.data` 中
- [ ] 提供 `PaginatedResponse` 泛型模型
- [ ] 所有分页接口统一使用此格式

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/schemas/common.py` | 修改 | 添加 PaginatedResponse |

## 实现方案

### PaginatedResponse 模型

```python
from typing import Generic, TypeVar, Any
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应数据，嵌套在 APIResponse.data 中
    
    格式：
    {
        "code": 0,
        "message": "success",
        "data": {
            "items": [...],
            "total": 100,
            "page": 1,
            "page_size": 20
        }
    }
    """
    
    items: list[Any] = Field(default_factory=list, description="当前页数据列表")
    total: int = Field(description="总记录数")
    page: int = Field(ge=1, description="当前页码，从 1 开始")
    page_size: int = Field(ge=1, le=100, description="每页大小")

    @property
    def total_pages(self) -> int:
        """计算总页数"""
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        """是否有下一页"""
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        """是否有上一页"""
        return self.page > 1
```

### Controller 使用示例

```python
from src.schemas import APIResponse, PaginatedResponse

@router.get("/test-cases")
async def list_test_cases(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    test_set_id: str | None = None,
):
    """分页获取测试用例列表"""
    items, total = await get_test_cases(
        page=page,
        page_size=page_size,
        test_set_id=test_set_id,
    )
    
    paginated = PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
    
    return APIResponse.success(data=paginated)
```

### 前端接收格式

```typescript
interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

// API 响应解包后
const response = await apiClient.get("/test-cases");
// response.data = { items: [...], total: 100, page: 1, page_size: 20 }
```

## 测试方案

1. 空列表分页返回 `{items: [], total: 0, page: 1, page_size: 20}`
2. 边界页码校验（page < 1 返回 400）
3. page_size 超限校验（> 100 返回 400）
4. total_pages 计算正确

## 注意事项

- 页码从 1 开始（非 0）
- page_size 上限 100，防止一次性拉取过多数据
- `total_pages`, `has_next`, `has_prev` 为计算属性，不序列化到 JSON（如需序列化需添加 `@computed_field`）
