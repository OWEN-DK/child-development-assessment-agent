# Phase 2: Schema 加固 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 解决根因 B（`structured_data: Dict[str, Any]` 无类型约束），让 `with_structured_output` 引导 LLM 生成正确结构，并统一运动名称模糊匹配逻辑。

**Architecture:** 在 `schemas/knowledge_qa.py` 中为 S2/S3 添加 Pydantic 子模型替代 `Dict[str, Any]`；新增 `IntensityLevel` 枚举统一强度表达；在 `nodes/base.py` 中提取 `fuzzy_match_exercise` 公共函数，替换 `plan_assemble.py` 和 `verify_citations.py` 中的重复实现。

**Tech Stack:** Python 3.13, Pydantic v2, difflib, pytest + pytest-asyncio

**⚠️ 前端 Breaking Change:** `SectionOutput.structured_data` 从 `Record<string, any>` 变为具有明确字段的对象。前端需同步适配。建议后端先实施，前端单独跟进。

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/src/schemas/knowledge_qa.py` | Modify | 新增 `ProblemItem`, `Section2StructuredData`, `ExerciseTypeItem`, `Section3StructuredData`, `IntensityLevel`, `INTENSITY_MAP`, `map_intensity`；修改 `Section2Response`, `Section3Response` 的 `structured_data` 类型 |
| `backend/src/core/knowledge_qa/nodes/base.py` | Modify | 新增 `fuzzy_match_exercise` 公共函数 |
| `backend/src/core/knowledge_qa/nodes/plan_assemble.py` | Modify | 删除 `_validate_exercise_names`，改用 `fuzzy_match_exercise` |
| `backend/src/core/knowledge_qa/nodes/verify_citations.py` | Modify | 删除 `_fuzzy_match_exercise`，改用 `base.fuzzy_match_exercise` |
| `backend/tests/unit/knowledge_qa/test_phase2_schema.py` | Create | Phase 2 全部单元测试 |
| `frontend/src/features/knowledge-qa/types/index.ts` | Modify | 添加 `IntensityLevel`, `ProblemItem`, `ExerciseTypeItem` 类型（可后置） |

---

## Task 1: 新增 Pydantic 子模型 + IntensityLevel 枚举

**Files:**
- Modify: `backend/src/schemas/knowledge_qa.py:210-243`
- Test: `backend/tests/unit/knowledge_qa/test_phase2_schema.py`

- [ ] **Step 1: 编写测试 — S2/S3 子模型 + IntensityLevel**

```python
# backend/tests/unit/knowledge_qa/test_phase2_schema.py
"""Phase 2 单元测试：Schema 加固 + IntensityLevel 枚举 + 模糊匹配"""

import pytest
from pydantic import ValidationError


# ==================== P2-1: S2/S3 structured_data 子模型 ====================


class TestSection2StructuredData:
    """Section2StructuredData (identify_problems 问题识别) 测试"""

    def test_valid_problems_list(self):
        from src.schemas.knowledge_qa import Section2StructuredData, ProblemItem

        data = Section2StructuredData(
            problems=[
                ProblemItem(description="注意力不集中", severity="高", category="注意力"),
                ProblemItem(description="睡眠不足", severity="中"),
            ]
        )
        assert len(data.problems) == 2
        assert data.problems[0].severity == "高"
        assert data.problems[1].category == ""

    def test_empty_problems_default(self):
        from src.schemas.knowledge_qa import Section2StructuredData

        data = Section2StructuredData()
        assert data.problems == []

    def test_invalid_severity_rejected(self):
        from src.schemas.knowledge_qa import ProblemItem

        with pytest.raises(ValidationError):
            ProblemItem(description="测试", severity="无效级别")

    def test_section2_response_structured_data_typed(self):
        from src.schemas.knowledge_qa import Section2Response, Section2StructuredData

        resp = Section2Response(
            content="## 问题分析",
            structured_data=Section2StructuredData(
                problems=[
                    {"description": "焦虑", "severity": "中", "category": "情绪"},
                ]
            ),
        )
        assert isinstance(resp.structured_data, Section2StructuredData)
        assert len(resp.structured_data.problems) == 1

    def test_section2_response_backward_compat_dict(self):
        """structured_data 接受 dict 输入，自动转为子模型"""
        from src.schemas.knowledge_qa import Section2Response, Section2StructuredData

        resp = Section2Response(
            content="## 问题分析",
            structured_data={
                "problems": [
                    {"description": "焦虑", "severity": "中", "category": "情绪"},
                ]
            },
        )
        assert isinstance(resp.structured_data, Section2StructuredData)


class TestSection3StructuredData:
    """Section3StructuredData (recommend_types 运动类型推荐) 测试"""

    def test_valid_exercise_types(self):
        from src.schemas.knowledge_qa import Section3StructuredData, ExerciseTypeItem

        data = Section3StructuredData(
            exercise_types=[
                ExerciseTypeItem(name="跑步", tier="核心推荐", rationale="改善注意力"),
                ExerciseTypeItem(name="游泳", tier="备选推荐"),
            ],
            child_age_group="6-8岁",
        )
        assert len(data.exercise_types) == 2
        assert data.child_age_group == "6-8岁"

    def test_empty_exercise_types_rejected(self):
        """min_length=1 确保至少有一个推荐"""
        from src.schemas.knowledge_qa import Section3StructuredData

        with pytest.raises(ValidationError):
            Section3StructuredData(exercise_types=[])

    def test_section3_response_structured_data_typed(self):
        from src.schemas.knowledge_qa import Section3Response, Section3StructuredData

        resp = Section3Response(
            content="## 运动推荐",
            structured_data=Section3StructuredData(
                exercise_types=[{"name": "跑步", "tier": "核心推荐"}]
            ),
        )
        assert isinstance(resp.structured_data, Section3StructuredData)

    def test_section3_response_backward_compat_dict(self):
        from src.schemas.knowledge_qa import Section3Response, Section3StructuredData

        resp = Section3Response(
            content="## 运动推荐",
            structured_data={
                "exercise_types": [{"name": "跑步", "tier": "核心推荐"}],
                "child_age_group": "6-8岁",
            },
        )
        assert isinstance(resp.structured_data, Section3StructuredData)


# ==================== P2-2: IntensityLevel 枚举 ====================


class TestIntensityLevel:
    """IntensityLevel 枚举 + 映射函数测试"""

    def test_enum_values(self):
        from src.schemas.knowledge_qa import IntensityLevel

        assert IntensityLevel.LOW.value == "low"
        assert IntensityLevel.MODERATE.value == "moderate"
        assert IntensityLevel.HIGH.value == "high"

    def test_map_exact_chinese(self):
        from src.schemas.knowledge_qa import map_intensity, IntensityLevel

        assert map_intensity("低强度") == IntensityLevel.LOW
        assert map_intensity("中低强度") == IntensityLevel.LOW_MODERATE
        assert map_intensity("中强度") == IntensityLevel.MODERATE
        assert map_intensity("中高强度") == IntensityLevel.MODERATE_HIGH
        assert map_intensity("高强度") == IntensityLevel.HIGH

    def test_map_with_parentheses(self):
        """带括号描述的强度值（如 '中强度（最大心率65%-75%）'）也能正确映射"""
        from src.schemas.knowledge_qa import map_intensity, IntensityLevel

        assert map_intensity("中强度（最大心率65%-75%）") == IntensityLevel.MODERATE
        assert map_intensity("高强度耐力") == IntensityLevel.HIGH

    def test_map_prefix_fallback(self):
        """前缀匹配兜底"""
        from src.schemas.knowledge_qa import map_intensity, IntensityLevel

        # "中-高强度" 应该映射到 MODERATE_HIGH
        result = map_intensity("中-高强度")
        assert result in (IntensityLevel.MODERATE_HIGH, IntensityLevel.MODERATE)

    def test_map_empty_returns_none(self):
        from src.schemas.knowledge_qa import map_intensity

        assert map_intensity("") is None
        assert map_intensity(None) is None

    def test_map_unknown_returns_none(self):
        from src.schemas.knowledge_qa import map_intensity

        assert map_intensity("完全未知") is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/owen/project/ai/main-child-dev-ass-agent/backend && python -m pytest tests/unit/knowledge_qa/test_phase2_schema.py -v --tb=short 2>&1 | head -40`
Expected: ImportError/ModuleNotFoundError — 新类型尚不存在

- [ ] **Step 3: 实现 Pydantic 子模型 + IntensityLevel**

在 `backend/src/schemas/knowledge_qa.py` 中：

**1. 添加 `Literal` 导入**（如尚未导入）：

```python
from typing import Any, Dict, List, Literal, Optional
```

**2. 在 `Section2Response` 之前（约 line 209）新增**：

```python
class ProblemItem(BaseModel):
    """识别出的问题项"""
    description: str = Field(..., description="问题描述")
    severity: Literal["高", "中", "低", "待评估"] = Field(..., description="严重程度")
    category: str = Field(default="", description="问题分类（如：注意力、情绪、社交）")


class Section2StructuredData(BaseModel):
    """第 2 节结构化数据 — 问题识别"""
    problems: List[ProblemItem] = Field(default_factory=list, description="问题列表")
```

**3. 修改 `Section2Response.structured_data` 字段**（line 218-219）：

```python
class Section2Response(BaseModel):
    """identify_problems Agent 的 response_format"""

    title: str = Field(default="问题识别")
    content: str = Field(..., description="Markdown 正文")
    citations: List[Dict[str, Any]] = Field(
        default_factory=list, description="引用列表"
    )
    structured_data: Section2StructuredData = Field(
        default_factory=Section2StructuredData, description="第 2 节结构化数据"
    )

    @field_validator("citations", mode="before")
    @classmethod
    def _parse_citations(cls, v):
        return _parse_list_field(v)
```

**4. 在 `Section3Response` 之前（约 line 227 之后）新增**：

```python
class ExerciseTypeItem(BaseModel):
    """运动类型推荐项"""
    name: str = Field(..., description="运动类型名称")
    tier: Literal["核心推荐", "备选推荐", "辅助推荐"] = Field(default="备选推荐", description="推荐层级")
    rationale: str = Field(default="", description="推荐理由")


class Section3StructuredData(BaseModel):
    """第 3 节结构化数据 — 运动类型推荐"""
    exercise_types: List[ExerciseTypeItem] = Field(
        default_factory=list, min_length=1, description="推荐的运动类型列表（至少 1 个）"
    )
    child_age_group: str = Field(default="", description="适用年龄段")
```

**5. 修改 `Section3Response.structured_data` 字段**（line 236-237）：

```python
class Section3Response(BaseModel):
    """recommend_types Agent 的 response_format"""

    title: str = Field(default="运动类型推荐")
    content: str = Field(..., description="Markdown 正文")
    citations: List[Dict[str, Any]] = Field(
        default_factory=list, description="引用列表"
    )
    structured_data: Section3StructuredData = Field(
        default_factory=Section3StructuredData, description="第 3 节结构化数据"
    )

    @field_validator("citations", mode="before")
    @classmethod
    def _parse_citations(cls, v):
        return _parse_list_field(v)
```

**6. 在文件中（`Section4OutlineResponse` 之后）新增 IntensityLevel 枚举**：

```python
import difflib
from enum import Enum


class IntensityLevel(str, Enum):
    """运动强度级别（标准化 5 级）"""
    LOW = "low"
    LOW_MODERATE = "low-moderate"
    MODERATE = "moderate"
    MODERATE_HIGH = "moderate-high"
    HIGH = "high"


INTENSITY_MAP: dict[str, IntensityLevel] = {
    "低强度": IntensityLevel.LOW,
    "零强度": IntensityLevel.LOW,
    "被动/低强度": IntensityLevel.LOW,
    "中低强度": IntensityLevel.LOW_MODERATE,
    "低-中强度": IntensityLevel.LOW_MODERATE,
    "中强度": IntensityLevel.MODERATE,
    "中-高强度": IntensityLevel.MODERATE_HIGH,
    "中高强度": IntensityLevel.MODERATE_HIGH,
    "高强度": IntensityLevel.HIGH,
    "高强度耐力": IntensityLevel.HIGH,
    "极高强度耐力": IntensityLevel.HIGH,
}


def map_intensity(raw: str | None) -> IntensityLevel | None:
    """中文强度描述 → IntensityLevel 枚举。

    策略：精确匹配 → 前缀匹配兜底。
    """
    if not raw:
        return None
    raw = raw.strip()
    result = INTENSITY_MAP.get(raw)
    if result:
        return result
    # 前缀匹配：处理 "中强度（最大心率65%-75%）" 等带括号描述
    for cn, enum_val in INTENSITY_MAP.items():
        if raw.startswith(cn[:2]) or cn.startswith(raw[:2]):
            return enum_val
    return None
```

**注意**：`difflib` 和 `Enum` 的 import 应添加到文件顶部的 import 区块。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/owen/project/ai/main-child-dev-ass-agent/backend && python -m pytest tests/unit/knowledge_qa/test_phase2_schema.py::TestSection2StructuredData -v --tb=short`
Run: `cd /Users/owen/project/ai/main-child-dev-ass-agent/backend && python -m pytest tests/unit/knowledge_qa/test_phase2_schema.py::TestSection3StructuredData -v --tb=short`
Run: `cd /Users/owen/project/ai/main-child-dev-ass-agent/backend && python -m pytest tests/unit/knowledge_qa/test_phase2_schema.py::TestIntensityLevel -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 5: 运行已有测试确保无回归**

Run: `cd /Users/owen/project/ai/main-child-dev-ass-agent/backend && python -m pytest tests/unit/knowledge_qa/ -v --tb=short 2>&1 | tail -20`
Expected: 全部 PASS，无 regression

---

## Task 2: 统一运动名称模糊匹配函数

**Files:**
- Modify: `backend/src/core/knowledge_qa/nodes/base.py`
- Test: `backend/tests/unit/knowledge_qa/test_phase2_schema.py`（追加测试类）

- [ ] **Step 1: 编写测试 — fuzzy_match_exercise**

在 `test_phase2_schema.py` 底部追加：

```python
# ==================== P2-3: 运动名称模糊匹配统一 ====================


class TestFuzzyMatchExercise:
    """fuzzy_match_exercise 公共函数测试"""

    def test_exact_match(self):
        from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise

        names = ["跑步", "游泳", "瑜伽"]
        assert fuzzy_match_exercise("跑步", names) == "跑步"

    def test_case_insensitive_exact(self):
        from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise

        names = ["跑步", "游泳"]
        assert fuzzy_match_exercise("  跑步  ", names) == "跑步"

    def test_substring_match(self):
        """LLM 输出是清单名称的子串"""
        from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise

        names = ["蹦床跳跃休息（课间/工作间切换）"]
        assert fuzzy_match_exercise("蹦床跳跃", names) == "蹦床跳跃休息（课间/工作间切换）"

    def test_substring_reverse_match(self):
        """清单名称是 LLM 输出的子串"""
        from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise

        names = ["慢跑"]
        assert fuzzy_match_exercise("慢跑30分钟", names) == "慢跑"

    def test_difflib_fuzzy_match(self):
        """difflib 序列匹配兜底"""
        from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise

        names = ["散步（轻松步行）"]
        result = fuzzy_match_exercise("散步", names, cutoff=0.3)
        assert result == "散步（轻松步行）"

    def test_no_match_returns_none(self):
        from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise

        names = ["跑步", "游泳", "瑜伽"]
        assert fuzzy_match_exercise("量子力学", names) is None

    def test_empty_inputs(self):
        from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise

        assert fuzzy_match_exercise("", ["跑步"]) is None
        assert fuzzy_match_exercise("跑步", []) is None
        assert fuzzy_match_exercise(None, ["跑步"]) is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/owen/project/ai/main-child-dev-ass-agent/backend && python -m pytest tests/unit/knowledge_qa/test_phase2_schema.py::TestFuzzyMatchExercise -v --tb=short 2>&1 | head -20`
Expected: ImportError — `fuzzy_match_exercise` 尚不存在

- [ ] **Step 3: 实现 fuzzy_match_exercise**

在 `backend/src/core/knowledge_qa/nodes/base.py` 中新增（放在模块顶层，在 `_get_model_name` 附近）：

```python
import difflib


def fuzzy_match_exercise(
    name: str | None, valid_names: list[str], cutoff: float = 0.6
) -> str | None:
    """统一运动名称模糊匹配（精确 → 子串 → difflib）。

    替代 plan_assemble._validate_exercise_names 和
    verify_citations._fuzzy_match_exercise 的重复逻辑。
    """
    if not name or not valid_names:
        return None
    name_lower = name.strip().lower()
    valid_lower = {n.lower().strip(): n for n in valid_names if n.strip()}

    # 1. 精确匹配
    if name_lower in valid_lower:
        return valid_lower[name_lower]

    # 2. 子串匹配
    for vl, vo in valid_lower.items():
        if vl in name_lower or name_lower in vl:
            return vo

    # 3. difflib 序列匹配
    matches = difflib.get_close_matches(
        name, list(valid_lower.keys()), n=1, cutoff=cutoff
    )
    return valid_lower[matches[0]] if matches else None
```

**注意**：`difflib` 是标准库，只需在 base.py 顶部 import（如尚未导入）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/owen/project/ai/main-child-dev-ass-agent/backend && python -m pytest tests/unit/knowledge_qa/test_phase2_schema.py::TestFuzzyMatchExercise -v --tb=short`
Expected: 全部 PASS

---

## Task 3: 替换 plan_assemble 中的重复模糊匹配

**Files:**
- Modify: `backend/src/core/knowledge_qa/nodes/plan_assemble.py:96-130`
- Test: 已有 Task 2 覆盖，无需新测试

- [ ] **Step 1: 重构 _validate_exercise_names 使用 fuzzy_match_exercise**

替换 `plan_assemble.py:96-130` 的 `_validate_exercise_names` 函数：

```python
def _validate_exercise_names(phases: List[dict], valid_names: List[str]) -> int:
    """后处理：用 S3 运动名称做模糊匹配修正。返回修正数量。"""
    if not valid_names:
        return 0

    from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise

    fixed_count = 0
    for ph in phases:
        for wk in ph.get("weeks", []):
            for day in wk.get("days", []):
                for ex in day.get("main_exercises", []):
                    ex_name = (ex.get("name", "") or "").strip()
                    if not ex_name:
                        continue
                    matched = fuzzy_match_exercise(ex_name, valid_names)
                    if matched and matched != ex_name:
                        ex["name"] = matched
                        fixed_count += 1
                        logger.info(f"运动名称修正: '{ex_name}' → '{matched}'")

    return fixed_count
```

- [ ] **Step 2: 运行已有测试确保无回归**

Run: `cd /Users/owen/project/ai/main-child-dev-ass-agent/backend && python -m pytest tests/unit/knowledge_qa/ -v --tb=short 2>&1 | tail -20`
Expected: 全部 PASS

---

## Task 4: 替换 verify_citations 中的重复模糊匹配

**Files:**
- Modify: `backend/src/core/knowledge_qa/nodes/verify_citations.py:49-72`
- Test: 已有 Task 2 + test_verify_citations.py 覆盖

- [ ] **Step 1: 重构 verify_citations 使用 fuzzy_match_exercise**

**1. 添加 import**（在 verify_citations.py 顶部 imports 区）：

```python
from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise
```

**2. 替换 `_fuzzy_match_exercise` 函数**（line 49-72）为简单代理：

```python
def _fuzzy_match_exercise(name: str, valid_set: set[str]) -> Optional[str]:
    """模糊匹配运动名称 — 委托给 base.fuzzy_match_exercise 公共实现。"""
    return fuzzy_match_exercise(name, list(valid_set))
```

- [ ] **Step 2: 运行 verify_citations 测试确认通过**

Run: `cd /Users/owen/project/ai/main-child-dev-ass-agent/backend && python -m pytest tests/unit/knowledge_qa/test_verify_citations.py -v --tb=short`
Expected: 全部 PASS（行为不变）

---

## Task 5: 全量回归测试 + 计划文档更新

**Files:**
- Modify: `docs/knowledge-qa/planning/solutions.md`（更新进度）
- Test: 全量测试

- [ ] **Step 1: 运行全量 knowledge_qa 单元测试**

Run: `cd /Users/owen/project/ai/main-child-dev-ass-agent/backend && python -m pytest tests/unit/knowledge_qa/ -v --tb=short 2>&1 | tail -30`
Expected: 全部 PASS

- [ ] **Step 2: 更新 solutions.md 实施进度**

将 Phase 2 状态更新为 `✅ 已实施`：

```
| **Phase 2: Schema 加固** | ✅ **已实施** (2026-05-28) | 68+ passed |
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/schemas/knowledge_qa.py backend/src/core/knowledge_qa/nodes/base.py backend/src/core/knowledge_qa/nodes/plan_assemble.py backend/src/core/knowledge_qa/nodes/verify_citations.py backend/tests/unit/knowledge_qa/test_phase2_schema.py docs/knowledge-qa/planning/solutions.md
git commit -m "feat(knowledge-qa): Phase 2 schema hardening — S2/S3 structured_data 子模型 + IntensityLevel 枚举 + 模糊匹配统一"
```
