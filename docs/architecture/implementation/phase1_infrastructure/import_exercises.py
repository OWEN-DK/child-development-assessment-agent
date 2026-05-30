"""将运动清单 JSON 直接导入 Neo4j（全新部署，非迁移）。

放置位置: backend/src/scripts/import_exercises_to_neo4j.py
用法: uv run python scripts/import_exercises_to_neo4j.py [--json-path PATH] [--uri URI]
"""

import json
import re
import sys
import argparse
from pathlib import Path

from neo4j import GraphDatabase

BOOK_ID = "exercise_book_001"
BOOK_TITLE = "运动改变大脑"

# 不适合儿童的运动序号
UNSUITABLE_FOR_CHILDREN = {9, 10, 19, 35, 36, 92}


def parse_age_range(text: str) -> tuple[int, int]:
    """解析年龄文本，返回 (min_age, max_age)。"""
    if not text:
        return (0, 18)
    numbers = re.findall(r'\d+', text)
    if len(numbers) >= 2:
        return (int(numbers[0]), int(numbers[1]))
    elif len(numbers) == 1:
        return (int(numbers[0]), 18)
    return (0, 18)


def import_exercises(json_path: str, uri: str, user: str, password: str):
    """导入运动数据到 Neo4j。"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"📖 读取 {len(data)} 条运动记录: {json_path}")
    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        # 确保 Book 节点存在
        session.run(
            "MERGE (b:Book {book_id: $book_id}) SET b.title = $title",
            book_id=BOOK_ID, title=BOOK_TITLE,
        )

        count = 0
        skipped = 0

        for item in data:
            seq = str(item.get("序号", "")).zfill(3)
            name = item.get("运动名称", "").strip()
            if not name:
                skipped += 1
                continue

            category = item.get("运动类别", "")
            chapter = item.get("所在章节", "")
            benefits = item.get("运动效果", "")
            intensity = item.get("强度建议", "")

            seq_num = int(seq.lstrip("0") or "0")
            suitable = seq_num not in UNSUITABLE_FOR_CHILDREN
            min_age, max_age = parse_age_range(item.get("适合年龄", ""))
            chapter_id = f"CH_{BOOK_ID}_{chapter.replace(' ', '_')[:50]}"

            session.run("""
                MERGE (e:Exercise {exercise_id: $eid})
                SET e.name = $name,
                    e.category = $category,
                    e.benefits = $benefits,
                    e.intensity = $intensity,
                    e.suitable_for_children = $suitable,
                    e.min_age = $min_age,
                    e.max_age = $max_age,
                    e.book_id = $book_id,
                    e.curation_status = 'published'
                WITH e
                MATCH (b:Book {book_id: $book_id})
                MERGE (b)-[:CONTAINS_EXERCISE]->(e)
                WITH e, b
                MERGE (ch:Chapter {chapter_id: $chapter_id})
                SET ch.title = $chapter, ch.book_id = $book_id
                MERGE (b)-[:HAS_CHAPTER]->(ch)
                MERGE (ch)-[:DESCRIBES_EXERCISE]->(e)
            """,
                eid=f"EX{seq}", name=name, category=category,
                benefits=benefits, intensity=intensity,
                suitable=suitable, min_age=min_age, max_age=max_age,
                book_id=BOOK_ID, chapter=chapter, chapter_id=chapter_id,
            )
            count += 1

        # 验证
        total = session.run("MATCH (e:Exercise) RETURN count(e)").single()[0]
        suitable_count = session.run(
            "MATCH (e:Exercise) WHERE e.suitable_for_children = true RETURN count(e)"
        ).single()[0]
        unsuitable_count = session.run(
            "MATCH (e:Exercise) WHERE e.suitable_for_children = false RETURN e.name AS name"
        ).data()

        print(f"✅ 导入完成: {count} 条处理, {skipped} 条跳过")
        print(f"📊 Neo4j 验证: {total} Exercise 节点, {suitable_count} 适合儿童")
        if unsuitable_count:
            print(f"⚠️  不适合儿童: {[u['name'] for u in unsuitable_count]}")

    driver.close()


def main():
    parser = argparse.ArgumentParser(description="导入运动数据到 Neo4j")
    parser.add_argument("--json-path", type=str, help="JSON 文件路径")
    parser.add_argument("--uri", default="bolt://localhost:7687", help="Neo4j URI")
    parser.add_argument("--user", default="neo4j", help="Neo4j 用户名")
    parser.add_argument("--password", default="devpass123", help="Neo4j 密码")
    args = parser.parse_args()

    json_path = args.json_path
    if not json_path:
        # 默认路径: backend/data/运动改变大脑_运动清单.json
        json_path = str(
            Path(__file__).resolve().parent.parent.parent.parent
            / "backend" / "data" / "运动改变大脑_运动清单.json"
        )

    if not Path(json_path).exists():
        print(f"❌ 文件不存在: {json_path}")
        sys.exit(1)

    import_exercises(json_path, args.uri, args.user, args.password)


if __name__ == "__main__":
    main()
