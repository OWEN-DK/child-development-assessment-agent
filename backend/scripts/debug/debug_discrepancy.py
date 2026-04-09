import asyncio
import sys
import os
# Add backend to path so 'src' can be imported
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, backend_dir)

from src.service.rag_service import rag_service
from src.service.document_manager import document_manager
from src.config.settings import settings
import chromadb


async def debug_discrepancy():
    print("=" * 80)
    print("数据不一致问题调试")
    print("=" * 80)
    
    # 1. 检查文档管理器
    print("\n1. 文档列表:")
    docs = document_manager.list_documents()
    pdf_docs = [d for d in docs if d.file_name.lower().endswith('.pdf')]
    for doc in docs:
        print(f"   - {doc.file_name}, hash={doc.file_hash}, status={doc.status}")
    
    if not pdf_docs:
        print("\n❌ 没有找到PDF文档！")
        return
    
    pdf_doc = pdf_docs[0]
    print(f"\n2. 测试获取 {pdf_doc.file_name} 的分块:")
    chunks = rag_service.get_document_chunks(pdf_doc.file_hash, page=1, page_size=10)
    print(f"   ✅ 分块接口返回: {chunks['total']} 个分块")
    
    # 3. 检查索引管理器的状态
    print(f"\n3. 索引管理器状态:")
    print(f"   - 索引是否可用: {rag_service.index_manager.is_index_available()}")
    print(f"   - 语料库大小: {rag_service.index_manager.get_corpus_size()}")
    print(f"   - BM25检索器: {rag_service.retrieval_service.bm25_retriever is not None}")
    print(f"   - Vector检索器: {rag_service.retrieval_service.vector_retriever is not None}")
    
    # 4. 直接连接Chroma查看真实数据
    print(f"\n4. 直接连接Chroma检查:")
    persist_dir = settings.vector_store_config.get("persist_dir")
    collection_name = settings.vector_store_config.get("collection_name")
    
    db = chromadb.PersistentClient(path=persist_dir)
    collection = db.get_collection(collection_name)
    print(f"   - Chroma真实文档数: {collection.count()}")
    
    # 5. 检查索引内部的向量存储文档数
    if rag_service.index_manager.is_index_available():
        index = rag_service.index_manager.get_index()
        if hasattr(index, '_vector_store') and hasattr(index._vector_store, '_collection'):
            inner_count = index._vector_store._collection.count()
            print(f"   - 索引内部向量存储文档数: {inner_count}")
            
        if hasattr(index, 'docstore'):
            docstore_count = len(index.docstore.docs)
            print(f"   - 索引内部docstore文档数: {docstore_count}")
    
    # 6. 检查是否是因为docstore为空导致BM25检索器未初始化
    print(f"\n5. 问题分析:")
    if rag_service.retrieval_service.bm25_retriever is None:
        print("   ❌ BM25检索器未初始化，因为docstore为空！")
        print("   ✅ 向量检索器应该可以工作，但需要检查过滤条件")
    
    # 7. 测试直接使用向量检索器搜索
    print(f"\n6. 测试向量检索:")
    if rag_service.retrieval_service.vector_retriever:
        query = "行为"
        expanded_query = await rag_service.retrieval_service._expand_synonyms(query)
        vector_nodes = await rag_service.retrieval_service.vector_retriever.aretrieve(expanded_query)
        print(f"   - 搜索关键词 '{query}'，向量检索返回 {len(vector_nodes)} 个结果")
        if vector_nodes:
            for i, node in enumerate(vector_nodes[:3]):
                source = node.node.metadata.get("file_name", "Unknown")
                print(f"     {i+1}. {source}: {node.node.text[:80]}... (score: {node.score:.4f})")
    
    # 8. 测试搜索接口
    print(f"\n7. 测试完整搜索接口:")
    results = await rag_service.search_content("行为", limit=10)
    print(f"   - 搜索接口返回 {results['total']} 个结果")
    if results['results']:
        for i, res in enumerate(results['results'][:3]):
            print(f"     {i+1}. {res['source_book']}: {res['content'][:80]}... (score: {res['score']:.2f})")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(debug_discrepancy())
