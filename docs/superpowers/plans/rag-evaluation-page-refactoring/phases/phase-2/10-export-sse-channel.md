# 10 - 导出 SSE 通道 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 10 - 导出 SSE 通道

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Test: `tests/test_placeholder.py`

- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

## 目标

为 PDF/CSV/JSON 导出任务提供独立的 SSE 通道，与测试运行通道隔离，避免事件混淆。

## 频道设计

### 频道格式

```
exports:{user_id}
```

使用 `user_id` 而非 `export_id` 作为频道标识：
- **为什么**：一个用户可能同时发起多个导出任务，使用 `user_id` 可以统一接收所有导出完成通知
- **隔离性**：不同用户的导出事件互不干扰

### 事件类型

仅一种事件：`export_ready`

```json
{
  "type": "export_ready",
  "export_id": "uuid-string",
  "format": "pdf",
  "download_url": "/rag/test/exports/uuid-string/download",
  "file_size_bytes": 1048576,
  "expires_at": "2026-04-18T10:00:00Z",
  "timestamp": "2026-04-17T10:05:00Z"
}
```

## 后端实现

### 1. SSE 端点

已在 `04-sse-controller-routes.md` 中定义：

```python
@router.get("/sse/exports")
async def get_export_sse(user_id: str = Query(..., description="用户标识")):
    return sse_response(f"exports:{user_id}")
```

### 2. 导出完成发布

```python
from src.api.sse import SSEPublisher
from fastapi.encoders import jsonable_encoder

async def notify_export_complete(
    user_id: str,
    export_id: str,
    format: str,
    download_url: str,
    file_size_bytes: int,
    expires_at: datetime
):
    """通知用户导出完成"""
    await SSEPublisher.publish(
        f"exports:{user_id}",
        jsonable_encoder({
            "type": "export_ready",
            "export_id": export_id,
            "format": format,
            "download_url": download_url,
            "file_size_bytes": file_size_bytes,
            "expires_at": expires_at
        })
    )
```

### 3. 导出任务流程

```python
async def run_export_task(
    export_id: str,
    user_id: str,
    format: str,
    report_id: str
):
    """导出异步任务"""
    try:
        # 1. 生成导出文件
        file_path = await generate_export_file(format, report_id)
        file_size = os.path.getsize(file_path)

        # 2. 存储到临时目录，设置过期时间
        download_url = f"/rag/test/exports/{export_id}/download"
        expires_at = datetime.now() + timedelta(hours=24)

        # 3. 通知用户
        await notify_export_complete(
            user_id=user_id,
            export_id=export_id,
            format=format,
            download_url=download_url,
            file_size_bytes=file_size,
            expires_at=expires_at
        )

    except Exception as e:
        # 导出失败也通知用户
        await SSEPublisher.publish(
            f"exports:{user_id}",
            jsonable_encoder({
                "type": "export_failed",
                "export_id": export_id,
                "error": str(e)
            })
        )
```

## 前端实现

### 导出 SSE 客户端

```typescript
class ExportSseClient {
  private eventSource: EventSource | null = null;

  connect(userId: string): void {
    const url = `/api/sse/exports?user_id=${userId}`;
    this.eventSource = new EventSource(url);

    this.eventSource.onmessage = (event: MessageEvent) => {
      const data = JSON.parse(event.data);
      if (data.type === 'export_ready') {
        // 显示下载通知
        showDownloadNotification(data);
      }
    };
  }

  disconnect(): void {
    this.eventSource?.close();
    this.eventSource = null;
  }
}
```

### React 集成

在 App 级别连接导出 SSE 通道，全局监听：

```typescript
// frontend/src/App.tsx
useEffect(() => {
  const exportClient = new ExportSseClient();
  exportClient.connect(currentUserId);
  return () => exportClient.disconnect();
}, [currentUserId]);
```

## 与测试运行通道的区别

| 特性 | 测试运行通道 | 导出通道 |
|------|-------------|---------|
| 频道格式 | `test_run:{run_id}` | `exports:{user_id}` |
| 事件数量 | 9 种 | 2 种（export_ready, export_failed） |
| 连接时机 | 进入运行详情页时 | App 级别全局连接 |
| 心跳 | 15 秒 | 复用 SSEPublisher 全局心跳 |
| 断线重连 | 需要（运行中不能丢失进度） | 不需要（导出是瞬时事件） |

## 验收标准

- [ ] 导出完成后，前端在 1 秒内收到通知
- [ ] 多用户并发导出，事件不串台
- [ ] 导出失败时，前端收到错误通知
- [ ] 前端关闭后，导出通道连接正确释放
