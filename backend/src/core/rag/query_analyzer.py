"""查询类型分析器（适配中文场景）

根据查询特征（长度、专业术语、疑问词、连接词）对查询进行分类，
为动态权重决策提供可靠输入。
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from src.config import settings
from src.schemas.query import QueryType
from src.utils.logger import logger


# 内部详细类型到统一 QueryType 的映射
_INTERNAL_TYPE_MAP = {
    "SHORT": QueryType.DEFAULT,
    "TERMINOLOGY": QueryType.DEFAULT,
    "DESCRIPTIVE": QueryType.SIMPLE,
    "COMPLEX": QueryType.COMPLEX,
    "DEFAULT": QueryType.DEFAULT,
}


@dataclass
class QueryAnalysis:
    """查询分析结果"""

    query_type: QueryType
    original_query: str
    char_length: int
    has_terminology: bool
    matched_terminology: List[str] = field(default_factory=list)
    has_question_word: bool = False
    has_conjunction: bool = False
    confidence: float = 0.0


class QueryAnalyzer:
    """查询类型分析器（适配中文场景）"""

    _ever_initialized = False

    def __init__(self, terminology_file: Optional[str] = None):
        self._terminology_set: Set[str] = self._load_terminology(terminology_file)
        self._question_words = {"怎么办", "如何", "为什么", "怎样", "什么", "哪些"}
        self._conjunction_words = {"和", "与", "的区别", "比较", "对比", "还是"}

    def _load_terminology(self, terminology_file: Optional[str] = None) -> Set[str]:
        """加载专业术语词典（三级降级）

        优先级：
        1. 数据库配置（system_configs 表，key=rag_terminology_list）
        2. 本地 JSON 文件
        3. 内置默认词典（空集合）
        """
        terminology = set()

        # 尝试从数据库配置加载
        try:
            db_config = getattr(settings, "rag_terminology_list", None)
            if db_config and isinstance(db_config, list):
                terminology.update(db_config)
                if not QueryAnalyzer._ever_initialized:
                    QueryAnalyzer._ever_initialized = True
                    logger.info(f"从数据库配置加载 {len(db_config)} 个专业术语")
                return terminology
        except Exception as e:
            logger.debug(f"从数据库加载术语失败：{e}")

        # 尝试从本地 JSON 文件加载
        try:
            if terminology_file:
                file_path = Path(terminology_file)
            else:
                file_path = (
                    Path(__file__).parent.parent.parent / "data" / "terminology.json"
                )

            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # 支持两种格式：
                # 1. {"domain1": ["term1", "term2"], "domain2": [...]}
                # 2. ["term1", "term2", ...]
                if isinstance(data, dict):
                    for terms in data.values():
                        if isinstance(terms, list):
                            terminology.update(terms)
                elif isinstance(data, list):
                    terminology.update(data)

                if not QueryAnalyzer._ever_initialized:
                    QueryAnalyzer._ever_initialized = True
                    logger.info(
                        f"从本地文件加载 {len(terminology)} 个专业术语：{file_path}"
                    )
                return terminology
        except Exception as e:
            logger.debug(f"从本地文件加载术语失败：{e}")

        logger.warning("使用空术语词典（降级到默认）")
        return terminology

    def _match_terminology(self, query: str) -> List[str]:
        """匹配查询中的专业术语（最长匹配优先）

        使用最长匹配策略，避免短术语覆盖长术语。
        例如："感统训练" 和 "感统" 同时存在时，优先匹配 "感统训练"。
        """
        if not self._terminology_set:
            return []

        matched_terms = []
        query_lower = query.lower()

        # 按长度降序排序，实现最长匹配优先
        sorted_terms = sorted(self._terminology_set, key=len, reverse=True)

        # 记录已匹配的字符位置，避免重复匹配
        matched_positions = set()

        for term in sorted_terms:
            term_lower = term.lower()
            start_pos = query_lower.find(term_lower)

            if start_pos != -1:
                # 检查是否与已匹配的位置重叠
                term_positions = set(range(start_pos, start_pos + len(term)))
                if not term_positions.intersection(matched_positions):
                    matched_terms.append(term)
                    matched_positions.update(term_positions)

        return matched_terms

    def analyze(self, query: str) -> QueryAnalysis:
        """分析查询类型

        判定逻辑（优先级从高到低）：
        1. 复杂查询：>15 字 + 含连接词
        2. 短查询：<5 字
        3. 专业术语：含领域关键词 + 3-8 字
        4. 描述性查询：5-15 字 + 含疑问词
        5. 默认：不满足以上任何条件
        """
        stripped_query = query.strip()
        char_length = len(stripped_query)

        # 空查询处理
        if char_length == 0:
            return QueryAnalysis(
                query_type=QueryType.DEFAULT,
                original_query=query,
                char_length=0,
                has_terminology=False,
                matched_terminology=[],
                has_question_word=False,
                has_conjunction=False,
                confidence=0.0,
            )

        # 提取特征
        matched_terms = self._match_terminology(stripped_query)
        has_question = any(w in stripped_query for w in self._question_words)
        has_conjunction = any(w in stripped_query for w in self._conjunction_words)

        # 内部详细分类（用于权重选择）
        if char_length > 15 and has_conjunction:
            _internal_type = "COMPLEX"
        elif matched_terms and 3 <= char_length <= 8:
            _internal_type = "TERMINOLOGY"
        elif char_length < 5:
            _internal_type = "SHORT"
        elif 5 <= char_length <= 15 and has_question:
            _internal_type = "DESCRIPTIVE"
        else:
            _internal_type = "DEFAULT"

        # 映射到统一 QueryType
        query_type = _INTERNAL_TYPE_MAP[_internal_type]

        # 计算置信度
        confidence = self._calculate_confidence(
            query_type, char_length, matched_terms, has_question, has_conjunction
        )

        return QueryAnalysis(
            query_type=query_type,
            original_query=query,
            char_length=char_length,
            has_terminology=bool(matched_terms),
            matched_terminology=matched_terms,
            has_question_word=has_question,
            has_conjunction=has_conjunction,
            confidence=confidence,
        )

    def _calculate_confidence(
        self,
        query_type: QueryType,
        char_length: int,
        matched_terms: List[str],
        has_question: bool,
        has_conjunction: bool,
    ) -> float:
        """计算分类置信度 (0-1)，基于特征匹配强度"""
        confidence = 0.5

        if query_type == QueryType.COMPLEX:
            confidence = 0.9 if char_length > 15 and has_conjunction else 0.7
        elif query_type == QueryType.SIMPLE:
            confidence = 0.85 if has_question and 5 <= char_length <= 15 else 0.7
        else:
            confidence = 0.5

        return round(confidence, 2)
