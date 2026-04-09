import asyncio
import sys
import os
# Add backend to path so 'src' can be imported
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, backend_dir)

from src.service.rag_service import rag_service


async def debug_index():
    print("=" * 80)
    print("索引状态调试")
    print("=" * 80)
    
    # 1. 检查索引是否可用
    index_available = rag_service.index_manager.is_index_available()
    print(f"\n1. 索引是否可用: {index_available}")
    
    if index_available:
        index = rag_service.index_manager.get_index()
        
        # 2. 检查 docstore
        if hasattr(index, 'docstore') and index.docstore:
            docstore_docs = index.docstore.docs
            print(f"\n2. Docstore 文档数量: {len(docstore_docs)}")
            
            if docstore_docs:
                # 统计文件类型
                pdf_count = 0
                epub_count = 0
                other_count = 0
                
                for doc_id, doc in docstore_docs.items():
                    file_name = doc.metadata.get("file_name", "")
                    if file_name.lower().endswith(".pdf"):
                        pdf_count += 1
                    elif file_name.lower().endswith(".epub"):
                        epub_count += 1
                    else:
                        other_count += 1
                
                print(f"   - PDF: {pdf_count}")
                print(f"   - EPUB: {epub_count}")
                print(f"   - 其他: {other_count}")
                
                # 显示前3个文档
                print(f"\n3. 前3个文档示例:")
                for i, (doc_id, doc) in enumerate(list(docstore_docs.items())[:3]):
                    print(f"\n   文档 {i+1}:")
                    print(f"   - ID: {doc_id}")
                    print(f"   - 文件名: {doc.metadata.get('file_name', 'Unknown')}")
                    print(f"   - 内容长度: {len(doc.text)}")
                    print(f"   - 内容预览: {doc.text[:100]}...")
            else:
                print("   Docstore 为空！")
        else:
            print("   索引没有 docstore 属性")
        
        # 3. 检查 corpus size
        corpus_size = rag_service.index_manager.get_corpus_size()
        print(f"\n4. Corpus size (get_corpus_size): {corpus_size}")
        
        # 4. 检查向量存储
        if hasattr(index, '_vector_store') and index._vector_store:
            vector_store = index._vector_store
            if hasattr(vector_store, '_collection') and vector_store._collection:
                collection_count = vector_store._collection.count()
                print(f"\n5. 向量存储中文档数量: {collection_count}")
            else:
                print("\n5. 向量存储没有 _collection 属性")
        else:
            print("\n5. 索引没有 _vector_store 属性")
        
        # 5. 检查检索器
        print(f"\n6. 检索器状态:")
        print(f"   - BM25 retriever: {rag_service.retrieval_service.bm25_retriever is not None}")
        print(f"   - Vector retriever: {rag_service.retrieval_service.vector_retriever is not None}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(debug_index())
