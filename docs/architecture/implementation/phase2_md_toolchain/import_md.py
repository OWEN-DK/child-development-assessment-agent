"""MD 入库 CLI — 将审核后的 MD 文件导入 Neo4j。

放置位置: backend/src/scripts/import_md.py
用法:
  uv run python scripts/import_md.py --file path/to/reviewed.md
  uv run python scripts/import_md.py --file path/to/reviewed.md --dry-run
"""

import argparse
import sys
from pathlib import Path

# scripts/ 的 parent 是 src/，neo4j 模块在 src/core/knowledge_qa/neo4j/
_src = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_src / "core" / "knowledge_qa" / "neo4j"))

from neo4j import GraphDatabase
from md_parser import parse_md, execute_cypher


def main():
    parser = argparse.ArgumentParser(description="MD 入库 Neo4j")
    parser.add_argument("--file", required=True, help="审核后的 MD 文件路径")
    parser.add_argument("--uri", default="bolt://localhost:7687", help="Neo4j URI")
    parser.add_argument("--user", default="neo4j", help="Neo4j 用户名")
    parser.add_argument("--password", default="devpass123", help="Neo4j 密码")
    parser.add_argument("--dry-run", action="store_true", help="仅预览不执行")
    args = parser.parse_args()

    md_path = Path(args.file)
    if not md_path.exists():
        print(f"❌ 文件不存在: {md_path}")
        sys.exit(1)

    content = md_path.read_text(encoding="utf-8")
    result = parse_md(content)

    print(f"📖 解析完成: {result.book_title}")
    print(f"   book_id: {result.book_id}")
    print(f"   status: {result.status}")
    print(f"   version: {result.version}")
    print(f"   Cypher 语句数: {len(result.cypher_statements)}")

    if args.dry_run:
        print("\n--- DRY RUN ---")
        driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
        with driver.session() as session:
            count = execute_cypher(result, session, dry_run=True)
        driver.close()
        print(f"\n📋 预览 {count} 条语句（未执行）")
    else:
        print(f"\n🚀 开始入库...")
        driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
        with driver.session() as session:
            count = execute_cypher(result, session, dry_run=False)
        driver.close()
        print(f"✅ 成功执行 {count} 条 Cypher 语句")

        # 验证
        driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
        with driver.session() as session:
            entity_count = session.run(
                "MATCH (n) WHERE n.book_id = $bid RETURN count(n)",
                bid=result.book_id,
            ).single()[0]
            print(f"📊 验证: {result.book_id} 共 {entity_count} 个节点")
        driver.close()


if __name__ == "__main__":
    main()
