"""Neo4j 性能测试 — 验证查询延迟和并发能力。

放置位置: backend/scripts/neo4j_perf_test.py
用法: uv run python scripts/neo4j_perf_test.py --concurrency 100 --iterations 10
"""

from __future__ import annotations

import argparse
import statistics
import time
import concurrent.futures
from neo4j import GraphDatabase


TEST_QUERIES = {
    "exercise_by_age": {
        "query": """
            MATCH (e:Exercise)
            WHERE e.suitable_for_children = true AND e.min_age <= 8 AND e.max_age >= 8
            RETURN e.name, e.category, e.benefits
            LIMIT 20
        """,
        "params": {},
        "description": "按年龄查询运动（最频繁）",
    },
    "cross_book_relations": {
        "query": """
            MATCH (a)-[r:CROSS_BOOK_CONSENSUS|CROSS_BOOK_COMPLEMENTS|CROSS_BOOK_CONFLICTS]->(b)
            RETURN a.name, type(r), b.name
            LIMIT 50
        """,
        "params": {},
        "description": "跨书关系查询（最复杂）",
    },
    "problem_context": {
        "query": """
            MATCH (p:Problem)-[r]->(rc:RootCause)
            WHERE p.name = '注意力不集中'
            RETURN p.name, rc.name, type(r)
        """,
        "params": {},
        "description": "问题上下文查询",
    },
    "fulltext_search": {
        "query": """
            CALL db.index.fulltext.queryNodes('exercise_fulltext', '有氧运动')
            YIELD node, score
            RETURN node.name, score
            LIMIT 10
        """,
        "params": {},
        "description": "全文搜索",
    },
}


def run_single_query(driver, query_config: dict) -> float:
    """执行单次查询，返回延迟(毫秒)。"""
    start = time.perf_counter()
    with driver.session() as session:
        session.run(query_config["query"], **query_config["params"]).data()
    elapsed_ms = (time.perf_counter() - start) * 1000
    return elapsed_ms


def run_perf_test(uri: str, user: str, password: str, concurrency: int, iterations: int):
    """运行性能测试。"""
    driver = GraphDatabase.driver(uri, auth=(user, password))

    print(f"🔍 Neo4j 性能测试")
    print(f"   并发: {concurrency}, 每查询迭代: {iterations}\n")

    for name, config in TEST_QUERIES.items():
        latencies = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = []
            for _ in range(concurrency * iterations):
                futures.append(executor.submit(run_single_query, driver, config))

            for future in concurrent.futures.as_completed(futures):
                latencies.append(future.result())

        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)

        status = "✅" if p99 < 500 else "⚠️"
        print(f"  {status} {config['description']}")
        print(f"     avg={avg:.1f}ms  P50={p50:.1f}ms  P95={p95:.1f}ms  P99={p99:.1f}ms")

        if p99 >= 500:
            print(f"     ⚠️  P99 ({p99:.0f}ms) 超过 500ms 目标!")

    driver.close()
    print("\n✅ 性能测试完成")


def main():
    parser = argparse.ArgumentParser(description="Neo4j 性能测试")
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--user", default="neo4j")
    parser.add_argument("--password", default="devpass123")
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--iterations", type=int, default=10)
    args = parser.parse_args()

    run_perf_test(args.uri, args.user, args.password, args.concurrency, args.iterations)


if __name__ == "__main__":
    main()
