# Phase 3 - 统一响应格式

> **本文档包含**: Phase 3 总览、需求点清单、验收标准、实施顺序

---

## 目标

定义统一的 API 响应格式，采用国内常见双字段方案：HTTP 状态码保持语义，业务错误码使用 `code`（数字）+ `error_code`（字符串）。

---

## 需求点清单

| # | 需求点名称 | 实施文件 | 预估工作量 |
|---|-----------|---------|-----------|
| 1 | APIResponse 模型定义 | `01-api-response-model.md` | 小 |
| 2 | 成功响应格式 | `02-success-response-format.md` | 小 |
| 3 | 错误响应格式 | `03-error-response-format.md` | 小 |
| 4 | 分页数据格式 | `04-pagination-format.md` | 小 |
| 5 | HTTP 状态码映射 | `05-http-status-mapping.md` | 小 |

---

## 验收标准

- [ ] `APIResponse` 模型定义正确，包含 `success()` 和 `error()` 类方法
- [ ] 成功响应：`{code: 0, message: "success", data: {...}}`
- [ ] 错误响应：`{code, message, error_code, details?, trace_id?}`
- [ ] 分页数据：`{items: [...], total, page, page_size}`
- [ ] HTTP 状态码与业务码映射正确（200/400/401/403/404/409/429/500/503）

---

## 响应格式策略

- **HTTP 状态码**：保持 HTTP 语义（200 成功、4xx 客户端错误、5xx 服务端错误）
- **业务错误码**：`code`（数字）+ `error_code`（字符串）双字段

---

## 实施顺序

1. 定义 APIResponse 模型 → 2. 定义成功响应 → 3. 定义错误响应 → 4. 定义分页格式 → 5. 定义 HTTP 映射

---

**下一步**: [01-api-response-model.md](./01-api-response-model.md)
