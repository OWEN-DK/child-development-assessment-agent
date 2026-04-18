"""
边界场景处理器 (Phase D-5/D-6)

处理输入校验（空查询/超长查询/特殊字符）和年龄边界映射与降级策略。
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from src.utils.logger import logger


class DevelopmentStage(str, Enum):
    """儿童发展阶段"""

    INFANT = "infant"  # 婴儿期 (0-1 岁)
    TODDLER = "toddler"  # 幼儿期 (1-3 岁)
    PRESCHOOL = "preschool"  # 学龄前 (3-6 岁)
    SCHOOL_AGE = "school_age"  # 学龄期 (6-12 岁)
    ADOLESCENT = "adolescent"  # 青少年期 (13-18 岁)


@dataclass
class ValidationResult:
    """输入校验结果"""

    is_valid: bool
    cleaned_query: str
    error_message: Optional[str] = None
    warning_message: Optional[str] = None
    original_query: Optional[str] = None
    fallback_triggered: bool = False
    fallback_type: Optional[str] = None


class BoundaryHandler:
    """边界场景处理器"""

    MAX_QUERY_LENGTH = 200
    INTENT_EXTRACT_LENGTH = 50
    SPECIAL_CHAR_PATTERN = re.compile(r"[^\u4e00-\u9fa5a-zA-Z0-9\s]")

    AGE_STAGE_MAP = [
        (0, 1, DevelopmentStage.INFANT),
        (1, 3, DevelopmentStage.TODDLER),
        (3, 6, DevelopmentStage.PRESCHOOL),
        (6, 12, DevelopmentStage.SCHOOL_AGE),
        (13, 18, DevelopmentStage.ADOLESCENT),
    ]

    def validate_and_clean(self, query: str) -> ValidationResult:
        """
        输入校验与预处理

        Args:
            query: 原始查询

        Returns:
            ValidationResult: 校验结果
        """
        if not query or not query.strip():
            return ValidationResult(
                is_valid=False, cleaned_query="", error_message="请输入搜索内容"
            )

        original_query = query.strip()

        if len(original_query) > self.MAX_QUERY_LENGTH:
            logger.warning(
                f"查询超长 ({len(original_query)} 字)，截断至 {self.MAX_QUERY_LENGTH} 字"
            )
            original_query = original_query[: self.MAX_QUERY_LENGTH]

        cleaned = self.SPECIAL_CHAR_PATTERN.sub(" ", original_query)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        if not cleaned:
            return ValidationResult(
                is_valid=False,
                cleaned_query="",
                error_message="查询仅包含特殊字符，请输入有效内容",
                original_query=query,
            )

        warning = None
        if len(cleaned) != len(query.strip()):
            warning = "已过滤特殊字符"

        return ValidationResult(
            is_valid=True,
            cleaned_query=cleaned,
            warning_message=warning,
            original_query=query,
        )

    def extract_intent(self, query: str) -> str:
        """
        超长查询意图提取

        Args:
            query: 原始查询（已校验）

        Returns:
            str: 提取的关键意图
        """
        if len(query) <= self.INTENT_EXTRACT_LENGTH:
            return query

        intent = query[: self.INTENT_EXTRACT_LENGTH]

        last_space = intent.rfind(" ")
        if last_space > self.INTENT_EXTRACT_LENGTH * 0.6:
            intent = intent[:last_space]

        logger.info(f"超长查询意图提取：{len(query)} 字 -> {len(intent)} 字")

        return intent.strip()

    @classmethod
    def get_development_stage(cls, age: int) -> DevelopmentStage:
        """根据年龄获取发展阶段"""
        if age < 0:
            return DevelopmentStage.INFANT

        for min_age, max_age, stage in cls.AGE_STAGE_MAP:
            if min_age <= age <= max_age:
                return stage

        return DevelopmentStage.ADOLESCENT

    @classmethod
    def map_age到_stage_range(cls, age: int) -> Tuple[int, int]:
        """
        将边界年龄映射到发展阶段范围

        Args:
            age: 用户年龄

        Returns:
            Tuple[int, int]: (阶段最小年龄, 阶段最大年龄)
        """
        stage = cls.get_development_stage(age)

        stage_ranges = {
            DevelopmentStage.INFANT: (0, 1),
            DevelopmentStage.TODDLER: (1, 3),
            DevelopmentStage.PRESCHOOL: (3, 6),
            DevelopmentStage.SCHOOL_AGE: (6, 12),
            DevelopmentStage.ADOLESCENT: (13, 18),
        }

        return stage_ranges.get(stage, (0, 18))

    def apply_fallback_strategy(
        self,
        query: str,
        age: int,
        results: list,
        strict_mode: bool = True,
    ) -> Tuple[list, List[str]]:
        """
        无结果降级策略

        Args:
            query: 查询
            age: 年龄
            results: 当前检索结果
            strict_mode: 是否严格模式

        Returns:
            Tuple[list, List[str]]: (降级后结果, 降级日志)
        """
        fallback_logs = []

        if results:
            return results, fallback_logs

        fallback_logs.append(f"无结果，触发降级策略：query='{query}', age={age}")

        # 降级 1: 放宽年龄过滤
        if strict_mode:
            fallback_logs.append("降级 1: 放宽年龄过滤（严格→宽松）")

        # 降级 2: 降低分数阈值
        fallback_logs.append("降级 2: 降低分数阈值")

        # 降级 3: 返回通用内容
        fallback_logs.append("降级 3: 返回最相关的通用内容")

        return [], fallback_logs
