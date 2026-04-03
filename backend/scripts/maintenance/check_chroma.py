#!/usr/bin/env python3
"""检查 Chroma 数据库内容（新版本 API）"""

import chromadb

# 连接到 Chroma 数据库（新 API）
client = chromadb.PersistentClient(path="./chroma_data")

# 获取集合
collections = client.list_collections()
print(f"集合数量：{len(collections)}")

for coll in collections:
    print(f"\n集合名称：{coll.name}")
    
    # 获取集合统计
    count = coll.count()
    print(f"文档数量：{count}")
    
    # 尝试查询所有数据
    if count > 0:
        results = coll.get(include=["metadatas", "documents"])
        print(f"返回数量：{len(results['ids'])}")
        
        # 检查 metadata 中的 file_hash
        if results['metadatas']:
            file_hashes = set()
            for meta in results['metadatas']:
                if meta and 'file_hash' in meta:
                    file_hashes.add(meta['file_hash'])
            print(f"file_hash 列表：{file_hashes}")
            
            # 测试 where 查询
            if file_hashes:
                test_hash = list(file_hashes)[0]
                print(f"\n测试查询 file_hash={test_hash}")
                filtered = coll.get(
                    where={"file_hash": test_hash},
                    include=["metadatas", "documents"]
                )
                print(f"过滤后数量：{len(filtered['ids'])}")
