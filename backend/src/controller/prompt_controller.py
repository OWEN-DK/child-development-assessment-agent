from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from src.core.prompt.manager import prompt_manager
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/prompts", tags=["Prompt Management"])


class CreateVersionRequest(BaseModel):
    content: str
    description: Optional[str] = None
    created_by: Optional[str] = None
    variables: Optional[list] = None
    tags: Optional[list] = None
    fallback: Optional[str] = None


class CreateABTestRequest(BaseModel):
    name: str
    variant_a_version: str
    variant_b_version: str
    variant_a_ratio: float = 0.5


class ToggleABTestRequest(BaseModel):
    is_active: bool


@router.post("/ab-tests")
async def create_ab_test(request: CreateABTestRequest):
    """创建 A/B 测试"""
    try:
        test_id = await prompt_manager.create_ab_test(
            prompt_key=request.variant_a_version.split("_")[0],
            name=request.name,
            variant_a_version=request.variant_a_version,
            variant_b_version=request.variant_b_version,
            variant_a_ratio=request.variant_a_ratio,
        )
        return {"id": test_id, "message": "A/B 测试已创建"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建 A/B 测试失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ab-tests")
async def list_ab_tests(prompt_key: Optional[str] = Query(None)):
    """列出 A/B 测试"""
    try:
        tests = await prompt_manager.list_ab_tests(prompt_key)
        return {"tests": tests}
    except Exception as e:
        logger.error(f"列出 A/B 测试失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ab-tests/{test_id}/toggle")
async def toggle_ab_test(test_id: str, request: ToggleABTestRequest):
    """启用/禁用 A/B 测试"""
    try:
        await prompt_manager.toggle_ab_test(test_id, request.is_active)
        return {"message": f"A/B 测试已{'启用' if request.is_active else '禁用'}"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"切换 A/B 测试状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{prompt_key}")
async def get_prompt(
    prompt_key: str,
    version: Optional[str] = Query(None),
    ab_test_id: Optional[str] = Query(None),
):
    """获取提示词"""
    try:
        content = await prompt_manager.get_prompt(
            prompt_key=prompt_key,
            version=version,
            ab_test_id=ab_test_id,
        )
        return {
            "prompt_key": prompt_key,
            "version": version or "latest",
            "content": content,
        }
    except Exception as e:
        logger.error(f"获取提示词失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{prompt_key}/versions")
async def create_version(prompt_key: str, request: CreateVersionRequest):
    """创建新版本"""
    try:
        version = await prompt_manager.create_prompt_version(
            prompt_key=prompt_key,
            content=request.content,
            description=request.description,
            created_by=request.created_by,
            variables=request.variables,
            tags=request.tags,
            fallback=request.fallback,
        )
        return {"version": version, "message": "版本已创建"}
    except Exception as e:
        logger.error(f"创建提示词版本失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{prompt_key}/versions")
async def list_versions(prompt_key: str):
    """列出所有版本"""
    try:
        versions = await prompt_manager.list_versions(prompt_key)
        return {"versions": versions}
    except Exception as e:
        logger.error(f"列出提示词版本失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{prompt_key}/versions/{version}")
async def get_version_detail(prompt_key: str, version: str):
    """获取版本详情"""
    try:
        detail = await prompt_manager.get_version_detail(prompt_key, version)
        if not detail:
            raise HTTPException(status_code=404, detail="版本未找到")
        return detail
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取版本详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{prompt_key}/compare")
async def compare_versions(
    prompt_key: str,
    version_1: str = Query(...),
    version_2: str = Query(...),
):
    """对比版本"""
    try:
        diff = await prompt_manager.compare_versions(
            prompt_key=prompt_key,
            version_1=version_1,
            version_2=version_2,
        )
        return diff
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"对比版本失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
