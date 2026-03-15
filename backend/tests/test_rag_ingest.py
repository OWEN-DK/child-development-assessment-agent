import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from service.rag_service import rag_service


async def test_ingest_and_search():
    print("Ingesting '运动改变大脑 .epub'...")

    # Ingest the book about sports
    book_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "book", "运动改变大脑 .epub"
    )
    await rag_service.ingest_book(book_path, "运动改变大脑.epub")

    print("\nIngestion complete. Testing search for '运动'...")

    # Test search
    results = await rag_service.search_content("运动", limit=10)

    print(f"\nFound {len(results)} results:")
    for i, result in enumerate(results):
        print(f"\nResult {i+1} (score: {result['score']:.2f})")
        print(f"Source: {result['source_book']} (Page: {result['page_label']})")
        print(f"Content preview: {result['content'][:300]}...")

    # Also test retrieve_knowledge function
    print("\n\nTesting retrieve_knowledge for '运动', age=3...")
    knowledge = await rag_service.retrieve_knowledge("运动", age=3, limit=5)

    print(f"Found {len(knowledge)} knowledge items:")
    for i, item in enumerate(knowledge):
        print(f"\nItem {i+1} (score: {item.relevance_score:.2f})")
        print(f"Source: {item.source_book}")
        print(f"Content: {item.content[:300]}...")


if __name__ == "__main__":
    asyncio.run(test_ingest_and_search())
