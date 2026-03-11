import os
import hashlib
from typing import List
from src.model.schemas import KnowledgeItem, RiskLevel
from src.model.document import DocumentRecord, DocumentMetadata
from src.service.document_manager import document_manager
from src.core.parsers import get_parser
from src.core.metadata_extractor import MetadataExtractor
from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.vector_stores import MetadataFilter, MetadataFilters, FilterOperator
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
from src.core.prompts import MOCK_KNOWLEDGE_ITEMS

# Define paths
STORAGE_DIR = "./storage"

class RagService:
    def __init__(self):
        self.index = None
        self._initialize_index()

    def _initialize_index(self):
        """Initialize the vector index from storage or build it from books."""
        if not os.path.exists(STORAGE_DIR):
            os.makedirs(STORAGE_DIR)
            
        try:
            # Check if index exists in storage
            if os.path.exists(os.path.join(STORAGE_DIR, "docstore.json")):
                print("Loading index from storage...")
                storage_context = StorageContext.from_defaults(persist_dir=STORAGE_DIR)
                self.index = load_index_from_storage(storage_context)
                print("Index loaded successfully.")
            else:
                print("No existing index found. Waiting for file uploads.")
                self.index = None
        except Exception as e:
            print(f"Failed to load index from storage: {e}")
            self.index = None

    async def retrieve_knowledge(self, query: str, age: int, limit: int = 3) -> List[KnowledgeItem]:
        """
        根据查询和年龄检索相关知识点
        """
        print(f"Retrieving knowledge for query: '{query}', age: {age}")
        
        if not self.index:
            print("Index not available, returning mock data.")
            return self._get_mock_knowledge(query, age, limit)
        
        try:
            # Create filters
            filters = []
            if age > 0:
                # Range filtering: target_age_min <= age AND target_age_max >= age
                filters.append(MetadataFilter(key="target_age_min", value=age, operator=FilterOperator.LTE))
                filters.append(MetadataFilter(key="target_age_max", value=age, operator=FilterOperator.GTE))
            
            metadata_filters = MetadataFilters(filters=filters) if filters else None
            
            # Create retriever with filters
            retriever = self.index.as_retriever(
                similarity_top_k=limit,
                filters=metadata_filters
            )
            nodes = await retriever.aretrieve(query)
            
            results = []
            for node_with_score in nodes:
                node = node_with_score.node
                # Fallback to get_content if 'content' metadata is missing
                content = node.metadata.get("content", node.get_content())
                metadata = node.metadata or {}
                source = metadata.get("file_name", "Unknown Source")
                score = node_with_score.score or 0.0
                
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
                    relevance_score=float(score)
                )
                results.append(item)
            
            if not results:
                print("No results found in vector store, falling back to mock.")
                return self._get_mock_knowledge(query, age, limit)
                
            return results
            
        except Exception as e:
            print(f"Error during retrieval: {e}")
            return self._get_mock_knowledge(query, age, limit)

    def _get_mock_knowledge(self, query: str, age: int, limit: int) -> List[KnowledgeItem]:
        # 使用 prompts.py 中定义的 Mock 数据
        mock_items = []
        for item_data in MOCK_KNOWLEDGE_ITEMS:
            # 动态调整年龄范围（如果需要）
            min_age = item_data["target_age_min"]
            max_age = item_data["target_age_max"]
            
            # 简单的动态替换逻辑
            content = item_data["content"]
            if "{age}" in content:
                content = content.replace("{age}", str(age))
                # 如果是模板数据，调整年龄范围适配当前查询
                if min_age < 0:
                    min_age = max(0, age - 1)
                    max_age = min(18, age + 2)
            
            mock_items.append(KnowledgeItem(
                content=content,
                source_book=item_data["source_book"],
                brain_regions=item_data["brain_regions"],
                benefits=item_data["benefits"],
                risk_level=item_data["risk_level"],
                target_age_min=min_age,
                target_age_max=max_age,
                relevance_score=item_data["relevance_score"]
            ))
        
        return mock_items[:limit]

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of a file."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    async def ingest_book(self, file_path: str):
        """
        Process book file and build index with semantic metadata.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        print(f"Ingesting book: {file_path}")
        
        # 1. Deduplication check
        file_hash = self._calculate_file_hash(file_path)
        if document_manager.exists(file_hash):
            print(f"Document {file_path} already exists (hash: {file_hash}). Skipping ingestion.")
            return

        try:
            # 2. Parse Document
            parser_cls = get_parser(file_path)
            documents = parser_cls.parse(file_path)
            
            print(f"Parsed {len(documents)} document chunks/pages.")
            
            # 3. Semantic Chunking & Metadata Extraction
            splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=20)
            all_nodes = []
            
            for doc in documents:
                # Split large pages/chapters into smaller nodes
                # Note: get_nodes_from_documents expects a list
                nodes = splitter.get_nodes_from_documents([doc])
                
                for node in nodes:
                    # Set common ref_doc_id for deletion
                    node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id=file_hash)
                    
                    # Extract semantic metadata using LLM
                    extracted_meta = await MetadataExtractor.extract(node.get_content())
                    
                    # Merge metadata
                    node.metadata.update(extracted_meta.model_dump())
                    node.metadata["content"] = node.get_content() # Store original content
                    node.metadata["file_hash"] = file_hash
                    
                    all_nodes.append(node)
            
            print(f"Generated {len(all_nodes)} semantic nodes.")

            # 4. Indexing
            if self.index:
                self.index.insert_nodes(all_nodes)
                self.index.storage_context.persist(persist_dir=STORAGE_DIR)
            else:
                self.index = VectorStoreIndex(all_nodes)
                self.index.storage_context.persist(persist_dir=STORAGE_DIR)
                
            # 5. Register in Document Manager
            file_name = os.path.basename(file_path)
            doc_record = DocumentRecord(
                file_hash=file_hash,
                file_name=file_name,
                ref_doc_ids=[file_hash], # Use file_hash as the common ref_doc_id
                metadata=DocumentMetadata(
                    title=file_name, 
                    total_pages=len(documents)
                )
            )
            document_manager.add_document(doc_record)
                
            print(f"Successfully ingested {file_path}")
            
        except Exception as e:
            print(f"Failed to ingest book: {e}")
            raise

    def delete_document(self, file_name: str) -> bool:
        """Delete a document by file name."""
        if not self.index:
            print("Index not initialized.")
            return False
            
        doc = document_manager.get_document_by_name(file_name)
        if not doc:
            print(f"Document {file_name} not found in registry.")
            return False
            
        print(f"Deleting document: {file_name} (hash: {doc.file_hash})")
        
        try:
            # Delete from index using ref_doc_ids
            for ref_id in doc.ref_doc_ids:
                self.index.delete_ref_doc(ref_id, delete_from_docstore=True)
            
            self.index.storage_context.persist(persist_dir=STORAGE_DIR)
            document_manager.delete_document(doc.file_hash)
            print(f"Successfully deleted {file_name}")
            return True
        except Exception as e:
            print(f"Failed to delete document: {e}")
            return False

# 单例实例
rag_service = RagService()
