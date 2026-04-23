"""章节分块策略模块

将章节级文档拆分为更小的语义块。
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional

from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document, Node

from src.core.metadata.node_cleaner import clean_node_content
from src.core.metadata.splitter_manager import get_chapter_splitter
from src.utils.logger import logger
from src.utils.text_cleaner import clean_document_text


def split_chapters_into_chunks(
    documents: List[Document],
    chunk_target_size: int = 1024,
    file_hash: Optional[str] = None,
    progress_callback: Optional[Callable[[str, float, str], None]] = None,
) -> List[Node]:
    """将章节级文档拆分为更小的块

    使用语义分块，保持语意完整性。采用多线程并发处理。

    Args:
        documents: 章节级文档列表
        chunk_target_size: 目标块大小（字符数），推荐 1024-1200
        file_hash: 文档哈希值
        progress_callback: 进度回调函数

    Returns:
        拆分后的节点列表
    """
    all_nodes = []
    sample_text = "\n".join([doc.text[:500] for doc in documents if doc.text])
    splitter = get_chapter_splitter(sample_text)

    max_workers = min(len(documents), 5) or 1

    logger.info(
        f"Starting parallel semantic splitting for {len(documents)} chapters "
        f"with {max_workers} threads"
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_doc = {
            executor.submit(
                _process_chapter, doc, splitter, chunk_target_size, file_hash
            ): doc
            for doc in documents
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
                    logger.info(f"Processed {completed_count}/{len(documents)} chapters")
            except Exception as e:
                logger.error(
                    f"Failed to process chapter "
                    f"{doc.metadata.get('chapter_title', 'unknown')}: {e}"
                )

    logger.info(
        f"Split {len(documents)} chapters into {len(all_nodes)} semantic chunks"
    )
    return all_nodes


def _process_chapter(
    doc: Document,
    splitter,
    chunk_target_size: int,
    file_hash: Optional[str],
) -> List[Node]:
    """处理单个章节文档"""
    chapter_nodes = []
    new_text = clean_document_text(doc.text)
    current_doc = Document(text=new_text, metadata=doc.metadata) if new_text != doc.text else doc

    if _is_poorly_formatted(current_doc.text):
        return _fallback_split([current_doc], chunk_target_size, file_hash, doc.metadata)

    docs_to_process = _pre_split_if_needed(current_doc)

    for sub_doc in docs_to_process:
        try:
            chunks = splitter.get_nodes_from_documents([sub_doc])
            chunks = _filter_empty_nodes(chunks)
            final_chunks = _refine_chunks(chunks, chunk_target_size)
            for chunk in final_chunks:
                _attach_metadata(chunk, doc.metadata, file_hash)
                chapter_nodes.append(chunk)
        except Exception as e:
            logger.error(f"Semantic splitting failed: {e}. Falling back.")
            fallback = _fallback_split([sub_doc], chunk_target_size, file_hash, doc.metadata)
            chapter_nodes.extend(fallback)

    return chapter_nodes


def _is_poorly_formatted(text: str) -> bool:
    """检查文本是否排版混乱（超长单行）"""
    return max((len(line) for line in text.split("\n")), default=0) > 1500


def _pre_split_if_needed(doc: Document) -> List[Document]:
    """如果文档过大，进行预切分"""
    MAX_PRE_SPLIT_SIZE = 20000
    if len(doc.text) > MAX_PRE_SPLIT_SIZE:
        logger.debug(f"Chapter too large ({len(doc.text)} chars), pre-splitting...")
        pre_splitter = SentenceSplitter(chunk_size=MAX_PRE_SPLIT_SIZE, chunk_overlap=500)
        return _filter_empty_nodes(pre_splitter.get_nodes_from_documents([doc]))
    return [doc]


def _filter_empty_nodes(nodes: List) -> List:
    """过滤空节点和纯空格节点"""
    from llama_index.core.schema import TextNode
    
    filtered = []
    for node in nodes:
        cleaned = clean_node_content(node.text)
        if not cleaned:
            continue
        new_node = TextNode(
            text=cleaned,
            metadata=node.metadata.copy(),
            relationships=node.relationships.copy(),
            embedding=node.embedding,
            excluded_embed_metadata_keys=node.excluded_embed_metadata_keys.copy(),
            excluded_llm_metadata_keys=node.excluded_llm_metadata_keys.copy(),
            metadata_separator=node.metadata_separator,
            metadata_template=node.metadata_template,
            text_template=node.text_template,
        )
        filtered.append(new_node)
    return filtered


def _refine_chunks(chunks: List, chunk_target_size: int) -> List:
    """优化分块：过滤过小、合并相邻、二次分割过大"""
    MIN_CHUNK_SIZE = int(chunk_target_size * 0.4)
    valid_chunks = [c for c in chunks if len(c.text) >= MIN_CHUNK_SIZE] or chunks

    merged = _merge_adjacent(valid_chunks, chunk_target_size)

    # 二次分割阈值降低至 1.2 倍，确保不超过 embedding 模型 1536 字符限制
    SECONDARY_SPLIT_THRESHOLD = int(chunk_target_size * 1.2)
    secondary = SentenceSplitter(chunk_size=chunk_target_size, chunk_overlap=200)
    final = []
    for chunk in merged:
        if len(chunk.text) > SECONDARY_SPLIT_THRESHOLD:
            sub = secondary.get_nodes_from_documents(
                [Document(text=chunk.text, metadata=chunk.metadata)]
            )
            final.extend(sub)
        else:
            final.append(chunk)
    return _filter_empty_nodes(final)


def _merge_adjacent(valid_chunks: List, chunk_target_size: int) -> List:
    """合并同一章节内相邻的小块"""
    if not valid_chunks:
        return []

    merged = []
    current = valid_chunks[0]
    for next_chunk in valid_chunks[1:]:
        curr_ch = current.metadata.get("chapter_title") or current.metadata.get("chapter")
        next_ch = next_chunk.metadata.get("chapter_title") or next_chunk.metadata.get("chapter")
        combined = len(current.text) + len(next_chunk.text)

        if curr_ch == next_ch and combined <= chunk_target_size * 1.2:
            merged_text = current.text.strip() + "\n\n" + next_chunk.text.strip()
            current = Document(
                text=merged_text, metadata=current.metadata
            )
        else:
            merged.append(current)
            current = next_chunk
    merged.append(current)
    return merged


def _fallback_split(
    docs: List[Document], chunk_target_size: int, file_hash: Optional[str], meta: dict
) -> List[Node]:
    """降级为规则分块"""
    splitter = SentenceSplitter(chunk_size=chunk_target_size, chunk_overlap=200)
    chunks = splitter.get_nodes_from_documents(docs)
    chunks = _filter_empty_nodes(chunks)
    for chunk in chunks:
        _attach_metadata(chunk, meta, file_hash)
    return chunks


def _attach_metadata(chunk: Node, source_meta: dict, file_hash: Optional[str]) -> None:
    """为分块附加元数据和源关联"""
    chunk.metadata.update(source_meta)
    if file_hash:
        from llama_index.core.schema import NodeRelationship, RelatedNodeInfo

        chunk.metadata["file_hash"] = file_hash
        chunk.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id=file_hash)
