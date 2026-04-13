# backend/scripts/performance/stress_test.py
import asyncio
import aiohttp
import time
import argparse
from statistics import mean, median, percentile


async def stress_test(
    base_url: str,
    concurrency: int = 100,
    total_requests: int = 1000,
    endpoint: str = "/rag/search",
):
    """压力测试"""

    semaphore = asyncio.Semaphore(concurrency)

    async def make_request(session, i):
        async with semaphore:
            start = time.time()
            try:
                async with session.post(
                    f"{base_url}{endpoint}",
                    json={"query": "感觉统合训练方法", "age": 3.0},
                ) as resp:
                    latency = (time.time() - start) * 1000
                    return {
                        "status": resp.status,
                        "latency": latency,
                        "success": resp.status == 200,
                    }
            except Exception as e:
                return {
                    "status": 0,
                    "latency": (time.time() - start) * 1000,
                    "success": False,
                    "error": str(e),
                }

    async with aiohttp.ClientSession() as session:
        tasks = [make_request(session, i) for i in range(total_requests)]

        start_time = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # 统计
        latencies = [r["latency"] for r in results if r["success"]]
        success_count = sum(1 for r in results if r["success"])
        errors = [r["error"] for r in results if not r["success"]][
            :10
        ]  # 只显示前10个错误

        print(f"=== 压力测试结果 ===")
        print(f"总请求数：{total_requests}")
        print(f"并发数：{concurrency}")
        print(f"测试端点：{endpoint}")
        print(f"成功数：{success_count}")
        print(f"失败数：{total_requests - success_count}")
        print(f"成功率：{success_count / total_requests:.2%}")
        print(f"总耗时：{total_time:.2f}s")
        print(f"QPS: {total_requests / total_time:.2f}")
        if latencies:
            print(f"平均延迟：{mean(latencies):.2f}ms")
            print(f"P50 延迟：{median(latencies):.2f}ms")
            print(f"P95 延迟：{percentile(latencies, 95):.2f}ms")
            print(f"P99 延迟：{percentile(latencies, 99):.2f}ms")
        if errors:
            print(f"\n前10个错误：")
            for err in errors:
                print(f"- {err}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG服务压力测试")
    parser.add_argument("--url", default="http://localhost:8000", help="服务地址")
    parser.add_argument("--concurrency", type=int, default=100, help="并发数")
    parser.add_argument("--requests", type=int, default=1000, help="总请求数")
    parser.add_argument("--endpoint", default="/rag/search", help="测试端点")

    args = parser.parse_args()

    asyncio.run(
        stress_test(
            base_url=args.url,
            concurrency=args.concurrency,
            total_requests=args.requests,
            endpoint=args.endpoint,
        )
    )
