#!/usr/bin/env python3
"""生成模块评估脚本 - 评估RAG生成内容的忠实度、相关性、专业性"""

import sys
import os
import json
import time
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.config.settings import settings
from src.utils.logger import logger
from src.service.rag_service import rag_service

EVALUATION_PROMPT = """你是一位专业的儿童发展评估专家，请评估以下RAG生成内容的质量。

用户问题：{query}
儿童年龄：{age}岁
检索上下文：{context}
生成回答：{answer}

请从以下维度进行评分（0-1之间的小数）：

1. 忠实度（faithfulness）：生成内容是否严格基于检索上下文，没有编造信息
2. 回答相关性（relevance）：回答是否直接针对用户问题，相关性强
3. 完整性（completeness）：回答是否覆盖了问题的关键要点
4. 专业术语准确率（professional_terms_accuracy）：专业术语使用是否准确、规范
5. 年龄适配性（age_adaptation）：回答是否适合指定年龄段的儿童

请以JSON格式返回评分，格式如下：
{{
  "faithfulness": 0.95,
  "relevance": 0.90,
  "completeness": 0.85,
  "professional_terms_accuracy": 0.92,
  "age_adaptation": 0.88,
  "comments": "简要评价"
}}

只返回JSON，不要其他内容。"""


async def evaluate_single_case(
    test_case: dict, generated_answer: str, context: str
) -> dict:
    """评估单个测试用例的生成质量"""
    prompt = EVALUATION_PROMPT.format(
        query=test_case.get("query", ""),
        age=test_case.get("age", 0),
        context=context[:1000],
        answer=generated_answer,
    )

    try:
        from llama_index.llms.dashscope import DashScope

        llm = DashScope(
            model_name=settings.model_validation,
            api_key=settings.dashscope_api_key,
        )

        response = await llm.acomplete(prompt)
        result_text = response.text.strip()

        # 解析JSON
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        result_text = result_text.strip()

        scores = json.loads(result_text)
        return scores
    except Exception as e:
        logger.error(f"评估失败: {e}")
        return {
            "faithfulness": 0.0,
            "relevance": 0.0,
            "completeness": 0.0,
            "professional_terms_accuracy": 0.0,
            "age_adaptation": 0.0,
            "comments": f"评估出错: {str(e)}",
        }


def evaluate_generation(test_set_path: str = None):
    """运行生成质量评估"""
    if test_set_path and os.path.exists(test_set_path):
        with open(test_set_path, "r", encoding="utf-8") as f:
            test_set = json.load(f)
    else:
        print("错误：测试集文件不存在")
        return

    print(f"使用 {len(test_set)} 条测试用例进行生成评估")

    # 运行异步评估
    async def run_evaluation():
        all_scores = {
            "faithfulness": [],
            "relevance": [],
            "completeness": [],
            "professional_terms_accuracy": [],
            "age_adaptation": [],
        }

        for i, test_case in enumerate(test_set):
            print(
                f"\n评估第 {i + 1}/{len(test_set)} 条用例: {test_case.get('query', '')[:50]}..."
            )

            try:
                # 检索知识
                results = await rag_service.retrieve_knowledge(
                    query=test_case.get("query", ""),
                    age=test_case.get("age", 0),
                    limit=5,
                )

                # 构建上下文
                context = "\n\n".join([r.get("content", "") for r in results[:3]])

                # 生成回答（使用RAG服务）
                from llama_index.llms.dashscope import DashScope

                # 注意：RAG_SYSTEM_PROMPT 已迁移到 PromptManager，这里使用简单提示词
                RAG_SYSTEM_PROMPT = (
                    "你是一个专业的儿童发展评估助手，请基于检索上下文回答问题。"
                )

                llm = DashScope(
                    model_name=settings.model_assessment,
                    api_key=settings.dashscope_api_key,
                )

                user_prompt = f"问题：{test_case.get('query', '')}\n儿童年龄：{test_case.get('age', 0)}岁\n\n请基于以上检索上下文，给出专业、准确的回答。"

                response = await llm.acomplete(
                    RAG_SYSTEM_PROMPT
                    + "\n\n检索上下文：\n"
                    + context
                    + "\n\n"
                    + user_prompt
                )
                generated_answer = response.text

                # 评估生成质量
                scores = await evaluate_single_case(
                    test_case, generated_answer, context
                )

                for key in all_scores:
                    all_scores[key].append(scores.get(key, 0.0))

                print(f"  忠实度: {scores.get('faithfulness', 0):.2f}")
                print(f"  相关性: {scores.get('relevance', 0):.2f}")
                print(f"  年龄适配: {scores.get('age_adaptation', 0):.2f}")

            except Exception as e:
                logger.error(f"测试用例 {i + 1} 执行失败: {e}")
                continue

        return all_scores

    all_scores = asyncio.run(run_evaluation())

    # 计算平均指标
    metrics = {}
    for key, values in all_scores.items():
        if values:
            metrics[key] = sum(values) / len(values)
        else:
            metrics[key] = 0.0

    print(f"\n=== 生成质量评估报告 ===")
    print(f"评估用例数: {len(all_scores['faithfulness'])}")
    print(f"忠实度: {metrics['faithfulness']:.4f}")
    print(f"回答相关性: {metrics['relevance']:.4f}")
    print(f"完整性: {metrics['completeness']:.4f}")
    print(f"专业术语准确率: {metrics['professional_terms_accuracy']:.4f}")
    print(f"年龄适配性: {metrics['age_adaptation']:.4f}")

    report = {
        "timestamp": time.time(),
        "test_cases_count": len(all_scores["faithfulness"]),
        "metrics": metrics,
        "config": {
            "model_assessment": settings.model_assessment,
            "model_validation": settings.model_validation,
        },
    }

    os.makedirs("backend/reports", exist_ok=True)
    report_path = "backend/reports/generation_evaluation_report_v1.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存到: {report_path}")

    # 达标检查
    print(f"\n=== 达标检查 ===")
    checks = [
        ("忠实度 >= 0.98", metrics["faithfulness"] >= 0.98),
        ("回答相关性 >= 4.5/5.0", metrics["relevance"] >= 0.90),
        ("专业术语准确率 >= 0.99", metrics["professional_terms_accuracy"] >= 0.99),
        ("年龄适配性 >= 4.8/5.0", metrics["age_adaptation"] >= 0.96),
    ]
    for name, passed in checks:
        status = "✅ 通过" if passed else "❌ 未达标"
        print(f"  {name}: {status}")


if __name__ == "__main__":
    test_set = sys.argv[1] if len(sys.argv) > 1 else None
    evaluate_generation(test_set)
