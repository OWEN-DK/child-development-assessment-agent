# 10 - Layer 5c: 错误模式分组 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 10 - Layer 5c: 错误模式分组

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/core/validation/layers/layer5c_error_patterns.py`
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

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `5.5.3 校验 5c: 错误模式分组` 节
> **所属 Phase**: Phase 4

## 需求定义

对 Bad Case 进行多维交叉分组，找出共性失败模式。错误类型 × 发展领域 × 年龄组。

## 验收标准

- [ ] 多维交叉分组正确
- [ ] 每组输出名称、数量、占比、示例、修复方案
- [ ] 修复方案规则映射正确

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/validation/layers/layer5c_error_patterns.py` | 新增 | Layer 5c 实现 |

## 实现方案

### 后端实现

```python
# backend/src/core/validation/layers/layer5c_error_patterns.py
import logging
from typing import Any
from collections import defaultdict

logger = logging.getLogger(__name__)

FIX_SOLUTION_MAP = {
    "未召回": "增加 top_k，检查关键词覆盖",
    "排序倒置": "增加 reranker_initial_k，检查重排序模型",
    "误杀": "减小 fusion_threshold，检查同义词扩展",
    "年龄过滤排除": "降低 age_filter_strictness",
    "部分召回": "检查分块粒度，调整 chunk_size",
    "重排序误判": "检查重排序模型适用领域",
}

class Layer5cErrorPatterns:
    """Layer 5c: 错误模式分组"""
    
    def __init__(self, db, test_run):
        self.db = db
        self.test_run = test_run
    
    async def execute(self) -> dict:
        """执行错误模式分组"""
        bad_cases = self._get_bad_cases()
        
        if not bad_cases:
            return {"status": "skipped", "data": {"reason": "缺少 Bad Case 列表"}}
        
        groups = defaultdict(list)
        
        for bc in bad_cases:
            error_type = bc.get("failure_type", "unknown")
            domain = bc.get("domain", "unknown")
            age_group = bc.get("age_group", "unknown")
            
            key = f"{error_type}-{domain}-{age_group}"
            groups[key].append(bc)
        
        error_groups = []
        total_bad_cases = len(bad_cases)
        
        for group_name, cases in sorted(groups.items(), key=lambda x: -len(x[1])):
            error_type = group_name.split("-")[0]
            fix_solution = FIX_SOLUTION_MAP.get(error_type, "需进一步分析")
            
            error_groups.append({
                "group_name": group_name,
                "count": len(cases),
                "ratio": len(cases) / total_bad_cases,
                "example_queries": [c.get("query") for c in cases[:3]],
                "suggested_fix": fix_solution,
            })
        
        return {
            "status": "completed",
            "data": {
                "error_groups": error_groups,
                "total_groups": len(error_groups),
                "total_bad_cases": total_bad_cases,
            },
        }
    
    def _get_bad_cases(self) -> list:
        """获取 Bad Case 列表 (hit_at_5 = 0)"""
        results = self.test_run.test_run_results or []
        return [
            {
                "query": getattr(r, "query", ""),
                "failure_type": getattr(r, "failure_type", None),
                "domain": getattr(r, "domain", None),
                "age_group": getattr(r, "age_group", None),
            }
            for r in results
            if getattr(r, "hit_at_5", 1) == 0
        ]
```

## 测试方案

```python
@pytest.mark.asyncio
async def test_cross_grouping():
    """多维交叉分组正确"""
    ...

@pytest.mark.asyncio
async def test_fix_solution_mapping():
    """修复方案规则映射正确"""
    ...
```

## 注意事项

- 直接使用 TestRun 的 Bad Case 列表，不等待 Layer 3
- 分组按数量降序排列
