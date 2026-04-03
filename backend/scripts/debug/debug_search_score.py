#!/usr/bin/env python3
"""
调试搜索分数构成
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def debug_search():
    print("=" * 80)
    print("调试搜索分数构成")
    print("=" * 80)
    
    try:
        from src.service.retrieval_service import RetrievalService
        from src.service.index_manager_service import IndexManagerService
        from src.service.cache_service import CacheService
        
        index_manager = IndexManagerService()
        cache_service = CacheService()
        retrieval_service = RetrievalService(index_manager, cache_service)
        
        query = "临床医生"
        print(f"\n搜索查询：'{query}'")
        print("\n执行搜索...\n")
        
        # 执行搜索（不指定 age，避免年龄适配度影响）
        results = await retrieval_service.search_content(query, limit=5, user_age=None)
        
        print(f"找到 {len(results)} 个结果\n")
        
        for i, result in enumerate(results, 1):
            print(f"Top {i}:")
            print(f"  - 最终分数：{result.relevance_score:.4f}")
            print(f"  - 内容：{result.content[:80]}...")
            print(f"  - 来源：{result.source_book}")
            print(f"  - 章节：{result.chapter_title}")
            print()
        
        # 现在测试带年龄的搜索
        print("\n" + "=" * 80)
        print("带年龄的搜索 (age=3)")
        print("=" * 80)
        
        results_with_age = await retrieval_service.search_content(query, limit=5, user_age=3)
        
        print(f"\n找到 {len(results_with_age)} 个结果\n")
        
        for i, result in enumerate(results_with_age, 1):
            print(f"Top {i}:")
            print(f"  - 最终分数：{result.relevance_score:.4f}")
            print(f"  - 内容：{result.content[:80]}...")
            print(f"  - 来源：{result.source_book}")
            print(f"  - 适用年龄：{result.target_age_min}-{result.target_age_max}岁")
            print()
        
        print("=" * 80)
        print("调试完成")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(debug_search())
