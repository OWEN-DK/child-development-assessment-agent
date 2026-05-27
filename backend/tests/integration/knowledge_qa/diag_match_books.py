"""match_books 节点诊断脚本 — 逐步骤追踪失败根因"""

import asyncio
import logging
import time
from unittest.mock import AsyncMock, MagicMock

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TEST_QUESTION = "现在有一个孩子，想要改变注意力，我想根据《运动改变大脑》这本书来推荐一些运动改善。"


async def main():
    from src.core.knowledge_qa.tools import clear_http_client, set_http_client
    from src.schemas.knowledge_qa import (
        clear_partial_collector, clear_progress_context, clear_prompt_manager,
        init_partial_collector, set_progress_context, set_prompt_manager,
    )

    set_progress_context(callback=AsyncMock(), task_id="diag", task_type="knowledge_qa")
    mock_pm = MagicMock()
    mock_pm.get_prompt = AsyncMock(return_value=None)
    set_prompt_manager(mock_pm)

    from src.utils.http_client import RagHttpClient
    http_client = RagHttpClient(base_url="http://127.0.0.1:8000")
    set_http_client(http_client)
    init_partial_collector()

    try:
        # Step 1: Test RAG search directly
        print("\n=== Step 1: 直接测试 RAG 搜索 ===")
        results = await http_client.search_chunks(
            question="运动改变大脑 儿童注意力",
            limit=5,
        )
        print(f"搜索返回 {len(results)} 条结果")
        for r in results[:2]:
            print(f"  source_book={r.get('source_book')}, file_hash={r.get('file_hash')}, chapter={r.get('chapter_title')}")

        # Step 2: Test _extract_books_from_tool_history
        print("\n=== Step 2: 测试搜索累加器提取 ===")
        from src.core.knowledge_qa.tools import init_search_accumulator, add_to_search_accumulator, get_search_accumulator, clear_search_accumulator

        init_search_accumulator()
        add_to_search_accumulator(results)
        acc = get_search_accumulator()
        print(f"累加器中有 {len(acc)} 条结果")

        source_books = {}
        for r in acc:
            sb = r.get("source_book")
            fh = r.get("file_hash")
            if sb and fh:
                source_books[sb] = fh
        print(f"提取到 {len(source_books)} 本书: {source_books}")
        clear_search_accumulator()

        # Step 3: Test _batch_resolve_book_ids
        print("\n=== Step 3: 测试 book_id 批量解析 ===")
        from src.core.knowledge_qa.nodes.match_books import _batch_resolve_book_ids
        test_ids = list(source_books.values())
        print(f"输入 IDs: {test_ids}")
        id_mapping = await _batch_resolve_book_ids(test_ids)
        print(f"解析结果: {id_mapping}")

        # Step 4: Test full match_books fallback logic
        print("\n=== Step 4: 模拟 match_books 降级逻辑 ===")
        init_search_accumulator()
        add_to_search_accumulator(results)

        source_books2 = {}
        for r in get_search_accumulator():
            sb = r.get("source_book")
            fh = r.get("file_hash")
            if sb and fh:
                source_books2[sb] = fh
        print(f"source_books: {source_books2}")

        file_hash_to_uuid = await _batch_resolve_book_ids(list(source_books2.values()))
        print(f"file_hash_to_uuid: {file_hash_to_uuid}")

        matched_books = []
        for source_book, file_hash in source_books2.items():
            uuid = file_hash_to_uuid.get(file_hash)
            print(f"  {source_book} (hash={file_hash}) -> uuid={uuid}")
            if uuid:
                title = source_book.rsplit(".", 1)[0] if "." in source_book else source_book
                matched_books.append({
                    "book_id": source_book,
                    "title": title,
                    "author": None,
                    "source_type": "book",
                    "match_reason": "从搜索结果中自动匹配",
                })
        print(f"matched_books: {matched_books}")
        clear_search_accumulator()

        # Step 5: Run actual match_books coordinator (short time)
        print("\n=== Step 5: 运行实际 match_books 协调器 ===")
        from src.core.knowledge_qa.nodes.match_books import (
            _create_match_books_coordinator,
            _extract_books_from_tool_history,
            get_search_accumulator as gsa,
            get_match_books_result,
            init_search_accumulator as isa,
            init_match_books_result as imbr,
        )
        from src.core.knowledge_qa.tools import search_knowledge_base
        from src.core.knowledge_qa.sub_agents import match_books_finalize

        isa()
        imbr()

        coordinator = await _create_match_books_coordinator()

        print(f"协调器工具: search_knowledge_base, match_books_finalize")
        print(f"开始 invoke...")
        start = time.monotonic()

        try:
            msg_result = await asyncio.wait_for(
                coordinator.ainvoke(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": f"用户问题：{TEST_QUESTION}\n\n用户预设书籍 ID（如有）：[]\n\n知识上下文（预取）：",
                            }
                        ]
                    },
                    config={"recursion_limit": 15},
                ),
                timeout=40,
            )
            elapsed = time.monotonic() - start
            print(f"协调器完成 (耗时 {elapsed:.1f}s)")

            # Check messages
            messages = msg_result.get("messages", [])
            print(f"消息总数: {len(messages)}")
            for i, msg in enumerate(messages):
                msg_type = type(msg).__name__
                content_preview = str(getattr(msg, 'content', ''))[:100] if hasattr(msg, 'content') else ''
                tool_calls = getattr(msg, 'tool_calls', [])
                tool_name = getattr(msg, 'name', '')
                print(f"  [{i}] {msg_type}"
                      + (f" tool_call={[tc.get('name','') for tc in tool_calls]}" if tool_calls else "")
                      + (f" tool_result={tool_name}" if tool_name else "")
                      + f" {content_preview}")

        except asyncio.TimeoutError:
            elapsed = time.monotonic() - start
            print(f"协调器超时 (耗时 {elapsed:.1f}s)")

        # Check accumulator after coordinator
        acc_after = gsa()
        print(f"\n协调器运行后累加器: {len(acc_after)} 条")
        if acc_after:
            books = {}
            for r in acc_after:
                sb = r.get("source_book", "?")
                books[sb] = books.get(sb, 0) + 1
            print(f"  书籍分布: {books}")

        # Check match_books_result
        mbr = get_match_books_result()
        print(f"match_books_result: {mbr}")

        # Test fallback extraction
        if not mbr:
            print("\n=== 降级提取 ===")
            source_books_fb = await _extract_books_from_tool_history()
            print(f"extract from tool history: {source_books_fb}")

        from src.core.knowledge_qa.tools import clear_search_accumulator as csa
        from src.core.knowledge_qa.sub_agents import clear_match_books_result
        csa()
        clear_match_books_result()

    finally:
        clear_progress_context()
        clear_prompt_manager()
        clear_partial_collector()
        clear_http_client()
        await http_client.close()


if __name__ == "__main__":
    asyncio.run(main())
