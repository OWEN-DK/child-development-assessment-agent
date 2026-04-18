"""节点内容清理模块

提供节点文本内容的标准化清理功能。
"""

import re


def clean_node_content(content: str) -> str:
    """清理节点内容，去除多余空行、行首尾空格和连续空格

    清理步骤：
    1. 清理连续换行（保留最多 2 个换行符表示段落分隔）
    2. 清理行首行尾空格，但保留行内单词间的单个空格
    3. 清理多个连续空格为单个空格
    4. 去除首尾空白字符

    Args:
        content: 原始文本内容

    Returns:
        清理后的文本内容
    """
    if not content:
        return ""

    cleaned_content = re.sub(r"\n\s*\n", "\n\n", content)

    cleaned_content = "\n".join(
        line.strip() for line in cleaned_content.split("\n")
    )

    cleaned_content = re.sub(r" {2,}", " ", cleaned_content)

    cleaned_content = cleaned_content.strip()

    return cleaned_content
