"""提示词管理 API 控制器"""

from fastapi import APIRouter
from typing import Optional

from src.core.database import async_session_factory
from src.core.prompt.manager import prompt_manager
from src.schemas import (ImpactAnalysisResponse, PromptComparisonResponse,
                         PromptDetailResponse, PromptListResponse,
                         PromptMetadataResponse, PromptTestRequest,
                         PromptTestResponse, PromptVersionResponse,
                         UpdatePromptRequest)
from src.service.prompt_impact_analyzer import (PromptImpactAnalyzer,
                                                VariableValidator)
from src.utils.exceptions import (ForbiddenException, InvalidParamsException,
                                   InternalServerErrorException,
                                   PromptNotFoundException,
                                   PromptVersionNotFoundException)
from src.utils.logger import logger

router = APIRouter(prefix="/api/v1/rag/prompts", tags=["提示词管理"])


class PromptController:
    """提示词管理 API 控制器"""

    def __init__(self):
        self._impact_analyzer = PromptImpactAnalyzer()

    def register_routes(self, app):
        """注册路由"""

        @router.get("", response_model=PromptListResponse)
        async def list_prompts(
            category: Optional[str] = None,
            is_active: Optional[bool] = None,
        ):
            """获取提示词列表"""
            try:
                from sqlalchemy import select

                from src.models.prompt_enums import PromptCategory
                from src.models.prompt_metadata import PromptMetadata

                async with async_session_factory() as session:
                    query = select(PromptMetadata)

                    if category:
                        try:
                            cat_enum = PromptCategory(category)
                            query = query.where(PromptMetadata.category == cat_enum)
                        except ValueError:
                            raise InvalidParamsException(message=f"无效的分类: {category}")

                    if is_active is not None:
                        query = query.where(PromptMetadata.is_active == is_active)

                    query = query.order_by(PromptMetadata.updated_at.desc())
                    result = await session.execute(query)
                    prompts = result.scalars().all()

                    items = [
                        PromptMetadataResponse(
                            id=p.id,
                            prompt_key=p.prompt_key,
                            name_zh=p.name_zh,
                            purpose=p.purpose,
                            category=p.category.value,
                            subcategory=p.subcategory,
                            is_active=p.is_active,
                            is_system=p.is_system,
                            created_at=p.created_at.isoformat() if p.created_at else None,
                            updated_at=p.updated_at.isoformat() if p.updated_at else None,
                        )
                        for p in prompts
                    ]

                    return PromptListResponse(items=items, total=len(items))
            except Exception as e:
                logger.error(f"获取提示词列表失败: {e}")
                raise InternalServerErrorException(message="获取提示词列表失败")

        @router.get("/{prompt_key}", response_model=PromptDetailResponse)
        async def get_prompt_detail(prompt_key: str):
            """获取提示词详情"""
            try:
                from sqlalchemy import select

                from src.models.prompt_metadata import PromptMetadata
                from src.models.prompt_version import PromptVersion

                async with async_session_factory() as session:
                    # 获取元数据
                    result = await session.execute(
                        select(PromptMetadata).where(
                            PromptMetadata.prompt_key == prompt_key
                        )
                    )
                    metadata = result.scalar_one_or_none()
                    if not metadata:
                        raise PromptNotFoundException(prompt_id=prompt_key)

                    # 获取所有版本
                    result = await session.execute(
                        select(PromptVersion)
                        .where(PromptVersion.prompt_key == prompt_key)
                        .order_by(PromptVersion.version_number.desc())
                    )
                    versions = result.scalars().all()

                    version_responses = [
                        PromptVersionResponse(
                            id=v.id,
                            prompt_key=v.prompt_key,
                            version_label=v.version_label,
                            version_number=v.version_number,
                            content=v.content,
                            variables_extracted=v.variables_extracted,
                            change_impact=v.change_impact,
                            change_summary=v.change_summary,
                            created_at=v.created_at.isoformat() if v.created_at else None,
                            created_by=v.created_by,
                        )
                        for v in versions
                    ]

                    current_version = version_responses[0] if version_responses else None

                    return PromptDetailResponse(
                        metadata=PromptMetadataResponse(
                            id=metadata.id,
                            prompt_key=metadata.prompt_key,
                            name_zh=metadata.name_zh,
                            purpose=metadata.purpose,
                            category=metadata.category.value,
                            subcategory=metadata.subcategory,
                            is_active=metadata.is_active,
                            is_system=metadata.is_system,
                            created_at=metadata.created_at.isoformat() if metadata.created_at else None,
                            updated_at=metadata.updated_at.isoformat() if metadata.updated_at else None,
                        ),
                        current_version=current_version,
                        versions=version_responses,
                    )
            except Exception as e:
                logger.error(f"获取提示词详情失败: {e}")
                raise InternalServerErrorException(message="获取提示词详情失败")

        @router.post("/{prompt_key}/update")
        async def update_prompt(prompt_key: str, req: UpdatePromptRequest):
            """更新提示词内容"""
            try:
                import hashlib
                import uuid
                from datetime import datetime

                from sqlalchemy import select

                from src.models.prompt_metadata import PromptMetadata
                from src.models.prompt_version import PromptVersion

                async with async_session_factory() as session:
                    # 获取元数据
                    result = await session.execute(
                        select(PromptMetadata).where(
                            PromptMetadata.prompt_key == prompt_key
                        )
                    )
                    metadata = result.scalar_one_or_none()
                    if not metadata:
                        raise PromptNotFoundException(prompt_id=prompt_key)

                    if metadata.is_system and not req.created_by:
                        raise ForbiddenException(message="系统内置提示词不可修改")

                    # 获取当前版本
                    result = await session.execute(
                        select(PromptVersion)
                        .where(PromptVersion.prompt_key == prompt_key)
                        .order_by(PromptVersion.version_number.desc())
                        .limit(1)
                    )
                    current_version = result.scalar_one_or_none()

                    # 检查内容是否变化
                    content_hash = hashlib.sha256(req.content.encode()).hexdigest()
                    if current_version and current_version.content_hash == content_hash:
                        return {"message": "内容未变化", "version": current_version.version_label}

                    # 提取变量
                    variables = VariableValidator.extract_variables(req.content)

                    # 分析影响
                    current_variables = current_version.variables_extracted if current_version else []
                    impact = await self._impact_analyzer.analyze(
                        prompt_key, req.content, current_variables
                    )

                    # 创建新版本
                    next_version_number = (current_version.version_number + 1) if current_version else 1
                    version_label = f"v{next_version_number}"

                    new_version = PromptVersion(
                        id=str(uuid.uuid4()),
                        prompt_key=prompt_key,
                        version_label=version_label,
                        version_number=next_version_number,
                        content=req.content,
                        content_hash=content_hash,
                        variables_extracted=variables,
                        change_impact=impact.model_dump(),
                        change_summary=req.change_summary,
                        created_by=req.created_by or "system",
                    )
                    session.add(new_version)
                    await session.commit()

                    # 清除缓存
                    await prompt_manager.cache.invalidate_tag(f"prompt:{prompt_key}")

                    return {
                        "message": "提示词已更新",
                        "version": version_label,
                        "impact": impact.model_dump(),
                    }
            except Exception as e:
                logger.error(f"更新提示词失败: {e}")
                raise InternalServerErrorException(message="更新提示词失败")

        @router.post("/{prompt_key}/analyze", response_model=ImpactAnalysisResponse)
        async def analyze_prompt_impact(prompt_key: str, req: UpdatePromptRequest):
            """分析提示词修改影响（不保存）"""
            try:
                from sqlalchemy import select

                from src.models.prompt_version import PromptVersion

                async with async_session_factory() as session:
                    # 获取当前版本变量
                    result = await session.execute(
                        select(PromptVersion)
                        .where(PromptVersion.prompt_key == prompt_key)
                        .order_by(PromptVersion.version_number.desc())
                        .limit(1)
                    )
                    current_version = result.scalar_one_or_none()
                    current_variables = current_version.variables_extracted if current_version else []

                    # 分析影响
                    impact = await self._impact_analyzer.analyze(
                        prompt_key, req.content, current_variables
                    )

                    return ImpactAnalysisResponse(
                        code_references=[ref.model_dump() for ref in impact.code_references],
                        variable_changes=impact.variable_changes.model_dump(),
                        config_dependencies=[dep.model_dump() for dep in impact.config_dependencies],
                        affected_files=impact.affected_files,
                        risk_level=impact.risk_level,
                    )
            except Exception as e:
                logger.error(f"分析提示词影响失败: {e}")
                raise InternalServerErrorException(message="分析提示词影响失败")

        @router.post("/test", response_model=PromptTestResponse)
        async def test_prompt(req: PromptTestRequest):
            """测试提示词渲染"""
            try:
                # 获取提示词内容
                content = await prompt_manager.get_prompt(
                    prompt_key=req.prompt_key,
                    version=req.version,
                    variables=req.variables,
                )

                # 提取使用的变量
                used_vars = VariableValidator.extract_variables(content)
                missing_vars = [v for v in req.variables.keys() if f"{{{v}}}" not in content]

                return PromptTestResponse(
                    rendered_prompt=content,
                    variables_used=used_vars,
                    variables_missing=missing_vars,
                )
            except Exception as e:
                logger.error(f"测试提示词失败: {e}")
                raise InternalServerErrorException(message="测试提示词失败")

        @router.get("/{prompt_key}/compare", response_model=PromptComparisonResponse)
        async def compare_prompt_versions(
            prompt_key: str,
            version_1: str,
            version_2: str,
        ):
            """对比两个提示词版本"""
            try:
                from sqlalchemy import select

                from src.models.prompt_version import PromptVersion

                async with async_session_factory() as session:
                    result = await session.execute(
                        select(PromptVersion).where(
                            PromptVersion.prompt_key == prompt_key,
                            PromptVersion.version_label.in_([version_1, version_2]),
                        )
                    )
                    versions = result.scalars().all()

                    if len(versions) != 2:
                        raise PromptVersionNotFoundException(version_id=f"{version_1}, {version_2}")

                    v1 = next(v for v in versions if v.version_label == version_1)
                    v2 = next(v for v in versions if v.version_label == version_2)

                    # 计算 diff
                    diff = {
                        "added_chars": len(v2.content) - len(v1.content),
                        "version_1_length": len(v1.content),
                        "version_2_length": len(v2.content),
                    }

                    return PromptComparisonResponse(
                        version_1=PromptVersionResponse(
                            id=v1.id,
                            prompt_key=v1.prompt_key,
                            version_label=v1.version_label,
                            version_number=v1.version_number,
                            content=v1.content,
                            variables_extracted=v1.variables_extracted,
                            change_impact=v1.change_impact,
                            change_summary=v1.change_summary,
                            created_at=v1.created_at.isoformat() if v1.created_at else None,
                            created_by=v1.created_by,
                        ),
                        version_2=PromptVersionResponse(
                            id=v2.id,
                            prompt_key=v2.prompt_key,
                            version_label=v2.version_label,
                            version_number=v2.version_number,
                            content=v2.content,
                            variables_extracted=v2.variables_extracted,
                            change_impact=v2.change_impact,
                            change_summary=v2.change_summary,
                            created_at=v2.created_at.isoformat() if v2.created_at else None,
                            created_by=v2.created_by,
                        ),
                        diff=diff,
                    )
            except Exception as e:
                logger.error(f"对比提示词版本失败: {e}")
                raise InternalServerErrorException(message="对比提示词版本失败")

        app.include_router(router)
