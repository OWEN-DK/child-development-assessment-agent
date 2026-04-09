from typing import Dict, Any, List, Tuple
import json
import httpx
from pydantic import BaseModel, Field
from src.config import settings
from src.model.schemas import ChildProfile, ProposedPlan, ChildState, KnowledgeItem
from src.utils.logger import logger


class QwenScoringOutput(BaseModel):
    score: float = Field(description="预测的评分，0-100之间")
    reasoning: str = Field(description="评分理由")
    feature_importance: Dict[str, float] = Field(description="各特征重要度，总和为100")


class QwenScorer:
    def __init__(self):
        self.api_key = settings.dashscope_api_key
        self.model = settings.ml_scoring_qwen_model
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

    async def predict(
        self,
        child: ChildProfile,
        plan: ProposedPlan,
        child_state: ChildState,
        docs: List[KnowledgeItem],
        ahp_scores: Dict[str, float],
    ) -> Tuple[float, Dict[str, float], str]:
        try:
            # 准备输入数据
            child_age = child.age
            child_gender = "男" if child.gender == "male" else "女"
            child_issues = ", ".join(child.issues) if child.issues else "无"
            child_state_str = child_state.model_dump_json() if child_state else "无"
            plan_activities = "\n".join(
                [
                    f"- {a.name}: {a.intensity}强度, 每次{a.duration_minutes}分钟, 每周{a.frequency_weekly}次"
                    for a in plan.activities
                ]
            )
            plan_goals = ", ".join(plan.goals) if plan.goals else "无"
            total_duration = sum(
                a.duration_minutes * a.frequency_weekly for a in plan.activities
            )
            scientific_score = ahp_scores["scientific"]
            age_score = ahp_scores["age"]
            safety_score = ahp_scores["safety"]
            ahp_total_score = ahp_scores["total"]
            rag_docs = (
                "\n".join(
                    [f"- 《{d.source_book}》: {d.content[:200]}..." for d in docs]
                )
                if docs
                else "无"
            )

            # 构造prompt
            system_prompt = """你是儿童发展评估专家，需要对儿童训练计划进行打分。
请根据以下信息给出0-100的综合评分，并说明评分理由和各影响因素的重要度。
输出必须是严格的JSON格式，包含三个字段：
- score: 数字类型，0-100之间的评分
- reasoning: 字符串类型，评分理由
- feature_importance: 对象类型，key是特征名称，value是0-100的数字，总和为100，特征包括scientific_match, age_appropriateness, safety等影响因素

不要输出任何其他内容，只输出JSON。"""

            user_prompt = f"""
儿童信息:
年龄: {child_age}岁
性别: {child_gender}
存在问题: {child_issues}
发育状态: {child_state_str}

训练计划:
活动列表: {plan_activities}
计划目标: {plan_goals}
周总时长: {total_duration}分钟

规则引擎评分结果:
科学性得分: {scientific_score}分
年龄适配度得分: {age_score}分
安全性得分: {safety_score}分
综合规则得分: {ahp_total_score}分

检索到的知识文档:
{rag_docs}

请基于以上信息给出专业的评分，输出严格的JSON格式。"""

            # 调用千问API
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model,
                "input": {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ]
                },
                "parameters": {
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
            }

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.base_url, headers=headers, json=payload
                )
                response.raise_for_status()
                result = response.json()

            # 解析结果
            output_text = result["output"]["choices"][0]["message"]["content"]
            output_data = json.loads(output_text)

            # 验证输出格式
            scoring_output = QwenScoringOutput(**output_data)

            logger.info(f"Qwen ML scoring completed, score: {scoring_output.score}")
            return (
                scoring_output.score,
                scoring_output.feature_importance,
                scoring_output.reasoning,
            )

        except Exception as e:
            logger.error(f"Qwen scoring failed: {e}", exc_info=True)
            # 失败时回退到AHP得分
            return ahp_scores["total"], {}, "ML评分失败，使用规则评分结果"
