import asyncio
import sys
import os
# Add backend to path so 'src' can be imported
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, backend_dir)

from src.service.document_manager import document_manager
from src.service.index_manager_service import IndexManagerService
from src.config.settings import settings


def debug_storage():
    print("=" * 80)
    print("存储和文档管理调试")
    print("=" * 80)
    
    # 1. 检查文档管理器
    print("\n1. 文档管理器中的文档:")
    docs = document_manager.list_documents()
    print(f"   总文档数: {len(docs)}")
    for doc in docs:
        print(f"   - {doc.file_name}: status={doc.status}, hash={doc.file_hash[:8]}...")
        if hasattr(doc, 'ref_doc_ids') and doc.ref_doc_ids:
            print(f"     ref_doc_ids: {len(doc.ref_doc_ids)} 个")
    
    # 2. 检查存储目录
    storage_dir = settings.rag_storage_dir
    print(f"\n2. 存储目录: {storage_dir}")
    if os.path.exists(storage_dir):
        print("   存储目录存在")
        
        # 检查 index 目录
        index_dir = os.path.join(storage_dir, "index")
        if os.path.exists(index_dir):
            print(f"   Index 目录存在: {index_dir}")
            # 列出文件
            files = os.listdir(index_dir)
            print(f"   Index 文件: {files}")
            
            # 检查 docstore.json
            docstore_path = os.path.join(index_dir, "docstore.json")
            if os.path.exists(docstore_path):
                import json
                with open(docstore_path, 'r', encoding='utf-8') as f:
                    docstore_data = json.load(f)
                docs_in_docstore = docstore_data.get('docs', {})
                print(f"   docstore.json 中的文档数: {len(docs_in_docstore)}")
                if docs_in_docstore:
                    # 显示第一个文档
                    first_id = list(docs_in_docstore.keys())[0]
                    first_doc = docs_in_docstore[first_id]
                    print(f"   第一个文档示例:")
                    print(f"     - ID: {first_id}")
                    print(f"     - 文件名: {first_doc.get('metadata', {}).get('file_name', 'Unknown')}")
                    print(f"     - 内容长度: {len(first_doc.get('text', ''))}")
            else:
                print("   docstore.json 不存在！")
        else:
            print("   Index 目录不存在！")
    else:
        print("   存储目录不存在！")
    
    # 3. 检查 Chroma 持久化目录
    if hasattr(settings, 'vector_store_config'):
        chroma_path = settings.vector_store_config.get('persist_directory')
        if chroma_path:
            print(f"\n3. Chroma 持久化目录: {chroma_path}")
            if os.path.exists(chroma_path):
                print("   Chroma 目录存在")
                files = os.listdir(chroma_path)
                print(f"   Chroma 文件: {files[:10]}...")
            else:
                print("   Chroma 目录不存在！")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    debug_storage()
