"""BookMetadataAnalyzer - 从文档中提取年龄范围和领域元数据"""

import json
from typing import Optional

from json_repair import repair_json as _repair

from src.schemas.rag_eval.draft import BookMetadata
from src.schemas.rag_eval.source_document import SourceDocumentRead
from src.schemas.llm import LLMMessage, LLMRequest
from src.config.core.manager import ConfigManager
from src.core.llm.factory import LLMServiceFactoryCompat
from src.utils.logger import logger


_VALID_DOMAINS = {"gross_motor", "fine_motor", "language", "cognitive", "social_emotional", "sensory_integration"}

_METADATA_PROMPT = """分析以下文档，推断适用的儿童年龄范围和测试领域。返回 JSON:
{{"age_ranges": [[0, 0.5]], "domains": ["gross_motor"], "difficulty_hint": "easy", "topic_summary": "..."}}
文档标题: {title} | 类型: {file_type}
内容摘要: {content_summary}"""


class BookMetadataAnalyzer:
    """从文档中提取年龄范围和领域元数据"""

    def __init__(self, config_cache: Optional[ConfigManager] = None):
        self._config = config_cache or ConfigManager()

    async def analyze(self, document: SourceDocumentRead) -> BookMetadata:
        prompt = _METADATA_PROMPT.format(
            title=document.title or "",
            file_type=document.file_type or "",
            content_summary=(document.content_summary or "")[:3000],
        )

        try:
            model = self._config.get_config_value("rag.eval.draft.llm_model", "") or "qwen-plus"
            llm = LLMServiceFactoryCompat.create(
                model_name=model,
                temperature=self._config.get_config_value("rag.eval.draft.temperature", 0.3),
                max_tokens=self._config.get_config_value("rag.eval.draft.max_tokens", 2048),
            )
            resp = await llm.chat(LLMRequest(
                messages=[LLMMessage(role="user", content=prompt)],
                model_name=model,
            ))

            try:
                parsed = json.loads(resp.content.strip())
            except json.JSONDecodeError:
                parsed = json.loads(_repair(resp.content.strip()))

            age_ranges = [
                (float(r[0]), float(r[1]))
                for r in parsed.get("age_ranges", [])
                if isinstance(r, list) and len(r) == 2
            ]
            domains = [d for d in parsed.get("domains", []) if d in _VALID_DOMAINS]

            logger.info(f"元数据分析: age={age_ranges}, domains={domains}")
            return BookMetadata(
                age_ranges=age_ranges,
                domains=domains,
                difficulty_hint=parsed.get("difficulty_hint"),
                topic_summary=parsed.get("topic_summary", ""),
            )
        except Exception as e:
            logger.error(f"元数据分析失败: {e}")
            return BookMetadata(age_ranges=[], domains=[], topic_summary="")

    def _extract_chunks_by_metadata(self, chunks: list[dict], metadata: BookMetadata) -> list[dict]:
        """根据元数据过滤和分组分块（当前直接返回全部，子类可覆写）"""
        return chunks
