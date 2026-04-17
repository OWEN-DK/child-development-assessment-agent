# Phase 2A.1: 执行路径统一

> **前置文档:** [Overview](./02-phase-2a-00-overview.md) | [数据模型扩展](./02-phase-2a-01-data-model.md)
> **状态:** ⏳ 完全待实现
> **预计工期:** 2人天

### 🟠 2.2 执行路径统一（⏳ 完全待实现，2人天）
> 技术方案：一次性迁移策略，通过同步工具将存量JSON数据全量导入MySQL后直接切换，不保留双写双读

#### Task 2.2.1: 存量JSON数据同步工具
**Files:**
- Create: `src/scripts/sync_rag_test_data_to_mysql.py`
- Test: `tests/scripts/test_sync_rag_test_data.py`

- [ ] **Step 1: 编写同步脚本**
```python
import asyncio
import json
from pathlib import Path
from tqdm import tqdm
from src.config import settings
from src.repository.test_run_repository import test_run_repo
from src.repository.test_run_result_repository import test_run_result_repo
from src.core.db import async_session
from src.utils.logger import logger  # 新增日志导入

async def sync_all_data(json_dir: str = None, batch_size: int = 50):
    """将JSON测试数据全量同步到MySQL（分批事务，避免单文件失败导致全局回滚）"""
    json_dir = json_dir or settings.paths.rag_test_data_dir
    path = Path(json_dir)
    
    if not path.exists():
        print(f"JSON数据目录不存在: {json_dir}")
        return
    
    test_run_files = list(path.glob("run_*.json"))
    print(f"找到 {len(test_run_files)} 个测试运行文件")
    
    success_count = 0
    fail_count = 0
    
    # 分批处理，每 batch_size 个文件一个独立事务
    for batch_start in range(0, len(test_run_files), batch_size):
        batch_files = test_run_files[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        
        async with async_session() as session:
            try:
                for file in tqdm(batch_files, desc=f"同步批次 {batch_num}"):
                    data = json.loads(file.read_text(encoding="utf-8"))
                    run_id = data.get("id") or int(file.stem.split("_")[1])
                    data["id"] = run_id
                    
                    existing = await test_run_repo.get_by_id(session, run_id)
                    if existing:
                        print(f"跳过已存在的测试运行: {run_id}")
                        continue
                    
                    await test_run_repo.create(session, data)
                    
                    # 同步结果
                    result_file = path / f"results_{run_id}.json"
                    if result_file.exists():
                        results = json.loads(result_file.read_text(encoding="utf-8"))
                        for result in results:
                            result["test_run_id"] = run_id
                            await test_run_result_repo.create(session, result)
                
                await session.commit()
                success_count += len(batch_files)
                print(f"✅ 批次 {batch_num} 同步完成")
                
            except Exception as e:
                await session.rollback()
                fail_count += len(batch_files)
                print(f"❌ 批次 {batch_num} 失败: {e}")
                # 记录失败批次，继续下一批次（已存在记录会被跳过）
                logger.error(f"同步批次 {batch_num} 失败，已记录日志")
    
    print(f"同步完成！成功: {success_count}, 失败: {fail_count}")
    if fail_count > 0:
        print(f"⚠️ 有 {fail_count} 个文件同步失败，请检查日志后重试")

if __name__ == "__main__":
    asyncio.run(sync_all_data())
```

- [ ] **Step 2: 运行同步工具**
Run: `python src/scripts/sync_rag_test_data_to_mysql.py`
Expected: 所有历史数据同步到MySQL，无数据丢失

- [ ] **Step 3: 验证数据一致性**
```python
import json
from pathlib import Path

async def verify_sync(json_dir: str = None):
    """验证同步后的数据一致性"""
    json_dir = json_dir or settings.paths.rag_test_data_dir
    path = Path(json_dir)
    
    test_run_files = list(path.glob("run_*.json"))
    all_match = True
    
    async with async_session() as session:
        for file in test_run_files:
            run_id = int(file.stem.split("_")[1])
            
            # 读取JSON
            with open(file, "r") as f:
                json_data = json.load(f)
            
            # 读取MySQL
            mysql_data = await test_run_repo.get_by_id(session, run_id)
            
            if not mysql_data:
                print(f"❌ 缺失: {run_id}")
                all_match = False
                continue
            
            # 对比关键字段
            if (json_data.get("name") != mysql_data.name or
                json_data.get("test_set_ids") != mysql_data.test_set_ids):
                print(f"❌ 不一致: {run_id}")
                all_match = False
    
    if all_match:
        print("✅ 所有数据一致")
    return all_match
```

---

#### Task 2.2.2: 统一测试执行API入口
**Files:**
- Modify: `src/controller/rag_test_controller.py`
- Test: `tests/controller/test_rag_test_controller.py`

- [ ] **Step 1: 编写测试用例**
```python
from fastapi.testclient import TestClient
import pytest

@pytest.mark.asyncio
async def test_run_test_api(client: TestClient):
    response = client.post(
        "/api/v1/rag/test/run",
        json={
            "name": "批量测试",
            "test_set_ids": [1, 2],
            "custom_case_ids": [3, 4],
            "report_export_format": "markdown"
        }
    )
    
    assert response.status_code == 202
    data = response.json()
    assert "run_id" in data
    assert data["status"] == "pending"
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/controller/test_rag_test_controller.py::test_run_test_api -v`
Expected: FAIL - API未实现

- [ ] **Step 3: 实现统一API入口**
修改`src/controller/rag_test_controller.py`:
```python
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional
from src.service.rag_test_service import rag_test_service
from src.models.rag import ReportExportFormat

router = APIRouter(prefix="/api/v1/rag/test", tags=["rag-test"])

class RunTestRequest(BaseModel):
    name: Optional[str] = Field(None, description="测试运行名称")
    description: Optional[str] = Field(None, description="测试运行描述")
    test_set_ids: List[int] = Field(default_factory=list, description="要执行的测试集ID列表")
    custom_case_ids: List[int] = Field(default_factory=list, description="自定义执行的测试用例ID列表")
    report_export_format: Optional[ReportExportFormat] = Field(ReportExportFormat.MARKDOWN, description="报告导出格式")
    notify_when_complete: bool = Field(False, description="执行完成后是否通知")

@router.post("/run", status_code=202)
async def run_test(
    request: RunTestRequest,
    background_tasks: BackgroundTasks,
    service: RagTestService = Depends(rag_test_service)
):
    """统一测试执行入口"""

> **服务注入说明**: `rag_test_service`通过DI容器注册，在`src/core/di_container.py`中添加：
> ```python
> from src.service.rag_test_service import RagTestService
> from injector import singleton
> 
> def configure_services(binder):
>     binder.bind(RagTestService, to=RagTestService, scope=singleton)
> 
> # 全局导出
> rag_test_service = injector.get(RagTestService)
> ```
    # 创建测试运行记录
    test_run = await service.create_test_run({
        "name": request.name,
        "description": request.description,
        "test_set_ids": request.test_set_ids,
        "custom_case_ids": request.custom_case_ids,
        "report_export_format": request.report_export_format,
        "status": "pending"
    })
    
    # 异步执行测试
    background_tasks.add_task(
        service.execute_test_run,
        run_id=test_run.id,
        notify_when_complete=request.notify_when_complete
    )
    
    return {
        "run_id": test_run.id,
        "status": test_run.status,
        "message": "测试已提交，后台执行中"
    }
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/controller/test_rag_test_controller.py::test_run_test_api -v`
Expected: PASS

---

#### Task 2.2.3: 实现MRR/NDCG指标计算服务
**Files:**
- Create: `src/core/rag/metrics_calculator.py`
- Test: `tests/core/rag/test_metrics_calculator.py`

- [ ] **Step 1: 编写测试用例**
```python
import pytest

def test_calculate_mrr():
    """MRR = 平均倒数排名，Q为测试用例总数，rank_i为第i个用例第一个相关结果的排名"""
    from src.core.rag.metrics_calculator import calculate_mrr
    
    # 第一个结果就是相关的
    assert calculate_mrr(["doc1"], ["doc1", "doc2", "doc3"]) == 1.0
    # 第二个结果是相关的
    assert calculate_mrr(["doc2"], ["doc1", "doc2", "doc3"]) == 0.5
    # 第三个结果是相关的
    assert calculate_mrr(["doc3"], ["doc1", "doc2", "doc3"]) == 1/3
    # 没有相关结果
    assert calculate_mrr(["doc4"], ["doc1", "doc2", "doc3"]) == 0.0

def test_calculate_ndcg():
    """NDCG@k = DCG@k / IDCG@k，DCG = sum(rel_i / log2(i+1))"""
    from src.core.rag.metrics_calculator import calculate_ndcg
    
    # 完全匹配
    assert calculate_ndcg(["doc1", "doc2"], ["doc1", "doc2", "doc3"], k=3) == 1.0
    # 部分匹配
    assert calculate_ndcg(["doc1", "doc2"], ["doc2", "doc1", "doc3"], k=3) == pytest.approx(1.0)
    # 无相关结果 → 返回 None（应跳过聚合）
    assert calculate_ndcg(["doc4"], ["doc1", "doc2", "doc3"], k=3) is None
    # 空期望文档 → 返回 None
    assert calculate_ndcg([], ["doc1", "doc2"], k=3) is None

def test_calculate_precision_recall():
    """Precision = TP/(TP+FP), Recall = TP/(TP+FN)"""
    from src.core.rag.metrics_calculator import calculate_precision, calculate_recall
    
    # 完全匹配
    assert calculate_precision(["doc1", "doc2"], ["doc1", "doc2"]) == 1.0
    assert calculate_recall(["doc1", "doc2"], ["doc1", "doc2"]) == 1.0
    # 部分匹配：检索3个，2个相关；期望2个，命中2个
    assert calculate_precision(["doc1", "doc2"], ["doc1", "doc2", "doc3"]) == 2/3
    assert calculate_recall(["doc1", "doc2"], ["doc1", "doc2", "doc3"]) == 1.0
    # 部分匹配：检索2个，1个相关；期望2个，命中1个
    assert calculate_precision(["doc1", "doc2"], ["doc1", "doc3"]) == 0.5
    assert calculate_recall(["doc1", "doc2"], ["doc1", "doc3"]) == 0.5
    # 无相关结果
    assert calculate_precision(["doc1"], ["doc2", "doc3"]) == 0.0
    assert calculate_recall(["doc1"], ["doc2", "doc3"]) == 0.0
    # 空期望文档
    assert calculate_precision([], ["doc1", "doc2"]) == 0.0
    assert calculate_recall([], ["doc1", "doc2"]) == 0.0
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/core/rag/test_metrics_calculator.py -v`
Expected: FAIL - 模块不存在

- [ ] **Step 3: 实现指标计算逻辑**
创建`src/core/rag/metrics_calculator.py`:
```python
import math
from typing import List, Optional

def calculate_mrr(relevant_docs: List[str], retrieved_docs: List[str]) -> float:
    """计算平均倒数排名(MRR)
    
    MRR = 1/rank，rank为第一个相关结果的排名（从1开始）
    """
    for idx, doc_id in enumerate(retrieved_docs):
        if doc_id in relevant_docs:
            return 1.0 / (idx + 1)
    return 0.0

def calculate_dcg(relevant_docs: List[str], retrieved_docs: List[str], k: int = 10) -> float:
    """计算折损累计增益(DCG)
    
    DCG = sum(rel_i / log2(i+1))，i从1开始
    """
    dcg = 0.0
    for idx, doc_id in enumerate(retrieved_docs[:k]):
        if doc_id in relevant_docs:
            dcg += 1.0 / math.log2(idx + 2)
    return dcg

def calculate_idcg(relevant_docs: List[str], k: int = 10) -> float:
    """计算理想折损累计增益(IDCG)"""
    idcg = 0.0
    for idx in range(min(len(relevant_docs), k)):
        idcg += 1.0 / math.log2(idx + 2)
    return idcg

def calculate_ndcg(relevant_docs: List[str], retrieved_docs: List[str], k: int = 10) -> Optional[float]:
    """计算归一化折损累计增益(NDCG)
    
    NDCG@k = DCG@k / IDCG@k
    
    Returns:
        float: NDCG 值 [0, 1]
        None: 当 relevant_docs 为空或 IDCG 为 0 时（应跳过聚合，避免拉低平均分）
    """
    if not relevant_docs:
        return None
    
    dcg = calculate_dcg(relevant_docs, retrieved_docs, k)
    idcg = calculate_idcg(relevant_docs, k)
    
    if idcg == 0:
        return None
    
    return dcg / idcg

def calculate_hit_rate(relevant_docs: List[str], retrieved_docs: List[str], k: int = 10) -> float:
    """计算召回率@k（命中的相关文档数/总相关文档数）
    若需要标准行业hit rate定义（是否至少命中1个，返回0或1），使用：
    return 1.0 if len(set(retrieved_docs[:k]) & set(relevant_docs)) > 0 else 0.0
    """
    if not relevant_docs:
        return 0.0
    
    hits = len(set(retrieved_docs[:k]) & set(relevant_docs))
    return hits / len(relevant_docs)

def calculate_precision(relevant_docs: List[str], retrieved_docs: List[str], k: int = 10) -> float:
    """计算精确率@k（Precision@k）
    
    Precision = 命中数 / 检索结果数
    衡量检索结果的准确性
    """
    retrieved_at_k = retrieved_docs[:k]
    if not retrieved_at_k:
        return 0.0
    
    hits = len(set(retrieved_at_k) & set(relevant_docs))
    return hits / len(retrieved_at_k)

def calculate_recall(relevant_docs: List[str], retrieved_docs: List[str], k: int = 10) -> float:
    """计算召回率@k（Recall@k）
    
    Recall = 命中数 / 期望相关文档数
    衡量检索结果的覆盖度
    """
    if not relevant_docs:
        return 0.0
    
    retrieved_at_k = retrieved_docs[:k]
    hits = len(set(retrieved_at_k) & set(relevant_docs))
    return hits / len(relevant_docs)
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/core/rag/test_metrics_calculator.py -v`
Expected: PASS

---

**上一阶段：** [数据模型扩展](./02-phase-2a-01-data-model.md)  
**下一阶段：** [报告生命周期管理](./02-phase-2a-03-report-lifecycle.md)
