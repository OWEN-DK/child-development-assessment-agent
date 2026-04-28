# ⚠️ 已废弃 - 草稿生成 RAG 检索增强 - 实施方案

> **废弃日期**: 2026-04-24  
> **替代方案**: `docs/superpowers/specs/2026-04-21-draft-generation-redesign.md` (Chunk-Grounded 逐块生成)  
> **废弃原因**: 原方案 B 仍采用"检索增强 + 降级到文档全文"的架构，未从根本上解决 LLM 编造问题。新方案采用逐 chunk 独立生成 + 忠实性校验，彻底杜绝编造。

---

# 草稿生成 RAG 检索增强 - 实施方案

**日期**: 2026-04-21  
**状态**: ❌ 已废弃  
**方案**: B - 基于 RAG 检索增强 + 可追溯性验证

---

## 核心目标

解决草稿与原书籍完全不相关的问题，通过：
1. **检索增强**：从书籍索引的 chunks 中获取相关内容
2. **强制标注来源**：LLM 生成草稿时必须引用来源 chunk
3. **可追溯性验证**：验证来源 chunk 是否真实存在于书籍中
4. **人工审核辅助**：审核页面展示来源引用，快速判断相关性

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/src/service/rag_test/draft_retrieval_service.py` | **新增** | 检索增强服务 |
| `backend/src/service/rag_test/draft_service.py` | **修改** | 集成检索和来源验证 |
| `backend/src/core/prompts_fallback.py` | **修改** | 更新 prompt 模板，强制标注来源 |
| `backend/src/models/test_case.py` | **修改** | 添加来源标注字段 |
| `.ai/full_init_script_mysql57.sql` | **修改** | 更新 DDL |
| `backend/src/config/modules/rag/testing.py` | **修改** | 添加配置项 |

---

## 阶段 1：核心功能

### 1.1 新增 `backend/src/service/rag_test/draft_retrieval_service.py`

```python
"""草稿检索增强服务

基于 IndexManager 直接获取文档 chunks，按元数据过滤和排序，
为草稿生成提供高质量的文档片段。
"""

import json
from typing import List

from src.service.index_manager.facade import IndexManagerService
from src.utils.logger import logger


class DraftRetrievalService:
    """草稿检索服务单例"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.index_manager = IndexManagerService()
        self._initialized = True

    async def get_relevant_chunks(
        self,
        file_hash: str,
        domain: str,
        age_min_months: int,
        age_max_months: int,
        top_k: int = 15,
    ) -> List[dict]:
        """获取与领域和年龄段相关的文档片段

        Args:
            file_hash: 文件哈希值
            domain: 目标领域（中文，如"感觉统合"）
            age_min_months: 年龄段最小月龄
            age_max_months: 年龄段最大月龄
            top_k: 返回的 chunk 数量

        Returns:
            chunks 列表，每个包含 id, content, metadata, score
        """
        try:
            result = self.index_manager.get_document_chunks(
                file_hash=file_hash, page=1, page_size=1000
            )
        except Exception as e:
            logger.error(f"获取文档 chunks 失败: {e}")
            return []

        all_chunks = result.get("chunks", [])
        if not all_chunks:
            logger.warning(f"文档 {file_hash} 无索引 chunks")
            return []

        # 按元数据过滤
        filtered = []
        domain_keywords = self._get_domain_keywords(domain)

        for chunk in all_chunks:
            metadata = chunk.get("metadata", {})

            # 年龄段过滤
            chunk_age_min = metadata.get("target_age_min", 0)
            chunk_age_max = metadata.get("target_age_max", 18)
            age_overlap = self._check_age_overlap(
                chunk_age_min, chunk_age_max,
                age_min_months / 12, age_max_months / 12,
            )
            if not age_overlap:
                continue

            # 领域过滤（通过 topics 匹配）
            topics = metadata.get("topics", [])
            if isinstance(topics, str):
                try:
                    topics = json.loads(topics)
                except Exception:
                    topics = [topics]

            topic_match = any(
                kw in topic or topic in kw
                for kw in domain_keywords
                for topic in topics
            )

            # 计算相关性分数
            score = 0.0
            if topic_match:
                score += 0.6
            if age_overlap:
                score += 0.4

            filtered.append({
                "id": chunk["id"],
                "content": chunk["content"],
                "metadata": metadata,
                "score": score,
            })

        # 按分数排序，取 top-K
        filtered.sort(key=lambda x: x["score"], reverse=True)
        return filtered[:top_k]

    @staticmethod
    def _get_domain_keywords(domain: str) -> List[str]:
        """获取领域关键词映射"""
        mapping = {
            "粗大动作": ["粗大动作", "大肌肉", "跑", "跳", "爬", "走", "平衡", "gross_motor"],
            "精细动作": ["精细动作", "手眼协调", "小肌肉", "抓握", "捏", "穿珠", "fine_motor"],
            "语言发展": ["语言", "说话", "表达", "理解", "词汇", "语法", "language"],
            "认知能力": ["认知", "思维", "记忆", "注意力", "逻辑", "解决问题", "cognitive"],
            "社交情感": ["社交", "情感", "情绪", "互动", "合作", "分享", "social", "emotional"],
            "感觉统合": ["感觉统合", "前庭", "本体", "触觉", "感知", "sensory", "integration"],
        }
        return mapping.get(domain, ["感觉统合", "sensory"])

    @staticmethod
    def _check_age_overlap(
        chunk_min: float, chunk_max: float,
        target_min: float, target_max: float,
    ) -> bool:
        """检查年龄段是否有重叠"""
        return chunk_min <= target_max and chunk_max >= target_min

    def format_chunks_for_prompt(self, chunks: List[dict]) -> str:
        """将 chunks 格式化为 prompt 可用的字符串"""
        if not chunks:
            return "未检索到相关文档片段。"

        parts = []
        for i, chunk in enumerate(chunks, 1):
            metadata = chunk.get("metadata", {})
            topics = metadata.get("topics", [])
            if isinstance(topics, list):
                topics_str = ", ".join(topics)
            else:
                topics_str = str(topics)

            page = metadata.get("page_label", "?")
            parts.append(
                f"【片段 {i}】(ID: {chunk['id']}, 页码: {page})\n"
                f"主题: {topics_str}\n"
                f"年龄范围: {metadata.get('target_age_min', '?')}-{metadata.get('target_age_max', '?')}岁\n"
                f"内容: {chunk['content']}\n"
            )

        return "\n".join(parts)

    def get_chunk_ids(self, chunks: List[dict]) -> List[str]:
        """提取 chunk ID 列表"""
        return [c["id"] for c in chunks if "id" in c]


draft_retrieval_service = DraftRetrievalService()
```

### 1.2 修改 `backend/src/service/rag_test/draft_service.py`

#### 改动点 1: 新增导入（文件顶部，现有 import 下方）

```python
from src.service.rag_test.draft_retrieval_service import draft_retrieval_service
```

#### 改动点 2: 修改 DraftData 数据类（第 24-39 行）

```python
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
    # 新增字段
    source_chunks: List[dict] = field(default_factory=list)
    source_validated: bool = False
```

#### 改动点 3: 修改 generate_drafts_matrix() 获取文档内容逻辑（替换第 102-110 行）

```python
            # 2. 获取文档内容与检索增强
            config = await self._get_draft_config()

            # 尝试使用 RAG 检索增强
            retrieval_enabled = getattr(config, 'enable_retrieval_enhancement', True)
            retrieved_chunks = []
            source_chunk_ids = []
            chunks_formatted = ""

            if retrieval_enabled and doc.file_hash:
                try:
                    # 获取第一个目标领域和年龄段用于检索
                    target_domain = params.target_domains[0] if params.target_domains else "感觉统合"
                    target_age_stage = params.age_stages[0] if params.age_stages else "3-6岁"
                    age_info = self._get_age_stage_info(target_age_stage, config)

                    retrieved_chunks = await draft_retrieval_service.get_relevant_chunks(
                        file_hash=doc.file_hash,
                        domain=target_domain,
                        age_min_months=age_info["age_min_months"],
                        age_max_months=age_info["age_max_months"],
                        top_k=config.retrieval_top_k,
                    )

                    if retrieved_chunks:
                        chunks_formatted = draft_retrieval_service.format_chunks_for_prompt(retrieved_chunks)
                        source_chunk_ids = draft_retrieval_service.get_chunk_ids(retrieved_chunks)
                        logger.info(f"检索增强成功，获取 {len(retrieved_chunks)} 个 chunks")
                    else:
                        logger.warning("检索增强未返回 chunks，降级使用文档内容")
                except Exception as e:
                    logger.warning(f"检索增强失败，降级使用文档内容: {e}")

            # 降级方案：使用文档内容
            if not chunks_formatted:
                content_to_use = doc.content_summary or "暂无摘要内容"
                try:
                    if os.path.exists(doc.file_path):
                        with open(doc.file_path, "r", encoding="utf-8", errors="ignore") as f:
                            full_content = f.read()
                            content_to_use = full_content[:10000] if len(full_content) > 10000 else full_content
                except Exception as e:
                    logger.warning(f"Failed to load full document content: {e}")
                chunks_formatted = content_to_use
```

#### 改动点 4: 修改 _generate_batch() 方法签名和内部逻辑（替换第 365-435 行）

```python
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
        retrieved_chunks: Optional[List[dict]] = None,
        source_chunk_ids: Optional[List[str]] = None,
    ) -> List[DraftData]:
        """一次 LLM 调用生成一批草稿

        Args:
            retrieved_chunks: 检索到的文档片段
            source_chunk_ids: 来源 chunk ID 列表
        """
        config = await self._get_draft_config()
        age_info = self._get_age_stage_info(age_stage, config)

        configs_json = json.dumps([
            {"index": i, "query_type": c["query_type"], "difficulty": c["difficulty"]}
            for i, c in enumerate(draft_configs)
        ], ensure_ascii=False)

        # 构建检索到的 chunks 文本
        if retrieved_chunks:
            chunks_text = draft_retrieval_service.format_chunks_for_prompt(retrieved_chunks)
        else:
            chunks_text = text

        variables = {
            "text": text,
            "retrieved_chunks": chunks_text,
            "domain": domain,
            "age_stage_label": age_stage,
            "age_min_months": age_info["age_min_months"],
            "age_max_months": age_info["age_max_months"],
            "batch_count": len(draft_configs),
            "batch_configs": configs_json,
            "source_chunk_ids": json.dumps(source_chunk_ids or [], ensure_ascii=False),
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

        # 注入来源信息
        chunk_map = {c["id"]: c for c in (retrieved_chunks or [])}
        for i, draft in enumerate(parsed):
            if i < len(draft_configs):
                draft.domain = domain
                draft.age_stage_label = age_stage
                draft.batch_id = str(uuid.uuid4())
                # 保存来源 chunks（供验证和审核使用）
                draft.source_chunks = [
                    {
                        "chunk_id": cid,
                        "page": chunk_map.get(cid, {}).get("metadata", {}).get("page_label", ""),
                        "content_snippet": chunk_map.get(cid, {}).get("content", "")[:200],
                    }
                    for cid in (source_chunk_ids or [])[:3]  # 最多保留 3 个来源
                ]

        return parsed
```

#### 改动点 5: 在 generate_drafts_matrix() 中调用 _generate_batch 时传入 chunks（修改第 166-176 行附近）

```python
                        batch_drafts = await self._generate_batch(
                            doc_id=source_document_id,
                            text=content_to_use,
                            domain=combo["domain"],
                            age_stage=combo["age_stage"],
                            draft_configs=batch,
                            model=params.llm_model,
                            temperature=params.temperature,
                            max_retries=config.max_llm_retries,
                            retrieved_chunks=retrieved_chunks if retrieval_enabled else None,
                            source_chunk_ids=source_chunk_ids if retrieval_enabled else None,
                        )
```

#### 改动点 6: 去重后添加强制来源验证（替换第 184 行后的质量验证调用）

```python
                    # 6.3.1 来源可追溯性验证
                    for draft in filtered_drafts:
                        if draft.source_chunks:
                            # 验证来源 chunk 是否真实存在于书籍中
                            validated = await self._validate_source_traceability(
                                draft.source_chunks, doc.file_hash
                            )
                            draft.source_validated = validated
                        else:
                            draft.source_validated = False
```

#### 改动点 7: 修改 _save_drafts_idempotent() 方法，保存来源字段（在第 562-581 行创建新草稿时）

```python
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
                        source_chunks=draft.source_chunks or [],
                        source_validated=draft.source_validated,
                    )
```

#### 改动点 8: 新增 _validate_source_traceability() 方法（在文件末尾 delete_draft 方法前添加）

```python
    async def _validate_source_traceability(
        self,
        source_chunks: List[dict],
        file_hash: str,
    ) -> bool:
        """验证草稿的来源是否真实存在于书籍中

        Args:
            source_chunks: 来源标注列表 [{chunk_id, page, content_snippet}]
            file_hash: 书籍文件哈希

        Returns:
            是否全部来源有效
        """
        if not source_chunks:
            return False

        valid_count = 0
        for src in source_chunks:
            chunk_id = src.get("chunk_id")
            if not chunk_id:
                continue

            try:
                # 直接从 Chroma 验证 chunk 是否存在
                chunk = draft_retrieval_service.index_manager.get_chunk_detail(chunk_id)
                if chunk and chunk.get("metadata", {}).get("file_hash") == file_hash:
                    valid_count += 1
            except Exception as e:
                logger.warning(f"验证来源 chunk {chunk_id} 失败: {e}")

        # 至少 80% 的来源有效即通过
        return valid_count >= len(source_chunks) * 0.8
```

### 1.3 更新 Prompt 模板

修改 `backend/src/core/prompts_fallback.py` 中的 `TEST_CASE_DRAFT_GENERATION_PROMPT`（替换第 100-148 行）：

```python
TEST_CASE_DRAFT_GENERATION_PROMPT = """\
你是儿童发展、感觉统合、教育心理学领域的专业测试用例设计师。
请根据提供的文档内容，生成 RAG（检索增强生成）测试用例草稿。

## 检索到的文档片段
{retrieved_chunks}

## 生成约束
- 目标领域：{domain}（必须围绕此领域生成）
- 适用年龄段：{age_stage_label}（月龄范围 {age_min_months}-{age_max_months} 月，查询和答案必须符合此年龄段特征）
- 每个问题必须能在上述文档片段中找到答案
- 答案必须引用文档中的关键点
- **必须标注来源**：每个草稿必须指定答案来源的片段 ID

## 批次配置
请生成 {batch_count} 个草稿，每个草稿对应以下配置：
{batch_configs}

每个草稿必须严格匹配对应的 query_type 和 difficulty。

## 查询类型说明
- 事实性查询：是什么/有什么/定义类问题
- 比较性查询：区别/对比/优劣类问题
- 方案性查询：怎么做/如何改善/训练方法类问题
- 原因分析性查询：为什么/成因/机制类问题

## 难度说明
- 入门级：基础概念认知，适合家长日常提问
- 中级：场景应用和对比分析，适合有一定知识的家长
- 高级：专业深度和机制分析，适合专业人士

## 返回格式
必须返回严格的 JSON 对象，格式如下：
{{
  "drafts": [
    {{
      "age": 48,
      "query": "什么是前庭觉？",
      "description": "测试系统对基础概念的理解能力",
      "expected_keywords": ["前庭觉", "平衡", "内耳"],
      "answer_points": ["前庭觉定义", "主要功能", "发育阶段"],
      "professional_terms": ["前庭器官", "半规管"]
    }}
  ]
}}

## 约束
- age 必须为整数，范围在 {age_min_months}-{age_max_months} 月之间
- query 必须是完整的问句
- 每个草稿的 query 不能重复
- 仅返回 JSON，不要包含任何解释性文字
"""
```

### 1.4 添加配置项

修改 `backend/src/config/modules/rag/testing.py`，在文件末尾（第 111 行后）添加：

```python
    # ========== RAG 检索增强 ==========
    enable_retrieval_enhancement: bool = Field(
        default=True, description="是否启用检索增强草稿生成",
    )
    retrieval_top_k: int = Field(
        default=15, ge=5, le=50, description="检索增强时获取的 chunk 数量",
    )
    min_source_valid_ratio: float = Field(
        default=0.8, ge=0.0, le=1.0, description="最低来源有效比例",
    )
```

---

## 阶段 2：数据库

### 2.1 修改 `backend/src/models/test_case.py`

在 `TestCaseDraft` 类中（第 152 行 `generation_params` 之后）添加：

```python
    # 来源标注字段
    source_chunks: Mapped[list[dict] | None] = mapped_column(
        JSON, nullable=True,
        comment="来源标注: [{chunk_id, page, content_snippet}]"
    )
    source_validated: Mapped[bool] = mapped_column(
        default=False, comment="来源是否已验证"
    )
```

### 2.2 更新 `.ai/full_init_script_mysql57.sql`

在 `test_case_drafts` 表定义中（第 187 行 `generation_params` 之后）添加：

```sql
    `source_chunks` json DEFAULT NULL COMMENT '来源标注: [{chunk_id, page, content_snippet}]',
    `source_validated` tinyint(1) DEFAULT 0 COMMENT '来源是否已验证',
```

---

## 阶段 3：数据库配置初始化

执行以下 SQL 插入配置项（可通过系统配置页面或初始化脚本）：

```sql
INSERT INTO system_configs (config_key, config_value, category, description) VALUES
('draft_generation.enable_retrieval_enhancement', 'true', 'draft', '是否启用检索增强'),
('draft_generation.retrieval_top_k', '15', 'draft', '检索 chunk 数量'),
('draft_generation.min_source_valid_ratio', '0.8', 'draft', '最低来源有效比例');
```

---

## 关键设计决策说明

1. **核心目标**：解决草稿与书籍不相关的问题，而非评估质量
2. **可追溯性验证**：验证来源 chunk 是否真实存在于书籍中，确保草稿有依据
3. **降级策略**：检索失败时自动降级为读取文档前 10000 字符（从原 4000 提升）
4. **人工审核辅助**：前端审核页面展示来源引用（页码 + 内容片段），快速判断相关性
5. **配置热更新**：所有开关和阈值通过 `TestCaseGenerationConfig` 从 MySQL 读取
6. **零迁移原则**：新字段允许 NULL，不影响现有数据和 API 响应格式
