from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import Optional, List
from pydantic import BaseModel

from src.model.rag_test import TestCase
from src.service.rag_test_manager import rag_test_manager

router = APIRouter(prefix="/rag/test", tags=["RAG Test"])


class CreateTestCaseRequest(BaseModel):
    query: str
    age: int
    expected_knowledge_ids: List[str] = []
    expected_keywords: List[str] = []
    description: str = ""


class UpdateTestCaseRequest(BaseModel):
    query: Optional[str] = None
    age: Optional[int] = None
    expected_knowledge_ids: Optional[List[str]] = None
    expected_keywords: Optional[List[str]] = None
    description: Optional[str] = None


class CreateSnapshotRequest(BaseModel):
    name: str = ""
    description: str = ""


class RunTestsRequest(BaseModel):
    name: str = ""
    description: str = ""
    limit: int = Query(10, ge=1, le=50)


# 测试用例管理
@router.post("/cases", response_model=TestCase)
async def create_test_case(request: CreateTestCaseRequest):
    """创建测试用例"""
    test_case = TestCase(
        query=request.query,
        age=request.age,
        expected_knowledge_ids=request.expected_knowledge_ids,
        expected_keywords=request.expected_keywords,
        description=request.description,
    )
    return rag_test_manager.add_test_case(test_case)


@router.get("/cases", response_model=List[TestCase])
async def list_test_cases():
    """列出所有测试用例"""
    return rag_test_manager.list_test_cases()


@router.get("/cases/{case_id}", response_model=TestCase)
async def get_test_case(case_id: str):
    """获取单个测试用例"""
    test_case = rag_test_manager.get_test_case(case_id)
    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")
    return test_case


@router.put("/cases/{case_id}", response_model=TestCase)
async def update_test_case(case_id: str, request: UpdateTestCaseRequest):
    """更新测试用例"""
    existing = rag_test_manager.get_test_case(case_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Test case not found")

    # 更新字段
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(existing, field, value)

    updated = rag_test_manager.update_test_case(case_id, existing)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update test case")
    return updated


@router.delete("/cases/{case_id}")
async def delete_test_case(case_id: str):
    """删除测试用例"""
    success = rag_test_manager.delete_test_case(case_id)
    if not success:
        raise HTTPException(status_code=404, detail="Test case not found")
    return {"status": "success", "message": "Test case deleted"}


# 测试执行
@router.post("/run")
async def run_all_tests(request: RunTestsRequest):
    """运行所有测试用例"""
    try:
        test_run = await rag_test_manager.run_all_tests(
            name=request.name, description=request.description, limit=request.limit
        )
        return {"status": "success", "test_run": test_run.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run tests: {str(e)}")


@router.post("/run/{case_id}")
async def run_single_test(case_id: str, limit: int = Query(10, ge=1, le=50)):
    """运行单个测试用例"""
    test_case = rag_test_manager.get_test_case(case_id)
    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")

    try:
        result = await rag_test_manager.run_test_case(test_case, limit)
        return {"status": "success", "result": result.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run test: {str(e)}")


# 测试运行结果
@router.get("/runs")
async def list_test_runs():
    """列出所有测试运行"""
    return rag_test_manager.list_test_runs()


@router.get("/runs/{run_id}")
async def get_test_run(run_id: str):
    """获取单个测试运行结果"""
    run = rag_test_manager.get_test_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return run


@router.get("/compare")
async def compare_test_runs(run_id1: str, run_id2: str):
    """比较两个测试运行的结果"""
    try:
        comparison = rag_test_manager.compare_test_runs(run_id1, run_id2)
        return {"status": "success", "comparison": comparison}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# 快照管理
@router.post("/snapshots")
async def create_snapshot(request: CreateSnapshotRequest):
    """创建知识库快照"""
    try:
        snapshot = rag_test_manager.create_snapshot(
            name=request.name, description=request.description
        )
        return {"status": "success", "snapshot": snapshot.model_dump()}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create snapshot: {str(e)}"
        )


@router.get("/snapshots")
async def list_snapshots():
    """列出所有快照"""
    return rag_test_manager.list_snapshots()


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot(snapshot_id: str):
    """获取单个快照"""
    snapshot = rag_test_manager.get_snapshot(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot


@router.post("/snapshots/{snapshot_id}/restore")
async def restore_snapshot(snapshot_id: str, background_tasks: BackgroundTasks):
    """恢复到指定快照"""
    try:
        # 恢复操作可能耗时，放到后台执行
        background_tasks.add_task(rag_test_manager.restore_snapshot, snapshot_id)
        return {
            "status": "success",
            "message": "Snapshot restore started in background",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to restore snapshot: {str(e)}"
        )
