# 05 - PDF 导出（后端异步） Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 05 - PDF 导出（后端异步）

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

> **Phase**: 6
> **需求点**: 5
> **需求来源**: spec `04-frontend-pages.md` §4.10

## 目标

实现 weasyprint + Jinja2 模板的 PDF 异步导出功能。

## 方案设计

### 技术方案

| 项目 | 说明 |
|------|------|
| **技术选型** | weasyprint 库（纯 Python，无需系统依赖） |
| **模板方式** | HTML 模板 + Jinja2 渲染 → weasyprint 转换为 PDF |
| **模板位置** | `backend/src/templates/reports/report_summary.html` |
| **依赖声明** | `uv add weasyprint` |
| **字体处理** | macOS: PingFang SC, Windows: Microsoft YaHei |
| **文件大小** | 不含用例明细约 200-500KB；含 128 条用例明细约 1-2MB |

### 任务存储

导出任务状态存储在 Redis 中：

```
key: export_task:{task_id}
TTL: 24 小时
value: {
  "task_id": "uuid",
  "report_id": "uuid",
  "status": "pending|processing|completed|failed",
  "progress": 0-100,
  "download_url": "/api/exports/{task_id}/download",
  "created_at": "2026-04-16T10:30:00Z",
  "completed_at": null,
  "error": null
}
```

### 并发限制

- 最多 2 个并行 PDF 导出任务
- 超出任务排队等待
- 单个任务超时 60 秒

### Service 层实现

```python
# backend/src/service/export_service.py

import asyncio
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader

class ExportService:
    def __init__(self, redis_client, session_factory):
        self._redis = redis_client
        self._session_factory = session_factory
        self._semaphore = asyncio.Semaphore(2)  # 最多 2 个并行
        self._queue = asyncio.Queue()
    
    async def create_export_task(self, report_id: str) -> dict:
        """创建导出任务"""
        task_id = str(uuid4())
        task_data = {
            "task_id": task_id,
            "report_id": report_id,
            "status": "pending",
            "progress": 0,
            "created_at": datetime.utcnow().isoformat()
        }
        await self._redis.set(
            f"export_task:{task_id}",
            json.dumps(task_data),
            ex=86400  # 24 小时
        )
        
        # 加入队列
        await self._queue.put(task_id)
        
        # 启动后台处理
        asyncio.create_task(self._process_queue())
        
        return {"task_id": task_id, "status": "pending"}
    
    async def _process_queue(self):
        """处理导出队列"""
        async with self._semaphore:
            task_id = await self._queue.get()
            try:
                await self._generate_pdf(task_id)
            except asyncio.TimeoutError:
                await self._update_task_status(task_id, "failed", error="导出超时 (60s)")
            except Exception as e:
                await self._update_task_status(task_id, "failed", error=str(e))
            finally:
                self._queue.task_done()
    
    async def _generate_pdf(self, task_id: str):
        """生成 PDF"""
        await self._update_task_status(task_id, "processing", progress=10)
        
        # 获取报告数据
        async with self._session_factory() as session:
            report = await get_report_with_details(task_id, session)
        
        await self._update_task_status(task_id, "processing", progress=30)
        
        # 渲染 HTML 模板
        env = Environment(loader=FileSystemLoader("src/templates/reports"))
        template = env.get_template("report_summary.html")
        html_content = template.render(report=report)
        
        await self._update_task_status(task_id, "processing", progress=60)
        
        # 转换为 PDF
        pdf_file = HTML(string=html_content).write_pdf(
            presentational_hints=True,
            stylesheets=[
                CSS(string="""
                    @font-face {
                        font-family: 'ChineseFont';
                        src: local('PingFang SC'), local('Microsoft YaHei');
                    }
                    body { font-family: 'ChineseFont', sans-serif; }
                """)
            ]
        )
        
        await self._update_task_status(task_id, "processing", progress=90)
        
        # 存储 PDF 文件（本地或 OSS）
        file_path = f"exports/{task_id}.pdf"
        await save_pdf_file(file_path, pdf_file)
        
        await self._update_task_status(
            task_id,
            "completed",
            progress=100,
            download_url=f"/api/exports/{task_id}/download"
        )
    
    async def _update_task_status(self, task_id: str, status: str, **kwargs):
        """更新任务状态"""
        task_data = json.loads(await self._redis.get(f"export_task:{task_id}"))
        task_data.update({"status": status, **kwargs})
        if status == "completed":
            task_data["completed_at"] = datetime.utcnow().isoformat()
        await self._redis.set(f"export_task:{task_id}", json.dumps(task_data), ex=86400)
```

### API 端点

```
POST /api/reports/{report_id}/export
Response: { "task_id": "uuid", "status": "pending" }

GET /api/exports/{task_id}/status
Response: { "status": "pending|processing|completed|failed", "progress": 60 }

GET /api/exports/{task_id}/download
Response: PDF 文件流（仅当 status=completed 时可用）
```

### HTML 模板结构

```html
<!-- backend/src/templates/reports/report_summary.html -->
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; }
    .metrics { display: flex; gap: 20px; }
    .metric { text-align: center; padding: 10px; border: 1px solid #ddd; }
  </style>
</head>
<body>
  <h1>评估报告 {{ report.id }}</h1>
  
  <h2>指标总览</h2>
  <div class="metrics">
    <div class="metric">P@5: {{ report.metrics.p_at_5 }}</div>
    <div class="metric">R@5: {{ report.metrics.r_at_5 }}</div>
    <div class="metric">F1: {{ report.metrics.f1 }}</div>
  </div>
  
  <h2>校验结果摘要</h2>
  {% for layer in report.validation_results %}
    <h3>{{ layer.name }}</h3>
    <p>问题数: {{ layer.issue_count }}, 建议数: {{ layer.suggestion_count }}</p>
  {% endfor %}
  
  <h2>调优建议</h2>
  {% for suggestion in report.suggestions %}
    <p>{{ suggestion.param_name }}: {{ suggestion.current_value }} → {{ suggestion.suggested_value }}</p>
  {% endfor %}
</body>
</html>
```

### SSE 事件推送

任务完成后，通过 SSE 推送 `export_ready` 事件：

```json
{
  "event": "export_ready",
  "task_id": "uuid",
  "download_url": "/api/exports/{task_id}/download",
  "timestamp": "2026-04-16T10:35:00Z"
}
```

### 验收标准

- [ ] PDF 导出为异步任务
- [ ] 最多 2 个并行导出任务
- [ ] 单个任务超时 60 秒
- [ ] 任务状态存储在 Redis（TTL 24 小时）
- [ ] 完成后通过 SSE 推送 export_ready 事件
- [ ] PDF 包含中文，字体正确
- [ ] 下载端点返回 PDF 文件流
