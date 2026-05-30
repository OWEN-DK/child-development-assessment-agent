"""Neo4j 健康检查脚本 — 部署后冒烟测试。

放置位置: backend/src/scripts/neo4j_health_check.py
用法: uv run python scripts/neo4j_health_check.py [--uri URI]
"""

import sys
import argparse
from neo4j import GraphDatabase

CHECKS = {
    "连接性": "RETURN 1 AS ok",
    "节点数": "MATCH (n) RETURN count(n) AS total_nodes",
    "关系数": "MATCH ()-[r]->() RETURN count(r) AS total_relationships",
    "Book 节点": "MATCH (b:Book) RETURN count(b) AS books",
    "Exercise 节点": "MATCH (e:Exercise) RETURN count(e) AS exercises",
    "适合儿童运动": "MATCH (e:Exercise) WHERE e.suitable_for_children = true RETURN count(e) AS count",
}


def run_health_check(uri: str, user: str, password: str) -> bool:
    """运行所有健康检查，返回是否全部通过。"""
    print(f"🔍 Neo4j 健康检查: {uri}\n")

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
    except Exception as e:
        print(f"  ❌ 无法创建 Driver: {e}")
        return False

    all_ok = True
    with driver.session() as session:
        # 约束检查
        try:
            result = session.run("SHOW CONSTRAINTS")
            constraints = list(result)
            print(f"  ✅ 约束数: {len(constraints)}")
        except Exception as e:
            print(f"  ❌ 约束检查失败: {e}")
            all_ok = False

        # 索引检查
        try:
            result = session.run("SHOW INDEXES")
            indexes = list(result)
            print(f"  ✅ 索引数: {len(indexes)}")
        except Exception as e:
            print(f"  ❌ 索引检查失败: {e}")
            all_ok = False

        # 逐项检查
        for name, query in CHECKS.items():
            try:
                record = session.run(query).single()
                value = record.values()[0] if record else "N/A"
                print(f"  ✅ {name}: {value}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                all_ok = False

    driver.close()

    if all_ok:
        print("\n✅ 所有健康检查通过")
    else:
        print("\n❌ 部分检查未通过")

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Neo4j 健康检查")
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--user", default="neo4j")
    parser.add_argument("--password", default="devpass123")
    args = parser.parse_args()

    ok = run_health_check(args.uri, args.user, args.password)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
