import asyncio
import json
import os
import random
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Awaitable, Callable, Dict, List, Optional

from sqlalchemy import select

from src.config.modules.rag.testing import TestCaseGenerationConfig
from src.core.database import db_session_factory
from src.core.llm.factory import LLMFramework, LLMServiceFactoryCompat
from src.core.prompt_impl.facade import prompt_manager
from src.models.test_case import TestCase, TestCaseDraft
from src.schemas import (DifficultyLevel, DraftStatus, GenerationParams,
                         LLMMessage, LLMRequest, TestDomain)
from src.utils.logger import logger


@dataclass
class DraftData:
    """草稿数据载体"""

    query: str = ""
    age: float = 0
    domain: str = ""
    age_stage_label: str = ""
    draft_index: int = 0
    batch_id: Optional[str] = None
    description: str = ""
    expected_knowledge_ids: List[str] = field(default_factory=list)
    expected_keywords: List[str] = field(default_factory=list)
    answer_points: List[str] = field(default_factory=list)
    professional_terms: List[str] = field(default_factory=list)
    generation_params: Optional[dict] = None


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
        self._memory_locks: set = set()
        self._initialized = True

    # ==================== 新方法：多维度矩阵草稿生成 ====================

    async def generate_drafts_matrix(
        self,
        source_document_id: str,
        params: GenerationParams,
        progress_callback: Optional[Callable[[int, int, str], Awaitable[None]]] = None,
        cancellation_event: Optional[asyncio.Event] = None,
        task_id: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        多维度矩阵草稿生成

        Args:
            source_document_id: 文档 ID
            params: 生成参数（包含领域、年龄段、每组合草稿数等）
            progress_callback: 进度回调（由 AsyncTaskManager 自动注入）

        Returns:
            {
                "total_combinations": int,
                "total_generated": int,
                "total_deduplicated": int,
                "duration_seconds": float,
            }
        """
        start_time = time.time()

        # 0. 并发控制：获取分布式锁
        if not await self._acquire_lock(source_document_id):
            raise ValueError("该文档正在生成草稿，请稍后重试")

        try:
            # 1. 获取文档
            from src.models.document import SourceDocument

            async with db_session_factory() as session:
                stmt = select(SourceDocument).where(SourceDocument.id == source_document_id)
                result = await session.execute(stmt)
                doc = result.scalar_one_or_none()
            if not doc:
                raise ValueError(f"源文档不存在: {source_document_id}")

            # 2. 获取文档内容
            content_to_use = doc.content_summary or "暂无摘要内容"
            try:
                if os.path.exists(doc.file_path):
                    with open(doc.file_path, "r", encoding="utf-8", errors="ignore") as f:
                        full_content = f.read()
                        content_to_use = full_content[:4000] if len(full_content) > 4000 else full_content
            except Exception as e:
                logger.warning(f"Failed to load full document content: {e}")

            # 3. 获取配置
            config = await self._get_draft_config()

            # 4. 构建组合矩阵
            combinations = self._build_combinations(params)
            total_combinations = len(combinations)
            total_generated = 0
            total_deduplicated = 0

            # 4.1 初始化任务元数据
            if task_id and task_type:
                from src.utils.di import get_task_state_service
                task_state_service = get_task_state_service()
                await task_state_service.update(
                    task_id=task_id,
                    task_type=task_type,
                    updates={
                        "metadata": {
                            "total_combinations": total_combinations,
                            "current_combination": 0,
                            "generated": 0,
                            "deduplicated": 0,
                            "domain": params.target_domains[0] if params.target_domains else "未知领域",
                            "age_stage": params.age_stages[0] if params.age_stages else "未知年龄段",
                        }
                    }
                )

            # 5. 推送开始事件
            if progress_callback:
                await progress_callback(0, total_combinations, json.dumps({
                    "event": "draft_generation_started",
                    "total_combinations": total_combinations,
                    "total_drafts": total_combinations * params.drafts_per_combination,
                    "mode": params.mode,
                }))

            # 6. 按组合串行执行
            for i, combo in enumerate(combinations):
                try:
                    import asyncio

                    # 6.1 生成该组合的草稿配置（轮询分配查询类型和难度）
                    draft_configs = self._assign_draft_configs(
                        count=params.drafts_per_combination,
                        query_types=params.query_types,
                        difficulties=params.difficulty_levels,
                    )

                    # 6.2 按执行批次打包 LLM 调用
                    batch_size = config.batch_size
                    new_drafts = []
                    for j in range(0, len(draft_configs), batch_size):
                        batch = draft_configs[j:j + batch_size]
                        batch_drafts = await self._generate_batch(
                            doc_id=source_document_id,
                            text=content_to_use,
                            domain=combo["domain"],
                            age_stage=combo["age_stage"],
                            draft_configs=batch,
                            model=params.llm_model,
                            temperature=params.temperature,
                            max_retries=config.max_llm_retries,
                        )
                        new_drafts.extend(batch_drafts)

                    # 6.3 与历史草稿去重
                    existing_drafts = await self._get_existing_drafts(
                        source_document_id, combo["domain"], combo["age_stage_label"]
                    )
                    filtered_drafts = self._deduplicate_against_existing(
                        new_drafts, existing_drafts, config.deduplication_threshold
                    )
                    removed_count = len(new_drafts) - len(filtered_drafts)
                    total_deduplicated += removed_count

                    # 6.4 重新编号 draft_index
                    for idx, draft in enumerate(filtered_drafts):
                        draft.draft_index = idx

                    # 6.5 幂等入库
                    await self._save_drafts_idempotent(
                        filtered_drafts, source_document_id, params.mode
                    )
                    total_generated += len(filtered_drafts)

                    # 6.6 推送组合进度
                    completed = i + 1
                    if progress_callback:
                        await progress_callback(completed, total_combinations, json.dumps({
                            "event": "draft_combination_progress",
                            "current_combination": completed,
                            "total_combinations": total_combinations,
                            "domain": combo["domain"],
                            "age_stage": combo["age_stage_label"],
                            "generated": total_generated,
                            "deduplicated": removed_count,
                        }))

                    # 6.6.1 更新任务元数据
                    if task_id and task_type:
                        await task_state_service.update(
                            task_id=task_id,
                            task_type=task_type,
                            updates={
                                "metadata": {
                                    "total_combinations": total_combinations,
                                    "current_combination": completed,
                                    "generated": total_generated,
                                    "deduplicated": total_deduplicated,
                                    "domain": combo["domain"],
                                    "age_stage": combo["age_stage_label"],
                                }
                            }
                        )

                    # 6.7 组合间间隔
                    await asyncio.sleep(config.combination_interval_seconds)

                except Exception as e:
                    logger.error(f"组合生成失败: {combo['domain']}×{combo['age_stage_label']}: {e}")
                    if progress_callback:
                        await progress_callback(i, total_combinations, json.dumps({
                            "event": "draft_generation_failed",
                            "error": str(e),
                            "combination": f"{combo['domain']}×{combo['age_stage_label']}",
                        }))
                    # 继续下一组合

            # 7. 推送完成事件
            duration = time.time() - start_time
            if progress_callback:
                await progress_callback(total_combinations, total_combinations, json.dumps({
                    "event": "draft_generation_completed",
                    "total": total_generated,
                    "deduplicated": total_deduplicated,
                    "duration": self._format_duration(duration),
                }))

            return {
                "total_combinations": total_combinations,
                "total_generated": total_generated,
                "total_deduplicated": total_deduplicated,
                "duration_seconds": duration,
            }

        finally:
            await self._release_lock(source_document_id)

    # ==================== 辅助方法 ====================

    async def _acquire_lock(self, doc_id: str, ttl: int = 3600) -> bool:
        """获取分布式锁"""
        try:
            from src.core.redis_client import RedisClient
            redis_client = RedisClient.get_client()
            lock_key = f"draft_gen:{doc_id}"
            result = await redis_client.set(lock_key, "1", nx=True, ex=ttl)
            return bool(result)
        except Exception:
            if doc_id in self._memory_locks:
                return False
            self._memory_locks.add(doc_id)
            return True

    async def _release_lock(self, doc_id: str):
        """释放分布式锁"""
        try:
            from src.core.redis_client import RedisClient
            redis_client = RedisClient.get_client()
            lock_key = f"draft_gen:{doc_id}"
            await redis_client.delete(lock_key)
        except Exception:
            self._memory_locks.discard(doc_id)

    def _build_combinations(self, params: GenerationParams) -> List[dict]:
        """构建领域 × 年龄段组合矩阵"""
        combinations = []
        for domain in params.target_domains:
            for age_stage in params.age_stages:
                combinations.append({
                    "domain": domain,
                    "age_stage": age_stage,
                    "age_stage_label": age_stage,
                })
        return combinations

    def _assign_draft_configs(self, count: int, query_types: List[str], difficulties: List[str]) -> List[dict]:
        """
        轮询分配查询类型和难度，保证多样性。
        """
        configs = []

        # Step 1: 优先覆盖 — 每种查询类型 × 难度组合至少一次
        for qt in query_types:
            for diff in difficulties:
                if len(configs) >= count:
                    break
                configs.append({"query_type": qt, "difficulty": diff})
            if len(configs) >= count:
                break

        # Step 2: 剩余按轮询填充
        qt_idx = 0
        diff_idx = 0
        while len(configs) < count:
            qt = query_types[qt_idx % len(query_types)]
            diff = difficulties[diff_idx % len(difficulties)]
            configs.append({"query_type": qt, "difficulty": diff})
            qt_idx += 1
            diff_idx += 1

        # Step 3: 打乱顺序
        random.shuffle(configs)
        return configs

    def _get_age_stage_info(self, label: str, config: TestCaseGenerationConfig) -> dict:
        """从配置获取年龄段月龄范围"""
        for stage in config.age_stages:
            if stage["label"] == label:
                return stage
        return {"age_min_months": 36, "age_max_months": 72}  # 兜底

    async def _get_draft_config(self) -> TestCaseGenerationConfig:
        """从 ConfigManager 读取草稿生成配置（支持热更新）"""
        from src.config import config_manager

        if config_manager.current_config is None:
            await config_manager.load_latest_version()

        current_config = config_manager.current_config or {}

        # 优先从嵌套结构读取（rag.testing）
        testing_config = current_config.get("rag", {}).get("testing", {})
        if testing_config:
            return TestCaseGenerationConfig(**testing_config)

        # 兼容扁平结构：直接提取草稿生成相关字段
        config_keys = [
            "default_domains", "default_age_stages", "default_drafts_per_combination",
            "default_query_types", "default_difficulty_levels", "default_model",
            "deduplication_threshold", "batch_size", "combination_interval_seconds",
            "max_concurrent_tasks", "max_tokens_per_generation", "max_memory_mb",
            "max_llm_retries", "supported_domains", "age_stages", "query_types",
            "difficulty_levels", "enable_breakpoint_resume", "enable_quality_check",
            "enable_relevance_check",
        ]
        flat_config = {k: current_config[k] for k in config_keys if k in current_config}
        if flat_config:
            return TestCaseGenerationConfig(**flat_config)

        return TestCaseGenerationConfig()

    async def _generate_batch(
        self,
        doc_id: str,
        text: str,
        domain: str,
        age_stage: str,
        draft_configs: List[dict],
        model: str,
        temperature: float,
        max_retries: int,
    ) -> List[DraftData]:
        """一次 LLM 调用生成一批草稿"""
        config = await self._get_draft_config()
        age_info = self._get_age_stage_info(age_stage, config)

        configs_json = json.dumps([
            {"index": i, "query_type": c["query_type"], "difficulty": c["difficulty"]}
            for i, c in enumerate(draft_configs)
        ], ensure_ascii=False)

        variables = {
            "text": text,
            "domain": domain,
            "age_stage_label": age_stage,
            "age_min_months": age_info["age_min_months"],
            "age_max_months": age_info["age_max_months"],
            "batch_count": len(draft_configs),
            "batch_configs": configs_json,
        }

        prompt = await prompt_manager.get_prompt(
            "test_case_generation",
            variables=variables,
        )

        llm = LLMServiceFactoryCompat.create(
            framework=LLMFramework.LLAMAINDEX,
            model_name=model,
            scenario="test_case_generation",
            temperature=temperature,
        )

        messages = [
            LLMMessage(
                role="system",
                content="你是专业的儿童发展测试用例草稿生成专家。",
            ),
            LLMMessage(role="user", content=prompt),
        ]

        response = await llm.chat(
            LLMRequest(
                messages=messages,
                model_name=model,
                temperature=temperature,
                max_tokens=4096,
                scenario="test_case_generation",
                prompt_key="test_case_generation",
            )
        )
        response_text = response.content.strip()

        parsed = await self._parse_llm_response(response_text, max_retries)

        for i, draft in enumerate(parsed):
            if i < len(draft_configs):
                draft.domain = domain
                draft.age_stage_label = age_stage
                draft.batch_id = str(uuid.uuid4())

        return parsed

    async def _parse_llm_response(self, llm_output: str, max_retries: int = 2) -> List[DraftData]:
        """解析 LLM 输出，支持 JSON 修复和重试"""
        import json_repair

        for attempt in range(max_retries + 1):
            try:
                json_match = re.search(r"```json\s*(.*?)\s*```", llm_output, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    start = llm_output.find("{")
                    end = llm_output.rfind("}")
                    if start != -1 and end != -1:
                        json_str = llm_output[start:end + 1]
                    else:
                        json_str = llm_output

                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    data = json_repair.loads(json_str)

                if not isinstance(data, dict):
                    if isinstance(data, list):
                        data = {"drafts": data}
                    else:
                        raise ValueError("LLM response did not parse into a JSON object")

                draft_list = data.get("drafts", [])
                if not isinstance(draft_list, list):
                    if isinstance(data, list):
                        draft_list = data
                    else:
                        raise ValueError("'drafts' field is missing or not a list")

                return self._validate_and_convert_drafts(draft_list)

            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"LLM parse attempt {attempt + 1} failed: {e}")
                    continue
                else:
                    logger.error(f"LLM output parse failed after {max_retries} retries: {e}")
                    return []

    def _validate_and_convert_drafts(self, raw_drafts: List[dict]) -> List[DraftData]:
        """验证并转换草稿数据"""
        drafts = []
        for raw in raw_drafts:
            for field_name in ["expected_keywords", "answer_points", "professional_terms"]:
                if field_name in raw and isinstance(raw[field_name], str):
                    raw[field_name] = [raw[field_name]]
            drafts.append(DraftData(
                query=raw.get("query", ""),
                age=float(raw.get("age", 0)),
                description=raw.get("description", ""),
                expected_knowledge_ids=raw.get("expected_knowledge_ids", []),
                expected_keywords=raw.get("expected_keywords", []),
                answer_points=raw.get("answer_points", []),
                professional_terms=raw.get("professional_terms", []),
            ))
        return drafts

    async def _get_existing_drafts(self, doc_id: str, domain: str, age_stage_label: str) -> List[TestCaseDraft]:
        """查询历史草稿"""
        domain_enum = self._map_domain(domain)

        async with db_session_factory() as session:
            stmt = select(TestCaseDraft).where(
                TestCaseDraft.source_document_id == doc_id,
                TestCaseDraft.age_stage_label == age_stage_label,
            )
            if domain_enum:
                stmt = stmt.where(TestCaseDraft.domain == domain_enum)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    def _deduplicate_against_existing(
        self, new_drafts: List[DraftData], existing_drafts: List[TestCaseDraft], threshold: float
    ) -> List[DraftData]:
        """与历史草稿去重"""
        from difflib import SequenceMatcher

        filtered = []
        for new_draft in new_drafts:
            is_dup = False
            for existing in existing_drafts:
                query_sim = SequenceMatcher(None, new_draft.query, existing.query).ratio()
                domain_match = 1.0 if new_draft.domain == existing.domain.value else 0.5
                age_diff = abs(float(new_draft.age) - float(existing.age))
                age_factor = max(0, 1 - age_diff / 24)
                similarity = query_sim * 0.7 * domain_match + age_factor * 0.3
                if similarity >= threshold:
                    is_dup = True
                    break
            if not is_dup:
                filtered.append(new_draft)
        return filtered

    async def _save_drafts_idempotent(self, drafts: List[DraftData], doc_id: str, mode: str):
        """
        幂等入库
        mode="append": 不存在则插入，存在则跳过
        mode="overwrite": 不存在则插入，存在则更新
        """
        async with db_session_factory() as session:
            for draft in drafts:
                domain_enum = self._map_domain(draft.domain)

                stmt = select(TestCaseDraft).where(
                    TestCaseDraft.source_document_id == doc_id,
                    TestCaseDraft.domain == domain_enum,
                    TestCaseDraft.age_stage_label == draft.age_stage_label,
                    TestCaseDraft.draft_index == draft.draft_index,
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing and mode == "overwrite":
                    existing.query = draft.query
                    existing.description = draft.description
                    existing.expected_keywords = draft.expected_keywords
                    existing.answer_points = draft.answer_points
                    existing.professional_terms = draft.professional_terms
                    existing.version += 1
                elif not existing:
                    new_draft = TestCaseDraft(
                        id=str(uuid.uuid4()),
                        source_document_id=doc_id,
                        query=draft.query,
                        age=draft.age,
                        domain=domain_enum,
                        description=draft.description,
                        age_stage_label=draft.age_stage_label,
                        draft_index=draft.draft_index,
                        batch_id=draft.batch_id,
                        version=1,
                        expected_knowledge_ids=draft.expected_knowledge_ids or [],
                        expected_keywords=draft.expected_keywords or [],
                        answer_points=draft.answer_points or [],
                        professional_terms=draft.professional_terms or [],
                        generation_params=draft.generation_params,
                        status=DraftStatus.DRAFT,
                    )
                    session.add(new_draft)

            await session.commit()

    def _map_domain(self, domain_str: str) -> TestDomain:
        """领域字符串转 TestDomain Enum"""
        domain_mapping = {
            "粗大动作": TestDomain.GROSS_MOTOR,
            "精细动作": TestDomain.FINE_MOTOR,
            "语言发展": TestDomain.LANGUAGE,
            "认知能力": TestDomain.COGNITIVE,
            "社交情感": TestDomain.SOCIAL_EMOTIONAL,
            "感觉统合": TestDomain.SENSORY_INTEGRATION,
        }
        return domain_mapping.get(domain_str, TestDomain.SENSORY_INTEGRATION)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """格式化时间"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m{secs}s"

    async def create_draft(
        self,
        source_document_id: str,
        query: str,
        age: int,
        domain: str,
        expected_knowledge_ids: Optional[List[str]] = None,
        expected_keywords: Optional[List[str]] = None,
        description: str = "",
        answer_points: Optional[List[str]] = None,
        professional_terms: Optional[List[str]] = None,
        age_requirement: str = "",
    ) -> TestCaseDraft:
        """手动创建单个草稿"""
        from src.models.test_case import SourceDocument, TestDomain

        # 验证来源文档是否存在
        async with self.db_session_factory() as session:
            stmt = select(SourceDocument).where(SourceDocument.id == source_document_id)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()
        if not doc:
            raise ValueError(f"源文档不存在: {source_document_id}")

        # 领域映射
        domain_mapping = {
            "gross_motor": TestDomain.GROSS_MOTOR,
            "fine_motor": TestDomain.FINE_MOTOR,
            "language": TestDomain.LANGUAGE,
            "cognitive": TestDomain.COGNITIVE,
            "social_emotional": TestDomain.SOCIAL_EMOTIONAL,
            "sensory_integration": TestDomain.SENSORY_INTEGRATION,
            "粗大动作": TestDomain.GROSS_MOTOR,
            "精细动作": TestDomain.FINE_MOTOR,
            "语言发展": TestDomain.LANGUAGE,
            "认知能力": TestDomain.COGNITIVE,
            "社交情感": TestDomain.SOCIAL_EMOTIONAL,
            "感觉统合": TestDomain.SENSORY_INTEGRATION,
        }
        
        try:
            test_domain = domain_mapping.get(domain, TestDomain.SENSORY_INTEGRATION)
            if isinstance(test_domain, str):
                test_domain = TestDomain(test_domain)
        except Exception:
            test_domain = TestDomain.SENSORY_INTEGRATION

        draft = TestCaseDraft(
            id=str(uuid.uuid4()),
            source_document_id=source_document_id,
            query=query,
            age=age,
            domain=test_domain,
            description=description,
            expected_knowledge_ids=expected_knowledge_ids or [],
            expected_keywords=expected_keywords or [],
            answer_points=answer_points or [],
            professional_terms=professional_terms or [],
            age_requirement=age_requirement,
            status=DraftStatus.DRAFT,
        )

        async with self.db_session_factory() as session:
            session.add(draft)
            await session.commit()
            await session.refresh(draft)

        return draft

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
