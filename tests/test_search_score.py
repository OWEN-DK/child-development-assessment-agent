import asyncio
from src.service.retrieval_service import RetrievalService
from src.service.index_manager_service import IndexManagerService
from src.service.cache_service import CacheService

async def main():
    index_manager = IndexManagerService()
    cache_service = CacheService()
    service = RetrievalService(index_manager, cache_service)
    
    # Reload to make sure it's initialized
    service.reload_retrievers()
    
    results = await service.search_content("运动", limit=20)
    print(f"Found {len(results)} results")
    if results:
        print(f"Top result score: {results[0]['score']}")

asyncio.run(main())
