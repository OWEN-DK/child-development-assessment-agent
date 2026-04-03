#!/usr/bin/env python3
"""
检查 Chroma 数据库中的数据结构
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_chroma_structure():
    print("=" * 80)
    print("检查 Chroma 数据库中的数据结构")
    print("=" * 80)
    
    try:
        import chromadb
        
        chroma_path = "./chroma_data"
        print(f"\n连接到 Chroma 数据库：{chroma_path}")
        db = chromadb.PersistentClient(path=chroma_path)
        
        # 获取集合
        collections = db.list_collections()
        print(f"\n集合数量：{len(collections)}")
        
        for collection in collections:
            print(f"\n集合名称：{collection.name}")
            print(f"  - 元数据：{collection.metadata}")
            count = collection.count()
            print(f"  - 文档数量：{count}")
            
            if count > 0:
                # 获取所有文档
                print(f"\n  获取所有文档:")
                results = collection.get(include=["metadatas", "documents", "embeddings"])
                
                for i, (doc_id, doc_text, metadata) in enumerate(zip(results['ids'], results['documents'], results['metadatas'])):
                    print(f"\n    文档 {i+1}:")
                    print(f"      - ID: {doc_id}")
                    print(f"      - 内容：{doc_text[:100]}...")
                    print(f"      - 元数据：{metadata}")
                    
                    if i >= 2:  # 只显示前 3 个
                        print(f"\n    ... (共 {count} 个文档，仅显示前 3 个)")
                        break
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_chroma_structure()
