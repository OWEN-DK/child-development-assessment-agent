import os
from typing import List
from src.model.schemas import KnowledgeItem, RiskLevel
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage, Settings, Document
from llama_index.core.node_parser import SentenceSplitter
from src.core.prompts import MOCK_KNOWLEDGE_ITEMS

# Define paths
STORAGE_DIR = "./storage"
BOOK_DIR = "./book"

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
                # Do NOT automatically build index from directory
                # Index will be built when files are uploaded via API
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
            # Create retriever
            # similarity_top_k determines how many chunks to retrieve
            retriever = self.index.as_retriever(similarity_top_k=limit)
            nodes = await retriever.aretrieve(query)
            
            results = []
            for node_with_score in nodes:
                node = node_with_score.node
                content = node.get_content()
                metadata = node.metadata or {}
                source = metadata.get("file_name", "Unknown Source")
                score = node_with_score.score or 0.0
                
                # Simple heuristic/placeholder for structured fields
                # In a production system, we would use an LLM to extract these fields from the content
                brain_regions = [] 
                benefits = []
                
                # Create KnowledgeItem
                item = KnowledgeItem(
                    content=content.strip(),
                    source_book=source,
                    brain_regions=brain_regions,
                    benefits=benefits,
                    risk_level="Low", # Default risk level
                    target_age_min=max(0, age - 2), # Heuristic age range
                    target_age_max=min(18, age + 2), # Heuristic age range
                    relevance_score=float(score)
                )
                results.append(item)
            
            # If no results found (e.g. strict filtering), fall back or return empty
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

    async def ingest_book(self, file_path: str):
        """
        处理书籍文件并建立索引
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        print(f"Ingesting book: {file_path}")
        try:
            # Load documents
            documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
            
            # Configure node parser
            parser = SentenceSplitter(chunk_size=1024, chunk_overlap=20)
            nodes = parser.get_nodes_from_documents(documents)
            
            # Update or Create index
            if self.index:
                self.index.insert_nodes(nodes)
                self.index.storage_context.persist(persist_dir=STORAGE_DIR)
            else:
                self.index = VectorStoreIndex(nodes)
                self.index.storage_context.persist(persist_dir=STORAGE_DIR)
                
            print(f"Successfully ingested {file_path}")
        except Exception as e:
            print(f"Failed to ingest book: {e}")
            raise

# 单例实例
rag_service = RagService()
