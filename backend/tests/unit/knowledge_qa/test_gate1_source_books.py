"""
Gate 1 验证：source_books 填充率

运行方式:
  cd backend && source .venv/bin/activate
  PYTHONPATH=. python tests/unit/knowledge_qa/test_gate1_source_books.py

通过标准:
  - ProblemItem.source_books 非空率 ≥ 60%
  - ExerciseTypeItem.source_books 非空率 ≥ 60%

注意：此测试依赖实际 LLM 调用，需要后端服务运行且 LLM 可用。
"""
import asyncio
import json
import sys
from typing import List, Dict, Any


# 测试用例：多书籍场景的问题
TEST_CASES = [
    {
        "question": "8岁男孩注意力不集中，应该做什么运动来改善？",
        "expected_books": 2,  # 至少涉及 2 本书
    },
    {
        "question": "运动对孩子情绪调节和社交能力有什么影响？具体推荐什么运动？",
        "expected_books": 2,
    },
    {
        "question": "前庭觉失调的孩子适合哪些运动？运动频率和强度如何安排？",
        "expected_books": 2,
    },
    {
        "question": "小学生每天运动多长时间最合适？不同运动类型的推荐比例？",
        "expected_books": 2,
    },
    {
        "question": "如何通过运动改善孩子的专注力和学习成绩？",
        "expected_books": 2,
    },
]


def check_source_books_fill_rate(sections: Dict[int, Any]) -> Dict[str, Any]:
    """检查 S2/S3 的 source_books 填充率。

    Returns:
        {
            "s2_problems_total": int,
            "s2_problems_with_source": int,
            "s2_fill_rate": float,
            "s3_exercise_types_total": int,
            "s3_exercise_types_with_source": int,
            "s3_fill_rate": float,
            "overall_pass": bool,
        }
    """
    result = {
        "s2_problems_total": 0,
        "s2_problems_with_source": 0,
        "s2_fill_rate": 0.0,
        "s3_exercise_types_total": 0,
        "s3_exercise_types_with_source": 0,
        "s3_fill_rate": 0.0,
        "overall_pass": False,
    }

    # S2
    s2 = sections.get(2)
    if s2 and s2.structured_data:
        problems = s2.structured_data.get("problems", [])
        result["s2_problems_total"] = len(problems)
        result["s2_problems_with_source"] = sum(
            1 for p in problems if p.get("source_books")
        )

    # S3
    s3 = sections.get(3)
    if s3 and s3.structured_data:
        ets = s3.structured_data.get("exercise_types", [])
        result["s3_exercise_types_total"] = len(ets)
        result["s3_exercise_types_with_source"] = sum(
            1 for et in ets if et.get("source_books")
        )

    # 计算填充率
    if result["s2_problems_total"] > 0:
        result["s2_fill_rate"] = result["s2_problems_with_source"] / result["s2_problems_total"]
    if result["s3_exercise_types_total"] > 0:
        result["s3_fill_rate"] = result["s3_exercise_types_with_source"] / result["s3_exercise_types_total"]

    result["overall_pass"] = (
        result["s2_fill_rate"] >= 0.6
        and result["s3_fill_rate"] >= 0.6
    )
    return result


async def run_gate1_verification():
    """Gate 1: 运行 5 个测试 case，检查 source_books 填充率。

    此函数模拟验证逻辑。真实运行时需要替换为实际的 pipeline 调用。
    """
    print("=" * 60)
    print("Gate 1: source_books 填充率验证")
    print("=" * 60)

    # 模拟结果（真实运行时应从 pipeline 获取）
    # 这里展示验证逻辑结构
    mock_results = []

    for i, case in enumerate(TEST_CASES):
        print(f"\n--- Case {i + 1}: {case['question'][:50]}... ---")

        # TODO: 替换为实际的 pipeline 调用
        # from src.service.knowledge_qa_service import KnowledgeQAService
        # result = await service._run_qa_pipeline(...)

        # 模拟：假设 source_books 填充情况
        print(f"  [模拟] 需要实际运行 pipeline 获取真实数据")
        print(f"  预期: 匹配 >= {case['expected_books']} 本书籍")

    print("\n" + "=" * 60)
    print("运行方式（真实验证）:")
    print("=" * 60)
    print("""
# 1. 启动后端服务
cd backend && source .venv/bin/activate
python -m uvicorn src.main:app --port 8000

# 2. 通过 API 提交问题
curl -X POST http://localhost:8000/api/knowledge-qa/ask \\
  -H "Content-Type: application/json" \\
  -d '{"question": "8岁男孩注意力不集中，应该做什么运动？", "stream": true}'

# 3. 等待完成，检查 response.sections[1].structured_data.problems[].source_books
#    和 response.sections[2].structured_data.exercise_types[].source_books

# 4. 统计 5 个 case 的填充率
#    S2 通过标准: source_books 非空率 >= 60%
#    S3 通过标准: source_books 非空率 >= 60%
""")


if __name__ == "__main__":
    asyncio.run(run_gate1_verification())
