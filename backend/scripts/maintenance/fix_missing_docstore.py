import sys
import os
import json
import hashlib
# Add backend to path so 'src' can be imported
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, backend_dir)

from src.config.settings import settings
from src.model.document import DocumentRecord, DocumentMetadata
from src.service.document_manager import document_manager
from llama_index.core.schema import Document
import chromadb


def rebuild_docstore_and_docs():
    print("=" * 80)
    print("修复docstore和文档管理器")
    print("=" * 80)
    
    # 1. 连接Chroma获取所有数据（使用正确的路径，包含PDF数据）
    # persist_dir = settings.vector_store_config.get("persist_dir")
    persist_dir = "./chroma_data"  # 这个才是有数据的目录
    collection_name = settings.vector_store_config.get("collection_name")
    
    print(f"\n1. 连接Chroma: {persist_dir}, 集合: {collection_name}")
    db = chromadb.PersistentClient(path=persist_dir)
    collection = db.get_collection(collection_name)
    total = collection.count()
    print(f"   ✅ 找到 {total} 个文档")
    
    if total == 0:
        print("   ❌ Chroma为空，无法修复")
        return
    
    # 2. 获取所有文档
    print(f"\n2. 读取所有文档...")
    all_docs = collection.get(include=["metadatas", "documents"])
    
    # 3. 按文件分组
    files = {}
    for doc_id, doc_text, metadata in zip(all_docs['ids'], all_docs['documents'], all_docs['metadatas']):
        file_hash = metadata.get('file_hash')
        if not file_hash:
            continue
            
        if file_hash not in files:
            files[file_hash] = {
                'file_name': metadata.get('file_name', 'Unknown'),
                'total_pages': metadata.get('total_pages', 0),
                'chunks': []
            }
        
        # 重建Document对象
        doc = Document(
            id_=doc_id,
            text=doc_text,
            metadata=metadata
        )
        files[file_hash]['chunks'].append(doc)
    
    print(f"   ✅ 共找到 {len(files)} 个文件")
    for file_hash, info in files.items():
        print(f"   - {info['file_name']}: {len(info['chunks'])} 个分块")
    
    # 4. 重建文档管理器记录
    print(f"\n3. 重建文档管理器记录...")
    current_docs = {d.file_hash: d for d in document_manager.list_documents()}
    
    for file_hash, info in files.items():
        if file_hash not in current_docs:
            # 创建新的文档记录
            doc_record = DocumentRecord(
                file_hash=file_hash,
                file_name=info['file_name'],
                ref_doc_ids=[file_hash],
                metadata=DocumentMetadata(
                    title=info['file_name'],
                    total_pages=info['total_pages'],
                    chapter_count=len(info['chunks'])
                ),
                status="indexed",
                progress=100.0,
                upload_date=datetime.now().isoformat()
            )
            document_manager.add_document(doc_record)
            print(f"   ✅ 添加缺失的文档记录: {info['file_name']}")
        else:
            print(f"   ℹ️ 文档已存在: {info['file_name']}")
    
    # 5. 重建docstore.json
    print(f"\n4. 重建docstore.json...")
    index_dir = os.path.join(settings.rag_storage_dir, "index")
    docstore_path = os.path.join(index_dir, "docstore.json")
    
    docstore_data = {
        "docs": {}
    }
    
    for file_hash, info in files.items():
        for doc in info['chunks']:
            docstore_data["docs"][doc.id_] = {
                "id": doc.id_,
                "text": doc.text,
                "metadata": doc.metadata,
                "start_char_idx": getattr(doc, 'start_char_idx', 0),
                "end_char_idx": getattr(doc, 'end_char_idx', len(doc.text)),
                "relationships": {}
            }
    
    # 写入docstore.json
    with open(docstore_path, 'w', encoding='utf-8') as f:
        json.dump(docstore_data, f, ensure_ascii=False, indent=2)
    
    print(f"   ✅ docstore.json 重建完成，包含 {len(docstore_data['docs'])} 个文档")
    
    # 6. 清理旧的索引加载缓存
    print(f"\n5. 修复完成！请重启服务以加载新的索引。")
    print(f"   重启后检索服务会重新初始化，就能搜到PDF内容了。")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    from datetime import datetime
    rebuild_docstore_and_docs()
