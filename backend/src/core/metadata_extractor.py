import json
import re
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from src.config import settings
from src.utils.logger import logger
from src.core.prompts import METADATA_EXTRACTION_PROMPT
from src.core.llm.factory import LLMServiceFactory, LLMFramework
from src.core.llm.base import LLMRequest, LLMMessage


from src.config import rules


class ExtractedMetadata(BaseModel):
    summary: str = Field(default="", description="内容的简要摘要（最多50字）")
    topics: List[str] = Field(default_factory=list, description="关键词列表")
    brain_regions: List[str] = Field(
        default_factory=list, description="提到或隐含的大脑区域列表"
    )
    target_age_min: float = Field(
        default=0.0, description="推荐最小年龄，无明确标注时默认为0"
    )
    target_age_max: float = Field(
        default=18.0, description="推荐最大年龄，无明确标注时默认为18"
    )
    activity_type: str = Field(default="Theory", description="内容类型")


class RuleBasedMetadataExtractor:
    """基于规则的元数据提取器，作为LLM提取失败后的降级方案"""

    def __init__(self):
        # 从全局规则配置中加载元数据规则，受settings统一管控
        metadata_config = rules.metadata

        self.theme_keywords = metadata_config.theme_keywords
        self.brain_regions_map = metadata_config.brain_regions_map
        self.activity_type_keywords = metadata_config.activity_type_keywords
        self.age_patterns = metadata_config.age_patterns

        logger.info("Metadata rules loaded from global rule settings")

    def extract_age_range(self, text: str) -> Tuple[float, float]:
        """从文本中提取年龄范围"""
        for pattern in self.age_patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    return float(groups[0]), float(groups[1])
                elif len(groups) == 1:
                    age_value = float(groups[0])
                    match_text = match.group(0)
                    if "月龄" in match_text:
                        age = age_value / 12
                        return round(age, 1), round(age, 1)
                    elif "以上" in match_text:
                        return age_value, 18.0
        return 0.0, 18.0

    def extract_themes(self, text: str) -> List[str]:
        """提取内容主题"""
        themes = []
        for theme, keywords in self.theme_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    themes.append(theme)
                    break
        return list(set(themes))[:8]  # 最多返回8个主题

    def extract_brain_regions(self, themes: List[str]) -> List[str]:
        """根据主题提取相关脑区"""
        regions = set()
        for theme in themes:
            if theme in self.brain_regions_map:
                regions.update(self.brain_regions_map[theme])
        return list(regions)[:5]  # 最多返回5个脑区

    def extract_activity_type(self, text: str) -> str:
        """提取活动类型"""
        for activity_type, keywords in self.activity_type_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return activity_type
        return "Theory"

    def extract_summary(self, text: str, max_length: int = 50) -> str:
        """生成简易摘要，截取前 N 个字符"""
        # 清理多余空白：先处理连续换行，再清理行首尾空格，保留单词间单个空格
        cleaned_text = re.sub(r"\n\s*\n", "\n\n", text)
        cleaned_text = "\n".join(line.strip() for line in cleaned_text.split("\n"))
        cleaned_text = re.sub(r" {2,}", " ", cleaned_text)
        cleaned_text = cleaned_text.strip()
        if len(cleaned_text) <= max_length:
            return cleaned_text
        return cleaned_text[:max_length] + "..."

    def extract(self, text: str) -> ExtractedMetadata:
        """基于规则提取所有元数据"""
        age_min, age_max = self.extract_age_range(text)
        themes = self.extract_themes(text)

        return ExtractedMetadata(
            summary=self.extract_summary(text),
            topics=themes,
            brain_regions=self.extract_brain_regions(themes),
            target_age_min=int(age_min) if age_min.is_integer() else age_min,
            target_age_max=int(age_max) if age_max.is_integer() else age_max,
            activity_type=self.extract_activity_type(text),
        )


# 初始化规则提取器单例
_rule_extractor = RuleBasedMetadataExtractor()


# LLM 响应缓存（内存缓存，进程级别）
_llm_response_cache: Dict[str, ExtractedMetadata] = {}
_cache_max_size = 10000  # 最大缓存条目数


class MetadataExtractor:
    @staticmethod
    async def extract(
        text: str, max_retries: int = 1, use_cache: bool = True
    ) -> ExtractedMetadata:
        """
        使用三级降级机制提取结构化元数据：
        1. 优先使用 LLM 提取（支持重试和缓存）
        2. LLM 失败时使用规则引擎提取
        3. 规则提取失败时返回默认元数据

        Args:
            text: 待提取的文本
            max_retries: 最大重试次数，默认 1 次（减少重试以加速）
            use_cache: 是否使用缓存，默认 True
        """
        # 清理内容：去除多余空行，保留英文单词间单个空格
        cleaned_text = re.sub(r"\n\s*\n", "\n\n", text)
        # 清理行首行尾空格，但保留行内单词间的单个空格
        cleaned_text = "\n".join(line.strip() for line in cleaned_text.split("\n"))
        # 清理多个连续空格为单个空格
        cleaned_text = re.sub(r" {2,}", " ", cleaned_text)
        cleaned_text = cleaned_text.strip()

        # 输入校验
        if not cleaned_text or len(cleaned_text) < 10:
            logger.warning("内容过短，使用规则提取元数据")
            return _rule_extractor.extract(cleaned_text)

        # 生成缓存键（使用文本哈希）
        cache_key = None
        if use_cache:
            import hashlib

            cache_key = hashlib.md5(cleaned_text[:2000].encode()).hexdigest()
            if cache_key in _llm_response_cache:
                logger.debug(f"LLM 元数据提取命中缓存")
                return _llm_response_cache[cache_key]

        # 截断文本以避免 Token 限制问题
        truncated_text = cleaned_text[:2000]

        # 优先使用 LLM 提取，支持重试
        for attempt in range(max_retries + 1):
            try:
                if not settings.dashscope_api_key:
                    logger.warning("DASHSCOPE_API_KEY 未配置，降级到规则提取")
                    break

                # 格式化提示词
                prompt = METADATA_EXTRACTION_PROMPT.format(text=truncated_text)

                # 使用工厂创建 LLM 实例
                llm = LLMServiceFactory.create(
                    framework=LLMFramework.LLAMAINDEX,
                    model_name=settings.llm_models["metadata_extraction"],
                    scenario="metadata_extraction",
                    temperature=0.4,
                )

                # 构建提示词
                messages = [
                    LLMMessage(
                        role="system",
                        content="你是一个元数据提取专家，擅长从文本中提取结构化信息。",
                    ),
                    LLMMessage(role="user", content=prompt),
                ]

                # 调用 LLM
                response = await llm.chat(
                    LLMRequest(
                        messages=messages,
                        model_name=settings.llm_models["metadata_extraction"],
                        temperature=0.4,
                        max_tokens=1024,
                        scenario="metadata_extraction",
                        prompt_key="metadata_extraction",
                    )
                )
                response_text = response.content.strip()

                # 从响应中提取JSON
                json_match = re.search(
                    r"```json\s*(.*?)\s*```", response_text, re.DOTALL
                )
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

                # 增加长度限制，最多提取8个主题，5个脑区
                MAX_TOPICS = 8
                MAX_BRAIN_REGIONS = 5

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
                        # 支持浮点型年龄
                        age_min = float(data["target_age_min"])
                        data["target_age_min"] = max(0.0, min(18.0, age_min))
                    else:
                        data["target_age_min"] = 0.0

                    if "target_age_max" in data:
                        age_max = float(data["target_age_max"])
                        data["target_age_max"] = max(0.0, min(18.0, age_max))
                    else:
                        data["target_age_max"] = 18.0

                    # 确保最小年龄不大于最大年龄
                    if data["target_age_min"] > data["target_age_max"]:
                        data["target_age_min"], data["target_age_max"] = (
                            data["target_age_max"],
                            data["target_age_min"],
                        )

                    # 转换为整数保持兼容性
                    data["target_age_min"] = (
                        int(data["target_age_min"])
                        if data["target_age_min"].is_integer()
                        else data["target_age_min"]
                    )
                    data["target_age_max"] = (
                        int(data["target_age_max"])
                        if data["target_age_max"].is_integer()
                        else data["target_age_max"]
                    )

                except (ValueError, TypeError):
                    # 解析失败时使用规则提取的年龄
                    age_min, age_max = _rule_extractor.extract_age_range(text)
                    data["target_age_min"] = age_min
                    data["target_age_max"] = age_max

                # 构建结果对象
                result = ExtractedMetadata(**data)

                # 缓存结果
                if use_cache and cache_key:
                    if len(_llm_response_cache) >= _cache_max_size:
                        # 简单 LRU：删除第一个元素
                        _llm_response_cache.pop(next(iter(_llm_response_cache)))
                    _llm_response_cache[cache_key] = result

                logger.info("LLM 元数据提取成功")
                return result

            except (TimeoutError, ConnectionError) as e:
                # 可重试错误
                if attempt < max_retries - 1:
                    logger.warning(
                        f"LLM提取尝试 {attempt + 1} 失败（可重试）: {e}, 正在重试..."
                    )
                    await asyncio.sleep(1 * (attempt + 1))  # 指数退避
                else:
                    logger.error(f"LLM提取失败，已重试 {max_retries} 次: {e}")
            except Exception as e:
                # 不可重试错误，直接降级
                logger.error(f"LLM提取失败（不可重试错误）: {e}")
                break

        # LLM失败，使用规则引擎提取
        logger.info("降级到规则引擎提取元数据")
        try:
            metadata = _rule_extractor.extract(text)
            logger.info("规则引擎元数据提取成功")
            return metadata
        except Exception as e:
            logger.error(f"规则引擎提取失败: {e}, 使用默认元数据")

        # 所有方式都失败，返回默认元数据
        return ExtractedMetadata(summary="提取失败")
