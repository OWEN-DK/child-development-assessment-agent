#!/usr/bin/env python3
"""
检查 Chroma 数据库中的分块数据
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_chroma_data():
    print("=" * 80)
    print("检查 Chroma 数据库中的分块数据")
    print("=" * 80)
    
    try:
        import chromadb
        from chromadb.config import Settings
        
        # 连接到 Chroma 数据库
        chroma_path = "./chroma_data"
        print(f"\n连接到 Chroma 数据库：{chroma_path}")
        db = chromadb.PersistentClient(path=chroma_path)
        
        # 获取所有集合
        collections = db.list_collections()
        print(f"\n找到的集合数量：{len(collections)}")
        
        for collection in collections:
            print(f"\n集合名称：{collection.name}")
            print(f"  - 元数据：{collection.metadata}")
            
            # 获取集合中的文档数量
            count = collection.count()
            print(f"  - 文档数量：{count}")
            
            if count > 0:
                # 获取前 5 个文档
                print(f"\n  前 5 个文档的元数据:")
                try:
                    results = collection.get(limit=5, include=["metadatas"])
                    for i, (doc_id, metadata) in enumerate(zip(results['ids'], results['metadatas'])):
                        print(f"\n    文档 {i+1}:")
                        print(f"      - ID: {doc_id}")
                        print(f"      - file_hash: {metadata.get('file_hash', 'N/A')}")
                        print(f"      - source_book: {metadata.get('source_book', 'N/A')}")
                        print(f"      - page_label: {metadata.get('page_label', 'N/A')}")
                except Exception as e:
                    print(f"      获取文档失败：{e}")
            
            # 检查是否有特定的 file_hash
            target_hash = "8691571acbdceb2f53b899dd9899554a"
            print(f"\n  查找 file_hash={target_hash} 的文档:")
            try:
                results = collection.get(
                    where={"file_hash": target_hash},
                    include=["metadatas"]
                )
                print(f"    找到 {len(results['ids'])} 个文档")
                
                if results['ids']:
                    print(f"\n    前 3 个匹配的文档:")
                    for i, (doc_id, metadata) in enumerate(zip(results['ids'][:3], results['metadatas'][:3])):
                        print(f"\n      文档 {i+1}:")
                        print(f"        - ID: {doc_id}")
                        print(f"        - file_hash: {metadata.get('file_hash', 'N/A')}")
                        print(f"        - source_book: {metadata.get('source_book', 'N/A')}")
            except Exception as e:
                print(f"    查询失败：{e}")
        
        print("\n" + "=" * 80)
        print("检查完成")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_chroma_data()
