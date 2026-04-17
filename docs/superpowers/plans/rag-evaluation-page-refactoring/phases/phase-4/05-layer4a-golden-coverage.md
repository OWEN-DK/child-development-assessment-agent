# 05 - Layer 4a: Golden 覆盖度 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 05 - Layer 4a: Golden 覆盖度

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/core/validation/layers/layer4a_golden_coverage.py`
- Test: `backend/tests/test_placeholder.py`

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

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `5.4.1 校验 4a: Golden 覆盖度分析` 节
> **所属 Phase**: Phase 4

## 需求定义

检查测试用例是否覆盖了足够的源文档和章节。书籍覆盖率、章节覆盖率、各领域覆盖文档数。

## 验收标准

- [ ] 书籍覆盖率 < 60% 时警告
- [ ] 章节覆盖率 < 40% 时警告
- [ ] 某发展领域无覆盖时严重警告
- [ ] 执行延迟 < 500ms

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/validation/layers/layer4a_golden_coverage.py` | 新增 | Layer 4a 实现 |

## 实现方案

### 后端实现

```python
# backend/src/core/validation/layers/layer4a_golden_coverage.py
import logging
from typing import Any
from collections import defaultdict

logger = logging.getLogger(__name__)

class Layer4aGoldenCoverage:
    """Layer 4a: Golden 覆盖度分析"""
    
    def __init__(self, db, test_run):
        self.db = db
        self.test_run = test_run
    
    async def execute(self) -> dict:
        """执行覆盖度分析"""
        test_cases = self.test_run.test_cases or []
        source_documents = self.test_run.source_documents or []
        
        if not test_cases or not source_documents:
            return {"status": "skipped", "data": {"reason": "缺少测试用例或源文档"}}
        
        # 构建 doc_id → doc 索引（O(1) 查找）
        doc_index = {d["id"]: d for d in source_documents if d.get("id")}
        
        # 计算覆盖率
        covered_books = set()
        covered_chapters = set()
        domain_coverage = defaultdict(set)
        
        for tc in test_cases:
            doc_id = tc.get("source_document_id")
            if doc_id and doc_id in doc_index:
                doc = doc_index[doc_id]
                covered_books.add(doc.get("book_id"))
                covered_chapters.add(doc.get("chapter_id"))
                domain_coverage[doc.get("domain", "unknown")].add(doc_id)
        
        total_books = set(d.get("book_id") for d in source_documents if d.get("book_id"))
        total_chapters = set(d.get("chapter_id") for d in source_documents if d.get("chapter_id"))
        
        book_coverage = len(covered_books) / len(total_books) if total_books else 0
        chapter_coverage = len(covered_chapters) / len(total_chapters) if total_chapters else 0
        
        # 生成警告
        warnings = []
        if book_coverage < 0.60:
            warnings.append({"level": "warning", "message": f"书籍覆盖率低 ({book_coverage:.1%} < 60%)"})
        if chapter_coverage < 0.40:
            warnings.append({"level": "warning", "message": f"章节覆盖率低 ({chapter_coverage:.1%} < 40%)"})
        
        all_domains = set(d.get("domain") for d in source_documents if d.get("domain"))
        uncovered_domains = all_domains - set(domain_coverage.keys())
        for domain in uncovered_domains:
            warnings.append({"level": "critical", "message": f"领域 '{domain}' 无覆盖"})
        
        return {
            "status": "completed",
            "data": {
                "book_coverage": book_coverage,
                "chapter_coverage": chapter_coverage,
                "domain_coverage": {k: len(v) for k, v in domain_coverage.items()},
                "warnings": warnings,
            },
        }
```

## 测试方案

```python
@pytest.mark.asyncio
async def test_low_book_coverage():
    """书籍覆盖率低时警告"""
    ...

@pytest.mark.asyncio
async def test_uncovered_domain():
    """某领域无覆盖时严重警告"""
    ...
```

## 注意事项

- 纯内存计算，执行延迟 < 500ms
- 领域来自源文档元数据 `domain` 字段
