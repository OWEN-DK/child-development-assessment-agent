"""
本地同义词扩展器 (Phase C-2)

LLM 失败时的兜底策略，基于领域词典 + 多级匹配策略提供高质量的同义词扩展。
支持三级降级加载：数据库 → 本地 JSON → 空词典
"""

import json
from pathlib import Path
from typing import List, Optional, Set

from src.config import settings
from src.utils.logger import logger


class LocalSynonymExpander:
    """本地同义词扩展器（LLM 失败时兜底）"""

    _ever_initialized = False

    def __init__(self, synonyms_file: Optional[str] = None):
        self._synonyms_dict = self._load_synonyms(synonyms_file)
        if not LocalSynonymExpander._ever_initialized:
            LocalSynonymExpander._ever_initialized = True
            logger.info(
                f"LocalSynonymExpander 初始化完成，加载 {len(self._synonyms_dict)} 个领域词典"
            )

    def expand(self, query: str) -> List[str]:
        """
        扩展查询的同义词

        Args:
            query: 原始查询

        Returns:
            扩展后的同义词列表（包含原词）
        """
        result: Set[str] = {query}

        matched = self._exact_match(query)
        result.update(matched)

        matched = self._substring_match(query)
        result.update(matched)

        if len(query) > 4:
            matched = self._tokenized_match(query)
            result.update(matched)

        return list(dict.fromkeys(result))

    def _exact_match(self, query: str) -> Set[str]:
        """精确匹配：查询词完全等于词典中的键"""
        synonyms: Set[str] = set()

        for category, terms in self._synonyms_dict.items():
            if query in terms:
                synonyms.update(terms[query])
                break
            for key, values in terms.items():
                if query in values:
                    synonyms.add(key)
                    synonyms.update([v for v in values if v != query])
                    break

        return synonyms

    def _substring_match(self, query: str) -> Set[str]:
        """子串匹配：查询包含词典中的词"""
        synonyms: Set[str] = set()

        for category, terms in self._synonyms_dict.items():
            for key, values in terms.items():
                if key in query and len(key) >= 2:
                    synonyms.update(values)

        return synonyms

    def _tokenized_match(self, query: str) -> Set[str]:
        """分词匹配：对长查询分词后逐个匹配"""
        synonyms: Set[str] = set()

        tokens = self._extract_ngrams(query, min_n=2, max_n=4)

        for token in tokens:
            for category, terms in self._synonyms_dict.items():
                if token in terms:
                    synonyms.update(terms[token])

        return synonyms

    @staticmethod
    def _extract_ngrams(text: str, min_n: int = 2, max_n: int = 4) -> List[str]:
        """提取 n-gram 词组"""
        tokens = []
        for n in range(min_n, max_n + 1):
            for i in range(len(text) - n + 1):
                tokens.append(text[i : i + n])
        return tokens

    def _load_synonyms(self, synonyms_file: Optional[str] = None) -> dict:
        """加载本地同义词词典，三级降级"""
        try:
            config_value = getattr(settings, "rag_local_synonyms_dict", None)
            if config_value:
                synonyms = (
                    json.loads(config_value)
                    if isinstance(config_value, str)
                    else config_value
                )
                if not LocalSynonymExpander._ever_initialized:
                    logger.info("本地同义词词典从数据库配置加载成功")
                return synonyms
        except Exception as e:
            logger.warning(f"从数据库配置加载本地同义词词典失败: {e}")

        try:
            file_path = synonyms_file or str(
                Path(__file__).parent.parent.parent / "data" / "local_synonyms.json"
            )
            if Path(file_path).exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    synonyms = json.load(f)
                if not LocalSynonymExpander._ever_initialized:
                    logger.info(f"本地同义词词典从本地文件加载成功: {file_path}")
                return synonyms
        except Exception as e:
            logger.warning(f"从本地文件加载本地同义词词典失败: {e}")

        return {}
