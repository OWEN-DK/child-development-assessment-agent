import asyncio
from src.service.retrieval_service import RetrievalService
from src.service.index_manager_service import IndexManagerService
from src.service.cache_service import CacheService

async def main():
    try:
        index_manager = IndexManagerService()
        cache_service = CacheService()
        service = RetrievalService(index_manager, cache_service)
        expanded = await service._expand_synonyms("老师")
        print(f"Expanded: {expanded}")
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
