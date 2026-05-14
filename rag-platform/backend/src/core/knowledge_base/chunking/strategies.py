"""分块策略实现

5 种策略：fixed_size / semantic / paragraph / heading / recursive
"""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """分块结果"""
    content: str
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


def _estimate_tokens(text: str) -> int:
    """估算 Token 数量（中文 ×1.5，英文 ×1.3）"""
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + other_chars * 1.3)


class BaseChunkingStrategy(ABC):
    """分块策略基类"""

    @abstractmethod
    def chunk(self, text: str, config: dict[str, Any]) -> list[Chunk]:
        """执行分块

        Args:
            text: 输入文本
            config: 分块配置

        Returns:
            分块结果列表
        """


class FixedSizeChunking(BaseChunkingStrategy):
    """固定大小分块

    按 separator 分割 → 按 chunk_size 合并 → 计算 overlap
    """

    def chunk(self, text: str, config: dict[str, Any]) -> list[Chunk]:
        chunk_size = config.get("chunk_size", 512)
        overlap = config.get("overlap", 50)
        separator = config.get("separator", "\n\n")

        # 按分隔符分割
        segments = text.split(separator)
        segments = [s.strip() for s in segments if s.strip()]

        chunks = []
        current = ""

        for seg in segments:
            if len(current) + len(seg) + len(separator) > chunk_size and current:
                chunks.append(Chunk(
                    content=current.strip(),
                    token_count=_estimate_tokens(current.strip()),
                ))
                # 保留 overlap
                if overlap > 0 and len(current) > overlap:
                    current = current[-overlap:] + separator + seg
                else:
                    current = seg
            else:
                current = current + separator + seg if current else seg

        if current.strip():
            chunks.append(Chunk(
                content=current.strip(),
                token_count=_estimate_tokens(current.strip()),
            ))

        return chunks


class SemanticChunking(BaseChunkingStrategy):
    """语义分块

    按句子分割，计算相邻句子相似度，在相似度低于阈值处切分。
    简化实现：按句子边界分割，不实际调用 embedding。
    """

    def chunk(self, text: str, config: dict[str, Any]) -> list[Chunk]:
        min_chunk_size = config.get("min_chunk_size", 100)
        max_chunk_size = config.get("max_chunk_size", 4096)

        # 按句子分割
        sentences = re.split(r'(?<=[。！？.!?])\s*', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        current = ""

        for sent in sentences:
            if len(current) + len(sent) > max_chunk_size and current:
                chunks.append(Chunk(
                    content=current.strip(),
                    token_count=_estimate_tokens(current.strip()),
                ))
                current = sent
            else:
                current = current + " " + sent if current else sent

        # 处理最后一个块
        if current.strip():
            if len(current) < min_chunk_size and chunks:
                # 合并到前一个块
                last = chunks[-1]
                chunks[-1] = Chunk(
                    content=last.content + " " + current.strip(),
                    token_count=_estimate_tokens(last.content + " " + current.strip()),
                )
            else:
                chunks.append(Chunk(
                    content=current.strip(),
                    token_count=_estimate_tokens(current.strip()),
                ))

        return chunks


class ParagraphChunking(BaseChunkingStrategy):
    """段落分块

    按双换行分割段落，短段落合并到相邻块。
    """

    def chunk(self, text: str, config: dict[str, Any]) -> list[Chunk]:
        min_sentences = config.get("min_sentences_per_chunk", 2)
        max_chunk_size = config.get("max_chunk_size", 4096)

        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        chunks = []
        current = ""

        for para in paragraphs:
            sentence_count = len(re.findall(r'[。！？.!?]', para))

            if sentence_count < min_sentences and current:
                # 短段落合并到当前块
                current = current + "\n\n" + para
            elif len(current) + len(para) + 2 > max_chunk_size and current:
                chunks.append(Chunk(
                    content=current.strip(),
                    token_count=_estimate_tokens(current.strip()),
                ))
                current = para
            else:
                current = current + "\n\n" + para if current else para

        if current.strip():
            chunks.append(Chunk(
                content=current.strip(),
                token_count=_estimate_tokens(current.strip()),
            ))

        return chunks


class HeadingChunking(BaseChunkingStrategy):
    """标题分块

    识别 Markdown 标题层级，以标题为分块边界。
    """

    def chunk(self, text: str, config: dict[str, Any]) -> list[Chunk]:
        heading_levels = config.get("heading_levels", [1, 2, 3])
        max_chunk_size = config.get("max_chunk_size", 4096)

        # 构建标题正则
        level_pattern = "|".join([f"{'#' * l}" for l in heading_levels])
        heading_regex = re.compile(rf'^({level_pattern})\s+(.+)$', re.MULTILINE)

        # 按标题分割
        parts = heading_regex.split(text)

        chunks = []
        current_heading_path = []
        current_content = ""

        i = 0
        while i < len(parts):
            part = parts[i].strip()
            if re.match(rf'^({level_pattern})$', part) and i + 1 < len(parts):
                # 这是一个标题
                level = len(part)
                title = parts[i + 1].strip()

                # 保存之前的内容
                if current_content.strip():
                    chunks.append(Chunk(
                        content=current_content.strip(),
                        token_count=_estimate_tokens(current_content.strip()),
                        metadata={"heading_path": " > ".join(current_heading_path)},
                    ))

                # 更新标题路径
                while current_heading_path and len(current_heading_path) >= level:
                    current_heading_path.pop()
                current_heading_path.append(title)
                current_content = f"{part} {title}\n"
                i += 2
            else:
                current_content += part + "\n"
                i += 1

        # 处理最后一个块
        if current_content.strip():
            chunks.append(Chunk(
                content=current_content.strip(),
                token_count=_estimate_tokens(current_content.strip()),
                metadata={"heading_path": " > ".join(current_heading_path)},
            ))

        return chunks


class RecursiveChunking(BaseChunkingStrategy):
    """递归分块

    按优先级列表逐级尝试：双换行→单换行→句号→空格→字符
    """

    def chunk(self, text: str, config: dict[str, Any]) -> list[Chunk]:
        separator_priority = config.get("separator_priority_list", ["\n\n", "\n", ". ", " ", ""])
        max_chunk_size = config.get("max_chunk_size", 4096)
        min_chunk_size = config.get("min_chunk_size", 100)

        return self._recursive_split(text, separator_priority, 0, max_chunk_size, min_chunk_size)

    def _recursive_split(
        self, text: str, separators: list[str], sep_idx: int,
        max_size: int, min_size: int
    ) -> list[Chunk]:
        if len(text) <= max_size:
            return [Chunk(content=text, token_count=_estimate_tokens(text))]

        if sep_idx >= len(separators):
            # 强制按字符分割
            chunks = []
            for i in range(0, len(text), max_size):
                chunk_text = text[i:i + max_size]
                chunks.append(Chunk(content=chunk_text, token_count=_estimate_tokens(chunk_text)))
            return chunks

        sep = separators[sep_idx]
        if sep == "":
            # 字符级分割
            return self._recursive_split(text, separators, sep_idx + 1, max_size, min_size)

        parts = text.split(sep)
        chunks = []
        current = ""

        for part in parts:
            candidate = current + sep + part if current else part
            if len(candidate) > max_size and current:
                # 当前块已满，递归处理
                if len(current) > max_size:
                    chunks.extend(self._recursive_split(current, separators, sep_idx + 1, max_size, min_size))
                else:
                    chunks.append(Chunk(content=current, token_count=_estimate_tokens(current)))
                current = part
            else:
                current = candidate

        if current:
            if len(current) > max_size:
                chunks.extend(self._recursive_split(current, separators, sep_idx + 1, max_size, min_size))
            else:
                chunks.append(Chunk(content=current, token_count=_estimate_tokens(current)))

        return chunks
