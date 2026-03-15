import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from service.rag_service import rag_service


async def test_search():
    print("Testing RAG search for '运动'...")

    # Test search
    results = await rag_service.search_content("运动", limit=10)

    print(f"Found {len(results)} results:")
    for i, result in enumerate(results):
        print(f"\nResult {i+1} (score: {result['score']:.2f})")
        print(f"Source: {result['source_book']} (Page: {result['page_label']})")
        print(f"Content preview: {result['content'][:200]}...")

    # Also test retrieve_knowledge function
    print("\n\nTesting retrieve_knowledge for '运动', age=3...")
    knowledge = await rag_service.retrieve_knowledge("运动", age=3, limit=5)

    print(f"Found {len(knowledge)} knowledge items:")
    for i, item in enumerate(knowledge):
        print(f"\nItem {i+1} (score: {item.relevance_score:.2f})")
        print(f"Source: {item.source_book}")
        print(f"Content: {item.content[:200]}...")


if __name__ == "__main__":
    asyncio.run(test_search())
