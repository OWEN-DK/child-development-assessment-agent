"""RAG测试用例生成服务

支持按章节分块并行生成、多维度差异化、MinHash去重、断点续传
"""

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import jieba
from datasketch import MinHash, MinHashLSH

from src.config import ConfigManager
from src.config.modules.rag.testing import (TestCaseGenerationConfig,
                                            calculate_draft_count_by_pages)
from src.core.database import db_session_factory
from src.core.llm.factory import LLMServiceFactory
from src.core.prompts_fallback import TEST_CASE_DRAFT_GENERATION_PROMPT
from src.repository.test_case_repository import TestCaseDraftRepository
from src.utils.logger import logger


class DraftDeduplicator:
    """基于 MinHash + LSH 的高效去重器（分词级别，适配中文短文本）

    使用 datasketch 库实现真正的 MinHash + LSH 算法：
    - MinHash: 将文本转换为固定长度的签名向量，估计 Jaccard 相似度
    - LSH (Locality Sensitive Hashing): 快速查找相似候选，避免全量比较

    性能优势：
    - 时间复杂度：O(1) 近似查询（vs O(n) 全量比较）
    - 空间复杂度：O(n * num_perm) 存储签名
    - 适用于大规模数据（10万+条草稿）
    """

    def __init__(self, threshold: float = 0.8, num_perm: int = 128):
        """初始化去重器

        Args:
            threshold: Jaccard 相似度阈值，超过此值视为重复
            num_perm: MinHash 排列数，越大越精确但越慢（默认 128）
        """
        self.threshold = threshold
        self.num_perm = num_perm
        self.existing_queries: Dict[int, str] = {}  # idx -> query
        self._lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
        self._counter = 0

    def _compute_minhash(self, query: str) -> MinHash:
        """计算查询的 MinHash 签名

        Args:
            query: 查询文本

        Returns:
            MinHash 对象
        """
        m = MinHash(num_perm=self.num_perm)
        # 使用 jieba 分词
        words = jieba.lcut(query)
        for word in words:
            m.update(word.encode("utf-8"))
        return m

    def add_existing(self, query: str, idx: int = None):
        """添加已有查询到去重器

        Args:
            query: 查询文本
            idx: 索引 ID（可选，默认自增）
        """
        if idx is None:
            idx = self._counter
            self._counter += 1

        self.existing_queries[idx] = query
        minhash = self._compute_minhash(query)
        self._lsh.insert(str(idx), minhash)

    def is_duplicate(self, query: str) -> bool:
        """检查查询是否重复

        Args:
            query: 查询文本

        Returns:
            True 如果存在相似度 >= threshold 的已有查询
        """
        minhash = self._compute_minhash(query)
        # LSH 查询返回所有可能相似的候选 ID
        candidates = self._lsh.query(minhash)
        return len(candidates) > 0


class RagTestCaseService:
    """RAG测试用例生成服务"""

    def __init__(self):
        self.test_case_draft_repo = TestCaseDraftRepository(db_session_factory)
        self.config_manager = ConfigManager()
        self.llm_service = LLMServiceFactory()
        self._deduplicator_cache: Dict[str, DraftDeduplicator] = {}
        self._chapter_cache: Dict[int, List[Tuple[str, str]]] = {}

    def _get_testing_config(self) -> TestCaseGenerationConfig:
        """从 ConfigManager 加载测试用例生成配置"""
        try:
            full_config = self.config_manager.get_full_config()
            testing_data = full_config.get("rag_testing", {})
            return (
                TestCaseGenerationConfig(**testing_data)
                if testing_data
                else TestCaseGenerationConfig()
            )
        except Exception:
            return TestCaseGenerationConfig()

    async def batch_generate_drafts(
        self,
        document_id: str,
        document_content: str,
        page_count: int = None,
        domain: str = None,
    ) -> List[dict]:
        """批量生成测试用例草稿（按章节分块并行 + 多维度差异化 + 断点续传）"""
        config: TestCaseGenerationConfig = self._get_testing_config()

        # 根据文档长度动态计算草稿数量
        if page_count:
            target_count = calculate_draft_count_by_pages(page_count, config)
        else:
            target_count = config.test_case_draft_default_count

        max_concurrent = config.test_case_draft_concurrency
        duplicate_threshold = config.test_case_draft_deduplication_threshold

        # 生成配置指纹和批次ID
        config_str = f"{domain or 'all'}:{target_count}"
        config_hash = hashlib.md5(config_str.encode()).hexdigest()[:8]
        generation_batch_id = f"doc_{document_id}_{config_hash}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"

        # 查询同批次已生成的草稿（断点续传）
        if config.enable_breakpoint_resume:
            existing_drafts = await self.test_case_draft_repo.get_by_filter(
                source_document_id=document_id,
                generation_batch_id=generation_batch_id,
            )
        else:
            existing_drafts = []

        remaining_count = target_count - len(existing_drafts)

        if remaining_count <= 0:
            logger.info(
                f"文档 {document_id} 批次 {generation_batch_id} 已生成足够的草稿 ({len(existing_drafts)}条)，跳过"
            )
            return existing_drafts

        logger.info(
            f"需要为文档 {document_id} 批次 {generation_batch_id} 生成 {remaining_count} 条草稿"
        )

        # 按章节分块
        chapters = await self._get_document_chapters(document_id, document_content)

        # 初始化去重器
        cache_key = f"dedup:{document_id}:{generation_batch_id}"
        if cache_key not in self._deduplicator_cache:
            self._deduplicator_cache[cache_key] = DraftDeduplicator(
                threshold=duplicate_threshold
            )
        deduplicator = self._deduplicator_cache[cache_key]

        for idx, d in enumerate(existing_drafts):
            deduplicator.add_existing(d.query, idx)

        # 按章节并行生成草稿
        all_drafts = list(existing_drafts)
        semaphore = asyncio.Semaphore(max_concurrent)

        # 计算每个章节需要生成的草稿数量（按章节长度比例分配）
        total_chapter_length = sum(len(content) for _, content in chapters)
        chapter_tasks = []

        for chapter_title, chapter_content in chapters:
            if len(chapter_content) < 500:  # 跳过过短章节
                continue

            # 按长度比例分配数量
            chapter_count = max(
                5, int(remaining_count * len(chapter_content) / total_chapter_length)
            )

            chapter_tasks.append(
                {
                    "chapter_title": chapter_title,
                    "chapter_content": chapter_content,
                    "count": chapter_count,
                    "domain": domain,
                }
            )

        async def generate_chapter_drafts(task):
            async with semaphore:
                return await self._generate_chapter_drafts(
                    document_id=document_id,
                    generation_batch_id=generation_batch_id,
                    deduplicator=deduplicator,
                    **task,
                )

        results = await asyncio.gather(
            *[generate_chapter_drafts(task) for task in chapter_tasks],
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, list):
                all_drafts.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"章节生成失败: {result}")

        logger.info(
            f"文档 {document_id} 批次 {generation_batch_id} 共生成 {len(all_drafts) - len(existing_drafts)} 条新草稿，总计 {len(all_drafts)} 条"
        )
        return all_drafts

    async def _get_document_chapters(
        self, document_id: str, document_content: str
    ) -> List[Tuple[str, str]]:
        """获取文档章节分块"""
        # 检查缓存
        if document_id in self._chapter_cache:
            return self._chapter_cache[document_id]

        # 简单按标题分割文档
        chapters = self._split_by_headings(document_content)
        self._chapter_cache[document_id] = chapters
        return chapters

    def _split_by_headings(self, content: str) -> List[Tuple[str, str]]:
        """按标题分割文档为章节"""
        import re

        # 匹配 Markdown 标题或带编号的标题
        pattern = r"^(#{1,3}\s+.+|第[一二三四五六七八九十\d]+[章部分].+)$"
        lines = content.split("\n")
        chapters = []
        current_title = "引言"
        current_content = []

        for line in lines:
            if re.match(pattern, line.strip()):
                if current_content:
                    chapters.append((current_title, "\n".join(current_content)))
                current_title = line.strip().lstrip("# ").strip()
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            chapters.append((current_title, "\n".join(current_content)))

        # 如果只有一个章节，按固定长度分割
        if len(chapters) <= 1:
            chunk_size = 5000
            content_text = chapters[0][1] if chapters else content
            chapters = []
            for i in range(0, len(content_text), chunk_size):
                chunk = content_text[i : i + chunk_size]
                chapters.append((f"第{i // chunk_size + 1}部分", chunk))

        return chapters

    async def _generate_chapter_drafts(
        self,
        document_id: str,
        generation_batch_id: str,
        chapter_title: str,
        chapter_content: str,
        count: int,
        domain: Optional[str],
        deduplicator: DraftDeduplicator,
    ) -> List[dict]:
        """按章节生成草稿，覆盖多维度"""
        config: TestCaseGenerationConfig = self._get_testing_config()
        new_drafts = []

        # 多维度差异化生成策略
        age_stages = config.age_stages
        query_types = config.query_types
        difficulty_levels = config.difficulty_levels

        # 计算每个维度组合需要生成的数量
        dimension_tasks = []
        remaining = count

        for age_stage in age_stages:
            for query_type in query_types:
                for difficulty in difficulty_levels:
                    min_count = max(
                        age_stage.get("min_count", 10) // len(config.supported_domains),
                        query_type.get("min_count", 15) // len(age_stages),
                        difficulty.get("min_count", 20)
                        // (len(age_stages) * len(query_types)),
                    )
                    if min_count > 0 and remaining > 0:
                        actual_count = min(min_count, remaining)
                        dimension_tasks.append(
                            {
                                "age_stage": age_stage,
                                "query_type": query_type,
                                "difficulty_level": difficulty,
                                "count": actual_count,
                            }
                        )
                        remaining -= actual_count

        # 如果还有剩余，平均分配
        if remaining > 0 and dimension_tasks:
            extra = remaining // len(dimension_tasks)
            for task in dimension_tasks:
                task["count"] += extra

        # 并行生成（按 batch_size 分批调用 LLM）
        batch_size = config.test_case_draft_batch_size
        for task in dimension_tasks:
            if task["count"] <= 0:
                continue

            # 分批调用，每批生成 batch_size 条草稿
            batches = (task["count"] + batch_size - 1) // batch_size
            for batch_idx in range(batches):
                current_batch_count = min(
                    batch_size, task["count"] - batch_idx * batch_size
                )
                if current_batch_count <= 0:
                    continue

                try:
                    prompt = TEST_CASE_DRAFT_GENERATION_PROMPT.render(
                        document_content=chapter_content[:10000],
                        domain=domain,
                        age_stage=task["age_stage"],
                        query_type=task["query_type"],
                        difficulty_level=task["difficulty_level"],
                        count=current_batch_count,
                    )

                    llm = await self.llm_service.create("test_case_generation")
                    response = await llm.ainvoke(prompt)
                    content = response.content.strip()

                    # 清理markdown代码块
                    if content.startswith("```json"):
                        content = content[7:-3].strip()
                    elif content.startswith("```"):
                        content = content[3:-3].strip()

                    data = json.loads(content)
                    if isinstance(data, dict):
                        data = [data]
                    elif not isinstance(data, list):
                        continue

                    for result in data:
                        # 完整性校验
                        required_fields = [
                            "query",
                            "domain",
                            "age_min",
                            "age_max",
                            "expected_keywords",
                        ]
                        if not all(f in result for f in required_fields):
                            logger.warning("草稿字段不完整，跳过")
                            continue

                        # 去重校验
                        if deduplicator.is_duplicate(result["query"]):
                            logger.info(f"草稿重复，跳过: {result['query'][:30]}...")
                            continue

                        # 年龄范围校验
                        if (
                            result["age_min"] < task["age_stage"]["age_min"]
                            or result["age_max"] > task["age_stage"]["age_max"]
                        ):
                            logger.warning(
                                f"草稿年龄范围不符合要求，跳过: {result['age_min']}-{result['age_max']}"
                            )
                            continue

                        # 相关性校验
                        if config.enable_relevance_check:
                            relevance_score = self._calculate_relevance(
                                result["query"],
                                chapter_content,
                                result.get("expected_keywords", []),
                            )
                            if (
                                relevance_score
                                < config.test_case_draft_relevance_threshold
                            ):
                                logger.info(
                                    f"草稿相关性过低 ({relevance_score:.2f})，跳过: {result['query'][:30]}..."
                                )
                                continue

                        # 保存到数据库
                        draft = await self.test_case_draft_repo.create(
                            {
                                "id": str(
                                    hashlib.md5(
                                        f"{document_id}{result['query']}{datetime.now().isoformat()}".encode()
                                    ).hexdigest()
                                )[:16],
                                "source_document_id": document_id,
                                "generation_batch_id": generation_batch_id,
                                "query": result["query"],
                                "domain": result["domain"],
                                "age": result.get("age_min", 0),
                                "expected_keywords": result.get(
                                    "expected_keywords", []
                                ),
                                "description": result.get("description", ""),
                                "status": "draft",
                            }
                        )

                        new_drafts.append(draft)
                        deduplicator.add_existing(
                            result["query"], len(deduplicator.existing_queries)
                        )

                except Exception as e:
                    logger.warning(
                        f"生成草稿失败 (章节: {chapter_title}, 批次: {batch_idx + 1}/{batches}): {e}"
                    )
                    continue

        return new_drafts

    def _calculate_relevance(
        self, query: str, document_content: str, keywords: List[str]
    ) -> float:
        """计算草稿查询与文档内容的相关性（简单关键词匹配）"""
        if not keywords:
            return 0.0

        query_words = set(jieba.lcut(query))
        doc_words = set(jieba.lcut(document_content[:5000]))

        matched = sum(1 for kw in keywords if kw in doc_words)
        return matched / len(keywords) if keywords else 0.0


# 全局单例（懒加载）
_rag_test_case_service_instance = None


def get_rag_test_case_service():
    """获取 RagTestCaseService 单例（懒加载）"""
    global _rag_test_case_service_instance
    if _rag_test_case_service_instance is None:
        _rag_test_case_service_instance = RagTestCaseService()
    return _rag_test_case_service_instance
