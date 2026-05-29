"""
F1/F2 Schema 兼容性验证：测试 qwen3.5-27b 对深层嵌套 Pydantic 的遵循度。

运行方式:
  cd backend && source .venv/bin/activate
  PYTHONPATH=. python tests/unit/knowledge_qa/test_f1f2_schema_compat.py

通过标准:
  - 至少 2/3 case 中 Section4PhasesOnly.exercise_count >= 3
  - exercise.name 非空率 >= 90%
"""
import asyncio
import json
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ===== 嵌套 Schema 定义（与方案一致） =====

class OutlineExercise(BaseModel):
    exercise_id: str = Field(default="")
    name: str = Field(..., min_length=1)
    type_id: str = Field(default="")
    duration_min: int = Field(default=0, ge=0)
    intensity: Literal["低", "中", "高"] = "中"
    sets: Optional[int] = Field(default=None, ge=1)
    reps: Optional[int] = Field(default=None, ge=1)
    notes: str = Field(default="")
    source_books: List[str] = Field(default_factory=list)


class OutlineDay(BaseModel):
    day_index: int = Field(..., ge=1)
    day_label: str = Field(default="")
    main_exercises: List[OutlineExercise] = Field(default_factory=list, min_length=1)
    warmup: dict = Field(default_factory=dict)
    cooldown: dict = Field(default_factory=dict)
    total_duration_min: int = Field(default=0)


class OutlineWeek(BaseModel):
    week_index: int = Field(..., ge=1)
    focus: str = Field(default="")
    days: List[OutlineDay] = Field(default_factory=list)


class OutlinePhase(BaseModel):
    phase_id: str = Field(default="", pattern=r"^PH\d{2}$")
    phase_name: str = Field(..., min_length=1)
    goal: str = Field(default="")
    duration_weeks: int = Field(default=1, ge=1)
    weeks: List[OutlineWeek] = Field(default_factory=list)


class Section4PhasesOnly(BaseModel):
    phases: List[OutlinePhase] = Field(default_factory=list, min_length=1)


def count_exercises(response: Section4PhasesOnly) -> dict:
    """统计响应中的 exercise 数量和质量。"""
    total = 0
    with_name = 0
    with_duration = 0
    with_intensity = 0

    for phase in response.phases:
        for week in phase.weeks:
            for day in week.days:
                for ex in day.main_exercises:
                    total += 1
                    if ex.name:
                        with_name += 1
                    if ex.duration_min > 0:
                        with_duration += 1
                    if ex.intensity:
                        with_intensity += 1

    return {
        "total": total,
        "with_name": with_name,
        "with_duration": with_duration,
        "with_intensity": with_intensity,
        "name_rate": with_name / total if total > 0 else 0,
    }


async def verify_schema_compat():
    """验证嵌套 schema 兼容性。

    真实运行时替换为实际的 LLM 调用。
    """
    print("=" * 60)
    print("F1/F2 Schema 兼容性验证")
    print("=" * 60)

    # 验证 schema 本身能正常序列化
    ex = OutlineExercise(name="跑酷", duration_min=15, intensity="中")
    day = OutlineDay(day_index=1, main_exercises=[ex], total_duration_min=30)
    week = OutlineWeek(week_index=1, days=[day])
    phase = OutlinePhase(phase_id="PH01", phase_name="基础期", weeks=[week])
    s4 = Section4PhasesOnly(phases=[phase])

    stats = count_exercises(s4)
    print(f"Schema 自检: {stats['total']} exercises, name_rate={stats['name_rate']:.0%}")
    assert stats["total"] == 1 and stats["with_name"] == 1
    print("✅ Schema 自检通过")

    print("\n--- LLM 兼容性测试 ---")
    test_cases = [
        "8岁男孩注意力不集中，设计一个4周运动方案",
        "前庭觉失调儿童，推荐每周运动计划",
        "小学生每天30分钟运动方案，包含热身和放松",
    ]

    for i, question in enumerate(test_cases):
        print(f"\nCase {i + 1}: {question}")

        # TODO: 替换为实际 LLM 调用
        # from src.core.knowledge_qa.nodes.base import _invoke_llm_structured
        # response = await _invoke_llm_structured(
        #     system_prompt=SYSTEM_PROMPT,
        #     user_message=question,
        #     response_format=Section4PhasesOnly,
        #     step_label="f1f2_compat_test",
        #     timeout_seconds=60,
        # )
        # stats = count_exercises(response)

        print(f"  [待运行] 需实际 LLM 调用")

    print("\n" + "=" * 60)
    print("运行方式:")
    print("=" * 60)
    print("""
# 在 knowledge_qa_service 中临时替换 Section4OutlineResponse 为
# Section4PhasesOnly，运行 3 个测试问题，统计：
#   1. exercise_count >= 3 的 case 数
#   2. exercise.name 非空率 >= 90%
# 通过: >= 2/3 case 满足条件
""")


if __name__ == "__main__":
    asyncio.run(verify_schema_compat())
