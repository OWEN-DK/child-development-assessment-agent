import asyncio
import json
import re
from typing import List, Optional, Dict, Any, Callable
from llama_index.core.schema import Node, Document
from llama_index.core.node_parser import SentenceSplitter, SemanticSplitterNodeParser

# from llama_index.core.node_parser.text.sentence import SENTENCE_SPLITTER_RE
from src.core.metadata_extractor import MetadataExtractor
from src.config import settings
from src.utils.logger import logger
from src.utils.text_cleaner import clean_document_text

# 初始化语义分块器（全局单例）
_semantic_splitter = None
_semantic_splitter_en = None  # 英文优化的分块器


def get_semantic_splitter(content_text: str = None):
    """获取语义分块器单例

    Args:
        content_text: 可选的文本内容，用于检测语言并调整分块策略
    """
    global _semantic_splitter, _semantic_splitter_en

    # 检测语言，对英文内容使用更宽松的分块策略
    language = detect_language(content_text) if content_text else "zh"

    # 如果是英文且英文分块器已初始化，直接返回
    if language == "en" and _semantic_splitter_en is not None:
        return _semantic_splitter_en

    # 如果是中文且中文分块器已初始化，直接返回
    if language == "zh" and _semantic_splitter is not None:
        return _semantic_splitter

    from llama_index.core import Settings

    if language == "en":
        # 英文内容：使用更大的 buffer 和更高的阈值
        buffer_size = max(
            settings.semantic_splitter_buffer_size,
            settings.rag_chunking_english_buffer_size,
        )
        breakpoint_threshold = max(
            settings.semantic_splitter_breakpoint_threshold,
            settings.rag_chunking_english_breakpoint_threshold,
        )
        chunk_size = int(
            settings.rag_epub_chunk_target_size
            * settings.rag_chunking_english_size_multiplier
        )
        logger.debug(
            f"Using English-optimized semantic splitter: buffer={buffer_size}, threshold={breakpoint_threshold}, chunk_size={chunk_size}"
        )

        _semantic_splitter_en = SemanticSplitterNodeParser(
            embed_model=Settings.embed_model,
            buffer_size=buffer_size,
            breakpoint_percentile_threshold=breakpoint_threshold,
            chunk_size=chunk_size,
        )
        return _semantic_splitter_en
    else:
        # 中文内容：使用标准配置
        _semantic_splitter = SemanticSplitterNodeParser(
            embed_model=Settings.embed_model,
            buffer_size=settings.semantic_splitter_buffer_size,
            breakpoint_percentile_threshold=settings.semantic_splitter_breakpoint_threshold,
            chunk_size=settings.rag_epub_chunk_target_size,
        )
        return _semantic_splitter


def detect_language(text: str) -> str:
    """检测文本主要语言"""
    if not text:
        return "zh"

    # 统计英文字母和中文字符数量
    english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    total_chars = sum(1 for c in text if c.isalpha())

    if total_chars == 0:
        return "zh"

    # 如果英文字母占比超过配置阈值，判定为英文
    return (
        "en"
        if english_chars / total_chars
        > settings.rag_chunking_language_detection_threshold
        else "zh"
    )


def get_chapter_splitter(content_text: str = None):
    """获取针对长章节优化的语义分块器

    Args:
        content_text: 可选的文本内容，用于检测语言并调整分块策略
    """
    from llama_index.core import Settings

    # 检测语言，对英文内容使用更宽松的分块策略
    language = detect_language(content_text) if content_text else "zh"

    if language == "en":
        # 英文内容：使用更大的 buffer 和更高的阈值，减少分割
        buffer_size = max(
            settings.semantic_splitter_chapter_buffer_size,
            settings.rag_chunking_english_buffer_size,
        )
        breakpoint_threshold = max(
            settings.semantic_splitter_chapter_breakpoint_threshold,
            settings.rag_chunking_english_breakpoint_threshold,
        )
        chunk_size = int(
            settings.rag_epub_chunk_target_size
            * settings.rag_chunking_english_size_multiplier
        )
        logger.debug(
            f"Using English-optimized splitter: buffer={buffer_size}, threshold={breakpoint_threshold}, chunk_size={chunk_size}"
        )
    else:
        # 中文内容：使用标准配置
        buffer_size = settings.semantic_splitter_chapter_buffer_size
        breakpoint_threshold = settings.semantic_splitter_chapter_breakpoint_threshold
        chunk_size = settings.rag_epub_chunk_target_size

    return SemanticSplitterNodeParser(
        embed_model=Settings.embed_model,
        buffer_size=buffer_size,
        breakpoint_percentile_threshold=breakpoint_threshold,
        chunk_size=chunk_size,
    )


class MetadataProcessor:
    """元数据处理工具类，统一处理节点的元数据提取"""

    def __init__(self, concurrency: int = None):
        self.concurrency = concurrency or settings.rag_metadata_extraction_concurrency
        self._semaphore = None

    @property
    def semaphore(self):
        """Lazy initialization of semaphore to ensure it's attached to the current event loop"""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.concurrency)
        return self._semaphore

    async def process_nodes(
        self,
        nodes: List[Node],
        file_hash: str,
        progress_callback=None,
        total_chunks: int = None,
        use_hierarchical: bool = True,
        doc_level_metadata: dict = None,
    ) -> List[Node]:
        """
        批量处理节点，提取元数据
        支持三种策略：
        1. 分层提取（推荐）：文档级元数据 + 关键块单独提取
        2. 规则优先：默认规则提取，质量低时 LLM 兜底
        3. 全量 LLM：每个块都调用 LLM（不推荐用于大量分块）

        Args:
            nodes: 待处理的节点列表
            file_hash: 文档的哈希值，用于关联
            progress_callback: 进度回调函数
            total_chunks: 总块数，用于进度计算
            use_hierarchical: 是否使用分层提取策略
            doc_level_metadata: 文档级元数据（如果已预先提取）
        Returns:
            处理后的节点列表
        """
        if total_chunks is None:
            total_chunks = len(nodes)

        # 策略选择：根据分块数量自动选择
        if use_hierarchical and total_chunks > 100:
            logger.info(
                f"Using hierarchical metadata extraction for {total_chunks} chunks"
            )
            return await self._process_nodes_hierarchical(
                nodes, file_hash, progress_callback, total_chunks, doc_level_metadata
            )
        else:
            logger.info(f"Using standard metadata extraction for {total_chunks} chunks")
            return await self._process_nodes_standard(
                nodes, file_hash, progress_callback, total_chunks
            )

    async def _process_nodes_standard(
        self,
        nodes: List[Node],
        file_hash: str,
        progress_callback=None,
        total_chunks: int = None,
    ) -> List[Node]:
        """标准处理方式：每个节点都提取元数据（适合分块较少的场景）"""
        if total_chunks is None:
            total_chunks = len(nodes)

        processed_count = 0
        extraction_tasks = []

        async def process_single_node(node: Node) -> Optional[Node]:
            nonlocal processed_count
            async with self.semaphore:
                try:
                    # 提取元数据
                    extracted_meta = await MetadataExtractor.extract(node.get_content())
                    # 合并元数据，转换列表为 JSON 字符串以适配向量数据库
                    meta_dict = extracted_meta.model_dump()
                    # 序列化列表字段
                    if isinstance(meta_dict.get("topics"), list):
                        meta_dict["topics"] = json.dumps(
                            meta_dict["topics"], ensure_ascii=False
                        )
                    if isinstance(meta_dict.get("brain_regions"), list):
                        meta_dict["brain_regions"] = json.dumps(
                            meta_dict["brain_regions"], ensure_ascii=False
                        )
                    node.metadata.update(meta_dict)
                    # 清理节点内容
                    cleaned_content = self._clean_node_content(node.get_content())
                    node.metadata["content"] = cleaned_content
                    node.metadata["file_hash"] = file_hash

                    processed_count += 1
                    if progress_callback and (
                        processed_count % 20 == 0 or processed_count == total_chunks
                    ):
                        progress = (processed_count / total_chunks) * 100
                        message = f"处理中：{processed_count}/{total_chunks} ({progress:.1f}%)"
                        logger.info(f"Metadata extraction progress: {message}")
                        progress_callback("metadata_extraction", progress, message)

                    return node
                except Exception as e:
                    content_preview = node.get_content()[:100].replace("\n", " ")
                    logger.error(
                        f"Metadata extraction failed for chunk (file_hash: {file_hash}, "
                        f"content preview: {content_preview}...): {e}",
                        exc_info=True,
                    )
                    # 使用默认元数据继续处理，不中断整个流程
                    from src.core.metadata_extractor import ExtractedMetadata

                    extracted_meta = ExtractedMetadata()
                    # 合并元数据，转换列表为 JSON 字符串以适配向量数据库
                    meta_dict = extracted_meta.model_dump()
                    # 序列化列表字段
                    if isinstance(meta_dict.get("topics"), list):
                        meta_dict["topics"] = json.dumps(
                            meta_dict["topics"], ensure_ascii=False
                        )
                    if isinstance(meta_dict.get("brain_regions"), list):
                        meta_dict["brain_regions"] = json.dumps(
                            meta_dict["brain_regions"], ensure_ascii=False
                        )
                    node.metadata.update(meta_dict)
                    # 清理节点内容
                    cleaned_content = self._clean_node_content(node.get_content())
                    node.metadata["content"] = cleaned_content
                    node.metadata["file_hash"] = file_hash
                    node.metadata["metadata_extraction_failed"] = True

                    processed_count += 1
                    return node

        # 创建所有处理任务
        for node in nodes:
            extraction_tasks.append(process_single_node(node))

        # 并发执行
        processed_nodes = await asyncio.gather(*extraction_tasks)
        # 过滤掉 None（虽然理论上不会有）
        processed_nodes = [node for node in processed_nodes if node is not None]

        # 统计失败数量
        failed_count = sum(
            1
            for node in processed_nodes
            if node.metadata.get("metadata_extraction_failed", False)
        )
        success_count = len(processed_nodes) - failed_count

        logger.info(
            f"Completed metadata extraction: {success_count} succeeded, {failed_count} failed, "
            f"total: {len(processed_nodes)} nodes"
        )

        return processed_nodes

    async def _process_nodes_hierarchical(
        self,
        nodes: List[Node],
        file_hash: str,
        progress_callback=None,
        total_chunks: int = None,
        doc_level_metadata: dict = None,
    ) -> List[Node]:
        """
        分层元数据提取策略（适合大量分块场景）

        策略：
        1. 提取文档级元数据（使用所有分块的聚合文本）
        2. 对每个分块，使用规则提取（快速）
        3. 对关键分块（章节开头、内容变化处）使用 LLM 单独提取
        4. 普通分块继承文档级元数据 + 规则提取结果

        性能提升：
        - 4000 分块：从 4000 次 LLM 调用 → 1 次文档级 + ~50 次关键块 = 51 次 LLM 调用
        - 速度提升约 80 倍
        """
        if total_chunks is None:
            total_chunks = len(nodes)

        processed_count = 0

        # 步骤 1: 如果没有文档级元数据，则提取一次
        if doc_level_metadata is None:
            logger.info("Extracting document-level metadata...")
            # 聚合前 N 个分块的文本作为文档代表（避免 Token 超限）
            sample_size = min(50, len(nodes))
            sample_text = "\n".join(
                [node.get_content()[:500] for node in nodes[:sample_size]]
            )

            try:
                doc_meta = await MetadataExtractor.extract(sample_text, use_cache=True)
                doc_level_metadata = doc_meta.model_dump()
                logger.info(
                    f"Document-level metadata extracted: {doc_level_metadata.get('topics', [])}"
                )
            except Exception as e:
                logger.error(f"Failed to extract document-level metadata: {e}")
                doc_level_metadata = {}

        # 步骤 2: 识别关键分块（章节开头、内容突变处）
        key_chunk_indices = self._identify_key_chunks(nodes)
        logger.info(
            f"Identified {len(key_chunk_indices)} key chunks out of {total_chunks}"
        )

        # 步骤 3: 并行处理所有分块
        async def process_single_node(node: Node, idx: int) -> Optional[Node]:
            nonlocal processed_count
            async with self.semaphore:
                try:
                    is_key_chunk = idx in key_chunk_indices

                    if is_key_chunk:
                        # 关键分块：使用 LLM 单独提取
                        extracted_meta = await MetadataExtractor.extract(
                            node.get_content(), use_cache=True
                        )
                        meta_dict = extracted_meta.model_dump()
                        node.metadata["metadata_source"] = "llm_key_chunk"
                    else:
                        # 普通分块：使用规则提取 + 继承文档级元数据
                        from src.core.metadata_extractor import _rule_extractor

                        rule_meta = _rule_extractor.extract(node.get_content())
                        meta_dict = rule_meta.model_dump()

                        # 继承文档级的 topics 和 brain_regions（如果规则提取为空）
                        if not meta_dict.get("topics") and doc_level_metadata.get(
                            "topics"
                        ):
                            meta_dict["topics"] = doc_level_metadata["topics"]
                        if not meta_dict.get(
                            "brain_regions"
                        ) and doc_level_metadata.get("brain_regions"):
                            meta_dict["brain_regions"] = doc_level_metadata[
                                "brain_regions"
                            ]

                        node.metadata["metadata_source"] = "rule_based"

                    # 序列化列表字段
                    if isinstance(meta_dict.get("topics"), list):
                        meta_dict["topics"] = json.dumps(
                            meta_dict["topics"], ensure_ascii=False
                        )
                    if isinstance(meta_dict.get("brain_regions"), list):
                        meta_dict["brain_regions"] = json.dumps(
                            meta_dict["brain_regions"], ensure_ascii=False
                        )

                    node.metadata.update(meta_dict)
                    # 清理节点内容
                    cleaned_content = self._clean_node_content(node.get_content())
                    node.metadata["content"] = cleaned_content
                    node.metadata["file_hash"] = file_hash

                    processed_count += 1
                    if progress_callback and (
                        processed_count % 20 == 0 or processed_count == total_chunks
                    ):
                        progress = (processed_count / total_chunks) * 100
                        message = f"处理中：{processed_count}/{total_chunks} ({progress:.1f}%)"
                        logger.info(f"Metadata extraction progress: {message}")
                        progress_callback("metadata_extraction", progress, message)

                    return node
                except Exception as e:
                    content_preview = node.get_content()[:100].replace("\n", " ")
                    logger.error(
                        f"Metadata extraction failed for chunk (file_hash: {file_hash}, "
                        f"content preview: {content_preview}...): {e}",
                        exc_info=True,
                    )
                    # 使用默认元数据继续处理
                    from src.core.metadata_extractor import ExtractedMetadata

                    extracted_meta = ExtractedMetadata()
                    meta_dict = extracted_meta.model_dump()
                    if isinstance(meta_dict.get("topics"), list):
                        meta_dict["topics"] = json.dumps(
                            meta_dict["topics"], ensure_ascii=False
                        )
                    if isinstance(meta_dict.get("brain_regions"), list):
                        meta_dict["brain_regions"] = json.dumps(
                            meta_dict["brain_regions"], ensure_ascii=False
                        )
                    node.metadata.update(meta_dict)
                    # 清理节点内容
                    cleaned_content = self._clean_node_content(node.get_content())
                    node.metadata["content"] = cleaned_content
                    node.metadata["file_hash"] = file_hash
                    node.metadata["metadata_extraction_failed"] = True

                    processed_count += 1
                    return node

        # 创建所有处理任务
        extraction_tasks = [
            process_single_node(node, idx) for idx, node in enumerate(nodes)
        ]

        # 并发执行
        processed_nodes = await asyncio.gather(*extraction_tasks)
        processed_nodes = [node for node in processed_nodes if node is not None]

        # 统计
        llm_count = sum(
            1
            for node in processed_nodes
            if node.metadata.get("metadata_source") == "llm_key_chunk"
        )
        rule_count = sum(
            1
            for node in processed_nodes
            if node.metadata.get("metadata_source") == "rule_based"
        )
        failed_count = sum(
            1
            for node in processed_nodes
            if node.metadata.get("metadata_extraction_failed", False)
        )

        logger.info(
            f"Completed hierarchical metadata extraction: "
            f"{llm_count} LLM chunks, {rule_count} rule-based chunks, {failed_count} failed, "
            f"total: {len(processed_nodes)} nodes"
        )

        return processed_nodes

    def _identify_key_chunks(self, nodes: List[Node], max_key_chunks: int = 50) -> set:
        """
        识别关键分块（章节开头、内容突变处）

        策略：
        1. 每个章节的前 2 个分块
        2. 内容长度突变处（可能是新主题）
        3. 均匀采样：每隔 N 个分块取一个

        Args:
            nodes: 分块列表
            max_key_chunks: 最大关键分块数

        Returns:
            关键分块的索引集合
        """
        key_indices = set()
        n = len(nodes)

        if n == 0:
            return key_indices

        # 策略 1: 章节开头（假设 metadata 中有 chapter 信息）
        current_chapter = None
        for idx, node in enumerate(nodes):
            chapter = node.metadata.get("chapter_title") or node.metadata.get("chapter")
            if chapter != current_chapter:
                # 新章节开始，取前 2 个分块
                key_indices.add(idx)
                if idx + 1 < n:
                    key_indices.add(idx + 1)
                current_chapter = chapter

        # 策略 2: 均匀采样（如果关键分块太少）
        if len(key_indices) < max_key_chunks:
            step = max(1, n // max_key_chunks)
            for idx in range(0, n, step):
                key_indices.add(idx)
                if len(key_indices) >= max_key_chunks:
                    break

        # 策略 3: 内容长度突变处（可能是新主题开始）
        if n > 10:
            lengths = [len(node.get_content()) for node in nodes]
            avg_length = sum(lengths) / len(lengths)
            for idx in range(1, min(100, n)):  # 只检查前 100 个分块
                if lengths[idx] > avg_length * 1.5 or lengths[idx] < avg_length * 0.5:
                    key_indices.add(idx)

        # 限制最大数量
        if len(key_indices) > max_key_chunks:
            key_indices = set(sorted(key_indices)[:max_key_chunks])

        return key_indices

    def _clean_node_content(self, content: str) -> str:
        """
        清理节点内容，去除多余空行、行首尾空格和连续空格

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

        # 清理连续换行（保留最多 2 个换行符表示段落分隔）
        cleaned_content = re.sub(r"\n\s*\n", "\n\n", content)

        # 清理行首行尾空格，但保留行内单词间的单个空格
        cleaned_content = "\n".join(
            line.strip() for line in cleaned_content.split("\n")
        )

        # 清理多个连续空格为单个空格
        cleaned_content = re.sub(r" {2,}", " ", cleaned_content)

        # 去除首尾空白字符
        cleaned_content = cleaned_content.strip()

        return cleaned_content

    @staticmethod
    def split_chapters_into_chunks(
        documents: List[Document],
        chunk_target_size: int = 1024,
        file_hash: str = None,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
    ) -> List[Node]:
        """
        将章节级文档拆分为更小的块（适用于 EPUB 和带书签的 PDF）
        使用语义分块，保持语意完整性。
        采用多线程并发处理以加速 Embedding 计算。

        优化策略：
        1. 优先保证语义完整性，在句子/段落边界切割
        2. 设置 200 字符重叠，避免上下文断裂
        3. 增大块大小到 1024-1200 字符，保证完整案例
        4. 结合语义分割，而非纯固定字符数

        Args:
            documents: 章节级文档列表
            chunk_target_size: 目标块大小（字符数），推荐 1024-1200
            file_hash: 文档哈希值，用于设置源关联
        Returns:
            拆分后的节点列表
        """
        all_nodes = []
        # 使用针对长章节优化的分块器（传入文本用于语言检测）
        sample_text = "\n".join([doc.text[:500] for doc in documents if doc.text])
        splitter = get_chapter_splitter(sample_text)

        # 定义单个文档处理函数
        def process_chapter(doc):
            chapter_nodes = []
            # 预处理：清理文本中的空行和特殊字符
            new_text = clean_document_text(doc.text)

            current_doc = doc
            if new_text != doc.text:
                current_doc = Document(text=new_text, metadata=doc.metadata)

            # 策略优化：对于超大章节，先使用 SentenceSplitter 进行粗粒度拆分
            MAX_PRE_SPLIT_SIZE = 20000
            docs_to_process = []

            # 检查文本结构质量：如果存在超长单行（>1500 字符），说明排版混乱或缺乏换行
            # 这种情况下语义分块效果极差且会导致 Embedding 截断，应直接降级为规则分块
            longest_line_len = max(
                (len(line) for line in current_doc.text.split("\n")), default=0
            )
            is_poorly_formatted = longest_line_len > 1500

            if is_poorly_formatted:
                logger.warning(
                    f"Chapter content poorly formatted (max line len: {longest_line_len}), "
                    "skipping semantic splitting and using rule-based splitting."
                )
                # 直接使用规则分块，彻底跳过昂贵的语义分块
                # 优化：增加 overlap 到 200，保证上下文连续性
                fallback_splitter = SentenceSplitter(
                    chunk_size=chunk_target_size, chunk_overlap=200
                )
                fallback_chunks = fallback_splitter.get_nodes_from_documents(
                    [current_doc]
                )
                for chunk in fallback_chunks:
                    chunk.metadata.update(doc.metadata)
                    if file_hash:
                        from llama_index.core.schema import (
                            NodeRelationship,
                            RelatedNodeInfo,
                        )

                        chunk.metadata["file_hash"] = file_hash
                        chunk.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
                            node_id=file_hash
                        )
                    chapter_nodes.append(chunk)
                return chapter_nodes

            # 如果结构尚可，但总长度过大，进行预切分
            if len(current_doc.text) > MAX_PRE_SPLIT_SIZE:
                logger.debug(
                    f"Chapter too large ({len(current_doc.text)} chars), pre-splitting into smaller blocks..."
                )
                # 预切分也使用较大的 overlap
                pre_splitter = SentenceSplitter(
                    chunk_size=MAX_PRE_SPLIT_SIZE, chunk_overlap=500
                )
                docs_to_process = pre_splitter.get_nodes_from_documents([current_doc])
            else:
                docs_to_process = [current_doc]

            # 处理每个子文档
            for sub_doc in docs_to_process:
                try:
                    # 语义分块
                    chunks = splitter.get_nodes_from_documents([sub_doc])

                    # 二次检查与处理：过滤过小的 chunk，合并相邻的小 chunk
                    MIN_CHUNK_SIZE = int(
                        chunk_target_size * 0.4
                    )  # 最小 chunk 大小为目标大小的 40%

                    # 首先过滤掉过小的 chunk
                    valid_chunks = [
                        chunk for chunk in chunks if len(chunk.text) >= MIN_CHUNK_SIZE
                    ]

                    # 如果过滤后没有 chunk 了，说明原 chunk 都很小，全部保留
                    if not valid_chunks and chunks:
                        valid_chunks = chunks

                    # 合并相邻的小 chunk（关键优化：避免分段过短）
                    # 注意：只在同一章节内合并，跨章节的 chunk 不合并
                    merged_chunks = []
                    if valid_chunks:
                        current_chunk = valid_chunks[0]

                        for i in range(1, len(valid_chunks)):
                            next_chunk = valid_chunks[i]

                            # 检查章节边界：不同章节的 chunk 不能合并
                            current_chapter = current_chunk.metadata.get(
                                "chapter_title"
                            ) or current_chunk.metadata.get("chapter")
                            next_chapter = next_chunk.metadata.get(
                                "chapter_title"
                            ) or next_chunk.metadata.get("chapter")

                            is_same_chapter = current_chapter == next_chapter

                            # 只有在同一章节且合并后不超过目标大小的 1.2 倍时才合并
                            combined_size = len(current_chunk.text) + len(
                                next_chunk.text
                            )
                            if (
                                is_same_chapter
                                and combined_size <= chunk_target_size * 1.2
                            ):
                                # 合并两个 chunk
                                merged_text = (
                                    current_chunk.text + "\n\n" + next_chunk.text
                                )
                                current_chunk = Document(
                                    text=merged_text, metadata=current_chunk.metadata
                                )
                            else:
                                # 保存当前 chunk，开始新的 chunk
                                merged_chunks.append(current_chunk)
                                current_chunk = next_chunk

                        # 添加最后一个 chunk
                        merged_chunks.append(current_chunk)

                    # 二次分块：对过大的 chunk 进行细分，保持 200 字符重叠
                    secondary_splitter = SentenceSplitter(
                        chunk_size=chunk_target_size, chunk_overlap=200
                    )

                    final_chunks = []
                    for chunk in merged_chunks:
                        if len(chunk.text) > chunk_target_size * 1.5:
                            logger.debug(
                                f"Chunk too large ({len(chunk.text)} chars), applying secondary split"
                            )
                            sub_chunks = secondary_splitter.get_nodes_from_documents(
                                [Document(text=chunk.text, metadata=chunk.metadata)]
                            )
                            final_chunks.extend(sub_chunks)
                        else:
                            final_chunks.append(chunk)

                    for chunk in final_chunks:
                        chunk.metadata.update(doc.metadata)
                        if file_hash:
                            from llama_index.core.schema import (
                                NodeRelationship,
                                RelatedNodeInfo,
                            )

                            chunk.metadata["file_hash"] = file_hash
                            chunk.relationships[NodeRelationship.SOURCE] = (
                                RelatedNodeInfo(node_id=file_hash)
                            )
                        chapter_nodes.append(chunk)
                except Exception as e:
                    logger.error(
                        f"Semantic splitting failed for chapter block: {e}. Falling back to sentence splitting."
                    )
                    # 降级分块也使用 200 字符重叠
                    fallback_splitter = SentenceSplitter(
                        chunk_size=chunk_target_size, chunk_overlap=200
                    )
                    fallback_chunks = fallback_splitter.get_nodes_from_documents(
                        [sub_doc]
                    )
                    for chunk in fallback_chunks:
                        chunk.metadata.update(doc.metadata)
                        if file_hash:
                            from llama_index.core.schema import (
                                NodeRelationship,
                                RelatedNodeInfo,
                            )

                            chunk.relationships[NodeRelationship.SOURCE] = (
                                RelatedNodeInfo(node_id=file_hash)
                            )
                        chapter_nodes.append(chunk)
            return chapter_nodes

        # 使用线程池并发处理章节
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # 限制最大线程数，避免过多并发请求导致 API 限流
        # 根据文档数量动态调整，最多 5 个线程（Embedding API 通常有 QPS 限制）
        max_workers = min(len(documents), 5)
        if max_workers < 1:
            max_workers = 1

        logger.info(
            f"Starting parallel semantic splitting for {len(documents)} chapters with {max_workers} threads"
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_doc = {
                executor.submit(process_chapter, doc): doc for doc in documents
            }

            completed_count = 0
            for future in as_completed(future_to_doc):
                doc = future_to_doc[future]
                try:
                    nodes = future.result()
                    all_nodes.extend(nodes)
                    completed_count += 1
                    progress = (completed_count / len(documents)) * 100
                    message = f"处理章节：{completed_count}/{len(documents)} ({progress:.1f}%)"
                    if progress_callback:
                        progress_callback("chunking", progress, message)
                    if completed_count % 5 == 0:
                        logger.info(
                            f"Processed {completed_count}/{len(documents)} chapters"
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to process chapter {doc.metadata.get('chapter_title', 'unknown')}: {e}"
                    )

        logger.info(
            f"Split {len(documents)} chapters into {len(all_nodes)} semantic chunks"
        )
        return all_nodes

    @staticmethod
    def split_pages_into_chunks(
        documents: List[Document],
        chunk_size: int = 1536,
        chunk_overlap: int = 200,
        file_hash: str = None,
    ) -> List[Node]:
        """
        将页级文档拆分为更小的块（适用于普通 PDF）
        使用多线程并发处理语义分块。

        优化策略：
        1. 默认 chunk_overlap 提升到 200 字符，保证上下文连续性
        2. 优先在语义边界（句子、段落）切割
        3. 失败降级时也保持 200 字符重叠

        Args:
            documents: 页级文档列表
            chunk_size: 块大小
            chunk_overlap: 块重叠大小，默认 200 字符
            file_hash: 文档哈希值，用于设置源关联
        Returns:
            拆分后的节点列表
        """
        all_chunks = []
        # 使用语言检测优化分块器
        sample_text = "\n".join([doc.text[:500] for doc in documents if doc.text])
        splitter = get_semantic_splitter(sample_text)

        logger.info(
            f"Using parallel semantic splitting for PDF pages (target chunk size: {chunk_size}, overlap: {chunk_overlap})"
        )

        def process_page(doc):
            page_chunks = []
            try:
                # 预处理：移除过多的连续换行，但保留段落结构
                new_text = clean_document_text(doc.text)

                doc_to_split = doc
                if new_text != doc.text:
                    doc_to_split = Document(text=new_text, metadata=doc.metadata)

                # 使用语义分块器拆分
                chunks = splitter.get_nodes_from_documents([doc_to_split])

                for chunk in chunks:
                    chunk.metadata.update(doc.metadata)
                    if file_hash:
                        from llama_index.core.schema import (
                            NodeRelationship,
                            RelatedNodeInfo,
                        )

                        chunk.metadata["file_hash"] = file_hash
                        chunk.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
                            node_id=file_hash
                        )
                    page_chunks.append(chunk)
            except Exception as e:
                logger.error(
                    f"Semantic splitting failed for page {doc.metadata.get('page_label')}: {e}. Falling back to sentence splitting."
                )
                # 降级分块也使用 200 字符重叠，保证上下文连续性
                fallback_splitter = SentenceSplitter(
                    chunk_size=chunk_size, chunk_overlap=200
                )
                fallback_chunks = fallback_splitter.get_nodes_from_documents([doc])
                for chunk in fallback_chunks:
                    chunk.metadata.update(doc.metadata)
                    if file_hash:
                        from llama_index.core.schema import (
                            NodeRelationship,
                            RelatedNodeInfo,
                        )

                        chunk.metadata["file_hash"] = file_hash
                        chunk.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
                            node_id=file_hash
                        )
                    page_chunks.append(chunk)
            return page_chunks

        # 使用线程池并发处理
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # 页级文档通常数量较多，可以使用更多线程，但要考虑 API 限制
        # 设置最大线程数为 10
        max_workers = min(len(documents), 10)
        if max_workers < 1:
            max_workers = 1

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_doc = {
                executor.submit(process_page, doc): doc for doc in documents
            }

            completed_count = 0
            for future in as_completed(future_to_doc):
                doc = future_to_doc[future]
                try:
                    chunks = future.result()
                    all_chunks.extend(chunks)
                    completed_count += 1
                    if completed_count % 20 == 0:
                        logger.info(
                            f"Processed {completed_count}/{len(documents)} pages"
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to process page {doc.metadata.get('page_label', 'unknown')}: {e}"
                    )

        logger.info(
            f"Split {len(documents)} pages into {len(all_chunks)} semantic chunks"
        )
        return all_chunks

    @staticmethod
    def hierarchical_chunking(
        documents: List[Document],
        parent_chunk_size: int = 1500,
        child_chunk_size: int = 400,
        file_hash: str = None,
    ) -> List[Node]:
        """
        父子块关联分块策略：
        - 大块（parent）：提供完整上下文（1000-2000 tokens）
        - 小块（child）：用于精确检索（200-400 tokens）
        - 元数据关联：child 块记录 parent_id

        业界最佳实践：
        - 语义边界优先：使用标题层级（H1/H2/H3）、段落边界作为首要分割点
        - 结构感知：Markdown/HTML 标签、列表、代码块保持完整
        - 动态分块大小：根据内容密度自动调整，避免切断语义单元

        Args:
            documents: 文档列表
            parent_chunk_size: 父块大小（字符数）
            child_chunk_size: 子块大小（字符数）
            file_hash: 文档哈希值

        Returns:
            分块后的节点列表（包含父子块）
        """
        all_nodes = []

        for doc in documents:
            # 按标题层级分割（支持 Markdown 和常见文档结构）
            sections = re.split(r"\n(?=##?\s+)", doc.text)

            parent_nodes = []
            child_nodes = []

            for section_idx, section in enumerate(sections):
                if not section.strip():
                    continue

                # 创建父块（提供完整上下文）
                parent_node = Node(text=section, metadata=doc.metadata.copy())
                parent_node.metadata["chunk_type"] = "parent"
                parent_node.metadata["chunk_size"] = "large"
                parent_nodes.append(parent_node)

                # 细分为子块（用于精确检索）
                # 按段落分割
                paragraphs = section.split("\n\n")

                # 合并相邻段落直到达到目标大小
                current_child_text = ""
                child_count = 0

                for para in paragraphs:
                    if not para.strip():
                        continue

                    if len(current_child_text) + len(para) > child_chunk_size * 1.5:
                        # 创建子块
                        if current_child_text.strip():
                            child_node = Node(
                                text=current_child_text.strip(),
                                metadata={
                                    **doc.metadata,
                                    "parent_id": parent_node.node_id,
                                    "chunk_type": "child",
                                    "chunk_size": "small",
                                    "child_index": child_count,
                                },
                            )
                            child_nodes.append(child_node)
                            child_count += 1

                        current_child_text = para
                    else:
                        current_child_text += (
                            "\n\n" + para if current_child_text else para
                        )

                # 处理最后一个子块
                if current_child_text.strip():
                    child_node = Node(
                        text=current_child_text.strip(),
                        metadata={
                            **doc.metadata,
                            "parent_id": parent_node.node_id,
                            "chunk_type": "child",
                            "chunk_size": "small",
                            "child_index": child_count,
                        },
                    )
                    child_nodes.append(child_node)

            # 设置父子块的关联关系
            for parent_node in parent_nodes:
                if file_hash:
                    from llama_index.core.schema import (
                        NodeRelationship,
                        RelatedNodeInfo,
                    )

                    parent_node.metadata["file_hash"] = file_hash
                    parent_node.relationships[NodeRelationship.SOURCE] = (
                        RelatedNodeInfo(node_id=file_hash)
                    )
                all_nodes.append(parent_node)

            for child_node in child_nodes:
                if file_hash:
                    from llama_index.core.schema import (
                        NodeRelationship,
                        RelatedNodeInfo,
                    )

                    child_node.metadata["file_hash"] = file_hash
                    child_node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
                        node_id=file_hash
                    )
                all_nodes.append(child_node)

        logger.info(
            f"Hierarchical chunking completed: {len(documents)} documents -> "
            f"{len(all_nodes)} nodes (including parent-child relationships)"
        )

        return all_nodes
