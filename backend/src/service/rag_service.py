import os
import hashlib
import time
import asyncio
import re
import jieba
from typing import List, Any, Tuple
from src.model.schemas import KnowledgeItem, RiskLevel
from src.model.document import DocumentRecord, DocumentMetadata
from src.service.document_manager import document_manager
from src.core.parsers import get_parser, PDFVLParser, PDFParser
from src.core.metadata_extractor import MetadataExtractor
from src.config.settings import settings
from src.utils.logger import logger
from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
    Settings,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.vector_stores import (
    MetadataFilter,
    MetadataFilters,
    FilterOperator,
)
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo, Document
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.retrievers import BaseRetriever
from llama_index.llms.dashscope import DashScope
from llama_index.embeddings.dashscope import DashScopeEmbedding
from src.core.prompts import QUERY_REWRITE_PROMPT, SYNONYM_EXPANSION_PROMPT

# 索引存储路径
STORAGE_DIR = settings.rag_storage_dir


class RagService:
    def __init__(self):
        self.index = None
        self.bm25_retriever = None
        self.vector_retriever = None
        self.bm25_weight = 0.5
        self.vector_weight = 0.5
        self.merge_mode = "OR"
        # 缓存存储
        self.cache = {}
        self.cache_timestamps = {}

        self.dashscope_available = bool(settings.dashscope_api_key)
        if not self.dashscope_available:
            logger.warning(
                "DashScope API Key 未找到，RAG检索和元数据提取功能将不可用。"
                "请设置 DASHSCOPE_API_KEY 环境变量以启用完整功能。"
            )
            # 禁用默认的OpenAI模型加载
            Settings.llm = None
            Settings.embed_model = None
            Settings.chunk_size = settings.rag_chunk_size
        else:
            # 配置LlamaIndex使用通义千问模型
            Settings.llm = DashScope(
                model=settings.llm_models["assessment"],
                api_key=settings.dashscope_api_key,
            )
            Settings.embed_model = DashScopeEmbedding(
                model_name=settings.embedding_model_name, api_key=settings.dashscope_api_key
            )
            Settings.chunk_size = settings.rag_chunk_size

        self._initialize_index()

    def _initialize_index(self):
        """从存储中初始化向量索引"""
        if not os.path.exists(STORAGE_DIR):
            os.makedirs(STORAGE_DIR)

        try:
            # 检查存储中是否存在索引
            if os.path.exists(os.path.join(STORAGE_DIR, "docstore.json")):
                logger.info("Loading index from storage...")
                storage_context = StorageContext.from_defaults(persist_dir=STORAGE_DIR)
                self.index = load_index_from_storage(storage_context)
                logger.info("Index loaded successfully.")
                self._initialize_retrievers()
            else:
                logger.warning("No existing index found. Waiting for file uploads.")
                self.index = None
        except Exception as e:
            logger.error(f"Failed to load index from storage: {e}")
            self.index = None

    async def retrieve_knowledge(
        self, query: str, age: int, limit: int = 3
    ) -> List[KnowledgeItem]:
        """
        根据查询和年龄检索相关知识点
        """
        logger.info(f"Retrieving knowledge for query: '{query}', age: {age}")

        # Check cache first
        cache_key = self._get_cache_key(query, age, limit)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            logger.info(f"Cache hit for query: '{query}'")
            return cached_result

        # Rewrite query for better retrieval
        rewritten_query = await self._rewrite_query(query, age)
        # Expand synonyms to improve recall (including substring matching and translation)
        expanded_query = await self._expand_synonyms(rewritten_query)

        if not self.index:
            logger.warning("Index not available, returning empty results.")
            return []

        try:
            # Create filters
            filters = []
            if age > 0:
                # Range filtering: target_age_min <= age AND target_age_max >= age
                filters.append(
                    MetadataFilter(
                        key="target_age_min", value=age, operator=FilterOperator.LTE
                    )
                )
                filters.append(
                    MetadataFilter(
                        key="target_age_max", value=age, operator=FilterOperator.GTE
                    )
                )

            metadata_filters = MetadataFilters(filters=filters) if filters else None

            if not self.bm25_retriever or not self.vector_retriever:
                # Fallback to single vector retriever if hybrid not initialized
                corpus_size = len(self.index.docstore.docs) if hasattr(self.index, 'docstore') else 0
                adjusted_limit = min(limit, max(1, corpus_size))
                retriever = self.index.as_retriever(
                    similarity_top_k=adjusted_limit, filters=metadata_filters
                )
                nodes = await retriever.aretrieve(query)
            else:
                # Set filters for both retrievers
                self.bm25_retriever.filters = metadata_filters
                self.vector_retriever.filters = metadata_filters

                # Run both retrievals in parallel
                bm25_nodes = await self.bm25_retriever.aretrieve(expanded_query)
                vector_nodes = await self.vector_retriever.aretrieve(expanded_query)

                # Merge results with weighted scoring
                node_map = {}

                # Process BM25 results
                for node in bm25_nodes:
                    node_id = node.node.node_id
                    node.score = (
                        node.score * self.bm25_weight
                        if node.score
                        else self.bm25_weight
                    )
                    node_map[node_id] = node

                # Process vector results
                for node in vector_nodes:
                    node_id = node.node.node_id
                    if node_id in node_map:
                        # Merge scores if node exists in both results
                        existing_node = node_map[node_id]
                        existing_score = existing_node.score or 0
                        new_score = (
                            node.score * self.vector_weight
                            if node.score
                            else self.vector_weight
                        )
                        existing_node.score = existing_score + new_score
                    else:
                        # Add new node from vector results
                        node.score = (
                            node.score * self.vector_weight
                            if node.score
                            else self.vector_weight
                        )
                        node_map[node_id] = node

                # Convert to list and sort by combined score
                nodes = sorted(
                    node_map.values(), key=lambda x: x.score or 0.0, reverse=True
                )[:limit]

            results = []
            for node_with_score in nodes:
                node = node_with_score.node
                # Fallback to get_content if 'content' metadata is missing
                content = node.metadata.get("content", node.get_content())
                metadata = node.metadata or {}
                source = metadata.get("file_name", "Unknown Source")
                score = node_with_score.score or 0.0
                
                # 过滤掉PDF元信息等无效内容
                if not content or content.startswith("[General Information]") or "书名=" in content or "SS号=" in content:
                    continue
                    
                # 最低相似度阈值过滤，只返回大于阈值的结果，过滤不相关内容
                if score < settings.rag_search_min_similarity_threshold:
                    continue

                # Extract metadata fields
                brain_regions = metadata.get("brain_regions", [])
                topics = metadata.get("topics", [])
                # Map topics to benefits for compatibility if benefits not present
                benefits = metadata.get("benefits", topics)

                target_age_min = metadata.get("target_age_min", 0)
                target_age_max = metadata.get("target_age_max", 18)
                activity_type = metadata.get("activity_type", "Theory")
                chapter_title = metadata.get("chapter_title")
                page_label = metadata.get("page_label")

                # Create KnowledgeItem
                item = KnowledgeItem(
                    content=content.strip(),
                    source_book=source,
                    chapter_title=chapter_title,
                    page_label=page_label,
                    topics=topics,
                    brain_regions=brain_regions,
                    benefits=benefits,
                    risk_level="Low",
                    target_age_min=target_age_min,
                    target_age_max=target_age_max,
                    activity_type=activity_type,
                    relevance_score=float(score),
                )
                results.append(item)

            if not results:
                logger.warning("No results found in vector store.")

            # Save results to cache
            self._save_to_cache(cache_key, results)

            return results

        except Exception as e:
            logger.error(f"Error during retrieval: {e}")
            return []

    def _initialize_retrievers(self):
        """Initialize BM25, vector retrievers using config settings"""
        if not self.index:
            return

        rag_config = settings.rag_config["hybrid_retrieval"]
        
        # Get corpus size to adjust top_k values dynamically
        corpus_size = len(self.index.docstore.docs) if hasattr(self.index, 'docstore') else 0
        
        if corpus_size == 0:
            logger.warning("Index is empty. Skipping retriever initialization.")
            self.bm25_retriever = None
            self.vector_retriever = None
            return
        
        # Adjust top_k to never exceed corpus size (minimum 1)
        bm25_top_k = min(rag_config["bm25_top_k"], max(1, corpus_size))
        vector_top_k = min(rag_config["vector_top_k"], max(1, corpus_size))

        # Initialize BM25 retriever with Chinese tokenizer
        self.bm25_retriever = BM25Retriever.from_defaults(
            index=self.index, 
            similarity_top_k=bm25_top_k,
            tokenizer=jieba.lcut  # Use jieba for Chinese word segmentation
        )

        # Initialize vector retriever
        self.vector_retriever = self.index.as_retriever(
            similarity_top_k=vector_top_k
        )

        # We'll implement hybrid retrieval manually instead of relying on HybridRetriever
        self.bm25_weight = rag_config["bm25_weight"]
        self.vector_weight = rag_config["vector_weight"]
        self.merge_mode = rag_config["merge_mode"]

    def _clear_cache(self):
        """Clear all cached results, called when index is updated"""
        self.cache.clear()
        self.cache_timestamps.clear()
        logger.info("Cache cleared due to index update")

    def _get_cache_key(self, query: str, age: int, limit: int) -> Tuple[str, int, int]:
        """Generate a unique cache key for the query parameters"""
        return (query.strip().lower(), age, limit)

    def _get_from_cache(self, key: Tuple[str, int, int]) -> Any:
        """Retrieve result from cache if it exists and is not expired"""
        if not settings.rag_config["cache"]["enabled"]:
            return None

        if key in self.cache and key in self.cache_timestamps:
            timestamp = self.cache_timestamps[key]
            if time.time() - timestamp < settings.rag_config["cache"]["ttl_seconds"]:
                return self.cache[key]
            else:
                # Remove expired entry
                del self.cache[key]
                del self.cache_timestamps[key]
        return None

    def _save_to_cache(self, key: Tuple[str, int, int], value: Any):
        """Save result to cache with LRU eviction policy"""
        if not settings.rag_config["cache"]["enabled"]:
            return

        # Evict oldest entry if cache is full
        if len(self.cache) >= settings.rag_config["cache"]["max_size"]:
            oldest_key = min(
                self.cache_timestamps.keys(), key=lambda k: self.cache_timestamps[k]
            )
            del self.cache[oldest_key]
            del self.cache_timestamps[oldest_key]

        self.cache[key] = value
        self.cache_timestamps[key] = time.time()

    async def _expand_synonyms(self, query: str) -> str:
        """使用LLM生成领域同义词扩展查询以提高召回率"""
        if not self.dashscope_available:
            return query
            
        try:
            # 使用轻量模型生成同义词
            llm = DashScope(
                model=settings.llm_models["query_rewrite"],
                api_key=settings.dashscope_api_key,
            )
            
            prompt = SYNONYM_EXPANSION_PROMPT.format(query=query)
            response = await llm.acomplete(prompt)
            synonyms = response.text.strip()
            logger.info(f"Query expanded with LLM synonyms: '{query}' -> '{synonyms}'")
            return synonyms
        except Exception as e:
            logger.warning(f"Synonym expansion failed: {e}, using original query")
            return query

    async def _rewrite_query(self, query: str, age: int) -> str:
        """使用LLM重写用户查询以提高检索准确率"""
        if (
            not settings.rag_config["query_rewrite"]["enabled"]
            or not self.dashscope_available
        ):
            return query

        try:
            # 查询重写使用qwen-turbo模型，速度优先
            llm = DashScope(
                model=settings.llm_models["query_rewrite"],
                api_key=settings.dashscope_api_key,
            )
            prompt = QUERY_REWRITE_PROMPT.format(query=query, age=age)
            response = await llm.acomplete(prompt)
            rewritten_query = response.text.strip()
            logger.info(f"Query rewritten: '{query}' -> '{rewritten_query}'")
            return rewritten_query if rewritten_query else query
        except Exception as e:
            logger.warning(f"Query rewrite failed: {e}, using original query")
            return query

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of a file."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    async def ingest_book(self, file_path: str, original_filename: str = None, progress_callback=None):
        """
        Process book file and build index with semantic metadata.
        progress_callback: 进度回调函数，接收(stage: str, progress: float, message: str)参数
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Ingesting book: {file_path}")

        # Use original filename if provided, otherwise fallback to basename
        file_name = original_filename if original_filename else os.path.basename(file_path)

        # 1. Deduplication check
        file_hash = self._calculate_file_hash(file_path)
        if document_manager.exists(file_hash):
            logger.warning(
                f"Document {file_path} already exists (hash: {file_hash}). Skipping ingestion."
            )
            return

        try:
            # 获取PDF实际总页数（用于显示，不管解析结果）
            actual_total_pages = None
            if file_path.lower().endswith('.pdf'):
                import fitz
                with fitz.open(file_path) as pdf_doc:
                    actual_total_pages = len(pdf_doc)
            
            # 2. Parse Document
            parser_cls = get_parser(file_path)
            documents = parser_cls.parse(file_path)
            
            # 检查PDF提取质量：如果是PDF且提取率低于50%或平均每页文本长度过短，自动触发VL解析
            extracted_pages = len(documents)
            avg_text_length = 0
            
            if parser_cls == PDFParser and documents:
                # 获取PDF总页数
                total_pages = documents[0].metadata.get("total_pages", extracted_pages)
                # 计算平均文本长度
                total_text_length = sum(len(doc.text) for doc in documents)
                avg_text_length = total_text_length / extracted_pages if extracted_pages > 0 else 0
                
                # 判断是否为扫描版PDF：提取率低于阈值 或 平均每页文本长度低于阈值
                extraction_rate = extracted_pages / total_pages if total_pages > 0 else 0
                is_scanned_pdf = extraction_rate < settings.rag_ocr_extraction_rate_threshold or avg_text_length < settings.rag_ocr_min_avg_length_threshold
                
                if is_scanned_pdf:
                    logger.warning(
                        f"PDF extraction rate low ({extraction_rate:.0%}, avg length {avg_text_length:.0f}). "
                        f"Trying VL parsing for scanned PDF..."
                    )
                    try:
                        vl_documents = PDFVLParser.parse(file_path)
                        if vl_documents:
                            documents = vl_documents
                            logger.info(f"VL parsing succeeded, extracted {len(documents)} pages")
                        else:
                            logger.warning("VL parsing returned empty results, keeping original extraction")
                    except Exception as e:
                        logger.error(f"VL Parsing failed: {str(e)}")
                        # Keep the original documents if VL fails

            if not documents:
                raise ValueError(
                    "无法从文件中提取文本。该文件可能是扫描版PDF或空文件，且无法使用VL模型识别。"
                )

            logger.info(f"Parsed {len(documents)} document chunks/pages.")
            
            # 计算章节数（仅对有结构的文档：EPUB或带书签的PDF）
            chapter_count = None
            is_epub = file_path.lower().endswith('.epub')
            is_pdf_with_bookmarks = file_path.lower().endswith('.pdf') and documents and 'toc_level' in documents[0].metadata
            if is_epub or is_pdf_with_bookmarks:
                chapter_count = len(documents)
                logger.info(f"Document has {chapter_count} chapters")
            
            # 解析完成，更新进度
            if progress_callback:
                progress_msg = f"文件解析完成，共{chapter_count}章" if chapter_count else f"文件解析完成，共{len(documents)}页"
                progress_callback("chunking", 30.0, f"{progress_msg}，正在分块处理")

            # Update documents with correct filename and clean content
            cleaned_documents = []
            for doc in documents:
                # Clean up extra newlines and whitespace
                cleaned_text = re.sub(r'\n\s*\n', '\n\n', doc.text)  # Remove multiple blank lines
                cleaned_text = re.sub(r' +', ' ', cleaned_text)  # Remove multiple spaces
                cleaned_text = cleaned_text.strip()
                
                # Create new document with cleaned text (Document.text is read-only)
                new_doc = Document(
                    text=cleaned_text,
                    metadata=doc.metadata.copy()
                )
                
                new_doc.metadata["file_name"] = file_name
                # Ensure page_label is present
                if "page_label" not in new_doc.metadata:
                    new_doc.metadata["page_label"] = new_doc.metadata.get("chapter_title", "Unknown")
                
                cleaned_documents.append(new_doc)
            
            # Replace original documents with cleaned ones
            documents = cleaned_documents

            # 3. Semantic Chunking & Metadata Extraction
            # Determine if file is EPUB or PDF with bookmarks to use chapter-based chunking
            is_epub = file_path.lower().endswith('.epub')
            is_pdf_with_bookmarks = file_path.lower().endswith('.pdf') and documents and 'toc_level' in documents[0].metadata
            
            if is_epub or is_pdf_with_bookmarks:
                # For EPUB and bookmarked PDF, split by chapter first, then split into paragraph-based chunks
                file_type = "EPUB" if is_epub else "PDF with bookmarks"
                logger.info(f"Using chapter + paragraph based chunking for {file_type} file")
                all_nodes = []
                extraction_tasks = []
                semaphore = asyncio.Semaphore(settings.rag_metadata_extraction_concurrency)  # 从配置中读取并发数
                
                async def process_node(node, file_hash):
                    async with semaphore:
                        # Extract semantic metadata using LLM
                        extracted_meta = await MetadataExtractor.extract(node.get_content())
                        # Merge metadata
                        node.metadata.update(extracted_meta.model_dump())
                        node.metadata["content"] = (
                            node.get_content()
                        )  # Store original content
                        node.metadata["file_hash"] = file_hash
                        return node

                # Process each chapter, split into paragraph chunks
                for doc in documents:
                    chapter_title = doc.metadata.get("chapter_title", "")
                    page_label = doc.metadata.get("page_label", "")
                    
                    # Split chapter into paragraphs
                    paragraphs = [p.strip() for p in doc.text.split("\n\n") if p.strip()]
                    
                    # Merge short paragraphs into chunks (2-3 paragraphs per chunk, ~500-1000 chars)
                    current_chunk = ""
                    for para in paragraphs:
                        if len(current_chunk) + len(para) < settings.rag_epub_chunk_target_size:  # Target ~800 chars per chunk
                            current_chunk += para + "\n\n"
                        else:
                            if current_chunk:
                                # Create new document for this chunk
                                chunk_doc = Document(
                                    text=current_chunk.strip(),
                                    metadata=doc.metadata.copy()
                                )
                                chunk_doc.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
                                    node_id=file_hash
                                )
                                extraction_tasks.append(process_node(chunk_doc, file_hash))
                            current_chunk = para + "\n\n"
                    
                    # Add the last chunk
                    if current_chunk:
                        chunk_doc = Document(
                            text=current_chunk.strip(),
                            metadata=doc.metadata.copy()
                        )
                        chunk_doc.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
                            node_id=file_hash
                        )
                        extraction_tasks.append(process_node(chunk_doc, file_hash))
                
                logger.info(f"Split {len(documents)} chapters into {len(extraction_tasks)} paragraph chunks")
            else:
                # For other formats (PDF), use regular chunking
                splitter = SentenceSplitter(chunk_size=settings.rag_pdf_chunk_size, chunk_overlap=settings.rag_chunk_overlap)  # Increased chunk size to reduce total chunks
                all_nodes = []
                extraction_tasks = []
                semaphore = asyncio.Semaphore(settings.rag_metadata_extraction_concurrency)  # 从配置中读取并发数
                
                async def process_node(node, file_hash):
                    async with semaphore:
                        # Extract semantic metadata using LLM
                        extracted_meta = await MetadataExtractor.extract(node.get_content())
                        # Merge metadata
                        node.metadata.update(extracted_meta.model_dump())
                        node.metadata["content"] = (
                            node.get_content()
                        )  # Store original content
                        node.metadata["file_hash"] = file_hash
                        return node

                # Pre-split all documents into chunks first to get total count
                all_chunks = []
                for i, doc in enumerate(documents):
                    # Split large pages/chapters into smaller nodes
                    # Note: get_nodes_from_documents expects a list
                    nodes = splitter.get_nodes_from_documents([doc])
                    logger.info(f"Processing document {i+1}/{len(documents)}, generated {len(nodes)} chunks")
                    all_chunks.extend(nodes)

                # Set common ref_doc_id for all chunks
                for node in all_chunks:
                    node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(
                        node_id=file_hash
                    )
                    # Add extraction task to queue
                    extraction_tasks.append(process_node(node, file_hash))

            # Create pending document record with processing status
            pending_doc = DocumentRecord(
                file_hash=file_hash,
                file_name=file_name,
                ref_doc_ids=[file_hash],  # Use file_hash as the common ref_doc_id
                metadata=DocumentMetadata(
                    title=file_name, 
                    total_pages=actual_total_pages if actual_total_pages is not None else len(documents)
                ),
                status="processing",
                progress=0.0
            )
            document_manager.add_document(pending_doc)

            # Run all extraction tasks concurrently
            total_chunks = len(extraction_tasks)
            logger.info(f"Starting concurrent metadata extraction for {total_chunks} chunks...")
            
            processed_count = 0
            # Add progress tracking wrapper
            async def track_progress(task, idx):
                nonlocal processed_count
                result = await task
                processed_count += 1
                # Update progress every 5 chunks
                if processed_count % 5 == 0 or processed_count == total_chunks:
                    extraction_progress = (processed_count / total_chunks) * 60  # 元数据提取占60%进度（30%到90%）
                    overall_progress = 30.0 + extraction_progress
                    pending_doc.progress = overall_progress
                    document_manager.add_document(pending_doc)  # Update progress
                    
                    # 回调更新前端进度
                    if progress_callback:
                        progress_callback(
                            "embedding", 
                            overall_progress, 
                            f"正在提取元数据和生成向量：{processed_count}/{total_chunks} 个块"
                        )
                    
                    logger.info(f"Extraction progress: {extraction_progress:.1f}% ({processed_count}/{total_chunks} chunks)")
                return result
            
            # Wrap tasks with progress tracking
            tracked_tasks = [track_progress(task, i+1) for i, task in enumerate(extraction_tasks)]
            
            all_nodes = await asyncio.gather(*tracked_tasks)
            logger.info(f"Completed metadata extraction for all {len(all_nodes)} chunks.")
            
            # 元数据提取完成，更新进度
            if progress_callback:
                progress_callback("indexing", 90.0, "向量生成完成，正在构建索引")

            # 4. Indexing
            if self.index:
                # Incrementally insert new nodes
                self.index.insert_nodes(all_nodes)
                self.index.storage_context.persist(persist_dir=STORAGE_DIR)
                # Re-initialize retrievers to use updated index
                self._initialize_retrievers()
                # Clear cache since index has changed
                self._clear_cache()
            else:
                # Create new index for first time
                self.index = VectorStoreIndex(all_nodes)
                self.index.storage_context.persist(persist_dir=STORAGE_DIR)
                # 初始化检索器
                self._initialize_retrievers()

            # 5. Register in Document Manager as indexed
            # file_name is already defined at the start of the function
            doc_record = DocumentRecord(
                file_hash=file_hash,
                file_name=file_name,
                ref_doc_ids=[file_hash],  # Use file_hash as the common ref_doc_id
                metadata=DocumentMetadata(
                    title=file_name, 
                    total_pages=actual_total_pages if actual_total_pages is not None else len(documents),
                    chapter_count=chapter_count
                ),
                status="indexed",
                progress=100.0
            )
            document_manager.add_document(doc_record)

            logger.info(f"Successfully ingested {file_path}")

        except Exception as e:
            logger.error(f"Failed to ingest book: {e}")
            # Update document status to failed
            try:
                failed_doc = DocumentRecord(
                    file_hash=file_hash,
                    file_name=file_name,
                    ref_doc_ids=[file_hash],
                    metadata=DocumentMetadata(
                        title=file_name, 
                        total_pages=actual_total_pages if 'actual_total_pages' in locals() else 0
                    ),
                    status="failed",
                    progress=0.0
                )
                document_manager.add_document(failed_doc)
            except:
                pass
            raise

    def delete_document(self, file_name: str) -> bool:
        """Delete a document by file name."""
        if not self.index:
            logger.warning("Index not initialized.")
            return False

        doc = document_manager.get_document_by_name(file_name)
        if not doc:
            logger.warning(f"Document {file_name} not found in registry.")
            return False

        logger.info(f"Deleting document: {file_name} (hash: {doc.file_hash})")

        try:
            # Delete from index using ref_doc_ids
            for ref_id in doc.ref_doc_ids:
                self.index.delete_ref_doc(ref_id, delete_from_docstore=True)

            self.index.storage_context.persist(persist_dir=STORAGE_DIR)
            # Re-initialize retrievers to use updated index
            self._initialize_retrievers()
            # Clear cache since index has changed
            self._clear_cache()
            document_manager.delete_document(doc.file_hash)
            
            # 如果是最后一个文档，清空整个索引
            remaining_docs = document_manager.list_documents()
            if not remaining_docs:
                logger.info("All documents deleted, clearing entire index")
                # 清空索引对象
                self.index = None
                self.bm25_retriever = None
                self.vector_retriever = None
                # 删除存储目录下的所有文件
                import shutil
                if os.path.exists(STORAGE_DIR):
                    shutil.rmtree(STORAGE_DIR)
                    os.makedirs(STORAGE_DIR, exist_ok=True)
                logger.info("Index and storage cleared completely")
            
            logger.info(f"Successfully deleted {file_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False

    async def search_content(self, query: str, limit: int = 20) -> List[dict]:
        """
        搜索知识库内容，返回匹配的片段和元数据
        """
        if not self.index:
            logger.warning("Index not available, returning empty results.")
            return []

        try:
            # Expand synonyms to improve recall
            expanded_query = await self._expand_synonyms(query)
            
            # 同时使用BM25和向量检索获取更全面的结果
            if self.bm25_retriever and self.vector_retriever:
                # 并行执行两种检索
                bm25_nodes = await self.bm25_retriever.aretrieve(expanded_query)
                vector_nodes = await self.vector_retriever.aretrieve(expanded_query)

                # Normalize BM25 scores (map to 0-1 range)
                max_bm25 = 0.0
                if bm25_nodes:
                    max_bm25 = max(n.score for n in bm25_nodes) if bm25_nodes[0].score else 1.0
                    if max_bm25 > 0:
                        for n in bm25_nodes:
                            n.score = (n.score or 0.0) / max_bm25

                # 合并结果，使用加权融合 (Weighted Reciprocal Rank-like Fusion)
                node_map = {}
                # Balanced weights for better precision
                bm25_weight = settings.rag_search_bm25_weight
                vector_weight = settings.rag_search_vector_weight

                # 如果没有精确匹配 (max_bm25 == 0)，则惩罚向量检索的分数
                # 这有助于过滤掉仅有弱语义相关性的结果（例如搜"足球"出"积木"）
                vector_penalty = 1.0
                if max_bm25 == 0.0:
                    vector_penalty = settings.rag_search_no_match_vector_penalty  # 当没有关键词匹配时，大幅降低向量检索结果的权重

                for node in bm25_nodes:
                    node_id = node.node.node_id
                    node.score = (node.score or 0.0) * bm25_weight
                    node_map[node_id] = node

                for node in vector_nodes:
                    node_id = node.node.node_id
                    # Vector scores are usually 0.6-0.9, normalize them slightly if they are all very high
                    v_score = node.score or 0.0
                    weighted_score = v_score * vector_weight * vector_penalty
                    
                    if node_id in node_map:
                        node_map[node_id].score += weighted_score
                    else:
                        node.score = weighted_score
                        node_map[node_id] = node

                # Re-sort and take results
                nodes = sorted(
                    node_map.values(), key=lambda x: x.score or 0.0, reverse=True
                )[:limit]
            else:
                # 回退到单一向量检索，动态调整top_k避免超过语料库大小
                corpus_size = len(self.index.docstore.docs) if hasattr(self.index, 'docstore') else 0
                adjusted_limit = min(limit, max(1, corpus_size))
                retriever = self.index.as_retriever(similarity_top_k=adjusted_limit)
                nodes = await retriever.aretrieve(expanded_query)

            # Determine threshold based on retrieval mode
            # If hybrid, scores are weighted. Base threshold needs to be higher to filter noise.
            is_hybrid = self.bm25_retriever is not None and self.vector_retriever is not None
            threshold = settings.rag_search_score_threshold_hybrid if is_hybrid else settings.rag_search_score_threshold_vector  # Lower threshold to catch more results
            logger.debug(f"Search threshold: {threshold}, is_hybrid: {is_hybrid}, retrieved nodes: {len(nodes)}")
            
            if nodes:
                logger.debug(f"Top result score: {nodes[0].score or 0.0}")
                # Log all node scores for debugging
                for i, node in enumerate(nodes[:5]):  # Log top 5 scores
                    logger.debug(f"Node {i} score: {node.score or 0.0}, content: {node.node.get_content()[:100]}...")

            results = []
            
            # Dynamic Cutoff: If the top result is weak, drop everything.
            if nodes and (nodes[0].score or 0.0) < threshold:
                 # If top result is below threshold, return empty immediately
                 logger.debug(f"Top result score {nodes[0].score or 0.0} below threshold {threshold}, returning empty")
                 return []
                 
            # Relative Score Cutoff: Drop results that are much worse than the top result
            top_score = nodes[0].score or 0.0 if nodes else 0.0
            relative_cutoff = top_score * settings.rag_search_relative_cutoff_ratio

            # 不再按最高分归一化，避免低相关性的内容被错误显示为100%相似
            # 直接使用原始分数，范围0-1，对应0-100%
            score_scale = 1.0
            
            # 关键词匹配检查：查询词及其同义词必须出现在内容中才返回
            # 避免搜索"足球"却返回完全不相关的儿童实验内容，同时支持同义词和中英文匹配
            original_query_keywords = set(jieba.lcut(query.lower()))
            # 加入同义词扩展后的关键词
            expanded_keywords = set(jieba.lcut(expanded_query.lower()))
            all_keywords = original_query_keywords.union(expanded_keywords)
            # 移除停用词和单个字符
            stop_words = {"的", "了", "是", "我", "你", "他", "我们", "你们", "他们", "什么", "怎么", "如何", "为什么", "吗", "呢"}
            original_query_keywords = {kw for kw in original_query_keywords if len(kw) > 1 and kw not in stop_words}
            all_keywords = {kw for kw in all_keywords if len(kw) > 1 and kw not in stop_words}

            for node_with_score in nodes:
                node = node_with_score.node
                metadata = node.metadata or {}
                content = node.get_content()
                
                logger.debug(f"Node score: {node_with_score.score or 0.0}, content length: {len(content)}")
                
                # 过滤掉PDF元信息、参考文献等无效内容
                if not content or content.startswith("[General Information]") or "书名=" in content or "SS号=" in content or "参考文献" in content or "Reference" in content or "Bibliography" in content:
                    logger.debug(f"Filter out invalid metadata/content: {content[:100]}...")
                    continue
                    
                # 最低相似度阈值过滤，只返回大于阈值的结果
                raw_score = float(node_with_score.score or 0.0)
                # Apply both absolute threshold and relative cutoff
                if raw_score < threshold or raw_score < relative_cutoff:
                    logger.debug(f"Node score {raw_score} below threshold {threshold} or relative cutoff {relative_cutoff}, skipping")
                    continue
                
                # 关键词匹配检查：必须内容包含至少一个查询关键词，避免同义词扩展导致的不相关结果
                if all_keywords:
                    content_lower = content.lower()
                    has_keyword = any(kw in content_lower for kw in all_keywords)
                    if not has_keyword:
                        logger.debug(f"Content has no matching keywords for query '{query}', skipping")
                        continue
                
                # 关键词权重加成：原始查询词的匹配给予额外分数，提高精确匹配的相关性
                keyword_bonus = 0.0
                if original_query_keywords:
                    content_lower = content.lower()
                    # 计算匹配的原始关键词比例
                    matched_original = sum(1 for kw in original_query_keywords if kw in content_lower)
                    original_match_ratio = matched_original / len(original_query_keywords) if original_query_keywords else 0
                    # 原始关键词完全匹配额外加0.2分，部分匹配按比例加成
                    keyword_bonus = original_match_ratio * 0.2
                    logger.debug(f"Original keyword match ratio: {original_match_ratio:.2f}, bonus: {keyword_bonus:.2f}")
                
                # Scale score to 0-1 range for display, top result will be 1.0 (100%)
                score = min(raw_score * score_scale + keyword_bonus, 1.0)

                # Get correct filename from document manager if possible
                file_hash = metadata.get("file_hash")
                source_book = metadata.get("file_name", "Unknown Source")
                if file_hash:
                    doc = document_manager.get_document(file_hash)
                    if doc:
                        source_book = doc.file_name

                # Clean page label for better display
                page_label = metadata.get("page_label")
                if page_label:
                    if "index_split" in str(page_label) or ".html" in str(page_label):
                        page_label = metadata.get("chapter_title") or "Section"
                    elif len(str(page_label)) > 10 and not str(page_label).isdigit():
                        # If page label is too long and not a number (e.g. "尾声"), treat as chapter
                        page_label = f"章节: {page_label}"
                    elif str(page_label).isdigit():
                         # Standard numeric page
                         pass
                    else:
                        # Short text label (e.g. "IV", "Intro")
                        pass

                results.append(
                    {
                        "id": node.node_id,
                        "content": content,
                        "score": score,
                        "source_book": source_book,
                        "chapter_title": metadata.get("chapter_title"),
                        "page_label": page_label,
                        "target_age_min": metadata.get("target_age_min", 0),
                        "target_age_max": metadata.get("target_age_max", 18),
                        "brain_regions": metadata.get("brain_regions", []),
                        "topics": metadata.get("topics", []),
                        "file_hash": metadata.get("file_hash"),
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Error during content search: {e}")
            return []


# 单例实例
rag_service = RagService()
