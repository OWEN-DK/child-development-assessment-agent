"""MD 草稿生成 CLI。

放置位置: backend/src/scripts/generate_draft.py
用法:
  uv run python scripts/generate_draft.py --book-id exercise_book_001
  uv run python scripts/generate_draft.py --all
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 当文件放置在 backend/src/scripts/ 时，通过 sys.path 引入 neo4j 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core" / "knowledge_qa" / "neo4j"))

from chapter_parser import parse_epub
from md_generator import generate_book_md
from aggregator import aggregate_chapters
from md_renderer import render_md_draft


async def generate_for_book(book_id: str, epub_path: str, llm_client, output_dir: str):
    """为单本书生成 MD 草稿。"""
    print(f"📖 解析 EPUB: {epub_path}")
    parse_result = parse_epub(epub_path, book_id)
    print(f"   章节数: {len(parse_result.chapters)}, 总 tokens: {parse_result.total_tokens}")

    print(f"🤖 AI 生成中 ({len(parse_result.chapters)} 章)...")
    results = await generate_book_md(parse_result, llm_client)

    success_count = sum(1 for r in results if r.success)
    print(f"   成功: {success_count}/{len(results)}")

    # 解析 YAML 结果
    import yaml
    chapter_data = []
    for r in results:
        if r.success:
            try:
                data = yaml.safe_load(r.md_content)
                chapter_data.append({"chapter_id": r.chapter_id, "success": True, **(data or {})})
            except Exception:
                chapter_data.append({"chapter_id": r.chapter_id, "success": True, "concepts": []})
        else:
            chapter_data.append({"chapter_id": r.chapter_id, "success": False})

    print(f"📊 聚合中...")
    book = aggregate_chapters(chapter_data, book_id, parse_result.book_title)

    print(f"📝 渲染 MD...")
    md_content = render_md_draft(book)

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = str(Path(output_dir) / f"{parse_result.book_title}_draft_v1.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"✅ 输出: {output_path}")
    print(f"   实体: {len(book.entities)}, 主张: {len(book.claims)}, 处方: {len(book.prescriptions)}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="生成 MD 草稿")
    parser.add_argument("--book-id", required=True, help="书籍 ID")
    parser.add_argument("--epub-path", help="EPUB 文件路径")
    parser.add_argument("--output-dir", default="./drafts", help="输出目录")
    args = parser.parse_args()

    if not args.epub_path:
        print("❌ 需要 --epub-path 参数")
        sys.exit(1)

    # 注意: CLI 模式需要在实际部署时注入 LLM client
    # 此处为骨架，实际使用时替换为真实 llm_client
    print("⚠️  CLI 骨架 — 需要注入 llm_client 才能执行 AI 生成")
    print(f"   book_id: {args.book_id}")
    print(f"   epub: {args.epub_path}")
    print(f"   output: {args.output_dir}")


if __name__ == "__main__":
    main()
