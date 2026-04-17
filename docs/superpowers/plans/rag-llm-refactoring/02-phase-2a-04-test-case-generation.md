# Phase 2A.2: 测试用例生成优化

> **前置文档:** [Overview](./02-phase-2a-00-overview.md) | [报告生命周期管理](./02-phase-2a-03-report-lifecycle.md)
> **状态:** ⏳ 完全待实现
> **预计工期:** 1.5人天

### 🟠 2.4 测试用例草稿生成优化（⏳ 完全待实现，1.5人天）
> 优化目标：生成速度提升 500%（基准：当前单文档生成10条约2分钟 → 目标：单文档生成100条<5分钟），草稿重复率 < 5%，领域覆盖率 > 90%
> LLM场景配置：复用Phase 1的`content_generation`场景，或新增`test_case_generation`场景（需在LLM配置中定义）

#### Task 2.4.1: 优化提示词模板
**Files:**
- Modify: `src/core/prompt/templates/test_case_draft_generation.py`
- Test: `tests/core/prompt/test_test_case_prompt.py`

- [ ] **Step 1: 编写提示词测试用例**
```python
def test_test_case_prompt():
    from src.core.prompt.templates import test_case_draft_generation
    
    prompt = test_case_draft_generation.render(
        document_content="这是一份关于0-3岁儿童粗大运动发展的指南",
        domain="感觉统合",
        age_stage={"name": "0-1岁", "age_min": 0, "age_max": 1},
        query_type={"name": "事实性查询", "description": "是什么/有什么"},
        difficulty_level={"name": "入门级", "description": "基础概念"},
        count=10
    )
    
    assert "生成10个测试用例" in prompt
    assert "年龄范围0-1岁" in prompt
    assert "查询类型：事实性查询" in prompt
    assert "难度级别：入门级" in prompt
    assert "返回JSON格式" in prompt
```

- [ ] **Step 2: 升级提示词模板**
修改`src/core/prompt/templates/test_case_draft_generation.py`:
```python
from src.core.prompt.base import BasePromptTemplate

class TestCaseDraftGenerationPrompt(BasePromptTemplate):
    template = '''
你是一名儿童发展领域的专家，需要根据提供的文档内容生成测试用例，用于评估RAG检索系统的效果。

## 要求
1. 生成{count}个测试用例，必须严格覆盖以下维度：
   - **发展领域**：{domain}
   - **年龄段**：{age_stage_name}（{age_stage_desc}）
   - **查询类型**：{query_type_name}（{query_type_desc}）
   - **难度级别**：{difficulty_level_name}（{difficulty_level_desc}）

2. 每个测试用例包含以下字段：
   - query: 用户查询，模拟真实家长的提问，长度10-50字
   - domain: 所属发展领域，必须是六大领域之一（粗大动作、精细动作、语言发展、认知能力、社交情感、感觉统合）
   - age_min: 适用最小年龄（必须在{age_min}-{age_max}岁范围内）
   - age_max: 适用最大年龄（必须在{age_min}-{age_max}岁范围内）
   - query_type: 查询类型（事实性查询/比较性查询/方案性查询/原因分析性查询）
   - difficulty_level: 难度级别（入门级/中级/高级）
   - expected_keywords: 期望检索结果中包含的关键词，至少3个
   - description: 测试用例描述，说明该用例的测试目的

3. 所有内容必须严格基于提供的文档，不得编造文档中没有的信息
4. 同一批生成的测试用例必须互不重复，query 内容要有差异化
5. 返回纯JSON格式，不要任何其他解释说明，不要markdown格式

## 文档内容
{document_content}

## 输出示例
[
    {{
        "query": "1岁宝宝还不会走路正常吗",
        "domain": "粗大动作",
        "age_min": 1,
        "age_max": 1.5,
        "query_type": "事实性查询",
        "difficulty_level": "入门级",
        "expected_keywords": ["1岁", "走路", "粗大运动发展"],
        "description": "测试系统能否准确检索到1岁儿童走路的发展标准"
    }}
]
'''
    
    def render(
        self,
        document_content: str,
        domain: str = None,
        age_stage: dict = None,
        query_type: dict = None,
        difficulty_level: dict = None,
        count: int = 10
    ) -> str:
        age_stage = age_stage or {"name": "0-6岁", "age_min": 0, "age_max": 6, "desc": "全年龄段"}
        query_type = query_type or {"name": "事实性查询", "desc": "是什么/有什么"}
        difficulty_level = difficulty_level or {"name": "入门级", "desc": "基础概念"}
        
        return self.template.format(
            document_content=document_content,
            domain=domain or "所有领域",
            age_stage_name=age_stage["name"],
            age_stage_desc=age_stage.get("desc", f'{age_stage["age_min"]}-{age_stage["age_max"]}岁'),
            age_min=age_stage["age_min"],
            age_max=age_stage["age_max"],
            query_type_name=query_type["name"],
            query_type_desc=query_type.get("desc", ""),
            difficulty_level_name=difficulty_level["name"],
            difficulty_level_desc=difficulty_level.get("desc", ""),
            count=count
        )

test_case_draft_generation = TestCaseDraftGenerationPrompt()
```

---

#### Task 2.4.2: 优化生成逻辑（按章节分块并行 + 多维度差异化 + MinHash去重 + 断点续传）
**Files:**
- Modify: `src/service/rag_test_case_service.py`
- Test: `tests/service/test_rag_test_case_service.py`

- [ ] **Step 1: 编写性能测试用例**
```python
import pytest
import time

@pytest.mark.asyncio
async def test_batch_generation_performance():
    """性能测试：生成100条草稿耗时<5分钟，重复率<5%，领域覆盖率>90%"""
    from src.service.rag_test_case_service import rag_test_case_service
    
    start_time = time.time()
    # 生成100条草稿（按章节分块并行）
    drafts = await rag_test_case_service.batch_generate_drafts(
        document_id=1,
        page_count=100,  # 中等长度文档
    )
    
    duration = time.time() - start_time
    # 100条耗时不超过5分钟（基准：10条约2分钟，目标提升500%）
    assert duration < 300
    # 重复率<5%
    queries = [d.query for d in drafts]
    duplicate_rate = (len(queries) - len(set(queries))) / len(queries)
    assert duplicate_rate < 0.05
    # 领域覆盖率>90%（至少覆盖6个领域中的5个）
    domains = set([d.domain for d in drafts])
    assert len(domains) >= 6 * 0.9
    # 年龄段覆盖验证（至少覆盖3个年龄段）
    age_stages = set()
    for d in drafts:
        if d.age_max <= 1:
            age_stages.add("0-1岁")
        elif d.age_max <= 3:
            age_stages.add("1-3岁")
        elif d.age_max <= 6:
            age_stages.add("3-6岁")
        else:
            age_stages.add("6-12岁")
    assert len(age_stages) >= 3
```

- [ ] **Step 2: 实现优化后的生成逻辑（按章节分块并行 + 多维度差异化 + MinHash去重 + 批次标识断点续传）**
修改`src/service/rag_test_case_service.py`:
```python
import asyncio
import json
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from injector import inject
from datasketch import MinHash, MinHashLSH
from src.config import ConfigManager
from src.config.modules.rag.testing import TestCaseGenerationConfig, calculate_draft_count_by_pages
from src.core.llm.factory import llm_service_factory
from src.core.prompt.templates import test_case_draft_generation
from src.repository.test_case_draft_repository import test_case_draft_repo
from src.utils.logger import logger

import jieba  # 新增中文分词依赖

class DraftDeduplicator:
    """基于 MinHash + LSH 的高效去重器（分词级别，适配中文短文本）"""
    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold
        self.lsh = MinHashLSH(threshold=threshold, num_perm=128)
        self.existing_queries = {}

    def add_existing(self, query: str, idx: int):
        m = MinHash(num_perm=128)
        for word in jieba.lcut(query):
            m.update(word.encode('utf8'))
        self.lsh.insert(idx, m)
        self.existing_queries[idx] = query

    def is_duplicate(self, query: str) -> bool:
        m = MinHash(num_perm=128)
        for word in jieba.lcut(query):
            m.update(word.encode('utf8'))
        return len(self.lsh.query(m)) > 0


@inject
class RagTestCaseService:
    def __init__(self, test_case_draft_repo: TestCaseDraftRepository, config_manager: ConfigManager):
        self.test_case_draft_repo = test_case_draft_repo
        self.config_manager = config_manager
        self.llm_service = llm_service_factory
        self._deduplicator_cache: Dict[str, DraftDeduplicator] = {}
        self._chapter_cache: Dict[int, List[Tuple[str, str]]] = {}  # 缓存章节分块结果

    def _get_testing_config(self) -> TestCaseGenerationConfig:
        """从 ConfigManager 加载测试用例生成配置（MySQL > .env > 默认值）"""
        full_config = self.config_manager.get_full_config()
        testing_data = full_config.get("rag_testing", {})
        return TestCaseGenerationConfig(**testing_data) if testing_data else TestCaseGenerationConfig()

    async def batch_generate_drafts(
        self,
        document_id: int,
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
        existing_drafts = await self.test_case_draft_repo.list_by_batch(
            document_id=document_id,
            generation_batch_id=generation_batch_id
        )
        remaining_count = target_count - len(existing_drafts)
        
        if remaining_count <= 0:
            logger.info(f"文档 {document_id} 批次 {generation_batch_id} 已生成足够的草稿 ({len(existing_drafts)}条)，跳过")
            return existing_drafts
        
        logger.info(f"需要为文档 {document_id} 批次 {generation_batch_id} 生成 {remaining_count} 条草稿")
        
        # 按章节分块（复用文档解析、分块、元数据提取的已有结果，避免重复处理）
        chapters = await self._get_document_chapters(document_id, document_content)
        
        # 初始化去重器
        cache_key = f"dedup:{document_id}:{generation_batch_id}"
        if cache_key not in self._deduplicator_cache:
            self._deduplicator_cache[cache_key] = DraftDeduplicator(threshold=duplicate_threshold)
        deduplicator = self._deduplicator_cache[cache_key]
        for idx, d in enumerate(existing_drafts):
            deduplicator.add_existing(d.query, idx)
        
        # 按章节并行生成草稿
        all_drafts = existing_drafts.copy()
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # 计算每个章节需要生成的草稿数量（按章节长度比例分配）
        total_chapter_length = sum(len(content) for _, content in chapters)
        chapter_tasks = []
        
        for chapter_title, chapter_content in chapters:
            if len(chapter_content) < 500:  # 跳过过短章节
                continue
            
            # 按长度比例分配数量
            chapter_count = max(5, int(remaining_count * len(chapter_content) / total_chapter_length))
            
            chapter_tasks.append({
                "chapter_title": chapter_title,
                "chapter_content": chapter_content,
                "count": chapter_count,
                "domain": domain,
            })
        
        async def generate_chapter_drafts(task):
            async with semaphore:
                return await self._generate_chapter_drafts(
                    document_id=document_id,
                    generation_batch_id=generation_batch_id,
                    deduplicator=deduplicator,
                    **task
                )
        
        results = await asyncio.gather(
            *[generate_chapter_drafts(task) for task in chapter_tasks],
            return_exceptions=True
        )
        
        for result in results:
            if isinstance(result, list):
                all_drafts.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"章节生成失败: {result}")
        
        logger.info(f"文档 {document_id} 批次 {generation_batch_id} 共生成 {len(all_drafts) - len(existing_drafts)} 条新草稿，总计 {len(all_drafts)} 条")
        return all_drafts
    
    async def _get_document_chapters(self, document_id: int, document_content: str) -> List[Tuple[str, str]]:
        """获取文档章节分块（复用已有分块结果，避免重复处理）"""
        # 检查缓存
        if document_id in self._chapter_cache:
            return self._chapter_cache[document_id]
        
        # 尝试从元数据缓存获取章节结构
        try:
            from src.core.metadata_cache import metadata_cache
            chapters = metadata_cache.get_chapters(document_id)
            if chapters:
                self._chapter_cache[document_id] = chapters
                return chapters
        except ImportError:
            pass
        
        # 降级：简单按标题分割文档
        chapters = self._split_by_headings(document_content)
        self._chapter_cache[document_id] = chapters
        return chapters
    
    def _split_by_headings(self, content: str) -> List[Tuple[str, str]]:
        """按标题分割文档为章节"""
        import re
        # 匹配 Markdown 标题或带编号的标题
        pattern = r'^(#{1,3}\s+.+|第[一二三四五六七八九十\d]+[章部分].+)$'
        lines = content.split('\n')
        chapters = []
        current_title = "引言"
        current_content = []
        
        for line in lines:
            if re.match(pattern, line.strip()):
                if current_content:
                    chapters.append((current_title, '\n'.join(current_content)))
                current_title = line.strip().lstrip('# ').strip()
                current_content = []
            else:
                current_content.append(line)
        
        if current_content:
            chapters.append((current_title, '\n'.join(current_content)))
        
        # 如果只有一个章节，按固定长度分割
        if len(chapters) <= 1:
            chunk_size = 5000
            content_text = chapters[0][1] if chapters else content
            chapters = []
            for i in range(0, len(content_text), chunk_size):
                chunk = content_text[i:i+chunk_size]
                chapters.append((f"第{i//chunk_size + 1}部分", chunk))
        
        return chapters
    
    async def _generate_chapter_drafts(
        self,
        document_id: int,
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
                        difficulty.get("min_count", 20) // (len(age_stages) * len(query_types))
                    )
                    if min_count > 0 and remaining > 0:
                        actual_count = min(min_count, remaining)
                        dimension_tasks.append({
                            "age_stage": age_stage,
                            "query_type": query_type,
                            "difficulty_level": difficulty,
                            "count": actual_count,
                        })
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
                current_batch_count = min(batch_size, task["count"] - batch_idx * batch_size)
                if current_batch_count <= 0:
                    continue

                try:
                    prompt = test_case_draft_generation.render(
                        document_content=chapter_content[:10000],
                        domain=domain,
                        age_stage=task["age_stage"],
                        query_type=task["query_type"],
                        difficulty_level=task["difficulty_level"],
                        count=current_batch_count
                    )

                    llm = await self.llm_service.create("content_generation", framework="langchain")
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
                        required_fields = ["query", "domain", "age_min", "age_max", "expected_keywords"]
                        if not all(f in result for f in required_fields):
                            logger.warning("草稿字段不完整，跳过")
                            continue

                        # 去重校验
                        if deduplicator.is_duplicate(result["query"]):
                            logger.info(f"草稿重复，跳过: {result['query'][:30]}...")
                            continue

                        # 年龄范围校验
                        if result["age_min"] < task["age_stage"]["age_min"] or result["age_max"] > task["age_stage"]["age_max"]:
                            logger.warning(f"草稿年龄范围不符合要求，跳过: {result['age_min']}-{result['age_max']}")
                            continue

                        # 相关性校验
                        if config.enable_relevance_check:
                            relevance_score = self._calculate_relevance(
                                result["query"], chapter_content, result.get("expected_keywords", [])
                            )
                            if relevance_score < config.test_case_draft_relevance_threshold:
                                logger.info(f"草稿相关性过低 ({relevance_score:.2f})，跳过: {result['query'][:30]}...")
                                continue

                        # 保存到数据库
                        draft = await self.test_case_draft_repo.create({
                            "document_id": document_id,
                            "generation_batch_id": generation_batch_id,
                            "chapter_title": chapter_title,
                            "query": result["query"],
                            "domain": result["domain"],
                            "age_min": result["age_min"],
                            "age_max": result["age_max"],
                            "expected_keywords": result["expected_keywords"],
                            "query_type": result.get("query_type", task["query_type"]["name"]),
                            "difficulty_level": result.get("difficulty_level", task["difficulty_level"]["name"]),
                            "description": result.get("description", ""),
                            "status": "draft"
                        })

                        new_drafts.append(draft)
                        deduplicator.add_existing(result["query"], len(deduplicator.existing_queries))

                except Exception as e:
                    logger.warning(f"生成草稿失败 (章节: {chapter_title}, 批次: {batch_idx+1}/{batches}, 维度: {task['age_stage']['name']}/{task['query_type']['name']}): {e}")
                    # 仅跳过当前批次，继续下一批次
                    continue
        
        return new_drafts
    
    def _calculate_relevance(self, query: str, document_content: str, keywords: List[str]) -> float:
        """计算草稿查询与文档内容的相关性（简单关键词匹配）"""
        if not keywords:
            return 0.0
        
        query_words = set(jieba.lcut(query))
        doc_words = set(jieba.lcut(document_content[:5000]))
        
        matched = sum(1 for kw in keywords if kw in doc_words)
        return matched / len(keywords) if keywords else 0.0
```

**新增依赖:**
```toml
# pyproject.toml
[project]
dependencies = [
    # 已有依赖...
    "datasketch>=1.6.0",
    "jieba>=0.42.1",
]
```

> **文档服务集成示例**:
> ```python
> from src.service.document_service import document_service
> 
> # 从文档服务获取文档内容和页数
> document = await document_service.get_by_id(document_id)
> document_content = document.content
> page_count = document.page_count  # 用于动态计算草稿数量
> 
> # 调用批量生成方法（自动根据页数计算数量，并覆盖多维度）
> drafts = await rag_test_case_service.batch_generate_drafts(
>     document_id=document_id,
>     document_content=document_content,
>     page_count=page_count,
>     domain="感觉统合",  # 可选，不指定则覆盖所有领域
> )
> ```

- [ ] **Step 3: 运行性能测试验证**
Run: `pytest tests/service/test_rag_test_case_service.py::test_batch_generation_performance -v`
Expected: PASS，满足性能指标要求

---

**上一阶段：** [报告生命周期管理](./02-phase-2a-03-report-lifecycle.md)  
**下一阶段：** [前端UI增强](./02-phase-2a-05-frontend-ui.md)
