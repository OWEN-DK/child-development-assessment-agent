# Phase 5-1: 重命名 model → schemas

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `6.3.1` 节
> **所属 Phase**: Phase 5

## 需求定义

将 `backend/src/model/`（单数）目录重命名为 `backend/src/schemas/`，消除 `model` vs `models` 仅差一个 `s` 的混淆，对齐 CLAUDE.md "实体类集中管理" 规范。

## 验收标准

- [ ] `src/model/` 目录已重命名为 `src/schemas/`
- [ ] 31 处 `from src.model.` 引用全部更新为 `from src.schemas.`
- [ ] 无 `from src.model.` 引用残留
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/model/` | 重命名 → `schemas/` | 原 Pydantic 模型目录 |
| 31 处引用文件 | 修改 | 更新 import 路径 |

## 迁移映射

| 原路径 | 新路径 |
|--------|--------|
| `src.model.schemas` | `src.schemas.assessment` |
| `src.model.tuning` | `src.schemas.test_case` |
| `src.model.rag_test` | `src.schemas.test_case` |
| `src.model.document` | `src.schemas.rag` |

## 实现方案

### 步骤

1. 重命名目录：`mv backend/src/model backend/src/schemas`
2. 全局搜索替换：`from src.model.` → `from src.schemas.`
3. 按模块调整子目录：
   - `schemas/schemas.py` → `schemas/assessment.py`
   - `schemas/tuning.py` → 合并至 `schemas/test_case.py`
   - `schemas/rag_test.py` → 合并至 `schemas/test_case.py`
   - `schemas/document.py` → `schemas/rag.py`
4. 运行测试验证

### 搜索替换命令

```bash
# 查找所有引用
rg "from src\.model\." backend/src/ --type py

# 批量替换（需谨慎审查）
# 手动更新每个文件的 import 语句
```

## 测试方案

1. 全局搜索 `from src.model.` 确认无残留
2. 所有 import 无错误
3. Agent 工作流正常
4. RAG 测试正常

## 注意事项

- 重命名前确保 Phase 1 实体类迁移已完成
- 注意 `model/` 与 `models/` 的区别，只重命名单数目录
- 重命名后检查 `__pycache__` 是否清理
