"""
同义词质量验证器 (Phase C-1)

多维度验证 LLM 生成的同义词质量，防止引入不相关或太宽泛的词汇。
支持三级降级加载：数据库 → 本地 JSON → 空词典
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from src.config import settings
from src.utils.logger import logger


@dataclass
class ValidationReport:
    """同义词验证报告"""

    is_valid: bool
    valid_terms: List[str]
    rejected_terms: List[Tuple[str, str]]
    confidence: float


class SynonymValidator:
    """同义词质量验证器"""

    def __init__(self, validation_file: Optional[str] = None):
        self._validation_rules = self._load_rules(validation_file)
        self._blacklist_set = set(self._validation_rules.get("domain_blacklist", []))
        self._whitelist_set = set(self._validation_rules.get("domain_whitelist", []))
        self._domain_terms = self._validation_rules.get("domain_terms", {})

        self._chinese_pattern = re.compile(r"[\u4e00-\u9fa5]")
        self._valid_char_pattern = re.compile(r"^[\u4e00-\u9fa5a-zA-Z0-9\s]+$")

        logger.info(
            f"SynonymValidator 初始化完成，黑名单 {len(self._blacklist_set)} 个词，白名单 {len(self._whitelist_set)} 个词"
        )

    def validate(
        self,
        synonym_list: List[str],
        original_query: str,
    ) -> ValidationReport:
        """
        验证同义词列表质量

        Args:
            synonym_list: 待验证的同义词列表
            original_query: 原始查询词

        Returns:
            ValidationReport: 验证报告
        """
        valid_terms = []
        rejected_terms = []

        for term in synonym_list:
            if term == original_query:
                valid_terms.append(term)
                continue

            reason = self._check_term(term, original_query)
            if reason is None:
                valid_terms.append(term)
            else:
                rejected_terms.append((term, reason))
                if getattr(settings, "rag_synonym_log_rejected", True):
                    logger.debug(f"同义词被拒绝: '{term}'，原因: {reason}")

        total = len(synonym_list)
        valid_count = len(valid_terms)
        confidence = valid_count / total if total > 0 else 0.0

        threshold = getattr(settings, "rag_synonym_quality_threshold", 0.8)

        return ValidationReport(
            is_valid=confidence >= threshold,
            valid_terms=valid_terms,
            rejected_terms=rejected_terms,
            confidence=confidence,
        )

    def _check_term(self, term: str, original_query: str) -> Optional[str]:
        """
        检查单个扩展词，返回 None 表示通过，否则返回拒绝原因
        """
        if len(term) < 2:
            return "太短（单字）"

        if len(term) > 15:
            return "太长（超过 15 字）"

        if not self._valid_char_pattern.match(term):
            return "包含非法字符"

        if term in self._blacklist_set:
            return "在黑名单中（不相关领域）"

        if self._is_too_broad(term, original_query):
            return "太宽泛（粒度不如原词）"

        if term in self._whitelist_set:
            return None

        if self._matches_query_specific_rule(term, original_query):
            return None

        if not self._has_semantic_overlap(term, original_query):
            return "与原词语义无重叠"

        return None

    def _is_too_broad(self, term: str, original_query: str) -> bool:
        """判断扩展词是否比原词太宽泛"""
        query_rules = self._domain_terms.get(original_query, {})
        too_broad_list = query_rules.get("too_broad", [])
        if term in too_broad_list:
            return True

        if len(term) < len(original_query) and term in original_query:
            if len(original_query) - len(term) >= 2:
                return True

        if term in self._whitelist_set and original_query not in self._whitelist_set:
            if len(term) <= len(original_query) * 0.5:
                return True

        return False

    def _has_semantic_overlap(self, term: str, original_query: str) -> bool:
        """检查扩展词与原词是否有语义重叠"""
        if self._chinese_pattern.search(original_query):
            shared_chars = set(term) & set(original_query)
            if shared_chars:
                return True

        if re.search(r"[a-zA-Z]", original_query):
            term_words = set(re.findall(r"[a-zA-Z]{3,}", term.lower()))
            query_words = set(re.findall(r"[a-zA-Z]{3,}", original_query.lower()))
            if term_words & query_words:
                return True

        return False

    def _matches_query_specific_rule(self, term: str, original_query: str) -> bool:
        """检查是否匹配原词专属规则中的 valid 列表"""
        query_rules = self._domain_terms.get(original_query, {})
        valid_terms = query_rules.get("valid", [])
        return term in valid_terms

    def _load_rules(self, validation_file: Optional[str] = None) -> dict:
        """加载验证规则，三级降级"""
        try:
            config_value = getattr(settings, "rag_synonym_validation_rules", None)
            if config_value:
                rules = (
                    json.loads(config_value)
                    if isinstance(config_value, str)
                    else config_value
                )
                logger.info("同义词验证规则从数据库配置加载成功")
                return rules
        except Exception as e:
            logger.warning(f"从数据库配置加载同义词验证规则失败: {e}")

        try:
            file_path = validation_file or str(
                Path(__file__).parent.parent.parent / "data" / "synonym_validation.json"
            )
            if Path(file_path).exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    rules = json.load(f)
                logger.info(f"同义词验证规则从本地文件加载成功: {file_path}")
                return rules
        except Exception as e:
            logger.warning(f"从本地文件加载同义词验证规则失败: {e}")

        logger.warning("使用空验证规则词典，仅启用通用检查（长度/字符/语义重叠）")
        return {"domain_terms": {}, "domain_whitelist": [], "domain_blacklist": []}
