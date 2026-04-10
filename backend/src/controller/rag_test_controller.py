from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, UploadFile, File, Body, Form
from typing import Optional, List, Dict
from pydantic import BaseModel
import json
import os
import tempfile

from src.model.rag_test import TestCase, GenerationParams
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


# JSON导入相关接口
class BatchImportRequest(BaseModel):
    cases: List[dict]
    test_set_id: Optional[str] = None


@router.post("/cases/import/preview")
async def preview_import_cases(file: UploadFile = File(...)):
    """预览JSON导入的测试用例"""
    try:
        content = await file.read()
        import_data = json.loads(content.decode("utf-8"))
        valid, invalid, duplicates = rag_test_manager.preview_import_cases(import_data)
        return {
            "valid_cases": valid,
            "invalid_cases": invalid,
            "duplicates": duplicates
        }
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON格式错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.post("/cases/batch")
async def batch_import_cases(request: BatchImportRequest):
    """批量导入测试用例"""
    try:
        result = rag_test_manager.batch_import_cases(request.cases, request.test_set_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


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
        background_tasks.add_task(rag_test_manager.restore_snapshot, snapshot_id)
        return {
            "status": "success",
            "message": "Snapshot restore started in background",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to restore snapshot: {str(e)}"
        )


@router.get("/compare-configs/{version_id1}/{version_id2}")
async def compare_config_versions(version_id1: str, version_id2: str):
    """对比两个配置版本的测试结果"""
    try:
        comparison = rag_test_manager.compare_config_versions(version_id1, version_id2)
        return {"status": "success", "comparison": comparison}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Phase 2: 源文档管理
@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), title: str = Form(None), auto_generate: str = Form("true")):
    """上传源文档"""
    try:
        auto_gen = auto_generate.lower() in ("true", "1", "yes")
        
        suffix = os.path.splitext(file.filename)[1] if file.filename else ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        doc_title = title or file.filename or "未命名文档"
        file_type = suffix.lstrip(".").upper()

        doc = rag_test_manager.upload_source_document(tmp_path, doc_title, file_type)
        os.unlink(tmp_path)

        drafts = []
        if auto_gen:
            params = GenerationParams(
                target_domains=["感觉统合"],
                age_range=(0, 6),
                count=10,
                difficulty="medium",
                llm_model="qwen-plus",
                temperature=0.7,
            )
            drafts = await rag_test_manager.generate_test_case_drafts(doc.id, params)

        return {
            "status": "success",
            "document": doc.model_dump(),
            "drafts": [d.model_dump() for d in drafts],
            "draft_count": len(drafts),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("/documents")
async def list_documents():
    """列出所有源文档"""
    return rag_test_manager.list_source_documents()


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    """获取单个源文档"""
    doc = rag_test_manager.get_source_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """删除源文档"""
    success = rag_test_manager.delete_source_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"status": "success", "message": "文档已删除"}


# Phase 2: 草稿管理
class GenerateDraftsRequest(BaseModel):
    params: GenerationParams


@router.post("/documents/{doc_id}/generate-drafts")
async def generate_drafts(doc_id: str, request: GenerateDraftsRequest):
    """根据源文档生成测试用例草稿"""
    try:
        drafts = await rag_test_manager.generate_test_case_drafts(doc_id, request.params)
        return {"status": "success", "drafts": [d.model_dump() for d in drafts]}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成草稿失败: {str(e)}")


@router.get("/drafts")
async def list_drafts(source_document_id: Optional[str] = None):
    """列出草稿"""
    return rag_test_manager.list_drafts(source_document_id)


@router.get("/drafts/{draft_id}")
async def get_draft(draft_id: str):
    """获取单个草稿"""
    draft = rag_test_manager.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="草稿不存在")
    return draft


class UpdateDraftRequest(BaseModel):
    query: Optional[str] = None
    age: Optional[int] = None
    domain: Optional[str] = None
    expected_knowledge_ids: Optional[List[str]] = None
    expected_keywords: Optional[List[str]] = None
    description: Optional[str] = None
    answer_points: Optional[List[str]] = None
    professional_terms: Optional[List[str]] = None
    age_requirement: Optional[str] = None


@router.put("/drafts/{draft_id}")
async def update_draft(draft_id: str, request: UpdateDraftRequest):
    """更新草稿"""
    updates = request.model_dump(exclude_unset=True)
    draft = rag_test_manager.update_draft(draft_id, updates)
    if not draft:
        raise HTTPException(status_code=404, detail="草稿不存在")
    return draft


@router.post("/drafts/{draft_id}/review")
async def review_draft(draft_id: str, action: str = Query(..., description="reviewed/rejected")):
    """审核草稿"""
    try:
        draft = rag_test_manager.review_draft(draft_id, action)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在")
        return {"status": "success", "draft": draft.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class ImportDraftsRequest(BaseModel):
    draft_ids: List[str]


@router.post("/drafts/import")
async def import_drafts(request: ImportDraftsRequest):
    """导入已审核草稿"""
    try:
        result = rag_test_manager.import_reviewed_drafts(request.draft_ids)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


# Phase 3: 测试集管理
class CreateTestSetRequest(BaseModel):
    name: str
    description: str = ""
    source_type: str = "manual"


@router.post("/sets")
async def create_test_set(request: CreateTestSetRequest):
    """创建测试集"""
    try:
        test_set = rag_test_manager.create_test_set(request.name, request.description, request.source_type)
        return {"status": "success", "test_set": test_set.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.get("/sets")
async def list_test_sets():
    """列出所有测试集"""
    return rag_test_manager.list_test_sets()


@router.get("/sets/{set_id}")
async def get_test_set(set_id: str):
    """获取单个测试集"""
    test_set = rag_test_manager.get_test_set(set_id)
    if not test_set:
        raise HTTPException(status_code=404, detail="测试集不存在")
    return test_set


class UpdateTestSetRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@router.put("/sets/{set_id}")
async def update_test_set(set_id: str, request: UpdateTestSetRequest):
    """更新测试集"""
    updates = request.model_dump(exclude_unset=True)
    test_set = rag_test_manager.update_test_set(set_id, updates)
    if not test_set:
        raise HTTPException(status_code=404, detail="测试集不存在")
    return test_set


@router.delete("/sets/{set_id}")
async def delete_test_set(set_id: str):
    """删除测试集"""
    success = rag_test_manager.delete_test_set(set_id)
    if not success:
        raise HTTPException(status_code=404, detail="测试集不存在")
    return {"status": "success", "message": "测试集已删除"}


class AddCasesToSetRequest(BaseModel):
    case_ids: List[str]


@router.post("/sets/{set_id}/cases")
async def add_cases_to_set(set_id: str, request: AddCasesToSetRequest):
    """添加测试用例到测试集"""
    test_set = rag_test_manager.add_test_cases_to_set(set_id, request.case_ids)
    if not test_set:
        raise HTTPException(status_code=404, detail="测试集不存在")
    return test_set


@router.delete("/sets/{set_id}/cases")
async def remove_cases_from_set(set_id: str, case_ids: List[str] = Query(...)):
    """从测试集移除测试用例"""
    test_set = rag_test_manager.remove_test_cases_from_set(set_id, case_ids)
    if not test_set:
        raise HTTPException(status_code=404, detail="测试集不存在")
    return test_set


@router.get("/sets/{set_id}/export")
async def export_test_set(set_id: str):
    """导出测试集为JSON"""
    cases = rag_test_manager.export_test_set(set_id)
    if cases is None:
        raise HTTPException(status_code=404, detail="测试集不存在")
    return cases
