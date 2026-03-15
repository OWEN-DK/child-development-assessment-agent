import json
import re
from typing import List, Optional
from pydantic import BaseModel, Field
from llama_index.llms.dashscope import DashScope
from src.config.settings import settings
from src.utils.logger import logger
from src.core.prompts import METADATA_EXTRACTION_PROMPT


class ExtractedMetadata(BaseModel):
    summary: str = Field(default="", description="内容的简要摘要（最多50字）")
    topics: List[str] = Field(default_factory=list, description="关键词列表")
    brain_regions: List[str] = Field(
        default_factory=list, description="提到或隐含的大脑区域列表"
    )
    target_age_min: int = Field(
        default=0, description="推荐最小年龄，无明确标注时默认为0"
    )
    target_age_max: int = Field(
        default=18, description="推荐最大年龄，无明确标注时默认为18"
    )
    activity_type: str = Field(default="Theory", description="内容类型")


class MetadataExtractor:
    @staticmethod
    async def extract(text: str) -> ExtractedMetadata:
        """
        使用LLM从文本中提取结构化元数据。
        """
        # 截断文本以避免Token限制问题（例如2000字符）
        truncated_text = text[:2000]

        # 格式化提示词
        prompt = METADATA_EXTRACTION_PROMPT.format(text=truncated_text)

        try:
            if not settings.dashscope_api_key:
                logger.warning("DASHSCOPE_API_KEY 未配置，返回默认元数据。")
                return ExtractedMetadata(
                    summary="元数据提取功能需要API Key", topics=[], brain_regions=[]
                )
            # 增加长度限制，最多提取10个主题，避免返回过多标签
            MAX_TOPICS = 8
            MAX_BRAIN_REGIONS = 5

            # 元数据提取使用qwen-turbo模型，速度优先
            llm = DashScope(
                model=settings.llm_models["metadata_extraction"],
                api_key=settings.dashscope_api_key,
                timeout=10,  # 将超时时间减少到10秒以加快失败处理
                max_retries=1,  # 仅重试1次以减少延迟
            )

            # 调用LLM
            response = await llm.acomplete(prompt)
            response_text = str(response.text).strip()

            # 从响应中提取JSON
            # 可能被包裹在```json ... ```中
            json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试找到第一个{和最后一个}
                start = response_text.find("{")
                end = response_text.rfind("}")
                if start != -1 and end != -1:
                    json_str = response_text[start : end + 1]
                else:
                    json_str = response_text

            # 解析JSON
            data = json.loads(json_str)

            # 清理和限制topics
            if "topics" in data and isinstance(data["topics"], list):
                # 去重、过滤空字符串和过短内容
                cleaned_topics = list(
                    {
                        t.strip()
                        for t in data["topics"]
                        if isinstance(t, str) and len(t.strip()) >= 2
                    }
                )
                # 限制最大数量
                data["topics"] = cleaned_topics[:MAX_TOPICS]
            else:
                data["topics"] = []

            # 清理和限制brain_regions
            if "brain_regions" in data and isinstance(data["brain_regions"], list):
                cleaned_regions = list(
                    {
                        r.strip()
                        for r in data["brain_regions"]
                        if isinstance(r, str) and len(r.strip()) >= 2
                    }
                )
                data["brain_regions"] = cleaned_regions[:MAX_BRAIN_REGIONS]
            else:
                data["brain_regions"] = []

            # 验证activity_type
            allowed_activity_types = {
                "Theory",
                "Assessment",
                "Game/Activity",
                "Advice",
                "CaseStudy",
            }
            if (
                "activity_type" not in data
                or data["activity_type"] not in allowed_activity_types
            ):
                data["activity_type"] = "Theory"

            # 验证并清理年龄字段
            try:
                if "target_age_min" in data:
                    # 确保是整数，并且在0-18范围内
                    age_min = int(data["target_age_min"])
                    data["target_age_min"] = max(0, min(age_min, 18))
                else:
                    data["target_age_min"] = 0

                if "target_age_max" in data:
                    age_max = int(data["target_age_max"])
                    data["target_age_max"] = max(0, min(age_max, 18))
                else:
                    data["target_age_max"] = 18

                # 确保最小年龄不大于最大年龄
                if data["target_age_min"] > data["target_age_max"]:
                    data["target_age_min"], data["target_age_max"] = (
                        data["target_age_max"],
                        data["target_age_min"],
                    )
            except (ValueError, TypeError):
                # 解析失败时使用默认值
                data["target_age_min"] = 0
                data["target_age_max"] = 18

            return ExtractedMetadata(**data)

        except Exception as e:
            logger.error(f"元数据提取失败: {e}", exc_info=True)
            # 失败时返回默认/空元数据
            return ExtractedMetadata(summary="提取失败")
