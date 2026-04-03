#!/usr/bin/env python3
"""
调试脚本：检查分块数据
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.src.service.rag_service import rag_service
from backend.src.service.document_manager import document_manager

def main():
    print("=" * 80)
    print("分块调试诊断")
    print("=" * 80)
    
    # 1. 检查索引状态
    print("\n1. 索引状态检查:")
    print(f"   - 索引对象：{rag_service.index_manager.get_index()}")
    print(f"   - 索引是否存在：{rag_service.index_manager.is_index_available()}")
    
    if rag_service.index_manager.is_index_available():
        print(f"   - 索引类型：{type(rag_service.index_manager.get_index())}")
        print(f"   - 是否有 docstore: {hasattr(rag_service.index_manager.get_index(), 'docstore')}")
        
        if hasattr(rag_service.index_manager.get_index(), 'docstore'):
            docstore = rag_service.index_manager.get_index().docstore
            print(f"   - docstore 类型：{type(docstore)}")
            print(f"   - 文档总数：{len(docstore.docs) if hasattr(docstore, 'docs') else 'N/A'}")
            
            if hasattr(docstore, 'docs') and docstore.docs:
                print(f"\n   前 5 个文档的元数据:")
                for i, (doc_id, node) in enumerate(list(docstore.docs.items())[:5]):
                    print(f"\n   文档 {i+1}:")
                    print(f"     - ID: {doc_id}")
                    print(f"     - file_hash: {node.metadata.get('file_hash', 'N/A')}")
                    print(f"     - source_book: {node.metadata.get('source_book', 'N/A')}")
                    print(f"     - page_label: {node.metadata.get('page_label', 'N/A')}")
                    print(f"     - content 长度：{len(node.text)} 字符")
    
    # 2. 检查文档管理器
    print("\n2. 文档管理器检查:")
    docs = document_manager.list_documents()
    print(f"   - 已索引文档数：{len(docs)}")
    
    if docs:
        print(f"\n   文档列表:")
        for doc in docs:
            print(f"     - {doc.file_name} (hash: {doc.file_hash})")
    
    # 3. 测试获取分块
    print("\n3. 测试获取分块:")
    if docs:
        test_hash = docs[0].file_hash
        print(f"   使用第一个文档的 hash: {test_hash}")
        chunks = rag_service.get_document_chunks(test_hash)
        print(f"   - 返回分块数：{len(chunks)}")
        
        if chunks:
            print(f"\n   前 3 个分块:")
            for i, chunk in enumerate(chunks[:3]):
                print(f"\n   分块 {i+1}:")
                print(f"     - ID: {chunk['id']}")
                print(f"     - 内容长度：{len(chunk['content'])} 字符")
                print(f"     - metadata: {chunk['metadata']}")
    else:
        print("   没有已索引的文档，无法测试")
    
    print("\n" + "=" * 80)
    print("诊断完成")
    print("=" * 80)

if __name__ == "__main__":
    main()
