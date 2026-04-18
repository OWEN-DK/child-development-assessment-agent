import json
import os
import re
import uuid
from datetime import datetime
from typing import Awaitable, Callable, Dict, List, Optional

from sqlalchemy import select

from src.config import settings
from src.core.database import db_session_factory
from src.core.llm.factory import LLMFramework, LLMServiceFactory
from src.core.prompts_fallback import TEST_CASE_DRAFT_GENERATION_PROMPT
from src.models.test_case import TestCase, TestCaseDraft
from src.schemas import (DifficultyLevel, DraftStatus, GenerationParams,
                         LLMMessage, LLMRequest, TestDomain)
from src.utils.logger import logger


class DraftService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DraftService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.db_session_factory = db_session_factory
        self._initialized = True

    async def generate_test_case_drafts(
        self,
        source_document_id: str,
        params: GenerationParams,
        progress_callback: Optional[Callable[[int, int, str], Awaitable[None]]] = None,
    ) -> List[TestCaseDraft]:
        from src.models.test_case import SourceDocument

        async with self.db_session_factory() as session:
            stmt = select(SourceDocument).where(SourceDocument.id == source_document_id)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()
        if not doc:
            raise ValueError(f"源文档不存在: {source_document_id}")

        content_to_use = doc.content_summary or "暂无摘要内容"
        try:
            if os.path.exists(doc.file_path):
                with open(doc.file_path, "r", encoding="utf-8", errors="ignore") as f:
                    full_content = f.read()
                    if len(full_content) > 4000:
                        content_to_use = full_content[:4000] + "..."
                    else:
                        content_to_use = full_content
                    logger.info(
                        f"Loaded full document content, length: {len(content_to_use)}"
                    )
        except Exception as e:
            logger.warning(f"Failed to load full document content, using summary: {e}")

        if progress_callback:
            await progress_callback(0, params.count, "已加载文档内容，开始生成测试用例")

        batch_size = 3
        total_needed = params.count
        all_drafts = []
        generated_count = 0

        try:
            if not settings.dashscope_api_key:
                raise ValueError("DASHSCOPE_API_KEY 未配置，无法调用大模型")

            import json_repair

            def ensure_list(val):
                if isinstance(val, list):
                    return val
                if isinstance(val, str):
                    return [val] if val else []
                return []

            while generated_count < total_needed:
                current_batch_count = min(batch_size, total_needed - generated_count)
                batch_num = generated_count // batch_size + 1
                total_batch = (total_needed + batch_size - 1) // batch_size
                logger.info(
                    f"Generating batch {batch_num}/{total_batch}, count: {current_batch_count}"
                )
                if progress_callback:
                    await progress_callback(
                        generated_count,
                        params.count,
                        f"正在生成第 {batch_num}/{total_batch} 批测试用例"
                    )

                prompt = TEST_CASE_DRAFT_GENERATION_PROMPT.format(
                    count=current_batch_count,
                    text=content_to_use,
                    domains=",".join(params.target_domains)
                    if params.target_domains
                    else "通用领域",
                    age_range_min=params.age_range[0],
                    age_range_max=params.age_range[1],
                )

                try:
                    llm = LLMServiceFactory.create(
                        framework=LLMFramework.LLAMAINDEX,
                        model_name=params.llm_model,
                        scenario="test_case_generation",
                        temperature=params.temperature,
                    )

                    messages = [
                        LLMMessage(
                            role="system",
                            content="你是一个专业的测试用例生成专家，根据文档内容生成相关的测试用例。",
                        ),
                        LLMMessage(role="user", content=prompt),
                    ]

                    response = await llm.chat(
                        LLMRequest(
                            messages=messages,
                            model_name=params.llm_model,
                            temperature=params.temperature,
                            max_tokens=4096,
                            scenario="test_case_generation",
                            prompt_key="test_case_draft_generation",
                        )
                    )
                    response_text = response.content.strip()

                    json_match = re.search(
                        r"```json\s*(.*?)\s*```", response_text, re.DOTALL
                    )
                    if json_match:
                        json_str = json_match.group(1)
                    else:
                        start = response_text.find("{")
                        end = response_text.rfind("}")
                        if start != -1 and end != -1:
                            json_str = response_text[start : end + 1]
                        else:
                            json_str = response_text

                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError as je:
                        logger.warning(
                            f"Standard JSON decode failed, attempting repair: {je}"
                        )
                        data = json_repair.loads(json_str)

                    if not isinstance(data, dict):
                        if isinstance(data, list):
                            data = {"drafts": data}
                        else:
                            raise ValueError(
                                "LLM response did not parse into a JSON object"
                            )

                    draft_list = data.get("drafts", [])
                    if not isinstance(draft_list, list):
                        if isinstance(data, list):
                            draft_list = data
                        else:
                            raise ValueError("'drafts' field is missing or not a list")

                    for item in draft_list:
                        if generated_count >= total_needed:
                            break
                        
                        domain_mapping = {
                            "粗大动作": TestDomain.GROSS_MOTOR,
                            "精细动作": TestDomain.FINE_MOTOR,
                            "语言发展": TestDomain.LANGUAGE,
                            "认知能力": TestDomain.COGNITIVE,
                            "社交情感": TestDomain.SOCIAL_EMOTIONAL,
                            "感觉统合": TestDomain.SENSORY_INTEGRATION,
                        }
                        
                        try:
                            target_domain_str = params.target_domains[0] if params.target_domains else "感觉统合"
                            test_domain = domain_mapping.get(target_domain_str, TestDomain.SENSORY_INTEGRATION)
                        except Exception:
                            test_domain = TestDomain.SENSORY_INTEGRATION
                            
                        draft = TestCaseDraft(
                            id=str(uuid.uuid4()),
                            source_document_id=source_document_id,
                            query=item.get("query", ""),
                            age=params.age_range[0],
                            domain=test_domain,
                            description=item.get("description", ""),
                            expected_knowledge_ids=[],
                            expected_keywords=ensure_list(
                                item.get("expected_keywords", [])
                            ),
                            answer_points=ensure_list(item.get("answer_points", [])),
                            professional_terms=ensure_list(
                                item.get("professional_terms", [])
                            ),
                            age_requirement=f"{params.age_range[0]}-{params.age_range[1]}岁",
                            generation_params=params.model_dump(mode="json", exclude_unset=True)
                            if hasattr(params, "model_dump")
                            else {k: str(v) for k, v in params.__dict__.items() if not k.startswith("_")},
                            status=DraftStatus.DRAFT,
                        )
                        all_drafts.append(draft)
                        generated_count += 1
                        if progress_callback:
                            await progress_callback(
                                generated_count,
                                params.count,
                                f"已生成 {generated_count}/{params.count} 个测试用例"
                            )

                except Exception as batch_e:
                    logger.error(f"Batch generation failed: {batch_e}")
                    if generated_count == 0:
                        raise
                    break

            logger.info(
                f"Generated {len(all_drafts)} drafts for document {source_document_id}"
            )

            async with self.db_session_factory() as session:
                try:
                    for draft in all_drafts:
                        session.add(draft)
                    await session.commit()
                    for draft in all_drafts:
                        await session.refresh(draft)
                except Exception as e:
                    logger.error(f"Failed to save test case drafts: {str(e)}", exc_info=True)
                    await session.rollback()
                    raise

            return all_drafts

        except Exception as e:
            logger.error(f"Failed to generate drafts using LLM: {e}", exc_info=True)
            raise ValueError(f"生成测试用例草稿失败: {str(e)}")

    async def list_drafts(
        self, source_document_id: Optional[str] = None
    ) -> List[TestCaseDraft]:
        async with self.db_session_factory() as session:
            stmt = select(TestCaseDraft).where(
                TestCaseDraft.status == DraftStatus.DRAFT
            )
            if source_document_id:
                stmt = stmt.where(
                    TestCaseDraft.source_document_id == source_document_id
                )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_draft(self, draft_id: str) -> Optional[TestCaseDraft]:
        async with self.db_session_factory() as session:
            return await session.get(TestCaseDraft, draft_id)

    async def update_draft(
        self, draft_id: str, updates: Dict
    ) -> Optional[TestCaseDraft]:
        async with self.db_session_factory() as session:
            draft = await session.get(TestCaseDraft, draft_id)
            if not draft:
                return None

            for key, value in updates.items():
                if hasattr(draft, key):
                    setattr(draft, key, value)
            draft.updated_at = datetime.now()
            await session.commit()
            await session.refresh(draft)
            return draft

    async def review_draft(self, draft_id: str, action: str) -> Optional[TestCaseDraft]:
        async with self.db_session_factory() as session:
            try:
                draft = await session.get(TestCaseDraft, draft_id)
                if not draft:
                    return None

                if action == "reviewed":
                    draft.status = DraftStatus.REVIEWED
                    draft.updated_at = datetime.now()
                    test_case = TestCase(
                        id=str(uuid.uuid4()),
                        query=draft.query,
                        age=draft.age,
                        domain=draft.domain,
                        expected_knowledge_ids=draft.expected_knowledge_ids,
                        expected_keywords=draft.expected_keywords,
                        description=draft.description,
                        professional_terms=draft.professional_terms,
                        source_document_id=draft.source_document_id,
                        expected_knowledge_count=len(draft.expected_knowledge_ids) if draft.expected_knowledge_ids else 0,
                        answer_points_summary=draft.answer_points[0] if draft.answer_points and len(draft.answer_points) > 0 else "",
                        min_age_requirement=draft.age,
                        max_age_requirement=draft.age + 1,
                        difficulty_level=DifficultyLevel.MEDIUM
                    )
                    session.add(test_case)
                    draft.status = DraftStatus.IMPORTED
                    await session.commit()
                    await session.refresh(draft)
                    logger.info(
                        f"Draft {draft_id} reviewed and imported as test case {test_case.id}"
                    )
                elif action == "rejected":
                    deleted_draft = draft.model_copy()
                    await session.delete(draft)
                    await session.commit()
                    logger.info(f"Draft {draft_id} rejected and deleted")
                    return deleted_draft
                else:
                    raise ValueError(f"无效的审核操作: {action}")

                return draft
            except Exception as e:
                logger.error(f"审核草稿失败: {str(e)}", exc_info=True)
                await session.rollback()
                raise ValueError(f"审核草稿失败: {str(e)}")

    async def import_reviewed_drafts(self, draft_ids: List[str]) -> Dict:
        imported_ids = []
        failed_ids = []

        async with self.db_session_factory() as session:
            stmt = select(TestCaseDraft).where(TestCaseDraft.id.in_(draft_ids))
            result = await session.execute(stmt)
            drafts = result.scalars().all()
            
            draft_map = {draft.id: draft for draft in drafts}
            
            for draft_id in draft_ids:
                draft = draft_map.get(draft_id)
                if not draft:
                    failed_ids.append({"draft_id": draft_id, "error": "草稿不存在"})
                    continue

                if draft.status != DraftStatus.REVIEWED:
                    failed_ids.append({"draft_id": draft_id, "error": "草稿未通过审核"})
                    continue

                test_case = TestCase(
                    id=str(uuid.uuid4()),
                    query=draft.query,
                    age=draft.age,
                    domain=draft.domain,
                    expected_knowledge_ids=draft.expected_knowledge_ids,
                    expected_keywords=draft.expected_keywords,
                    description=draft.description,
                    answer_points=draft.answer_points,
                    professional_terms=draft.professional_terms,
                    age_requirement=draft.age_requirement,
                    source_document_id=draft.source_document_id,
                )

                session.add(test_case)
                draft.status = DraftStatus.IMPORTED
                draft.updated_at = datetime.now()
                imported_ids.append(test_case.id)

            await session.commit()

        return {
            "imported_count": len(imported_ids),
            "failed_count": len(failed_ids),
            "test_case_ids": imported_ids,
            "errors": failed_ids,
        }

    async def delete_draft(self, draft_id: str) -> bool:
        from src.repository import TestCaseDraftRepository
        
        repo = TestCaseDraftRepository(self.db_session_factory)
        existing = await repo.get_by_id(draft_id)
        if not existing:
            return False
        result = await repo.delete(draft_id)
        if result:
            logger.info(f"Draft deleted: {draft_id}")
        return result

    async def batch_delete_drafts(self, draft_ids: List[str]) -> int:
        from src.repository import TestCaseDraftRepository
        
        repo = TestCaseDraftRepository(self.db_session_factory)
        deleted_count = 0
        for draft_id in draft_ids:
            if await repo.delete(draft_id):
                deleted_count += 1
                logger.info(f"Draft deleted: {draft_id}")
        return deleted_count


draft_service = DraftService()
