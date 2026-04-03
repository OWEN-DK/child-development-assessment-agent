import asyncio
from src.service.retrieval_service import RetrievalService

class MockRetrievalService(RetrievalService):
    def __init__(self):
        self.dashscope_available = True
    
    async def _expand_synonyms(self, query: str) -> str:
        # Just to test UnboundLocalError
        synonym_list = ["老师"]
        try:
            if not self._validate_expansion(expanded_query, query):
                return self._local_expand_synonyms(query)
            
            all_terms = list(dict.fromkeys(synonym_list))
            expanded_query = " ".join(all_terms)
            return expanded_query
        except Exception as e:
            print(f"Exception type: {type(e)}")
            print(f"Exception str: {e}")
            return self._local_expand_synonyms(query)

async def main():
    service = MockRetrievalService()
    await service._expand_synonyms("老师")

asyncio.run(main())
