import asyncio
from src.service.retrieval_service import RetrievalService
from src.service.index_manager_service import IndexManagerService
from src.service.cache_service import CacheService

async def main():
    index_manager = IndexManagerService()
    index_manager.initialize()
    cache_service = CacheService()
    service = RetrievalService(index_manager, cache_service)
    
    # Reload to make sure it's initialized
    service.reload_retrievers()
    
    results = await service.search_content("老师", limit=20)
    print(f"Found {len(results)} results")

asyncio.run(main())
