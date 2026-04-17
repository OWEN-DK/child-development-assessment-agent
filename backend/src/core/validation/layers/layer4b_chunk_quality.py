"""校验层 - Layer 4b: 分块质量评分

检查文档分块的信息密度、可读性和切分合理性。
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

CHINESE_STOP_WORDS = set(
    "的了是在有和或但而与之及对关于通过根据按照由于因此虽然然而如果那么是否什么哪里怎么"
    "可以需要应该必须能够可能已经正在将要继续开始结束进行提供包含包括使用应用"
    "方法过程步骤结果原因目的意义价值作用效果影响关系条件环境背景情况分析研究调查"
    "报告数据显示图表说明解释描述定义概念原理理论基础实践操作经验技巧建议提示注意"
    "问题答案回复反馈意见建议评价标准规范要求指南手册教程示例样本模板格式结构内容"
)


class Layer4bChunkQuality:
    """Layer 4b: 分块质量评分"""

    def __init__(self, session_factory, test_run):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        """执行分块质量评分"""
        # 分块数据存储在向量库(Chroma)中，而非MySQL数据库
        # 当前层无法直接从test_run获取分块数据，优雅跳过
        return {
            "status": "skipped",
            "data": {"reason": "分块质量检查需从向量库获取数据，当前暂不支持"},
        }

        quality_scores = []
        low_quality_count = 0

        for chunk in chunks:
            content = chunk.get("content", "")
            if not content:
                continue

            info_density = self._calc_info_density(content)
            structure_level = self._calc_structure_level(content)
            split_rationality = self._calc_split_rationality(chunk)

            composite = (
                info_density * 0.4 + structure_level * 0.3 + split_rationality * 0.3
            )
            quality_scores.append(composite)

            if composite < 0.3:
                low_quality_count += 1

        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        low_quality_ratio = (
            low_quality_count / len(quality_scores) if quality_scores else 0
        )

        warnings = []
        if low_quality_ratio > 0.10:
            warnings.append(
                {
                    "level": "warning",
                    "message": f"低质量分块过多 ({low_quality_ratio:.1%} > 10%)",
                }
            )
        if avg_quality < 0.6:
            warnings.append(
                {
                    "level": "critical",
                    "message": f"平均质量过低 ({avg_quality:.2f} < 0.6)",
                }
            )

        return {
            "status": "completed",
            "data": {
                "avg_quality": avg_quality,
                "low_quality_ratio": low_quality_ratio,
                "low_quality_examples": self._get_low_quality_examples(
                    chunks, quality_scores
                )[:3],
                "warnings": warnings,
            },
        }

    def _calc_info_density(self, content: str) -> float:
        """信息密度 = 1 - (停用词数 / 总字符数)（按字符统计）"""
        chars = [c for c in content if c.strip()]
        if not chars:
            return 0
        stop_word_count = sum(1 for c in chars if c in CHINESE_STOP_WORDS)
        return 1 - (stop_word_count / len(chars))

    def _calc_structure_level(self, content: str) -> float:
        """结构化程度 = (标题数 × 2 + 列表项数) / 段落数"""
        lines = content.split("\n")
        paragraphs = [l for l in lines if l.strip()]
        if not paragraphs:
            return 0

        title_count = sum(
            1
            for l in lines
            if re.match(r"^#{1,6}\s", l)
            or re.match(r"^[一二三四五六七八九十]+[、.]", l)
        )
        list_item_count = sum(
            1
            for l in lines
            if re.match(r"^[\s]*[-*•]\s", l) or re.match(r"^\d+[.、]", l)
        )

        return min(1.0, (title_count * 2 + list_item_count) / len(paragraphs))

    def _calc_split_rationality(self, chunk: dict) -> float:
        """切分合理性 = 以完整句子/段落结束的分块占比"""
        content = chunk.get("content", "").strip()
        if not content:
            return 0

        ends_with_sentence = bool(re.search(r"[。！？\n]\s*$", content))
        return 1.0 if ends_with_sentence else 0.5

    def _get_low_quality_examples(self, chunks: list, scores: list) -> list:
        """获取低质量示例"""
        examples = []
        for chunk, score in zip(chunks, scores):
            if score < 0.3:
                examples.append(
                    {
                        "chunk_id": chunk.get("id"),
                        "quality_score": score,
                        "content_preview": chunk.get("content", "")[:100],
                    }
                )
        return examples
