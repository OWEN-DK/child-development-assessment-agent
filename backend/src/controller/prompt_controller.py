from typing import Optional

from fastapi import APIRouter, Query

from src.core.prompt.manager import prompt_manager
from src.schemas import (CreateABTestRequest, CreateVersionRequest,
                         ToggleABTestRequest)
from src.schemas.common import APIResponse
from src.utils.exceptions import (InvalidParamsException,
                                   PromptVersionNotFoundException,
                                   ResourceNotFoundException)
from src.utils.response import api_handler

router = APIRouter(prefix="/api/v1/prompts", tags=["Prompt Management"])


@router.post("/ab-tests")
@api_handler("创建 A/B 测试", exception_map={ValueError: InvalidParamsException})
async def create_ab_test(request: CreateABTestRequest):
    """创建 A/B 测试"""
    test_id = await prompt_manager.create_ab_test(
        prompt_key=request.variant_a_version.split("_")[0],
        name=request.name,
        variant_a_version=request.variant_a_version,
        variant_b_version=request.variant_b_version,
        variant_a_ratio=request.variant_a_ratio,
    )
    return APIResponse.success(data={"id": test_id, "message": "A/B 测试已创建"})


@router.get("/ab-tests")
@api_handler("列出 A/B 测试")
async def list_ab_tests(prompt_key: Optional[str] = Query(None)):
    """列出 A/B 测试"""
    tests = await prompt_manager.list_ab_tests(prompt_key)
    return APIResponse.success(data={"tests": tests})


@router.post("/ab-tests/{test_id}/toggle")
@api_handler("切换 A/B 测试状态", exception_map={ValueError: ResourceNotFoundException})
async def toggle_ab_test(test_id: str, request: ToggleABTestRequest):
    """启用/禁用 A/B 测试"""
    await prompt_manager.toggle_ab_test(test_id, request.is_active)
    return APIResponse.success(message=f"A/B 测试已{'启用' if request.is_active else '禁用'}")


@router.get("/{prompt_key}")
@api_handler("获取提示词")
async def get_prompt(
    prompt_key: str,
    version: Optional[str] = Query(None),
    ab_test_id: Optional[str] = Query(None),
):
    """获取提示词"""
    content = await prompt_manager.get_prompt(
        prompt_key=prompt_key,
        version=version,
        ab_test_id=ab_test_id,
    )
    return APIResponse.success(data={
        "prompt_key": prompt_key,
        "version": version or "latest",
        "content": content,
    })


@router.post("/{prompt_key}/versions")
@api_handler("创建提示词版本")
async def create_version(prompt_key: str, request: CreateVersionRequest):
    """创建新版本"""
    version = await prompt_manager.create_prompt_version(
        prompt_key=prompt_key,
        content=request.content,
        description=request.description,
        created_by=request.created_by,
        variables=request.variables,
        tags=request.tags,
        fallback=request.fallback,
    )
    return APIResponse.success(data={"version": version, "message": "版本已创建"})


@router.get("/{prompt_key}/versions")
@api_handler("列出提示词版本")
async def list_versions(prompt_key: str):
    """列出所有版本"""
    versions = await prompt_manager.list_versions(prompt_key)
    return APIResponse.success(data={"versions": versions})


@router.get("/{prompt_key}/versions/{version}")
@api_handler("获取版本详情")
async def get_version_detail(prompt_key: str, version: str):
    """获取版本详情"""
    detail = await prompt_manager.get_version_detail(prompt_key, version)
    if not detail:
        raise PromptVersionNotFoundException(version_id=version)
    return APIResponse.success(data=detail)


@router.get("/{prompt_key}/compare")
@api_handler("对比版本", exception_map={ValueError: InvalidParamsException})
async def compare_versions(
    prompt_key: str,
    version_1: str = Query(...),
    version_2: str = Query(...),
):
    """对比版本"""
    diff = await prompt_manager.compare_versions(
        prompt_key=prompt_key,
        version_1=version_1,
        version_2=version_2,
    )
    return APIResponse.success(data=diff)
