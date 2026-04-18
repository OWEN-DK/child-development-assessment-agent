# Phase 7-1: 错误码分段定义

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `8.1` 节
> **所属 Phase**: Phase 7

## 需求定义

建立统一的错误码分段体系，按模块分配错误码范围，避免冲突。

## 验收标准

- [ ] 错误码分段表定义完整
- [ ] 各模块范围不重叠
- [ ] 预留足够扩展空间（每模块 1000 个码）

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/utils/error_codes.py` | 新增 | 错误码常量定义 |

## 实现方案

### 错误码分段表

```python
"""
错误码分段定义

按模块分配错误码范围，每模块 1000 个码。
"""

# === 错误码范围分配 ===

# 0: 成功
ERROR_CODE_SUCCESS = 0

# 10000-10999: 通用错误
ERROR_CODE_RANGE_COMMON_START = 10000
ERROR_CODE_RANGE_COMMON_END = 10999

# 11000-11999: 评估模块 (Assessment)
ERROR_CODE_RANGE_ASSESSMENT_START = 11000
ERROR_CODE_RANGE_ASSESSMENT_END = 11999

# 12000-12999: RAG 知识库模块
ERROR_CODE_RANGE_RAG_START = 12000
ERROR_CODE_RANGE_RAG_END = 12999

# 13000-13999: RAG 测试模块
ERROR_CODE_RANGE_RAG_TEST_START = 13000
ERROR_CODE_RANGE_RAG_TEST_END = 13999

# 14000-14999: 配置管理模块
ERROR_CODE_RANGE_CONFIG_START = 14000
ERROR_CODE_RANGE_CONFIG_END = 14999

# 15000-15999: 提示词管理模块
ERROR_CODE_RANGE_PROMPT_START = 15000
ERROR_CODE_RANGE_PROMPT_END = 15999

# 16000-16999: 监控模块
ERROR_CODE_RANGE_MONITORING_START = 16000
ERROR_CODE_RANGE_MONITORING_END = 16999
```

## 测试方案

1. 各模块范围不重叠
2. 每模块有 1000 个码的扩展空间
3. 通用错误码在 10000-10999 范围内

## 注意事项

- 错误码一旦分配不应修改，避免前端硬编码判断失效
- 新模块新增时分配下一个 1000 范围
