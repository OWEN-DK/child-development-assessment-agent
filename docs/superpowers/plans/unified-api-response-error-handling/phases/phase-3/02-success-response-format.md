# Phase 3-2: 成功响应格式

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `4.2` 节
> **所属 Phase**: Phase 3

## 需求定义

定义所有成功接口的统一响应格式，采用 HTTP 200 + `code: 0` 双确认方案。

## 验收标准

- [ ] 所有成功响应 HTTP 状态码为 200
- [ ] 响应体包含 `code: 0`, `message: "success"`, `data` 三个字段
- [ ] `data` 可为 null、对象、数组
- [ ] 通过 `APIResponse.success(data)` 统一构造

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/schemas/common.py` | 已在 01 中定义 | APIResponse.success() |
| 所有 Controller 文件 | 修改 | 返回改为 APIResponse.success() |

## 实现方案

### 标准成功响应

**HTTP 200**
```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | `int` | 业务状态码，`0` 表示成功 |
| `message` | `string` | 提示信息 |
| `data` | `any` | 业务数据（可为 null、对象、数组） |

### 分页数据扩展格式

```json
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
```

### PaginatedResponse 模型

```python
from typing import Generic, TypeVar, List
from pydantic import BaseModel, Field

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应数据"""
    items: List[T] = Field(description="数据列表")
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页大小")

    @property
    def total_pages(self) -> int:
        """总页数"""
        return (self.total + self.page_size - 1) // self.page_size if self.page_size > 0 else 0
```

### Controller 使用示例

```python
from src.schemas import APIResponse, PaginatedResponse

# 普通列表
@router.get("/documents")
async def list_documents():
    docs = await get_all_documents()
    return APIResponse.success(data={"documents": docs})

# 分页列表
@router.get("/test-cases")
async def list_test_cases(page: int = 1, page_size: int = 20):
    items, total = await get_test_cases_page(page, page_size)
    paginated = PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
    return APIResponse.success(data=paginated)
```

## 改造策略

### 现有接口改造对照表

| 当前返回格式 | 改造后 |
|-------------|--------|
| `return {"status": "ok"}` | `return APIResponse.success()` |
| `return {"tasks": [...]}` | `return APIResponse.success(data={"tasks": [...]})` |
| `return {"documents": [...]}` | `return APIResponse.success(data={"documents": [...]})` |
| `return task_dict` | `return APIResponse.success(data=task_dict)` |
| `response_model=PydanticModel` | `return APIResponse.success(data=model)` |

## 测试方案

1. 所有 GET 接口返回 `{code: 0, data: {...}}`
2. 分页接口返回 `{code: 0, data: {items, total, page, page_size}}`
3. 创建/更新接口返回 `{code: 0, message: "创建成功"}`

## 注意事项

- SSE 流式响应不参与统一包装
- 文件下载接口不参与统一包装
- 文件上传接口参与统一包装，返回 `task_id`
