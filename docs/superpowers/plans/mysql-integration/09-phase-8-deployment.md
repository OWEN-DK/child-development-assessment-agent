# Phase 8: 数据库迁移与性能调优

> 本文档是 MySQL + Redis 集成重构实施方案的一部分
> 
> **返回索引：** [README.md](./README.md) | [项目概览](./00-overview.md)

---

## Phase 8: 数据库迁移与性能调优（周期：1 天）

### 目标
执行数据库迁移，进行压力测试和性能调优，编写旧 JSON 文件清理脚本。

### 前提条件

- MySQL 5.7 已部署并可用
- Redis 7.0 已部署并可用
- 应用配置已指向正确的 MySQL 和 Redis 地址

---

### Task 8.1: 执行数据库迁移

**Files:**
- Modify: `backend/alembic/versions/*.py`

- [ ] **Step 1: 生成最终迁移脚本**

```bash
cd backend

# 生成所有模型的迁移
alembic revision --autogenerate -m "add all mysql tables"

# 检查迁移脚本
vim alembic/versions/*_add_all_mysql_tables.py

# 应用迁移
alembic upgrade head

# 验证
alembic current
```

- [ ] **Step 2: 数据迁移（从 JSON 到 MySQL）**

```python
# backend/scripts/migrate_json_to_mysql.py
import json
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

async def migrate_test_cases():
    """迁移测试用例"""
    # 读取 JSON
    with open('app_data/storage/test_cases.json', 'r') as f:
        test_cases = json.load(f)
    
    # 写入 MySQL
    engine = create_async_engine("mysql+aiomysql://...")
    async_session = sessionmaker(engine, class_=AsyncSession)
    
    async with async_session() as session:
        for tc_data in test_cases:
            # 转换为模型
            tc = TestCase(**tc_data)
            session.add(tc)
        
        await session.commit()
    
    print(f"迁移完成：{len(test_cases)} 个测试用例")

asyncio.run(migrate_test_cases())
```

---

### Task 8.2: 压力测试和性能调优

**Files:**
- Create: `backend/scripts/performance/stress_test.py`

- [ ] **Step 1: 创建压力测试脚本**

```python
# backend/scripts/performance/stress_test.py
import asyncio
import aiohttp
import time
from statistics import mean, median, percentile

async def stress_test(
    base_url: str,
    concurrency: int = 100,
    total_requests: int = 1000,
):
    """压力测试"""
    
    async def make_request(session, i):
        start = time.time()
        try:
            async with session.post(
                f"{base_url}/rag/search",
                json={"query": "测试查询", "age": 3.0}
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
        
        print(f"总请求数：{total_requests}")
        print(f"成功数：{success_count}")
        print(f"失败数：{total_requests - success_count}")
        print(f"成功率：{success_count/total_requests:.2%}")
        print(f"总耗时：{total_time:.2f}s")
        print(f"QPS: {total_requests/total_time:.2f}")
        print(f"平均延迟：{mean(latencies):.2f}ms")
        print(f"P50 延迟：{median(latencies):.2f}ms")
        print(f"P95 延迟：{percentile(latencies, 95):.2f}ms")
        print(f"P99 延迟：{percentile(latencies, 99):.2f}ms")

# 运行
asyncio.run(stress_test("http://localhost:8000", concurrency=100, total_requests=1000))
```

- [ ] **Step 2: 性能调优**

```bash
# 运行压力测试
cd backend
uv run python scripts/performance/stress_test.py

# 根据结果调优
# 1. 调整数据库连接池大小
# 2. 调整 Redis 缓存 TTL
# 3. 调整 LLM 并发数
# 4. 优化慢查询
```

---

### Task 8.3: 旧 JSON 文件清理脚本
**Files:**
- Create: `backend/scripts/cleanup_old_json.py`

- [ ] **Step 1: 创建清理脚本**
```python
# backend/scripts/cleanup_old_json.py
"""
清理旧 JSON 文件（MySQL 迁移后执行）

⚠️ 重要：执行前请确认所有数据已成功迁移到 MySQL
"""
import os
import shutil
from pathlib import Path
from src.utils.logger import logger

# 可安全删除的旧文件/目录
FILES_TO_DELETE = [
    "app_data/data/configs/",              # 配置版本和审计日志
    "app_data/storage/test_cases.json",    # 测试用例
    "app_data/storage/test_sets/",         # 测试集
    "app_data/storage/test_case_drafts/",  # 测试用例草稿
    "app_data/storage/test_runs/",         # 测试运行结果
    "app_data/storage/source_documents/",  # 源文档元数据
    "app_data/storage/document_store.json",# 文档记录
    "app_data/storage/ab_test_metrics.json",
    "app_data/storage/memory_store.json",
    "app_data/cache/",                     # 磁盘缓存
]

# 保留的文件
FILES_TO_KEEP = [
    "backend/src/config/rules/rules.json",  # 业务规则
    "backend/src/data/",                    # 静态数据
]

def cleanup(dry_run: bool = True):
    """执行清理（默认 dry_run 模式）"""
    base_dir = Path(__file__).parent.parent.parent
    
    for rel_path in FILES_TO_DELETE:
        full_path = base_dir / rel_path
        
        if not full_path.exists():
            logger.info(f"[跳过] 不存在: {rel_path}")
            continue
        
        if dry_run:
            if full_path.is_dir():
                size = sum(f.stat().st_size for f in full_path.rglob('*') if f.is_file())
            else:
                size = full_path.stat().st_size
            logger.info(f"[预览] 将删除: {rel_path} ({size / 1024:.1f} KB)")
        else:
            if full_path.is_dir():
                shutil.rmtree(full_path)
            else:
                full_path.unlink()
            logger.info(f"[已删除] {rel_path}")
    
    if dry_run:
        logger.info("\n=== 预览模式，未实际删除 ===")
        logger.info("确认无误后，运行: python scripts/cleanup_old_json.py --execute")
    else:
        logger.info("\n=== 清理完成 ===")

if __name__ == "__main__":
    import sys
    dry_run = "--execute" not in sys.argv
    cleanup(dry_run=dry_run)
```

### Phase 8 完成验证

- [ ] 所有迁移步骤验证通过
- [ ] 压力测试达标（QPS > 100, P95 < 500ms）
- [ ] 旧 JSON 文件已清理
- [ ] 性能调优完成

---

**返回索引：** [README.md](./README.md)
