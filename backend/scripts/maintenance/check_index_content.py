#!/usr/bin/env python3
"""
检查实际索引中的文档内容
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def check_real_index():
    print("=" * 80)
    print("检查实际索引中的文档内容")
    print("=" * 80)
    
    try:
        from src.config.settings import settings
        from src.service.index_manager_service import IndexManagerService
        import chromadb
        
        index_manager = IndexManagerService()
        
        if not index_manager.index:
            print("索引未初始化！")
            return
        
        # 获取向量存储
        vector_store = index_manager.index._vector_store
        collection = vector_store._collection
        
        print(f"\n集合信息:")
        print(f"  - 名称：{collection.name}")
        print(f"  - 文档总数：{collection.count()}")
        
        # 获取所有文档（不分页）
        print(f"\n获取所有文档的元数据...")
        all_data = collection.get(include=["metadatas", "documents"])
        
        if all_data and all_data['metadatas']:
            print(f"\n找到 {len(all_data['metadatas'])} 个文档")
            
            # 统计有文本内容的文档数量
            docs_with_text = 0
            docs_without_text = 0
            
            for i, (doc_id, meta, doc_text) in enumerate(zip(
                all_data.get('ids', []),
                all_data.get('metadatas', []),
                all_data.get('documents', [])
            ), 1):
                if doc_text and doc_text.strip():
                    docs_with_text += 1
                    if i <= 5:  # 只显示前 5 个有内容的
                        print(f"\n  [有内容] 文档 {i}:")
                        print(f"    - ID: {doc_id}")
                        print(f"    - 内容长度：{len(doc_text)}")
                        print(f"    - 内容预览：{doc_text[:100]}...")
                        print(f"    - 元数据：{meta}")
                else:
                    docs_without_text += 1
                    if i <= 3:  # 只显示前 3 个无内容的
                        print(f"\n  [无内容] 文档 {i}:")
                        print(f"    - ID: {doc_id}")
                        print(f"    - 元数据：{meta}")
            
            print(f"\n统计:")
            print(f"  - 有文本内容的文档：{docs_with_text}")
            print(f"  - 无文本内容的文档：{docs_without_text}")
            
            # 检查一些具体的文档
            if docs_with_text > 0:
                print(f"\n" + "=" * 80)
                print("抽样检查：检索'临床医生'")
                print("=" * 80)
                
                from src.core.embedding import SafeDashScopeEmbedding
                embed_model = SafeDashScopeEmbedding(
                    model_name=settings.embedding_model_name,
                    api_key=settings.dashscope_api_key
                )
                
                query = "临床医生"
                query_embedding = embed_model.get_query_embedding(query)
                
                # 直接查询 Chroma
                results = collection.query(
                    query_embeddings=[query_embedding],
                    include=["distances", "documents", "metadatas"],
                    n_results=10
                )
                
                if results and results['distances']:
                    print(f"\nTop 10 检索结果:")
                    for i, (dist, doc, meta) in enumerate(zip(
                        results['distances'][0],
                        results['documents'][0],
                        results['metadatas'][0]
                    ), 1):
                        similarity = 1 - dist
                        print(f"\n  Top {i}:")
                        print(f"    - 相似度：{similarity:.4f} (距离：{dist:.4f})")
                        print(f"    - 内容长度：{len(doc) if doc else 0}")
                        print(f"    - 内容预览：{doc[:80] if doc else '(空)'}...")
                        if meta.get('source_book'):
                            print(f"    - 来源：{meta.get('source_book')}")
                        if meta.get('chapter_title'):
                            print(f"    - 章节：{meta.get('chapter_title')}")
        
        print("\n" + "=" * 80)
        print("检查完成")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_real_index())
