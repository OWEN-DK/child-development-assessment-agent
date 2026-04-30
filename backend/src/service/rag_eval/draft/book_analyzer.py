"""BookMetadataAnalyzer - 从文档中提取主题摘要"""

import json

from json_repair import repair_json

from src.schemas.rag_eval.draft import BookMetadata
from src.schemas.llm import LLMMessage, LLMRequest
from src.config.core.manager import ConfigManager
from src.core.llm.factory import LLMServiceFactoryCompat
from src.utils.logger import logger


_SUMMARY_PROMPT = """分析以下文档，用一句话概括其核心主题。返回 JSON:
{{"topic_summary": "..."}}
文档标题: {title} | 类型: {file_type}
内容摘要: {content_summary}"""


class BookMetadataAnalyzer:
    """从文档中提取 topic_summary，用于辅助生成 prompt 上下文"""

    def __init__(self, config_cache: ConfigManager | None = None):
        self._config = config_cache or ConfigManager()

    async def analyze(
        self, title: str, file_type: str, content_summary: str,
    ) -> BookMetadata:
        """提取文档主题摘要"""
        try:
            prompt = _SUMMARY_PROMPT.format(
                title=title, file_type=file_type,
                content_summary=content_summary or "（无摘要）",
            )
            model = self._config.get_config_value("rag.eval.draft.llm_model", "") or "qwen-plus"
            llm = LLMServiceFactoryCompat.create(
                model_name=model, temperature=0.1, max_tokens=256,
            )
            resp = await llm.chat(LLMRequest(
                messages=[LLMMessage(role="user", content=prompt)],
                model_name=model, temperature=0.1, max_tokens=256,
            ))

            try:
                data = json.loads(resp.content.strip())
            except json.JSONDecodeError:
                data = json.loads(repair_json(resp.content.strip()))

            return BookMetadata(
                topic_summary=data.get("topic_summary", ""),
            )
        except Exception as e:
            logger.warning(f"元数据提取失败: {e}")
            return BookMetadata()
