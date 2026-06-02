"""启动脚本：将运动清单 JSON 全量导入 Neo4j。

每次执行先清空由本脚本创建的所有节点和关系，再从 JSON 全量重新导入。

导入内容（对应 JSON 全部顶层结构）：
  - exercises[93]       → Exercise 节点（含全部字段）
  - brain_regions[16]   → BrainRegion 节点 + Exercise-AFFECTS->BrainRegion
  - principles[7]       → Principle 节点 + Principle-APPLIES_TO->Exercise
  - exercise_type_set   → ExerciseCategory 节点 + Exercise-BELONGS_TO->ExerciseCategory
  - exercise_name_to_id → 无需单独节点（查询通过 Exercise.name 实现）

辅助字段 exercise_name_set 与 exercise_type_set 为冗余索引，不导入。

用法:
    uv run python src/scripts/import_exercises_to_neo4j.py
    uv run python src/scripts/import_exercises_to_neo4j.py --uri bolt://host:7687
"""

import json
import re
import sys
import argparse
import logging
from pathlib import Path

from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BOOK_ID = "264cd32f3101b74bc36c938605bfe44f"
BOOK_TITLE = "运动改变大脑"

# 不适合儿童的运动 id
UNSUITABLE_FOR_CHILDREN = {9, 10, 19, 35, 36, 92}

# 本脚本管理的所有节点标签（清空时按此范围删除）
MANAGED_LABELS = ["Exercise", "Chapter", "BrainRegion", "Principle", "ExerciseCategory"]


# ── 工具函数 ──────────────────────────────────────────────


def _parse_age_range(text: str) -> tuple[int, int]:
    """解析 JSON age 字段 → (min_age, max_age)。"""
    if not text:
        return (0, 120)
    m = re.search(r"(\d+)\s*[岁+]?\s*[~～\-—]\s*(\d+)", text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = re.search(r"(\d+)\s*岁?\s*\+", text)
    if m:
        return (int(m.group(1)), 120)
    m = re.search(r"(\d+)", text)
    if m:
        return (int(m.group(1)), 120)
    return (0, 120)


def _normalize_brain_region_name(raw: str) -> str:
    """去掉括号内的英文，如 '海马体 (Hippocampus)' → '海马体'。"""
    return re.sub(r"\s*\(.*?\)", "", raw).strip()


# ── Step 1: 清空 ──────────────────────────────────────────


def _cleanup(session) -> int:
    """清空本脚本管理的所有节点（通过 book_id 标记），不影响其他书籍数据。"""
    total = 0
    for label in MANAGED_LABELS:
        result = session.run(f"""
            MATCH (n:{label}) WHERE n.book_id = $book_id
            DETACH DELETE n
            RETURN count(*) AS deleted
        """, book_id=BOOK_ID)
        deleted = result.single()["deleted"]
        if deleted:
            logger.info("  清空 %s: %d", label, deleted)
        total += deleted

    # 同时清理 Book 节点上本脚本创建的关系
    session.run("""
        MATCH (b:Book {book_id: $book_id})
        OPTIONAL MATCH (b)-[r:CONTAINS_EXERCISE|HAS_CHAPTER|CONTAINS_ENTITY]->(n)
        WHERE n IS NULL OR n.book_id = $book_id
        DELETE r
    """, book_id=BOOK_ID)

    logger.info("清空完成: %d 节点", total)
    return total


# ── Step 2: Book 节点 ─────────────────────────────────────


def _ensure_book(session):
    session.run(
        "MERGE (b:Book {book_id: $book_id}) SET b.title = $title, b.source_type = 'exercise_json'",
        book_id=BOOK_ID, title=BOOK_TITLE,
    )


# ── Step 3: Exercise + Chapter ────────────────────────────


def _import_exercises(session, exercises: list[dict]) -> dict[int, str]:
    """导入 Exercise + Chapter，返回 {json_id: exercise_id} 映射。"""
    chapter_cache: dict[str, str] = {}
    id_map: dict[int, str] = {}
    count = 0

    for item in exercises:
        eid_num = item.get("id", 0)
        name = (item.get("name") or "").strip()
        if not name:
            continue

        exercise_id = f"EX{eid_num:03d}"
        category = item.get("type", "")
        chapter_str = item.get("chapter", "")
        benefits = item.get("benefits", "")
        brain_mechanisms = item.get("brain_mechanisms", "")
        intensity = item.get("intensity", "")
        age_str = item.get("age", "")

        suitable = eid_num not in UNSUITABLE_FOR_CHILDREN
        min_age, max_age = _parse_age_range(age_str)

        # Chapter 节点（去重）
        if chapter_str and chapter_str not in chapter_cache:
            chapter_id = f"CH_{BOOK_ID}_{chapter_str.replace(' ', '_')[:50]}"
            chapter_cache[chapter_str] = chapter_id
            session.run("""
                MERGE (ch:Chapter {chapter_id: $chapter_id})
                SET ch.title = $title, ch.book_id = $book_id
            """, chapter_id=chapter_id, title=chapter_str, book_id=BOOK_ID)

        # Exercise 节点（全部字段）
        session.run("""
            MERGE (e:Exercise {exercise_id: $eid})
            SET e.name              = $name,
                e.category          = $category,
                e.benefits          = $benefits,
                e.brain_mechanisms  = $brain_mechanisms,
                e.intensity         = $intensity,
                e.suitable_for_children = $suitable,
                e.min_age           = $min_age,
                e.max_age           = $max_age,
                e.age_text          = $age_text,
                e.book_id           = $book_id,
                e.curation_status   = 'published'
        """,
            eid=exercise_id, name=name, category=category,
            benefits=benefits, brain_mechanisms=brain_mechanisms,
            intensity=intensity, suitable=suitable,
            min_age=min_age, max_age=max_age, age_text=age_str,
            book_id=BOOK_ID,
        )

        # Book → Exercise
        session.run("""
            MATCH (b:Book {book_id: $book_id})
            MATCH (e:Exercise {exercise_id: $eid})
            MERGE (b)-[:CONTAINS_EXERCISE]->(e)
        """, book_id=BOOK_ID, eid=exercise_id)

        # Chapter → Exercise
        chapter_id = chapter_cache.get(chapter_str, "")
        if chapter_id:
            session.run("""
                MATCH (b:Book {book_id: $book_id})
                MATCH (ch:Chapter {chapter_id: $chapter_id})
                MATCH (e:Exercise {exercise_id: $eid})
                MERGE (b)-[:HAS_CHAPTER]->(ch)
                MERGE (ch)-[:DESCRIBES_EXERCISE]->(e)
            """, book_id=BOOK_ID, chapter_id=chapter_id, eid=exercise_id)

        id_map[eid_num] = exercise_id
        count += 1

    logger.info("Exercise 导入: %d / %d", count, len(exercises))
    return id_map


# ── Step 4: BrainRegion ───────────────────────────────────


def _import_brain_regions(session, brain_regions: list[dict], exercise_id_map: dict[int, str]):
    """导入 BrainRegion + Exercise-AFFECTS->BrainRegion。"""
    count = 0
    link_count = 0

    for br in brain_regions:
        raw_name = br.get("region", "")
        display_name = _normalize_brain_region_name(raw_name)
        function = br.get("function", "")
        benefits = br.get("benefits", "")
        exercise_ids = br.get("exercise_ids", [])

        if not display_name:
            continue

        region_id = f"BR_{BOOK_ID}_{display_name[:30]}"

        session.run("""
            MERGE (br:BrainRegion {region_id: $region_id})
            SET br.name      = $name,
                br.full_name = $full_name,
                br.function  = $function,
                br.benefits  = $benefits,
                br.book_id   = $book_id
        """,
            region_id=region_id, name=display_name,
            full_name=raw_name, function=function,
            benefits=benefits, book_id=BOOK_ID,
        )

        # Book → BrainRegion
        session.run("""
            MATCH (b:Book {book_id: $book_id})
            MATCH (br:BrainRegion {region_id: $region_id})
            MERGE (b)-[:CONTAINS_ENTITY]->(br)
        """, book_id=BOOK_ID, region_id=region_id)

        # Exercise -[:AFFECTS]-> BrainRegion
        for eid_num in exercise_ids:
            exercise_id = exercise_id_map.get(eid_num)
            if exercise_id:
                session.run("""
                    MATCH (e:Exercise {exercise_id: $eid})
                    MATCH (br:BrainRegion {region_id: $region_id})
                    MERGE (e)-[:AFFECTS]->(br)
                """, eid=exercise_id, region_id=region_id)
                link_count += 1

        count += 1

    logger.info("BrainRegion 导入: %d 个脑区, %d 条 AFFECTS 关系", count, link_count)


# ── Step 5: Principle ─────────────────────────────────────


def _import_principles(session, principles: list[dict], exercise_id_map: dict[int, str],
                       type_to_exercise_ids: dict[str, list[str]],
                       exercise_names: dict[int, str]):
    """导入 Principle + Principle-APPLIES_TO->Exercise。

    principles[].exercise_types 是逗号分隔的运动类型名称（如 '行走、跑步、力量训练'），
    需要通过 Exercise.category 字段匹配到具体 Exercise 节点。
    """
    count = 0
    link_count = 0

    for p in principles:
        pid = p.get("id", 0)
        name = p.get("name", "").strip()
        content = p.get("content", "")
        exercise_types_str = p.get("exercise_types", "")
        scientific_basis = p.get("scientific_basis", "")

        if not name:
            continue

        principle_id = f"PR_{BOOK_ID}_{pid:03d}"

        session.run("""
            MERGE (pr:Principle {principle_id: $principle_id})
            SET pr.name              = $name,
                pr.content           = $content,
                pr.exercise_types    = $exercise_types,
                pr.scientific_basis  = $scientific_basis,
                pr.book_id           = $book_id
        """,
            principle_id=principle_id, name=name,
            content=content, exercise_types=exercise_types_str,
            scientific_basis=scientific_basis, book_id=BOOK_ID,
        )

        # Book → Principle
        session.run("""
            MATCH (b:Book {book_id: $book_id})
            MATCH (pr:Principle {principle_id: $principle_id})
            MERGE (b)-[:CONTAINS_ENTITY]->(pr)
        """, book_id=BOOK_ID, principle_id=principle_id)

        # Principle -[:APPLIES_TO]-> Exercise
        # 解析 exercise_types（顿号/逗号分隔），多维度匹配：
        #   1) 精确匹配 Exercise.category
        #   2) type_name 子串包含在 category 中
        #   3) type_name 子串包含在 Exercise.name 中（处理 "腹式呼吸"→"腹式呼吸/横膈膜呼吸"）
        type_names = re.split(r"[、，,]", exercise_types_str)
        matched_exercise_ids: set[str] = set()

        for tn in type_names:
            tn = tn.strip()
            if not tn or len(tn) < 2:
                continue
            # 1) 精确匹配 category
            for eid in type_to_exercise_ids.get(tn, []):
                matched_exercise_ids.add(eid)
            # 2) type_name 子串包含在 category 中（处理宽泛描述）
            for cat, eids in type_to_exercise_ids.items():
                if tn in cat and tn != cat:
                    matched_exercise_ids.update(eids)
            # 3) type_name 子串包含在 Exercise.name 中
            #    如 "腹式呼吸" → 匹配 "腹式呼吸/横膈膜呼吸"
            for eid_num, eid in exercise_id_map.items():
                ex_name = exercise_names.get(eid_num, "")
                if tn in ex_name:
                    matched_exercise_ids.add(eid)

        # "所有运动类型" 特殊处理：关联全部 Exercise
        if any("所有" in tn for tn in type_names):
            matched_exercise_ids = set(exercise_id_map.values())

        for eid in matched_exercise_ids:
            session.run("""
                MATCH (pr:Principle {principle_id: $principle_id})
                MATCH (e:Exercise {exercise_id: $eid})
                MERGE (pr)-[:APPLIES_TO]->(e)
            """, principle_id=principle_id, eid=eid)
            link_count += 1

        count += 1
        logger.info("  Principle P%d '%s': 关联 %d 个运动", pid, name, len(matched_exercise_ids))

    logger.info("Principle 导入: %d 条, %d 条 APPLIES_TO 关系", count, link_count)


# ── Step 6: ExerciseCategory ──────────────────────────────


def _import_exercise_categories(session, type_set: list[str], exercises: list[dict]):
    """导入 ExerciseCategory + Exercise-BELONGS_TO->ExerciseCategory。"""
    count = 0
    link_count = 0

    for cat_name in type_set:
        if not cat_name:
            continue

        cat_id = f"EC_{BOOK_ID}_{cat_name[:40]}"

        session.run("""
            MERGE (ec:ExerciseCategory {category_id: $cat_id})
            SET ec.name    = $name,
                ec.book_id = $book_id
        """, cat_id=cat_id, name=cat_name, book_id=BOOK_ID)

        # Book → ExerciseCategory
        session.run("""
            MATCH (b:Book {book_id: $book_id})
            MATCH (ec:ExerciseCategory {category_id: $cat_id})
            MERGE (b)-[:CONTAINS_ENTITY]->(ec)
        """, book_id=BOOK_ID, cat_id=cat_id)

        # Exercise -[:BELONGS_TO]-> ExerciseCategory
        for ex in exercises:
            if ex.get("type") == cat_name:
                eid = f"EX{ex['id']:03d}"
                session.run("""
                    MATCH (e:Exercise {exercise_id: $eid})
                    MATCH (ec:ExerciseCategory {category_id: $cat_id})
                    MERGE (e)-[:BELONGS_TO]->(ec)
                """, eid=eid, cat_id=cat_id)
                link_count += 1

        count += 1

    logger.info("ExerciseCategory 导入: %d 个分类, %d 条 BELONGS_TO 关系", count, link_count)


# ── 验证 ──────────────────────────────────────────────────


def _verify(session):
    """打印导入结果统计。"""
    logger.info("─── 验证 ───")

    for label in MANAGED_LABELS:
        result = session.run(f"""
            MATCH (n:{label}) WHERE n.book_id = $book_id
            RETURN count(n) AS c
        """, book_id=BOOK_ID)
        cnt = result.single()["c"]
        logger.info("  %-20s %d", label, cnt)

    # 关系统计
    rel_types = [
        "AFFECTS", "DESCRIBES_EXERCISE", "APPLIES_TO",
        "BELONGS_TO", "CONTAINS_EXERCISE", "HAS_CHAPTER", "CONTAINS_ENTITY",
    ]
    for rel in rel_types:
        result = session.run(f"""
            MATCH ()-[r:{rel}]->() WHERE endNode(r).book_id = $book_id OR startNode(r).book_id = $book_id
            RETURN count(r) AS c
        """, book_id=BOOK_ID)
        cnt = result.single()["c"]
        if cnt:
            logger.info("  %-20s %d 条关系", rel, cnt)

    # 核心断言
    total_ex = session.run(
        "MATCH (e:Exercise) WHERE e.book_id = $bid RETURN count(e) AS c", bid=BOOK_ID
    ).single()["c"]
    suitable = session.run(
        "MATCH (e:Exercise) WHERE e.book_id = $bid AND e.suitable_for_children = true RETURN count(e) AS c",
        bid=BOOK_ID,
    ).single()["c"]

    if total_ex < 50:
        logger.warning("⚠️  Exercise 数量异常（%d < 50），请检查 JSON", total_ex)
    else:
        logger.info("✅ 导入正常: %d Exercise (%d 适合儿童), 全部 JSON 结构已写入", total_ex, suitable)


# ── 主函数 ────────────────────────────────────────────────


def import_exercises(json_path: str, uri: str, user: str, password: str):
    """全量导入运动数据到 Neo4j（先清空再导入）。"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    exercises = data.get("exercises", [])
    brain_regions = data.get("brain_regions", [])
    principles = data.get("principles", [])
    type_set = list(data.get("exercise_type_set", []))

    if not exercises:
        logger.error("JSON 中 exercises 为空，终止")
        return

    logger.info("读取 JSON: %d Exercise, %d BrainRegion, %d Principle, %d ExerciseCategory",
                len(exercises), len(brain_regions), len(principles), len(type_set))
    logger.info("连接 Neo4j: %s", uri)

    # 构建 type → [exercise_id] 索引（供 Principle 关联用）
    type_to_exercise_ids: dict[str, list[str]] = {}
    for ex in exercises:
        cat = ex.get("type", "")
        eid = f"EX{ex['id']:03d}"
        type_to_exercise_ids.setdefault(cat, []).append(eid)

    driver = GraphDatabase.driver(uri, auth=(user, password))

    try:
        with driver.session() as session:
            _cleanup(session)
            _ensure_book(session)
            exercise_id_map = _import_exercises(session, exercises)
            _import_brain_regions(session, brain_regions, exercise_id_map)
            # 构建 exercise_id → name 索引
            _exercise_name_map = {ex.get("id", 0): (ex.get("name") or "") for ex in exercises}
            _import_principles(session, principles, exercise_id_map, type_to_exercise_ids, _exercise_name_map)
            _import_exercise_categories(session, type_set, exercises)
            _verify(session)
    finally:
        driver.close()

    logger.info("🎉 运动清单 Neo4j 全量导入完成")


def main():
    parser = argparse.ArgumentParser(description="导入运动清单 JSON 到 Neo4j（每次全量重置）")
    parser.add_argument(
        "--json-path", type=str, default=None,
        help="JSON 路径（默认: backend/src/data/运动改变大脑_运动清单.json）",
    )
    parser.add_argument("--uri", default="bolt://localhost:7687", help="Neo4j URI")
    parser.add_argument("--user", default="neo4j", help="Neo4j 用户名")
    parser.add_argument("--password", default="devpass123", help="Neo4j 密码")
    args = parser.parse_args()

    json_path = args.json_path or str(
        Path(__file__).resolve().parent.parent / "data" / "运动改变大脑_运动清单.json"
    )

    if not Path(json_path).exists():
        logger.error("文件不存在: %s", json_path)
        sys.exit(1)

    import_exercises(json_path, args.uri, args.user, args.password)


if __name__ == "__main__":
    main()
