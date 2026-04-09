import sys
import os
# Add backend to path so 'src' can be imported
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, backend_dir)

import chromadb


def check_chroma_content():
    print("=" * 80)
    print("检查Chroma内容")
    print("=" * 80)
    
    # 检查所有chroma数据库
    chroma_paths = [
        "./storage/vector_store",
        "./chroma_data",
        "./test_chroma"
    ]
    
    for path in chroma_paths:
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            continue
            
        print(f"\n\n检查: {abs_path}")
        try:
            db = chromadb.PersistentClient(path=abs_path)
            collections = db.list_collections()
            print(f"集合列表: {[c.name for c in collections]}")
            
            for coll in collections:
                collection = db.get_collection(coll.name)
                count = collection.count()
                print(f"\n集合 {coll.name} 有 {count} 个文档")
                
                if count > 0:
                    # 查看前几个文档的来源
                    sample = collection.peek(limit=10)
                    sources = set()
                    for meta in sample['metadatas']:
                        source = meta.get('file_name', 'Unknown')
                        sources.add(source)
                    print(f"来源文件: {sources}")
                    
                    # 检查有没有PDF
                    has_pdf = any('.pdf' in s.lower() for s in sources)
                    print(f"包含PDF: {'✅ 是' if has_pdf else '❌ 否'}")
                    
        except Exception as e:
            print(f"连接失败: {e}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    check_chroma_content()
