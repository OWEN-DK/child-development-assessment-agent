"""书籍元数据服务

通过关键词匹配 + LLM 兜底提取书籍主领域和适用年龄段
"""

import re
from typing import Dict, List, Tuple

from pydantic import BaseModel

from src.core.llm import LLMRequest, LLMServiceFactoryCompat


class BookMetadata(BaseModel):
    """书籍元数据"""

    primary_domain: str
    primary_domain_score: float
    applicable_age_stages: List[str]
    detected_age_ranges: List[Tuple[int, int]]
    text_sample: str


class BookMetadataService:
    """书籍内容解析服务（关键词匹配 + LLM 兜底）"""

    KEYWORD_THRESHOLD = 10

    DOMAIN_KEYWORDS = {
        "感觉统合": ["前庭", "本体觉", "触觉", "感觉统合", "感统", "前庭觉", "本体感", "触觉防御", "感觉处理"],
        "粗大动作": ["跑", "跳", "爬", "平衡", "大肌肉", "行走", "站立", "翻身", "坐立", "跨步"],
        "精细动作": ["抓握", "捏", "剪纸", "写字", "手眼协调", "串珠", "涂鸦", "搭积木", "扣纽扣"],
        "语言发展": ["说话", "词汇", "语法", "表达", "理解", "发音", "命名", "句子", "对话", "听力"],
        "认知能力": ["注意", "记忆", "思维", "推理", "分类", "排序", "因果", "空间", "数量", "逻辑"],
        "社交情感": ["情绪", "分享", "合作", "同理心", "自我控制", "交往", "规则", "自信", "独立性"],
    }

    AGE_PATTERNS = [
        r"(\d+)\s*[-~至]\s*(\d+)\s*岁",
        r"(\d+)\s*到\s*(\d+)\s*岁",
        r"(\d+)岁.*?(\d+)岁",
    ]

    AGE_STAGE_RANGES = [
        ("0-1岁", 0, 12),
        ("1-3岁", 12, 36),
        ("3-6岁", 36, 72),
        ("6-9岁", 72, 108),
        ("9-12岁", 108, 144),
        ("12-15岁", 144, 180),
        ("15-18岁", 180, 216),
    ]

    DOMAIN_CONFIRMATION_PROMPT = """\
请判断以下文本主要涉及儿童发展的哪个领域。
可选领域：粗大动作、精细动作、语言发展、认知能力、社交情感、感觉统合

文本片段：
{text_sample}

仅返回领域名称，不要解释。
"""

    async def extract_metadata(self, text: str) -> BookMetadata:
        """
        提取书籍主领域和适用年龄段

        Step 1: 关键词快速匹配（<1ms，覆盖 80% 场景）
        Step 2: LLM 辅助确认（关键词置信度低时触发）
        Step 3: 年龄段正则提取 + 映射到标准标签
        """
        domain_scores = self._match_domain_by_keywords(text)
        max_domain = max(domain_scores, key=domain_scores.get) if domain_scores else None
        max_score = domain_scores.get(max_domain, 0) if max_domain else 0

        primary_domain = max_domain
        if max_score <= self.KEYWORD_THRESHOLD:
            primary_domain = await self._confirm_domain_by_llm(text[:2000])
            if not primary_domain:
                primary_domain = max_domain or "感觉统合"

        age_ranges = self._extract_age_ranges(text)
        applicable_stages = self._map_age_ranges_to_stages(age_ranges)
        if not applicable_stages:
            applicable_stages = ["3-6岁"]

        return BookMetadata(
            primary_domain=primary_domain,
            primary_domain_score=max_score,
            applicable_age_stages=applicable_stages,
            detected_age_ranges=age_ranges,
            text_sample=text[:500],
        )

    def _match_domain_by_keywords(self, text: str) -> Dict[str, int]:
        """关键词匹配，返回各领域的命中次数"""
        scores = {}
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            count = sum(text.count(kw) for kw in keywords)
            scores[domain] = count
        return scores

    async def _confirm_domain_by_llm(self, text_sample: str) -> str:
        """LLM 辅助确认主领域"""
        try:
            llm = LLMServiceFactoryCompat.create()
            prompt = self.DOMAIN_CONFIRMATION_PROMPT.format(text_sample=text_sample)
            response = await llm.chat(LLMRequest(messages=[{"role": "user", "content": prompt}]))
            domain = response.content.strip()
            valid_domains = list(self.DOMAIN_KEYWORDS.keys())
            return domain if domain in valid_domains else ""
        except Exception:
            return ""

    def _extract_age_ranges(self, text: str) -> List[Tuple[int, int]]:
        """正则提取年龄范围"""
        ranges = []
        for pattern in self.AGE_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    min_age = int(match[0])
                    max_age = int(match[1])
                    if 0 <= min_age <= max_age <= 18:
                        ranges.append((min_age, max_age))
                except (ValueError, IndexError):
                    continue
        return ranges

    def _map_age_ranges_to_stages(self, age_ranges: List[Tuple[int, int]]) -> List[str]:
        """将年龄范围（年）映射为标准年龄段标签"""
        stages = set()
        for min_year, max_year in age_ranges:
            min_months = min_year * 12
            max_months = max_year * 12
            for label, stage_min, stage_max in self.AGE_STAGE_RANGES:
                if stage_min < max_months and stage_max > min_months:
                    stages.add(label)
        stage_order = {label: i for i, (label, _, _) in enumerate(self.AGE_STAGE_RANGES)}
        return sorted(stages, key=lambda x: stage_order.get(x, 99))
