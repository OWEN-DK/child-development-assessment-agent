#!/usr/bin/env python3
"""
测试向量化质量和索引状态
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_embedding_and_index():
    print("=" * 80)
    print("测试向量化质量和索引状态")
    print("=" * 80)
    
    try:
        from src.config.settings import settings
        from src.service.index_manager_service import IndexManagerService
        from src.core.embedding import SafeDashScopeEmbedding
        from llama_index.core import Settings as LlamaSettings
        import chromadb
        
        print(f"\n配置信息:")
        print(f"  - Embedding 模型：{settings.embedding_model_name}")
        print(f"  - 向量存储类型：{settings.vector_store_type}")
        print(f"  - 向量存储配置：{settings.vector_store_config}")
        
        # 1. 测试 Embedding 模型
        print("\n" + "=" * 80)
        print("1. 测试 Embedding 模型")
        print("=" * 80)
        
        embed_model = SafeDashScopeEmbedding(
            model_name=settings.embedding_model_name,
            api_key=settings.dashscope_api_key
        )
        
        test_texts = [
            "临床医生是医疗系统的核心力量",
            "医师需要专业的医学教育和培训",
            "医生负责诊断和治疗疾病",
            "这本书是关于儿童发展的指南"
        ]
        
        print(f"\n测试文本:")
        for i, text in enumerate(test_texts, 1):
            print(f"  {i}. {text}")
        
        print(f"\n生成 Embedding...")
        embeddings = embed_model.get_text_embedding_batch(test_texts)
        
        print(f"\nEmbedding 结果:")
        for i, (text, emb) in enumerate(zip(test_texts, embeddings), 1):
            print(f"  {i}. {text[:30]}...")
            print(f"     - 维度：{len(emb)}")
            print(f"     - 前 5 个值：{[f'{v:.4f}' for v in emb[:5]]}")
            print(f"     - 范数：{sum(v**2 for v in emb)**0.5:.4f}")
        
        # 计算余弦相似度
        print(f"\n余弦相似度矩阵:")
        def cosine_similarity(v1, v2):
            dot = sum(a * b for a, b in zip(v1, v2))
            norm1 = sum(a**2 for a in v1)**0.5
            norm2 = sum(b**2 for b in v2)**0.5
            return dot / (norm1 * norm2)
        
        for i in range(len(test_texts)):
            for j in range(i, len(test_texts)):
                sim = cosine_similarity(embeddings[i], embeddings[j])
                if i == j:
                    print(f"  [{i+1}][{j+1}] = {sim:.4f} (自身)")
                else:
                    print(f"  [{i+1}][{j+1}] = {sim:.4f}")
                    print(f"         {test_texts[i][:20]}... <-> {test_texts[j][:20]}...")
        
        # 2. 检查索引状态
        print("\n" + "=" * 80)
        print("2. 检查索引状态")
        print("=" * 80)
        
        index_manager = IndexManagerService()
        
        print(f"\n索引状态:")
        print(f"  - 索引是否存在：{index_manager.index is not None}")
        
        if index_manager.index:
            # 检查向量存储
            if hasattr(index_manager.index, '_vector_store'):
                vector_store = index_manager.index._vector_store
                print(f"\n向量存储信息:")
                print(f"  - 类型：{type(vector_store).__name__}")
                
                # 获取 Chroma 集合
                if hasattr(vector_store, '_collection'):
                    collection = vector_store._collection
                    print(f"  - 集合名称：{collection.name}")
                    
                    try:
                        count = collection.count()
                        print(f"  - 文档总数：{count}")
                    except Exception as e:
                        print(f"  - 获取数量失败：{e}")
                    
                    # 获取一些样本
                    try:
                        print(f"\n  样本数据（前 5 条）:")
                        results = collection.get(limit=5, include=["embeddings", "metadatas"])
                        
                        if results and results['embeddings']:
                            for i, (emb, meta) in enumerate(zip(results['embeddings'], results['metadatas']), 1):
                                print(f"\n    样本 {i}:")
                                print(f"      - 元数据：{meta}")
                                print(f"      - Embedding 维度：{len(emb)}")
                                print(f"      - 前 5 个值：{[f'{v:.4f}' for v in emb[:5]]}")
                                print(f"      - 范数：{sum(v**2 for v in emb)**0.5:.4f}")
                        else:
                            print("      (无数据)")
                    except Exception as e:
                        print(f"  - 获取样本失败：{e}")
            
            # 测试实际检索
            print("\n" + "=" * 80)
            print("3. 测试实际检索")
            print("=" * 80)
            
            test_query = "临床医生"
            print(f"\n测试查询：'{test_query}'")
            
            # 生成查询向量
            query_embedding = embed_model.get_query_embedding(test_query)
            print(f"查询 Embedding:")
            print(f"  - 维度：{len(query_embedding)}")
            print(f"  - 前 5 个值：{[f'{v:.4f}' for v in query_embedding[:5]]}")
            print(f"  - 范数：{sum(v**2 for v in query_embedding)**0.5:.4f}")
            
            # 与文档向量计算相似度
            if hasattr(vector_store, '_collection'):
                try:
                    collection = vector_store._collection
                    # 查询 Top 5
                    query_results = collection.query(
                        query_embeddings=[query_embedding],
                        include=["distances", "metadatas"],
                        n_results=5
                    )
                    
                    if query_results and query_results['distances']:
                        print(f"\nTop 5 检索结果（余弦距离）:")
                        distances = query_results['distances'][0]
                        metadatas = query_results['metadatas'][0]
                        
                        for i, (dist, meta) in enumerate(zip(distances, metadatas), 1):
                            # 余弦距离 = 1 - 余弦相似度
                            similarity = 1 - dist
                            print(f"\n  Top {i}:")
                            print(f"    - 余弦距离：{dist:.4f}")
                            print(f"    - 余弦相似度：{similarity:.4f}")
                            print(f"    - 元数据：{meta}")
                except Exception as e:
                    print(f"检索测试失败：{e}")
                    import traceback
                    traceback.print_exc()
        
        print("\n" + "=" * 80)
        print("测试完成")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_embedding_and_index())
