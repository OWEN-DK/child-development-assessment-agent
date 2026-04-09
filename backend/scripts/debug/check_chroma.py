import sys
import os
# Add backend to path so 'src' can be imported
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, backend_dir)

from src.config.settings import settings
import chromadb


def check_chroma():
    print("=" * 80)
    print("Chroma 向量存储检查")
    print("=" * 80)
    
    persist_dir = settings.vector_store_config.get("persist_dir")
    collection_name = settings.vector_store_config.get("collection_name")
    
    print(f"\n1. 持久化目录: {persist_dir}")
    print(f"2. 集合名称: {collection_name}")
    
    # 检查目录是否存在
    if os.path.exists(persist_dir):
        print(f"   目录存在: ✓")
        files = os.listdir(persist_dir)
        print(f"   文件列表: {files}")
    else:
        print(f"   目录不存在: ✗")
        return
    
    # 连接 Chroma
    print(f"\n3. 连接 Chroma...")
    try:
        db = chromadb.PersistentClient(path=persist_dir)
        print("   连接成功 ✓")
        
        # 列出所有集合
        collections = db.list_collections()
        print(f"\n4. 集合列表: {[c.name for c in collections]}")
        
        # 检查目标集合
        if collection_name in [c.name for c in collections]:
            collection = db.get_collection(collection_name)
            count = collection.count()
            print(f"\n5. 集合 '{collection_name}' 中的文档数: {count}")
            
            if count > 0:
                # 获取一些样本
                sample = collection.peek(limit=3)
                print(f"\n6. 样本数据:")
                for i, (doc_id, doc, metadata) in enumerate(zip(sample['ids'], sample['documents'], sample['metadatas'])):
                    print(f"\n   样本 {i+1}:")
                    print(f"   - ID: {doc_id}")
                    print(f"   - 文件名: {metadata.get('file_name', 'Unknown')}")
                    print(f"   - 内容长度: {len(doc)}")
                    print(f"   - 内容预览: {doc[:100]}...")
            else:
                print("   集合为空！")
        else:
            print(f"\n5. 集合 '{collection_name}' 不存在！")
            
    except Exception as e:
        print(f"   连接失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    check_chroma()
