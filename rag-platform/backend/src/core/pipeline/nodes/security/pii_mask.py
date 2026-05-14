"""PII 脱敏节点

正则匹配手机号/身份证/邮箱/姓名/地址/银行卡号，替换为脱敏字符。
"""
import re
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult
from src.utils.logger import logger


class PIIMaskExecutor(BaseNodeExecutor):
    """PII 脱敏执行器"""

    # PII 正则模式
    PATTERNS = {
        "phone": (r"1[3-9]\d{9}", "手机号"),
        "id_card": (r"\d{17}[\dXx]", "身份证号"),
        "email": (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "邮箱"),
        "bank_card": (r"\d{16,19}", "银行卡号"),
    }

    @property
    def category(self) -> str:
        return "security"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行 PII 脱敏"""
        candidates = context.input_data
        if not candidates:
            return NodeResult(output=[], node_id=context.node_id, node_type="pii_mask")

        target_types = context.config.get("target_types", ["phone", "id_card", "email"])
        mask_char = context.config.get("mask_char", "*")

        # 构建脱敏正则
        patterns = {}
        for pii_type in target_types:
            if pii_type in self.PATTERNS:
                pattern_str, _ = self.PATTERNS[pii_type]
                patterns[pii_type] = re.compile(pattern_str)

        masked_count = 0

        if isinstance(candidates, list):
            result = []
            for item in candidates:
                if isinstance(item, dict):
                    content = item.get("content", "")
                    masked_content, count = self._mask_text(content, patterns, mask_char)
                    masked_count += count
                    item = item.copy()
                    item["content"] = masked_content
                result.append(item)
        elif isinstance(candidates, str):
            result, masked_count = self._mask_text(candidates, patterns, mask_char)
        else:
            result = candidates

        logger.debug(f"PII 脱敏: {masked_count} 处匹配, types={target_types}")

        return NodeResult(
            output=result,
            metadata={
                "target_types": target_types,
                "masked_count": masked_count,
            },
            node_id=context.node_id,
            node_type="pii_mask",
        )

    def _mask_text(self, text: str, patterns: dict[str, re.Pattern], mask_char: str) -> tuple[str, int]:
        """脱敏文本中的 PII"""
        total_count = 0

        for pii_type, pattern in patterns.items():
            def replacer(m, mc=mask_char, pt=pii_type):
                original = m.group()
                # 保留前3后4
                if pt == "phone" and len(original) == 11:
                    return original[:3] + mc * 4 + original[7:]
                elif pt == "id_card" and len(original) == 18:
                    return original[:6] + mc * 8 + original[14:]
                elif pt == "email":
                    parts = original.split("@")
                    if len(parts[0]) > 2:
                        return parts[0][:2] + mc * (len(parts[0]) - 2) + "@" + parts[1]
                # 默认：保留首尾字符
                if len(original) > 2:
                    return original[0] + mc * (len(original) - 2) + original[-1]
                return mc * len(original)

            text, count = pattern.subn(replacer, text)
            total_count += count

        return text, total_count
