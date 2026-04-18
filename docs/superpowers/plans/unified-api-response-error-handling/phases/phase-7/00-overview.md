# Phase 7 - 错误码与后端实现

> **本文档包含**: Phase 7 总览、需求点清单、验收标准、实施顺序

---

## 目标

建立统一的错误码字典，实现全局异常处理器，注册响应包装中间件，完成前后端错误码对齐。

---

## 需求点清单

| # | 需求点名称 | 实施文件 | 预估工作量 |
|---|-----------|---------|-----------|
| 1 | 错误码分段定义 | `01-error-code-segmentation.md` | 小 |
| 2 | 通用错误码 | `02-common-error-codes.md` | 小 |
| 3 | 模块错误码 | `03-module-error-codes.md` | 中 |
| 4 | AppException 层级 | `04-app-exception-hierarchy.md` | 中 |
| 5 | 全局异常处理器 | `05-global-exception-handler.md` | 中 |
| 6 | 响应包装中间件 | `06-response-wrapper-middleware.md` | 中 |

---

## 验收标准

- [ ] 错误码分段：10000-10999 通用，11000-16999 各模块
- [ ] 通用错误码 10 个定义完整（SUCCESS, INVALID_PARAMS, UNAUTHORIZED, 等）
- [ ] 各模块错误码定义完整（RAG 12000+, 测试 13000+, 配置 14000+, 等）
- [ ] `AppException` 基类及子类定义完整
- [ ] 全局异常处理器注册（AppException, HTTPException, RequestValidationError, Exception）
- [ ] ResponseWrapperMiddleware 注册，自动包装成功响应
- [ ] 前端错误码映射表建立

---

## 错误码分段

| 范围 | 模块 | 说明 |
|------|------|------|
| `0` | - | 成功 |
| `10000-10999` | 通用错误 | 参数校验、权限、系统异常等 |
| `11000-11999` | 评估模块 | 儿童评估相关 |
| `12000-12999` | RAG 知识库模块 | 文档上传、检索、分块等 |
| `13000-13999` | RAG 测试模块 | 测试集、用例、运行、报告等 |
| `14000-14999` | 配置管理模块 | 系统配置、校验、回滚等 |
| `15000-15999` | 提示词管理模块 | Prompt 版本、A/B 测试等 |
| `16000-16999` | 监控模块 | LLM 调用统计、追踪等 |

---

## 实施顺序

1. 定义错误码分段 → 2. 定义通用错误码 → 3. 定义模块错误码 → 4. 实现 AppException 层级 → 5. 实现全局异常处理器 → 6. 实现响应包装中间件

---

**下一步**: [01-error-code-segmentation.md](./01-error-code-segmentation.md)
