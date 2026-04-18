"""细粒度年龄适配度计算器"""

import json
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple


class AgeFitScorer:
    """细粒度年龄适配度计算器"""

    # 类级别常量（避免重复初始化）
    _DOMAIN_KEYWORDS: Dict[str, list] = {
        "大动作": ["爬", "走", "跑", "跳", "平衡", "大动作"],
        "精细动作": ["抓", "捏", "画", "剪", "穿珠", "精细动作", "手眼"],
        "语言发展": ["说话", "表达", "词汇", "语言", "沟通"],
        "认知发展": ["思考", "逻辑", "记忆", "注意", "认知"],
        "社交技能": ["分享", "合作", "情绪", "社交", "同伴"],
        "感觉统合": ["前庭", "触觉", "本体", "感统", "感觉"],
    }

    _AGE_LENGTH_PROFILES: Dict[Tuple[int, int], dict] = {
        (0, 2): {"ideal_chars": (30, 100), "ideal_sentences": (1, 3)},
        (2, 4): {"ideal_chars": (50, 200), "ideal_sentences": (2, 5)},
        (4, 6): {"ideal_chars": (100, 400), "ideal_sentences": (3, 8)},
        (6, 12): {"ideal_chars": (200, 800), "ideal_sentences": (5, 15)},
    }

    _AGE_DOMAIN_PRIORITY: Dict[Tuple[int, int], list] = {
        (0, 2): ["大动作", "感觉统合"],
        (2, 4): ["精细动作", "语言发展", "感觉统合"],
        (4, 6): ["认知发展", "社交技能", "精细动作"],
        (6, 12): ["认知发展", "社交技能", "语言发展"],
    }

    @staticmethod
    @lru_cache(maxsize=1024)
    def calculate(
        content: str,
        user_age: int,
        target_age_min: int,
        target_age_max: int,
        metadata_str: str = "",  # 使用字符串而非 dict（lru_cache 要求可哈希）
    ) -> float:
        """
        计算年龄适配度分数

        Args:
            content: 内容文本
            user_age: 用户年龄
            target_age_min: 内容目标年龄下限
            target_age_max: 内容目标年龄上限
            metadata_str: 可选元数据的 JSON 字符串（如 topics, activity_type 等）

        Returns:
            float: 年龄适配度分数 (0-1 连续值)
        """
        metadata = json.loads(metadata_str) if metadata_str else None

        dimension1 = AgeFitScorer._calculate_age_range_match(
            user_age, target_age_min, target_age_max
        )
        dimension2 = AgeFitScorer._calculate_content_feature_fit(content, user_age)
        dimension3 = AgeFitScorer._calculate_domain_match(content, user_age, metadata)

        score = dimension1 + dimension2 + dimension3
        return round(min(1.0, max(0.0, score)), 4)

    @staticmethod
    def _calculate_age_range_match(
        user_age: int, target_min: int, target_max: int
    ) -> float:
        """维度 1: 年龄范围匹配度 (0-0.4)"""
        # 完全在范围内
        if target_min <= user_age <= target_max:
            # 计算在范围内的相对位置，越靠近中心越适配
            range_center = (target_min + target_max) / 2
            range_span = max(target_max - target_min, 1)
            distance_from_center = abs(user_age - range_center)
            # 距离中心越近，分数越高 [0.35, 0.4]
            dimension1 = 0.35 + 0.05 * (1 - distance_from_center / (range_span / 2))

        # 差 1 岁 [0.25, 0.35]
        elif abs(user_age - target_min) == 1 or abs(user_age - target_max) == 1:
            dimension1 = 0.25 + 0.1 * (
                1
                - abs(
                    user_age - target_min
                    if user_age < target_min
                    else user_age - target_max
                )
                / 2
            )

        # 差 2 岁 [0.1, 0.25]
        elif abs(user_age - target_min) == 2 or abs(user_age - target_max) == 2:
            dimension1 = 0.1 + 0.15 * (
                1
                - abs(
                    user_age - target_min
                    if user_age < target_min
                    else user_age - target_max
                )
                / 3
            )

        # 差 3 岁以上 [0, 0.1]
        else:
            diff = max(target_min - user_age, user_age - target_max)
            dimension1 = max(0, 0.1 * (1 - (diff - 3) / 5))

        return dimension1

    @staticmethod
    def _calculate_content_feature_fit(content: str, user_age: int) -> float:
        """维度 2: 内容特征适配度 (0-0.3)"""
        # 内容长度适配（句子数、字数）
        char_count = len(content)
        sentence_count = content.count("。") + content.count("！") + content.count("？")

        # 不同年龄段适合的内容长度特征
        profile = None
        for (min_a, max_a), p in AgeFitScorer._AGE_LENGTH_PROFILES.items():
            if min_a <= user_age <= max_a:
                profile = p
                break

        if profile:
            char_score = 1.0 - min(
                1.0,
                abs(char_count - sum(profile["ideal_chars"]) / 2)
                / sum(profile["ideal_chars"]),
            )
            sentence_score = 1.0 - min(
                1.0,
                abs(sentence_count - sum(profile["ideal_sentences"]) / 2)
                / sum(profile["ideal_sentences"]),
            )
            length_fit = (char_score + sentence_score) / 2
        else:
            length_fit = 0.5  # 默认

        # 专业术语密度适配
        domain_terms = [
            "前庭觉",
            "精细动作",
            "感统",
            "认知发展",
            "语言发展",
            "社交技能",
        ]
        term_count = sum(1 for term in domain_terms if term in content)
        term_density = term_count / max(sentence_count, 1)

        # 低龄儿童术语密度应低，高龄可高
        if user_age <= 3:
            term_fit = 1.0 - min(1.0, term_density / 0.3)  # 术语密度 >0.3 时得分降低
        else:
            term_fit = min(1.0, term_density / 0.1)  # 术语密度 >0.1 时得分增加

        dimension2 = 0.15 * length_fit + 0.15 * term_fit  # 范围 0-0.3
        return dimension2

    @staticmethod
    def _calculate_domain_match(
        content: str, user_age: int, metadata: Optional[Dict] = None
    ) -> float:
        """维度 3: 领域匹配度 (0-0.3)"""
        # 识别内容涉及的领域
        content_domains = []
        for domain, keywords in AgeFitScorer._DOMAIN_KEYWORDS.items():
            if any(kw in content for kw in keywords):
                content_domains.append(domain)

        # 计算领域匹配度
        priority_domains = []
        for (min_a, max_a), domains in AgeFitScorer._AGE_DOMAIN_PRIORITY.items():
            if min_a <= user_age <= max_a:
                priority_domains = domains
                break

        if not content_domains:
            domain_fit = 0.5  # 无法识别领域，给中等分数
        elif not priority_domains:
            domain_fit = 0.5
        else:
            # 计算内容领域与优先领域的重叠度
            overlap = len(set(content_domains) & set(priority_domains))
            domain_fit = overlap / max(len(priority_domains), 1)

        dimension3 = 0.3 * domain_fit  # 范围 0-0.3
        return dimension3
