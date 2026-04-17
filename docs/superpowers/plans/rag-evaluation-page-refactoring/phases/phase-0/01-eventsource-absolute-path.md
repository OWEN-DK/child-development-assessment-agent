# EventSource 相对路径修复 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** EventSource 相对路径修复

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Modify: `frontend/src/features/rag-evaluation/components/UploadDocumentModal.tsx`
- Modify: `frontend/src/lib/constants.ts`
- Test: `frontend/src/__tests__/sse-connection.test.ts`

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

> **需求来源**: spec 文档 `01-phase-0-bug-fixes.md` 中 `2.0.1` 节
> **所属 Phase**: Phase 0
> **根因**: 前端 dev server (5173) 和后端 (8000) 端口不同，SSE 请求走相对路径导致 404

---

## 需求定义

前端 `UploadDocumentModal.tsx` 中使用 `EventSource` 连接 SSE 时使用了相对路径：
```typescript
const sseUrl = `/rag/test/drafts/generate/${res.task_id}/stream`;
const es = new EventSource(sseUrl);
```

开发环境中前端运行在 `localhost:5173`，后端运行在 `localhost:8000`。相对路径 `/rag/test/...` 会请求到 `localhost:5173`，导致 404。

**修复要求**：
1. SSE 连接必须使用绝对路径（含协议、域名、端口）
2. 开发环境和生产环境都能正确解析后端地址
3. 不破坏现有认证机制（EventSource 无法发送自定义 Header，需确认后端 SSE 端点是否要求认证）

---

## 验收标准

- [ ] 开发环境 (5173→8000) SSE 连接成功，能接收到 draft 生成进度事件
- [ ] 生产环境 SSE 连接成功（同域部署时相对路径也可用）
- [ ] 不引入硬编码的域名/端口

---

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `frontend/src/features/rag-evaluation/components/UploadDocumentModal.tsx` | 修改 | EventSource URL 改为绝对路径 |
| `frontend/src/lib/constants.ts` | 修改 | 新增 `API_BASE_URL` 导出（如尚未存在） |

---

## 实现方案

### 前端实现

**步骤 1：确认 `API_BASE_URL` 已定义**

检查 `frontend/src/lib/constants.ts`，确保存在以下导出：

```typescript
// frontend/src/lib/constants.ts
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
```

环境变量 `VITE_API_BASE_URL` 在 `.env.development` 中设置为 `http://localhost:8000`，生产环境留空（同域部署）。

**步骤 2：修改 UploadDocumentModal.tsx 中的 EventSource URL**

找到以下代码（约第 61 行）：
```typescript
const sseUrl = `/rag/test/drafts/generate/${res.task_id}/stream`;
const es = new EventSource(sseUrl);
```

替换为：
```typescript
// 构建绝对路径：开发环境跨域时需要完整 URL，生产环境同域时可省略
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '';
const sseUrl = `${apiBaseUrl}/rag/test/drafts/generate/${res.task_id}/stream`;
const es = new EventSource(sseUrl);
```

**步骤 3：添加环境变量配置**

在 `frontend/.env.development` 中确保存在：
```
VITE_API_BASE_URL=http://localhost:8000
```

在 `frontend/.env.production` 中：
```
VITE_API_BASE_URL=
```

**步骤 4：完善 onerror 处理（附带修复）**

当前 `onerror` 会立即调用 `closeSSE()` 阻止 EventSource 自动重连。改为允许自动重连：

```typescript
es.onerror = () => {
  // EventSource 内置自动重连，onerror 触发时连接已断开
  // 不立即关闭，等待重连成功或用户手动关闭
  // 仅在达到最大重连次数或用户操作时关闭
};
```

如果需要限制重连次数，可以添加计数器：
```typescript
let reconnectAttempts = 0;
const MAX_RECONNECT = 5;

es.onerror = () => {
  reconnectAttempts++;
  if (reconnectAttempts >= MAX_RECONNECT) {
    message.error('SSE 连接失败次数过多，请刷新页面重试');
    closeSSE();
  }
};
```

### 后端配套修改：CORS 配置

开发环境跨域时（前端 5173 → 后端 8000），后端需配置 CORS 允许前端域名。

检查并确认 `backend/src/server.py` 中的 CORS middleware 配置包含前端开发地址：

```python
# backend/src/server.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite 开发服务器
        "http://localhost:3000",   # 备用端口
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

如果已使用环境变量管理 CORS 白名单，确保 `.env.development` 中包含：
```
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

### 认证方案

如果后端 SSE 端点要求认证（JWT Token），由于 EventSource 无法发送自定义 Header，有两种方案：

**方案 A（推荐）：SSE 端点免认证，通过 task_id 鉴权**

SSE 端点通过 `task_id` 判断请求合法性，不需要额外认证。task_id 本身就是临时凭证。

**安全增强措施**：
1. **task_id 使用 UUID v4**：32 位随机字符 + 4 个连字符，猜测概率极低（2^122）
2. **后端验证 task_id 存在性**：查询数据库或 Redis，确认 task_id 对应的任务存在且属于当前用户
3. **task_id 过期时间**：24 小时后自动失效（通过任务创建时间戳判断）
4. **防重放攻击**：任务完成后 task_id 立即失效，不能重复使用

**方案 B：通过 URL 参数传递 Token（不推荐，有安全风险）**

```typescript
const token = localStorage.getItem('token');
const sseUrl = `${apiBaseUrl}/rag/test/drafts/generate/${res.task_id}/stream?token=${token}`;
```

**结论**：采用方案 A + 安全增强措施，后端需实现 task_id 验证逻辑。

---

## 测试方案

### 手动测试

1. 启动前端 `npm run dev`（端口 5173）
2. 启动后端 `uv run start`（端口 8000）
3. 打开浏览器访问 `http://localhost:5173`
4. 上传一份文档，观察 SSE 连接是否成功
5. 确认能接收到 `progress`、`complete`、`error` 事件

### 自动化测试（E2E）

```typescript
// frontend/src/__tests__/sse-connection.test.ts
import { describe, it, expect } from 'vitest';

describe('SSE Connection', () => {
  it('should construct absolute URL correctly in development', () => {
    const apiBaseUrl = 'http://localhost:8000';
    const taskId = 'test-123';
    const expected = `${apiBaseUrl}/rag/test/drafts/generate/${taskId}/stream`;
    
    const actual = `${apiBaseUrl}/rag/test/drafts/generate/${taskId}/stream`;
    expect(actual).toBe(expected);
  });

  it('should use empty base URL in production', () => {
    const apiBaseUrl = '';
    const taskId = 'test-123';
    const expected = `/rag/test/drafts/generate/${taskId}/stream`;
    
    const actual = `${apiBaseUrl}/rag/test/drafts/generate/${taskId}/stream`;
    expect(actual).toBe(expected);
  });
});
```

---

## 注意事项

1. **EventSource 限制**：EventSource 只能发送 GET 请求，不能携带自定义 Header。如果后端 SSE 端点需要认证，必须通过 URL 参数或 cookie 传递。
2. **CORS 配置**：开发环境跨域时，后端需配置 CORS 允许 `http://localhost:5173`。检查 `backend/src/server.py` 中的 CORS middleware 配置。
3. **Vite proxy 不适用**：Vite 的 `server.proxy` 只对 `fetch`/`axios` 生效，对 `EventSource` 无效，必须使用绝对路径。
4. **生产环境**：如果前后端同域部署（Nginx 反向代理），`VITE_API_BASE_URL` 留空即可，相对路径可用。

---

**返回索引：** [Phase 0 总览](../00-overview.md)
