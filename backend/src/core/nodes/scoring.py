from typing import Any, Dict, List

import jieba

from src.config import settings
from src.config.rules import rules
from src.core.ml.qwen_scorer import QwenScorer
from src.core.nodes.base import BaseNode
from src.schemas import (AgentState, ChildProfile, ChildState,
                         DimensionAnalysis, EvaluationResult, KnowledgeItem,
                         ProposedPlan)
from src.utils.logger import logger


class ScoringNode(BaseNode):
    """评分"""

    def __init__(self):
        super().__init__()
        self.qwen_scorer = (
            QwenScorer()
            if settings.ml_scoring_enabled and settings.ml_scoring_mode == "qwen"
            else None
        )
        # TODO: 后续添加XGBoost scorer初始化

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Executing Scoring Node...")

        child = state.child_profile
        plan = state.proposed_plan
        child_state = state.child_state
        docs = state.retrieved_docs

        # Level 1: AHP Baseline Scoring
        score, explanation, suggestions, dimension_analysis = self._calculate_ahp_score(
            child, plan, child_state, docs
        )

        ahp_scores = {
            "scientific": dimension_analysis["scientific_match"].score,
            "age": dimension_analysis["age_appropriateness"].score,
            "safety": dimension_analysis["safety"].score,
            "total": score,
        }

        # Level 2: ML Prediction
        ml_score = score
        ml_feature_importance = {}
        ml_reasoning = ""
        if settings.ml_scoring_enabled:
            if settings.ml_scoring_mode == "qwen" and self.qwen_scorer:
                ml_score, ml_feature_importance, ml_reasoning = (
                    await self.qwen_scorer.predict(
                        child, plan, child_state, docs, ahp_scores
                    )
                )
            # TODO: 后续添加XGBoost模式支持

        # Level 3: Fusion
        final_score = (
            score * settings.ml_scoring_weight_ahp
            + ml_score * settings.ml_scoring_weight_ml
        )
        final_score = round(max(0, min(100, final_score)), 1)

        # 合并解释
        if settings.ml_scoring_enabled:
            ml_explanation = f" ML模型预测得分{ml_score:.0f} (权重{settings.ml_scoring_weight_ml*100:.0f}%)。"
            if ml_reasoning:
                ml_explanation += f" ML分析: {ml_reasoning}"
            explanation += ml_explanation

        result = EvaluationResult(
            score=final_score,
            reasoning=f"综合评分基于科学性、年龄适配度和安全性分析。{explanation}",
            shap_explanation={
                "scientific_match": 40 * settings.ml_scoring_weight_ahp
                + ml_feature_importance.get("scientific_match", 0)
                * settings.ml_scoring_weight_ml,
                "age_appropriateness": 30 * settings.ml_scoring_weight_ahp
                + ml_feature_importance.get("age_appropriateness", 0)
                * settings.ml_scoring_weight_ml,
                "safety": 30 * settings.ml_scoring_weight_ahp
                + ml_feature_importance.get("safety", 0)
                * settings.ml_scoring_weight_ml,
                **ml_feature_importance,
            },
            dimension_analysis=dimension_analysis,
            suggestions=suggestions,
        )

        return {"evaluation_result": result}

    def _calculate_ahp_score(
        self,
        child: ChildProfile,
        plan: ProposedPlan,
        child_state: ChildState,
        docs: List[KnowledgeItem],
    ) -> tuple[float, str, List[str], Dict[str, DimensionAnalysis]]:
        """
        计算 AHP 分数
        维度权重 (假设):
        1. 科学性 (Scientific Match): 40% - 是否有理论依据，是否针对孩子问题
        2. 年龄适配度 (Age Appropriateness): 30% - 强度、时长是否符合年龄
        3. 安全性 (Safety): 30% - 风险等级、禁忌症
        """

        suggestions = []
        dimension_analysis = {}

        # --- 1. Scientific Match (40%) ---
        scientific_score = 0
        scientific_reasoning = []
        scientific_issues = []

        doc_match_count = 0
        if docs:
            # 简单逻辑：如果有相关文档支持，且文档相关性高，则得分高
            avg_relevance = sum(d.relevance_score for d in docs) / len(docs)
            scientific_score = min(100, avg_relevance * 100)
            doc_match_count = len(docs)
            scientific_reasoning.append(
                f"基于 {doc_match_count} 条专业文献支持，平均相关度 {avg_relevance:.0%}"
            )
        else:
            scientific_score = 50  # 默认中等
            scientific_issues.append("缺乏明确的科学依据支持")
            suggestions.append("缺乏明确的科学依据支持，建议参考更多专业资料。")

        # 针对性检查：计划目标是否覆盖了孩子的问题
        covered_issues = 0
        if child.issues:
            for issue in child.issues:
                issue_kws = set(jieba.lcut(issue))
                matched = False
                for goal in plan.goals:
                    goal_kws = set(jieba.lcut(goal))
                    # 计算 Jaccard 相似度或简单的关键词重叠
                    # 过滤掉单字词
                    overlap = {kw for kw in (issue_kws & goal_kws) if len(kw) > 1}
                    if overlap:
                        matched = True
                        break
                    # Fallback to substring matching
                    if issue in goal or goal in issue:
                        matched = True
                        break

                if matched:
                    covered_issues += 1

            issue_coverage = covered_issues / len(child.issues)
            scientific_score = (scientific_score * 0.7) + (issue_coverage * 100 * 0.3)
            scientific_reasoning.append(
                f"计划目标覆盖了 {covered_issues}/{len(child.issues)} 个家长主诉问题"
            )

        dimension_analysis["scientific_match"] = DimensionAnalysis(
            score=scientific_score,
            weight=rules.scoring.weight_scientific,
            analysis="; ".join(scientific_reasoning),
            issues=scientific_issues,
        )

        # --- 2. Age Appropriateness (30%) ---
        age_score = 100
        age_reasoning = []
        age_issues = []

        total_duration = sum(
            a.duration_minutes * a.frequency_weekly for a in plan.activities
        )
        age_reasoning.append(f"周总训练时长: {total_duration}分钟")

        # 规则示例：5岁以下每周不宜超过 300 分钟高强度结构化训练 (假设)
        if (
            child.age < 5
            and total_duration > rules.scoring.max_weekly_duration_preschool
        ):
            age_score -= rules.scoring.penalty_duration_overlimit
            age_issues.append(
                f"周总时长({total_duration}min)超过幼儿建议上限({rules.scoring.max_weekly_duration_preschool}min)"
            )
            suggestions.append(
                f"对于 {child.age} 岁儿童，每周结构化训练时长过长 ({total_duration}分钟)，建议缩减。"
            )

        # 检查单次时长
        long_activities = []
        for activity in plan.activities:
            if (
                child.age < 6
                and activity.duration_minutes
                > rules.scoring.max_single_duration_preschool
            ):
                age_score -= rules.scoring.penalty_single_duration_overlimit
                long_activities.append(activity.name)
                suggestions.append(
                    f"活动 '{activity.name}' 单次时长 ({activity.duration_minutes}分) 对幼儿过长，建议拆分。"
                )

        if long_activities:
            age_issues.append(f"部分活动单次时长过长: {', '.join(long_activities)}")
        else:
            age_reasoning.append("单次活动时长设置合理")

        age_score = max(0, age_score)

        dimension_analysis["age_appropriateness"] = DimensionAnalysis(
            score=age_score,
            weight=rules.scoring.weight_age,
            analysis="; ".join(age_reasoning),
            issues=age_issues,
        )

        # --- 3. Safety (30%) ---
        safety_score = 100
        safety_reasoning = []
        safety_issues = []

        # 检查高风险活动
        high_risk_activities = [a for a in plan.activities if a.intensity == "high"]
        if child.age < 4 and high_risk_activities:
            safety_score -= rules.scoring.penalty_high_intensity_preschool
            safety_issues.append(
                f"低龄儿童包含 {len(high_risk_activities)} 项高强度活动"
            )
            suggestions.append("低龄儿童应避免过多高强度活动。")
        else:
            safety_reasoning.append("活动强度与年龄基本匹配")

        # 结合检索到的风险提示
        risk_docs = [doc for doc in docs if doc.risk_level == "High"]
        for doc in risk_docs:
            safety_score -= rules.scoring.penalty_risk_high
            safety_issues.append(f"知识库命中高风险提示: {doc.content[:15]}...")
            suggestions.append(f"注意风险：{doc.content[:20]}...")

        # 结合 Child State (个性化修正)
        if child_state:
            # 例如：如果前庭觉缺陷 (deficit)，一开始不宜进行过强的旋转 (High intensity)
            if (
                child_state.vestibular_system
                and child_state.vestibular_system.status == "deficit"
            ):
                for activity in plan.activities:
                    # 使用 category 进行更精准的判断
                    if (
                        activity.category == "vestibular"
                        and activity.intensity == "high"
                    ):
                        safety_score -= rules.scoring.penalty_vestibular_mismatch
                        safety_issues.append(
                            f"前庭觉敏感儿童不宜进行高强度前庭活动: {activity.name}"
                        )
                        suggestions.append(
                            f"鉴于前庭觉敏感，活动 '{activity.name}' 建议降低强度或改为温和的前庭活动。"
                        )

        safety_score = max(0, safety_score)

        dimension_analysis["safety"] = DimensionAnalysis(
            score=safety_score,
            weight=rules.scoring.weight_safety,
            analysis="; ".join(safety_reasoning) if not safety_issues else "",
            issues=safety_issues,
        )

        # 结合 RAG 资料丰富解释
        rag_info = ""
        if docs:
            high_relevance_docs = [d for d in docs if d.relevance_score > 0.8]
            if high_relevance_docs:
                rag_info = f"（其中，计划获得了《{high_relevance_docs[0].source_book}》等专业资料的强力支持）"
            elif len(docs) > 0:
                rag_info = f"（参考了《{docs[0].source_book}》等资料）"

        # --- Final Calculation ---
        final_score = (
            (scientific_score * rules.scoring.weight_scientific)
            + (age_score * rules.scoring.weight_age)
            + (safety_score * rules.scoring.weight_safety)
        )

        explanation = (
            f"科学性得分 {scientific_score:.0f} (权重{rules.scoring.weight_scientific*100:.0f}%), "
            f"年龄适配度 {age_score:.0f} (权重{rules.scoring.weight_age*100:.0f}%), "
            f"安全性 {safety_score:.0f} (权重{rules.scoring.weight_safety*100:.0f}%)。"
            f"{rag_info}"
        )

        return final_score, explanation, suggestions, dimension_analysis
