from typing import Dict, Any, List
import json
from llama_index.llms.dashscope import DashScope
from src.config.settings import settings
from src.config.rules import rules
from src.model.schemas import AgentState, ChildState, DevelopmentStatus
from src.core.nodes.base import BaseNode
from src.core.prompts import ASSESSMENT_SYSTEM_PROMPT
from src.utils.logger import logger


class AssessmentNode(BaseNode):
    """儿童发展评估"""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Executing Assessment Node...")

        child = state.child_profile
        condensed = state.condensed_context

        # 1. 准备历史特征摘要
        history_summary = "无历史记录"
        if condensed:
            history_summary = (
                f"周均时长: {condensed.weekly_avg_duration}分钟, "
                f"频率一致性: {condensed.frequency_consistency}, "
                f"强度趋势: {condensed.intensity_trend}, "
                f"近期反馈: {'; '.join(condensed.recent_feedbacks[:3])}"
            )

        # 2. 获取年龄里程碑（后续可替换为MCP调用）
        milestones = self._get_age_milestones(child.age)

        # 3. 构建 Prompt
        # 动态构建输入数据部分，没有历史数据则跳过历史特征
        input_lines = [
            f"- 姓名: {child.name}",
            f"- 年龄: {child.age} 岁",
            f"- 性别: {child.gender}",
            f"- 主要问题: {', '.join(child.issues) if child.issues else '无明显主诉'}",
        ]
        if condensed:
            input_lines.append(f"- 历史运动特征: {history_summary}")
        
        input_data = "\n".join(input_lines)
        prompt = ASSESSMENT_SYSTEM_PROMPT.format(
            milestones=milestones,
            input_data=input_data,
        )

        # 4. 调用 LLM (评估使用qwen-plus模型，专业推理能力)
        if settings.dashscope_api_key:
            try:
                llm = DashScope(
                    model=settings.llm_models["assessment"],
                    api_key=settings.dashscope_api_key,
                )
                response = await llm.acomplete(prompt)
                response_text = response.text.strip()
                logger.debug(f"LLM Assessment Raw Response: {response_text}")

                # 清理可能的 Markdown 标记
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                
                # 清理多余的空白字符和转义字符
                response_text = response_text.strip()
                
                # 尝试修复常见的JSON格式问题
                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON解析失败，尝试修复: {e}")
                    # 修复未闭合的字符串
                    response_text = response_text.rstrip()
                    # 检查并补充缺失的闭合引号、括号等
                    open_braces = response_text.count('{')
                    close_braces = response_text.count('}')
                    open_brackets = response_text.count('[')
                    close_brackets = response_text.count(']')
                    open_quotes = response_text.count('"') % 2 == 1
                    
                    # 补充缺失的闭合符号
                    if open_quotes:
                        response_text += '"'
                    for _ in range(open_brackets - close_brackets):
                        response_text += ']'
                    for _ in range(open_braces - close_braces):
                        response_text += '}'
                    
                    # 再次尝试解析
                    try:
                        data = json.loads(response_text)
                        logger.info("JSON修复成功")
                    except Exception as e2:
                        logger.error(f"JSON修复失败: {e2}，使用默认评估结果")
                        raise

                # 转换为 Pydantic 模型
                child_state = ChildState(
                    vestibular_system=(
                        DevelopmentStatus(**data.get("vestibular_system"))
                        if data.get("vestibular_system")
                        else None
                    ),
                    proprioception=(
                        DevelopmentStatus(**data.get("proprioception"))
                        if data.get("proprioception")
                        else None
                    ),
                    tactile_system=(
                        DevelopmentStatus(**data.get("tactile_system"))
                        if data.get("tactile_system")
                        else None
                    ),
                    core_strength=(
                        DevelopmentStatus(**data.get("core_strength"))
                        if data.get("core_strength")
                        else None
                    ),
                    emotional_regulation=(
                        DevelopmentStatus(**data.get("emotional_regulation"))
                        if data.get("emotional_regulation")
                        else None
                    ),
                    overall_assessment=data.get("overall_assessment", "评估完成"),
                )
                logger.info(f"Assessment completed for {child.name}")
                return {"child_state": child_state}

            except Exception as e:
                logger.error(f"评估失败: {e}")

        logger.warning("LLM不可用或调用失败，返回默认评估结果。")
        # 返回空的子项状态，避免误导
        child_state = ChildState(
            overall_assessment="系统暂时无法生成详细评估，请检查服务连接或API配置。",
        )
        return {"child_state": child_state}

    def _get_age_milestones(self, age: int) -> str:
        """根据年龄返回对应的发展里程碑描述"""
        milestones = rules.assessment.age_milestones
        if age < 3:
            return milestones.get("0-3", "")
        elif 3 <= age < 5:
            return milestones.get("3-5", "")
        elif 5 <= age < 7:
            return milestones.get("5-7", "")
        else:
            return milestones.get("7+", "")
