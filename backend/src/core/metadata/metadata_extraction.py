"""元数据提取核心逻辑

提供标准和分层两种元数据提取策略。
"""

import asyncio
from typing import Callable, List, Optional

from llama_index.core.schema import Node

from src.core.metadata.extraction_helpers import (
    handle_extraction_failure,
    log_hierarchical_stats,
    log_standard_stats,
    report_progress,
    serialize_list_fields,
)
from src.core.metadata.key_chunk_identifier import identify_key_chunks
from src.core.metadata.node_cleaner import clean_node_content
from src.core.metadata_extractor import MetadataExtractor


class MetadataExtractionService:
    """元数据提取服务，协调标准和分层提取策略"""

    def __init__(self, concurrency: int):
        self.concurrency = concurrency
        self._semaphore: Optional[asyncio.Semaphore] = None

    @property
    def semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.concurrency)
        return self._semaphore

    async def process_standard(
        self,
        nodes: List[Node],
        file_hash: str,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
        total_chunks: Optional[int] = None,
    ) -> List[Node]:
        """标准处理方式：每个节点都提取元数据"""
        total = total_chunks or len(nodes)
        processed_count = 0

        async def process_single(node: Node) -> Optional[Node]:
            nonlocal processed_count
            async with self.semaphore:
                try:
                    meta = await MetadataExtractor.extract(node.get_content())
                    meta_dict = meta.model_dump()
                    serialize_list_fields(meta_dict)
                    node.metadata.update(meta_dict)
                    node.metadata["content"] = clean_node_content(node.get_content())
                    node.metadata["file_hash"] = file_hash
                    processed_count += 1
                    report_progress(progress_callback, processed_count, total)
                    return node
                except Exception as e:
                    return handle_extraction_failure(node, file_hash, e)

        results = await asyncio.gather(*(process_single(n) for n in nodes))
        processed = [n for n in results if n is not None]
        log_standard_stats(processed)
        return processed

    async def process_hierarchical(
        self,
        nodes: List[Node],
        file_hash: str,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
        total_chunks: Optional[int] = None,
        doc_level_metadata: Optional[dict] = None,
    ) -> List[Node]:
        """分层元数据提取策略：文档级 + 关键块 LLM + 普通块规则"""
        total = total_chunks or len(nodes)
        processed_count = 0

        doc_level_metadata = doc_level_metadata or self._extract_doc_metadata(nodes)

        key_indices = identify_key_chunks(nodes)
        logger.info(f"Identified {len(key_indices)} key chunks out of {total}")

        async def process_single(node: Node, idx: int) -> Optional[Node]:
            nonlocal processed_count
            async with self.semaphore:
                try:
                    if idx in key_indices:
                        meta = await MetadataExtractor.extract(
                            node.get_content(), use_cache=True
                        )
                        meta_dict = meta.model_dump()
                        node.metadata["metadata_source"] = "llm_key_chunk"
                    else:
                        from src.core.metadata_extractor import _rule_extractor

                        meta_dict = _rule_extractor.extract(node.get_content()).model_dump()
                        self._inherit_doc_metadata(meta_dict, doc_level_metadata)
                        node.metadata["metadata_source"] = "rule_based"

                    serialize_list_fields(meta_dict)
                    node.metadata.update(meta_dict)
                    node.metadata["content"] = clean_node_content(node.get_content())
                    node.metadata["file_hash"] = file_hash
                    processed_count += 1
                    report_progress(progress_callback, processed_count, total)
                    return node
                except Exception as e:
                    return handle_extraction_failure(node, file_hash, e)

        results = await asyncio.gather(
            *(process_single(n, i) for i, n in enumerate(nodes))
        )
        processed = [n for n in results if n is not None]
        log_hierarchical_stats(processed)
        return processed

    @staticmethod
    async def _extract_doc_metadata(nodes: List[Node]) -> dict:
        """提取文档级元数据"""
        logger.info("Extracting document-level metadata...")
        sample = "\n".join(n.get_content()[:500] for n in nodes[:min(50, len(nodes))])
        try:
            meta = await MetadataExtractor.extract(sample, use_cache=True)
            logger.info(f"Document-level metadata extracted: {meta.topics}")
            return meta.model_dump()
        except Exception as e:
            logger.error(f"Failed to extract document-level metadata: {e}")
            return {}

    @staticmethod
    def _inherit_doc_metadata(meta_dict: dict, doc_meta: dict) -> None:
        """继承文档级元数据（如果规则提取为空）"""
        if not meta_dict.get("topics") and doc_meta.get("topics"):
            meta_dict["topics"] = doc_meta["topics"]
        if not meta_dict.get("brain_regions") and doc_meta.get("brain_regions"):
            meta_dict["brain_regions"] = doc_meta["brain_regions"]


from src.utils.logger import logger
