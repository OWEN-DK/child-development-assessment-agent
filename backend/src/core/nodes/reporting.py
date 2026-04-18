import asyncio
from typing import Any, Dict, List

from src.config import settings
from src.core.llm.factory import LLMFramework, LLMServiceFactory
from src.core.nodes.base import BaseNode
from src.core.prompt.manager import prompt_manager
from src.schemas import (AgentState, ChildProfile, ChildState,
                         EvaluationResult, FinalReport, KnowledgeItem,
                         LLMMessage, LLMRequest, ProposedPlan)
from src.utils.logger import logger

# 全局工厂实例（延迟初始化）
_llm_factory = None


def _get_llm_factory() -> LLMServiceFactory:
    """获取 LLM 工厂实例（延迟初始化）"""
    global _llm_factory
    if _llm_factory is None:
        from src.config.core.manager import config_manager
        from src.core.llm.provider_registry import ProviderRegistry

        provider_registry = ProviderRegistry()
        _llm_factory = LLMServiceFactory(config_manager, provider_registry)
    return _llm_factory


class ReportingNode(BaseNode):
    """报告生成"""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Executing Reporting Node...")

        child = state.child_profile
        plan = state.proposed_plan
        child_state = state.child_state
        eval_result = state.evaluation_result
        docs = state.retrieved_docs

        # 1. 准备 Prompt 数据

        # 整理发展状态详情
        dev_details = []
        radar_data = {}
        if child_state:
            # 提取关键维度分数用于雷达图 (1-5 映射到 20-100)
            if child_state.vestibular_system:
                dev_details.append(
                    f"- 前庭觉: {child_state.vestibular_system.description} (等级 {child_state.vestibular_system.level}/5)"
                )
                radar_data["vestibular"] = child_state.vestibular_system.level * 20
            if child_state.proprioception:
                dev_details.append(
                    f"- 本体感: {child_state.proprioception.description} (等级 {child_state.proprioception.level}/5)"
                )
                radar_data["proprioception"] = child_state.proprioception.level * 20
            if child_state.core_strength:
                dev_details.append(
                    f"- 核心力量: {child_state.core_strength.description} (等级 {child_state.core_strength.level}/5)"
                )
                radar_data["core"] = child_state.core_strength.level * 20
            if child_state.emotional_regulation:
                dev_details.append(
                    f"- 情绪调节: {child_state.emotional_regulation.description} (等级 {child_state.emotional_regulation.level}/5)"
                )
                radar_data["emotion"] = child_state.emotional_regulation.level * 20

        # 整理科学依据
        evidence_list = []
        reference_list = []
        for i, doc in enumerate(docs[:5]):  # 增加到前5条，提供更丰富的信息
            source_info = f"《{doc.source_book}》"
            if doc.chapter_title:
                source_info += f" - {doc.chapter_title}"
            if doc.page_label:
                source_info += f" (第{doc.page_label}页)"

            tags = []
            if doc.brain_regions:
                tags.append(f"脑区: {', '.join(doc.brain_regions)}")
            if doc.topics:
                tags.append(f"主题: {', '.join(doc.topics)}")

            tag_str = f" [{' | '.join(tags)}]" if tags else ""

            # 用于最终报告展示的 Markdown 格式
            evidence_list.append(
                f"{i + 1}. **【{source_info}】**{tag_str}\n   {doc.content}"
            )

            # 用于 Prompt 上下文的纯文本格式
            reference_list.append(f"资料{i + 1} [来源: {source_info}]: {doc.content}")

        # 整理建议
        suggestions_str = (
            "\n".join([f"- {s}" for s in eval_result.suggestions])
            if eval_result and eval_result.suggestions
            else "暂无特殊调整建议，当前计划表现良好。"
        )

        # 整理计划详情
        plan_content_parts = []
        if plan.goals:
            plan_content_parts.append(f"**目标**: {', '.join(plan.goals)}")

        plan_content_parts.append("**活动列表**:")
        for act in plan.activities:
            desc = f" ({act.description})" if act.description else ""
            plan_content_parts.append(
                f"- {act.name}: {act.duration_minutes}分钟, {act.frequency_weekly}次/周{desc}"
            )

        plan_content_str = "\n".join(plan_content_parts)

        # 整理算法分析详情
        algo_analysis_parts = []
        if eval_result and eval_result.dimension_analysis:
            da = eval_result.dimension_analysis

            # 科学性
            if "scientific_match" in da:
                sci = da["scientific_match"]
                algo_analysis_parts.append(f"- **科学性评分**: {sci.score:.0f}/100")
                algo_analysis_parts.append(f"  - 分析: {sci.analysis}")
                if sci.issues:
                    algo_analysis_parts.append(f"  - 发现问题: {'; '.join(sci.issues)}")

            # 年龄适配度
            if "age_appropriateness" in da:
                age = da["age_appropriateness"]
                algo_analysis_parts.append(f"- **年龄适配度评分**: {age.score:.0f}/100")
                algo_analysis_parts.append(f"  - 分析: {age.analysis}")
                if age.issues:
                    algo_analysis_parts.append(f"  - 发现问题: {'; '.join(age.issues)}")

            # 安全性
            if "safety" in da:
                safe = da["safety"]
                algo_analysis_parts.append(f"- **安全性评分**: {safe.score:.0f}/100")
                algo_analysis_parts.append(f"  - 分析: {safe.analysis}")
                if safe.issues:
                    algo_analysis_parts.append(
                        f"  - 发现问题: {'; '.join(safe.issues)}"
                    )

        algo_analysis_str = (
            "\n".join(algo_analysis_parts)
            if algo_analysis_parts
            else "暂无详细算法分析数据"
        )

        # 2. 构建 Prompt
        try:
            import hashlib
            from datetime import datetime

            current_date = datetime.now().strftime("%Y%m%d")
            name_hash = hashlib.md5(child.name.encode()).hexdigest()[:6].upper()
            issues_str = "、".join(child.issues) if child.issues else "暂无具体主诉"

            # Common replacements map
            replacements = {
                "{child_name}": child.name,
                "{date}": current_date,
                "{child_name_hash}": name_hash,
                "{issues_list}": issues_str,
                "{score}": str(round(eval_result.score, 1)) if eval_result else "0",
                "{overall_assessment}": (
                    child_state.overall_assessment if child_state else "暂无评估"
                ),
                "{development_details}": "\n".join(dev_details),
                "{plan_name}": plan.plan_name,
                "{plan_content}": plan_content_str,
                "{reasoning}": eval_result.reasoning if eval_result else "",
                "{algo_analysis}": algo_analysis_str,
                "{scientific_evidence}": (
                    "\n".join(evidence_list)
                    if evidence_list
                    else "暂无直接科学依据引用"
                ),
                "{reference_materials}": (
                    "\n".join(reference_list) if reference_list else "暂无相关参考资料"
                ),
                "{suggestions}": suggestions_str,
            }

            # Helper to format prompt
            def format_prompt(template, mapping):
                p = template
                for k, v in mapping.items():
                    p = p.replace(k, v)
                return p

            # Single-pass generation - 通过 PromptManager 获取提示词并渲染
            # 注意：replacements 的键是带花括号的格式，需要转换为 str.format() 所需的格式
            format_variables = {k.strip("{}"): v for k, v in replacements.items()}
            formatted_prompt_full = await prompt_manager.get_prompt(
                "reporting_system", variables=format_variables
            )

        except Exception as e:
            logger.error(f"Prompt formatting failed: {e}")
            formatted_prompt_full = "Report generation failed due to data error."

        # 3. 检查是否为流式模式
        if state.is_streaming:
            logger.info("Streaming mode enabled. Skipping direct generation.")
            # 返回 Prompts 供 Controller 使用
            report = FinalReport(
                markdown_content="",  # 留空，由 Controller 生成
                structured_data={
                    "score": eval_result.score if eval_result else 0,
                    "radar_chart": radar_data,
                    "key_suggestions": eval_result.suggestions if eval_result else [],
                },
            )
            return {
                "final_report": report,
                "report_prompts": [formatted_prompt_full],
            }

        # 4. 调用 LLM 生成报告 (单次调用)
        markdown_content = ""
        if settings.dashscope_api_key:
            try:
                # 使用新的异步工厂创建 LLM 实例
                factory = _get_llm_factory()
                llm = await factory.create("report_generation", framework="llamaindex")

                # 构建提示词
                messages = [
                    LLMMessage(
                        role="system",
                        content="你是一个专业的儿童发展评估报告撰写专家，根据提供的评估数据生成清晰、专业、易于家长理解的Markdown格式报告。",
                    ),
                    LLMMessage(role="user", content=formatted_prompt_full),
                ]

                # 调用 LLM（temperature/max_tokens 由工厂从配置自动读取）
                logger.info("Starting report generation...")
                response = await llm.chat(
                    LLMRequest(
                        messages=messages,
                        model_name=settings.model_report_generation,
                        scenario="report_generation",
                        prompt_key="report_generation",
                    )
                )
                markdown_content = response.content.strip()
                logger.info("Report generation completed.")

                # 释放引用
                await factory.release("report_generation", framework="llamaindex")

            except Exception as e:
                logger.error(f"Reporting failed: {e}")
                markdown_content = self._generate_fallback_report(
                    child, plan, eval_result, child_state
                )
        else:
            markdown_content = self._generate_fallback_report(
                child, plan, eval_result, child_state
            )

        # 5. 构建最终结果 (非流式模式)
        report = FinalReport(
            markdown_content=markdown_content,
            structured_data={
                "score": eval_result.score if eval_result else 0,
                "radar_chart": radar_data,
                "key_suggestions": eval_result.suggestions if eval_result else [],
            },
        )

        logger.info("Final report generated.")
        return {"final_report": report}

    def _generate_fallback_report(
        self,
        child: ChildProfile,
        plan: ProposedPlan,
        eval_result: EvaluationResult,
        child_state: ChildState,
    ) -> str:
        """简单的兜底报告生成逻辑"""
        score = eval_result.score if eval_result else 0
        assessment = child_state.overall_assessment if child_state else "暂无评估数据"
        reasoning = eval_result.reasoning if eval_result else "暂无详细分析"

        suggestions_list = []
        if eval_result and eval_result.suggestions:
            suggestions_list = [f"- {s}" for s in eval_result.suggestions]
        suggestions_str = (
            "\n".join(suggestions_list) if suggestions_list else "暂无特殊建议"
        )

        return f"""
# 儿童运动发展评估报告 (基础版)

> **注意**: 由于 AI 服务暂时繁忙，本报告为基础数据版。

## 1. 基本信息
- **姓名**: {child.name}
- **年龄**: {child.age}岁
- **综合评分**: **{score}/100**

## 2. 发展评估
{assessment}

## 3. 计划分析
**计划名称**: {plan.plan_name}

**评分详情**:
{reasoning}

**改进建议**:
{suggestions_str}
"""
