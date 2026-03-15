import asyncio
from typing import List, Optional
from llama_index.core.schema import Node, Document
from llama_index.core.node_parser import SentenceSplitter, SemanticSplitterNodeParser

# from llama_index.core.node_parser.text.sentence import SENTENCE_SPLITTER_RE
from src.core.metadata_extractor import MetadataExtractor
from src.config.settings import settings
from src.utils.logger import logger

# 初始化语义分块器（全局单例）
_semantic_splitter = None


def get_semantic_splitter():
    """获取语义分块器单例"""
    global _semantic_splitter
    if _semantic_splitter is None:
        from llama_index.core import Settings

        # 使用全局配置的嵌入模型，避免重复初始化
        _semantic_splitter = SemanticSplitterNodeParser(
            embed_model=Settings.embed_model,
            buffer_size=settings.semantic_splitter_buffer_size,
            breakpoint_percentile_threshold=settings.semantic_splitter_breakpoint_threshold,
            chunk_size=settings.rag_epub_chunk_target_size,
        )
    return _semantic_splitter


def get_chapter_splitter():
    """获取针对长章节优化的语义分块器"""
    from llama_index.core import Settings

    # 针对长章节，我们使用更小的buffer_size和更严格的阈值
    # 以确保长章节能被切分得更细
    return SemanticSplitterNodeParser(
        embed_model=Settings.embed_model,
        buffer_size=settings.semantic_splitter_chapter_buffer_size,  # 使用配置值
        breakpoint_percentile_threshold=settings.semantic_splitter_chapter_breakpoint_threshold,  # 使用配置值
        chunk_size=settings.rag_epub_chunk_target_size,
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
    ) -> List[Node]:
        """
        批量处理节点，提取元数据
        Args:
            nodes: 待处理的节点列表
            file_hash: 文档的哈希值，用于关联
            progress_callback: 进度回调函数
            total_chunks: 总块数，用于进度计算
        Returns:
            处理后的节点列表
        """
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
                    # 合并元数据
                    node.metadata.update(extracted_meta.model_dump())
                    node.metadata["content"] = node.get_content()
                    node.metadata["file_hash"] = file_hash

                    processed_count += 1
                    if progress_callback and (
                        processed_count % 20 == 0 or processed_count == total_chunks
                    ):
                        progress = (processed_count / total_chunks) * 100
                        message = f"处理中: {processed_count}/{total_chunks} ({progress:.1f}%)"
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
                    node.metadata.update(extracted_meta.model_dump())
                    node.metadata["content"] = node.get_content()
                    node.metadata["file_hash"] = file_hash
                    node.metadata["metadata_extraction_failed"] = True

                    processed_count += 1
                    return node

        # 创建所有处理任务
        for node in nodes:
            extraction_tasks.append(process_single_node(node))

        # 并发执行
        processed_nodes = await asyncio.gather(*extraction_tasks)
        # 过滤掉None（虽然理论上不会有）
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

    @staticmethod
    def split_chapters_into_chunks(
        documents: List[Document], chunk_target_size: int = 800, file_hash: str = None
    ) -> List[Node]:
        """
        将章节级文档拆分为更小的块（适用于EPUB和带书签的PDF）
        使用语义分块，保持语意完整性。
        采用多线程并发处理以加速 Embedding 计算。
        Args:
            documents: 章节级文档列表
            chunk_target_size: 目标块大小（字符数）
            file_hash: 文档哈希值，用于设置源关联
        Returns:
            拆分后的节点列表
        """
        all_nodes = []
        # 使用针对长章节优化的分块器
        splitter = get_chapter_splitter()
        
        # 定义单个文档处理函数
        def process_chapter(doc):
            chapter_nodes = []
            # 预处理：移除过多的连续换行，但保留段落结构
            import re
            
            # 安全地修改文本
            original_text = doc.text
            new_text = re.sub(r"\n{3,}", "\n\n", original_text)
            
            current_doc = doc
            if new_text != original_text:
                current_doc = Document(text=new_text, metadata=doc.metadata)

            # 策略优化：对于超大章节，先使用SentenceSplitter进行粗粒度拆分
            MAX_PRE_SPLIT_SIZE = 20000
            docs_to_process = []
            
            # 检查文本结构质量：如果存在超长单行（>1500字符），说明排版混乱或缺乏换行
            # 这种情况下语义分块效果极差且会导致Embedding截断，应直接降级为规则分块
            longest_line_len = max((len(line) for line in current_doc.text.split('\n')), default=0)
            is_poorly_formatted = longest_line_len > 1500

            if is_poorly_formatted:
                logger.warning(
                    f"Chapter content poorly formatted (max line len: {longest_line_len}), "
                    "skipping semantic splitting and using rule-based splitting."
                )
                # 直接使用规则分块，彻底跳过昂贵的语义分块
                fallback_splitter = SentenceSplitter(
                    chunk_size=chunk_target_size, chunk_overlap=50
                )
                fallback_chunks = fallback_splitter.get_nodes_from_documents([current_doc])
                for chunk in fallback_chunks:
                    chunk.metadata.update(doc.metadata)
                    if file_hash:
                        from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
                        chunk.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
                            node_id=file_hash
                        )
                    chapter_nodes.append(chunk)
                return chapter_nodes

            # 如果结构尚可，但总长度过大，进行预切分
            if len(current_doc.text) > MAX_PRE_SPLIT_SIZE:
                logger.debug(f"Chapter too large ({len(current_doc.text)} chars), pre-splitting into smaller blocks...")
                pre_splitter = SentenceSplitter(chunk_size=MAX_PRE_SPLIT_SIZE, chunk_overlap=500)
                docs_to_process = pre_splitter.get_nodes_from_documents([current_doc])
            else:
                docs_to_process = [current_doc]

            # 处理每个子文档
            for sub_doc in docs_to_process:
                try:
                    # 语义分块
                    chunks = splitter.get_nodes_from_documents([sub_doc])

                    # 二次检查与处理
                    final_chunks = []
                    secondary_splitter = SentenceSplitter(
                        chunk_size=chunk_target_size, chunk_overlap=50
                    )

                    for chunk in chunks:
                        if len(chunk.text) > chunk_target_size * 2:
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
                            from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
                            chunk.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
                                node_id=file_hash
                            )
                        chapter_nodes.append(chunk)
                except Exception as e:
                    logger.error(
                        f"Semantic splitting failed for chapter block: {e}. Falling back to sentence splitting."
                    )
                    fallback_splitter = SentenceSplitter(
                        chunk_size=chunk_target_size, chunk_overlap=50
                    )
                    fallback_chunks = fallback_splitter.get_nodes_from_documents([sub_doc])
                    for chunk in fallback_chunks:
                        chunk.metadata.update(doc.metadata)
                        if file_hash:
                            from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
                            chunk.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
                                node_id=file_hash
                            )
                        chapter_nodes.append(chunk)
            return chapter_nodes

        # 使用线程池并发处理章节
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # 限制最大线程数，避免过多并发请求导致API限流
        # 根据文档数量动态调整，最多5个线程（Embedding API通常有QPS限制）
        max_workers = min(len(documents), 5)
        if max_workers < 1:
            max_workers = 1
            
        logger.info(f"Starting parallel semantic splitting for {len(documents)} chapters with {max_workers} threads")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_doc = {executor.submit(process_chapter, doc): doc for doc in documents}
            
            completed_count = 0
            for future in as_completed(future_to_doc):
                doc = future_to_doc[future]
                try:
                    nodes = future.result()
                    all_nodes.extend(nodes)
                    completed_count += 1
                    if completed_count % 5 == 0:
                        logger.info(f"Processed {completed_count}/{len(documents)} chapters")
                except Exception as e:
                    logger.error(f"Failed to process chapter {doc.metadata.get('chapter_title', 'unknown')}: {e}")

        logger.info(
            f"Split {len(documents)} chapters into {len(all_nodes)} semantic chunks"
        )
        return all_nodes

    @staticmethod
    def split_pages_into_chunks(
        documents: List[Document],
        chunk_size: int = 1536,
        chunk_overlap: int = 20,
        file_hash: str = None,
    ) -> List[Node]:
        """
        将页级文档拆分为更小的块（适用于普通PDF）
        使用多线程并发处理语义分块。
        Args:
            documents: 页级文档列表
            chunk_size: 块大小
            chunk_overlap: 块重叠大小
            file_hash: 文档哈希值，用于设置源关联
        Returns:
            拆分后的节点列表
        """
        all_chunks = []
        splitter = get_semantic_splitter()
        
        logger.info(
            f"Using parallel semantic splitting for PDF pages (target chunk size: {chunk_size})"
        )

        def process_page(doc):
            page_chunks = []
            try:
                # 预处理：移除过多的连续换行，但保留段落结构
                import re
                
                # 安全地修改文本
                original_text = doc.text
                new_text = re.sub(r"\n{3,}", "\n\n", original_text)
                
                doc_to_split = doc
                if new_text != original_text:
                    doc_to_split = Document(text=new_text, metadata=doc.metadata)

                # 使用语义分块器拆分
                chunks = splitter.get_nodes_from_documents([doc_to_split])

                for chunk in chunks:
                    chunk.metadata.update(doc.metadata)
                    if file_hash:
                        from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
                        chunk.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
                            node_id=file_hash
                        )
                    page_chunks.append(chunk)
            except Exception as e:
                logger.error(
                    f"Semantic splitting failed for page {doc.metadata.get('page_label')}: {e}. Falling back to sentence splitting."
                )
                fallback_splitter = SentenceSplitter(
                    chunk_size=chunk_size, chunk_overlap=chunk_overlap
                )
                fallback_chunks = fallback_splitter.get_nodes_from_documents([doc])
                for chunk in fallback_chunks:
                    chunk.metadata.update(doc.metadata)
                    if file_hash:
                        from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
                        chunk.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
                            node_id=file_hash
                        )
                    page_chunks.append(chunk)
            return page_chunks

        # 使用线程池并发处理
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # 页级文档通常数量较多，可以使用更多线程，但要考虑API限制
        # 设置最大线程数为10
        max_workers = min(len(documents), 10)
        if max_workers < 1:
            max_workers = 1
            
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_doc = {executor.submit(process_page, doc): doc for doc in documents}
            
            completed_count = 0
            for future in as_completed(future_to_doc):
                doc = future_to_doc[future]
                try:
                    chunks = future.result()
                    all_chunks.extend(chunks)
                    completed_count += 1
                    if completed_count % 20 == 0:
                        logger.info(f"Processed {completed_count}/{len(documents)} pages")
                except Exception as e:
                    logger.error(f"Failed to process page {doc.metadata.get('page_label', 'unknown')}: {e}")

        logger.info(
            f"Split {len(documents)} pages into {len(all_chunks)} semantic chunks"
        )
        return all_chunks
