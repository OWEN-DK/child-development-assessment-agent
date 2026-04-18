"""页面分块策略模块

将页级文档拆分为更小的语义块。
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document, Node

from src.core.metadata.splitter_manager import get_semantic_splitter
from src.utils.logger import logger
from src.utils.text_cleaner import clean_document_text


def split_pages_into_chunks(
    documents: List[Document],
    chunk_size: int = 1536,
    chunk_overlap: int = 200,
    file_hash: Optional[str] = None,
) -> List[Node]:
    """将页级文档拆分为更小的块

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
    sample_text = "\n".join([doc.text[:500] for doc in documents if doc.text])
    splitter = get_semantic_splitter(sample_text)

    logger.info(
        f"Using parallel semantic splitting for PDF pages "
        f"(target chunk size: {chunk_size}, overlap: {chunk_overlap})"
    )

    def process_page(doc: Document) -> List[Node]:
        page_chunks = []
        try:
            new_text = clean_document_text(doc.text)

            doc_to_split = doc
            if new_text != doc.text:
                doc_to_split = Document(text=new_text, metadata=doc.metadata)

            chunks = splitter.get_nodes_from_documents([doc_to_split])

            for chunk in chunks:
                _attach_metadata(chunk, doc.metadata, file_hash)
                page_chunks.append(chunk)
        except Exception as e:
            logger.error(
                f"Semantic splitting failed for page "
                f"{doc.metadata.get('page_label')}: {e}. "
                f"Falling back to sentence splitting."
            )
            fallback_splitter = SentenceSplitter(
                chunk_size=chunk_size, chunk_overlap=200
            )
            fallback_chunks = fallback_splitter.get_nodes_from_documents([doc])
            for chunk in fallback_chunks:
                _attach_metadata(chunk, doc.metadata, file_hash)
                page_chunks.append(chunk)
        return page_chunks

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
                    f"Failed to process page "
                    f"{doc.metadata.get('page_label', 'unknown')}: {e}"
                )

    logger.info(
        f"Split {len(documents)} pages into {len(all_chunks)} semantic chunks"
    )
    return all_chunks


def _attach_metadata(
    chunk: Node, source_metadata: dict, file_hash: Optional[str]
) -> None:
    """为分块附加元数据和源关联"""
    chunk.metadata.update(source_metadata)
    if file_hash:
        from llama_index.core.schema import NodeRelationship, RelatedNodeInfo

        chunk.metadata["file_hash"] = file_hash
        chunk.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
            node_id=file_hash
        )
