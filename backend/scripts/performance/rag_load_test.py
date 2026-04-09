#!/usr/bin/env python3
"""RAG 系统性能压测脚本"""
import asyncio
import time
import statistics
from typing import List
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.service.rag_service import rag_service
from src.utils.logger import logger

async def load_test(concurrency: int = 10, duration: int = 60):
    """性能压测"""
    test_queries = [
        "2岁儿童前庭觉失调的表现",
        "婴幼儿精细动作训练方法",
        "3岁儿童语言发展迟缓怎么办",
        "5岁儿童社交情感发展里程碑",
        "4岁儿童认知能力训练游戏",
    ]
    
    response_times: List[float] = []
    errors = 0
    success = 0
    start_time = time.time()
    
    async def run_query(query: str):
        nonlocal errors, success
        try:
            start = time.time()
            await rag_service.retrieve_knowledge(query=query, age=3, limit=5)
            elapsed = (time.time() - start) * 1000
            response_times.append(elapsed)
            success += 1
        except Exception as e:
            errors += 1
            logger.error(f"Query failed: {e}")
    
    tasks = []
    while time.time() - start_time < duration:
        for query in test_queries:
            if time.time() - start_time >= duration:
                break
            tasks.append(asyncio.create_task(run_query(query)))
            if len(tasks) >= concurrency:
                await asyncio.gather(*tasks[:concurrency])
                tasks = tasks[concurrency:]
    
    await asyncio.gather(*tasks)
    
    total = success + errors
    if response_times:
        print(f"\n=== 性能压测报告 ===")
        print(f"总请求数: {total}")
        print(f"成功: {success}, 失败: {errors}")
        print(f"成功率: {success/total*100:.2f}%")
        print(f"平均响应时间: {statistics.mean(response_times):.2f}ms")
        print(f"P50响应时间: {statistics.median(response_times):.2f}ms")
        sorted_times = sorted(response_times)
        p95_idx = int(len(sorted_times) * 0.95)
        print(f"P95响应时间: {sorted_times[p95_idx]:.2f}ms")
        print(f"QPS: {success / (time.time() - start_time):.2f}")

if __name__ == "__main__":
    concurrency = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    asyncio.run(load_test(concurrency, duration))
