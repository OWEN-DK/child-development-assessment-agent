"""敏感词过滤节点

正则/列表匹配移除或脱敏敏感词。
"""
import re
from typing import Any

from src.core.pipeline.base_node import BaseNodeExecutor
from src.core.pipeline.node_context import NodeContext
from src.core.pipeline.node_result import NodeResult
from src.utils.logger import logger


class SensitiveFilterExecutor(BaseNodeExecutor):
    """敏感词过滤执行器"""

    @property
    def category(self) -> str:
        return "security"

    async def execute(self, context: NodeContext) -> NodeResult:
        """执行敏感词过滤"""
        candidates = context.input_data
        if not candidates:
            return NodeResult(output=[], node_id=context.node_id, node_type="sensitive_filter")

        word_list = context.config.get("word_list", [])
        filter_mode = context.config.get("filter_mode", "remove")  # remove / mask / flag
        apply_to = context.config.get("apply_to", "results")

        if not word_list:
            return NodeResult(
                output=candidates,
                metadata={"word_list_count": 0, "filter_mode": filter_mode},
                node_id=context.node_id,
                node_type="sensitive_filter",
            )

        # 构建正则模式
        pattern = self._build_pattern(word_list)

        filtered_count = 0

        if isinstance(candidates, list):
            result = []
            for item in candidates:
                if isinstance(item, dict):
                    content = item.get("content", "")
                    filtered_content, count = self._filter_text(content, pattern, filter_mode)
                    filtered_count += count
                    if filter_mode == "remove" and count > 0 and not filtered_content.strip():
                        continue  # 移除模式下，内容被完全过滤则跳过
                    item = item.copy()
                    item["content"] = filtered_content
                result.append(item)
        elif isinstance(candidates, str):
            result, filtered_count = self._filter_text(candidates, pattern, filter_mode)
        else:
            result = candidates

        logger.debug(f"敏感词过滤: {filtered_count} 处匹配, mode={filter_mode}")

        return NodeResult(
            output=result,
            metadata={
                "word_list_count": len(word_list),
                "filter_mode": filter_mode,
                "filtered_count": filtered_count,
            },
            node_id=context.node_id,
            node_type="sensitive_filter",
        )

    def _build_pattern(self, word_list: list[str]) -> re.Pattern:
        """构建敏感词正则模式"""
        escaped = [re.escape(w) for w in word_list]
        return re.compile("|".join(escaped), re.IGNORECASE)

    def _filter_text(self, text: str, pattern: re.Pattern, mode: str) -> tuple[str, int]:
        """过滤文本中的敏感词"""
        matches = pattern.findall(text)
        count = len(matches)

        if count == 0:
            return text, 0

        if mode == "remove":
            filtered = pattern.sub("", text)
        elif mode == "mask":
            filtered = pattern.sub(lambda m: "*" * len(m.group()), text)
        else:  # flag
            filtered = text  # flag 模式不修改文本

        return filtered, count
