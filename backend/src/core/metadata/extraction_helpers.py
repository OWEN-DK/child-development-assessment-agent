"""元数据提取辅助函数

包含序列化、进度报告、失败处理、统计日志等共享逻辑。
"""

import json
from typing import Callable, List, Optional

from llama_index.core.schema import Node

from src.utils.logger import logger


def serialize_list_fields(meta_dict: dict) -> None:
    """序列化列表字段为 JSON 字符串以适配向量数据库"""
    if isinstance(meta_dict.get("topics"), list):
        meta_dict["topics"] = json.dumps(meta_dict["topics"], ensure_ascii=False)
    if isinstance(meta_dict.get("brain_regions"), list):
        meta_dict["brain_regions"] = json.dumps(
            meta_dict["brain_regions"], ensure_ascii=False
        )


def report_progress(
    progress_callback: Optional[Callable[[str, float, str], None]],
    processed_count: int,
    total_chunks: int,
) -> None:
    """报告处理进度"""
    if progress_callback and (processed_count % 20 == 0 or processed_count == total_chunks):
        progress = (processed_count / total_chunks) * 100
        message = f"处理中：{processed_count}/{total_chunks} ({progress:.1f}%)"
        logger.info(f"Metadata extraction progress: {message}")
        progress_callback("metadata_extraction", progress, message)


def handle_extraction_failure(
    node: Node, file_hash: str, error: Exception
) -> Optional[Node]:
    """处理元数据提取失败，使用默认元数据继续"""
    content_preview = node.get_content()[:100].replace("\n", " ")
    logger.error(
        f"Metadata extraction failed for chunk (file_hash: {file_hash}, "
        f"content preview: {content_preview}...): {error}",
        exc_info=True,
    )

    from src.core.metadata_extractor import ExtractedMetadata
    from src.core.metadata.node_cleaner import clean_node_content

    extracted_meta = ExtractedMetadata()
    meta_dict = extracted_meta.model_dump()
    serialize_list_fields(meta_dict)
    node.metadata.update(meta_dict)

    node.metadata["content"] = clean_node_content(node.get_content())
    node.metadata["file_hash"] = file_hash
    node.metadata["metadata_extraction_failed"] = True

    return node


def log_standard_stats(processed_nodes: List[Node]) -> None:
    """记录标准策略完成统计"""
    failed = sum(
        1 for n in processed_nodes if n.metadata.get("metadata_extraction_failed", False)
    )
    logger.info(
        f"Completed metadata extraction: {len(processed_nodes) - failed} succeeded, "
        f"{failed} failed, total: {len(processed_nodes)} nodes"
    )


def log_hierarchical_stats(processed_nodes: List[Node]) -> None:
    """记录分层策略完成统计"""
    llm = sum(1 for n in processed_nodes if n.metadata.get("metadata_source") == "llm_key_chunk")
    rule = sum(1 for n in processed_nodes if n.metadata.get("metadata_source") == "rule_based")
    failed = sum(
        1 for n in processed_nodes if n.metadata.get("metadata_extraction_failed", False)
    )
    logger.info(
        f"Completed hierarchical metadata extraction: "
        f"{llm} LLM chunks, {rule} rule-based chunks, "
        f"{failed} failed, total: {len(processed_nodes)} nodes"
    )
