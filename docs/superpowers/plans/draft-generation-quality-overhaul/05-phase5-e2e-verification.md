# 阶段 5：TDD 验证 + 端到端集成

> 前置：阶段 1-4 全部完成。
>
> **注意：** 本方案为重构，核心接口变更（Schema/签名）通过 Task 14 的契约测试验证。纯重构的 edge case 不要求严格的 Red-Green 循环，但必须通过单元测试覆盖所有变更点。

---

### Task 14: 后端单元测试

**Files:**
- Create: `backend/tests/service/rag_eval/draft/test_generator_simplified.py`
- Create: `backend/tests/service/rag_eval/draft/test_faithfulness_checker.py`

- [ ] **Step 1: 编写 DraftGenerator 简化版测试**

```python
"""DraftGenerator 简化版测试 — 验证 age/domain 移除后的行为"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.schemas.rag_eval.draft import DraftCreate, DraftGenerationConfig


@pytest.fixture
def config():
    return DraftGenerationConfig(max_qa_per_chunk=3, min_qa_per_chunk=1)


class TestDraftGeneratorSimplified:
    """验证 generate() 不再接受 age_ranges/domains 参数"""

    def test_generate_signature_no_metadata(self):
        """generate() 签名不应包含 metadata 参数"""
        import inspect
        from src.service.rag_eval.draft.generator import DraftGenerator
        sig = inspect.signature(DraftGenerator.generate)
        assert "metadata" not in sig.parameters
        assert "age_ranges" not in sig.parameters
        assert "domains" not in sig.parameters

    def test_draft_create_no_age_domain(self):
        """DraftCreate 不应包含 age/domain 字段，也不含 source_document_id（由 facade 层传参）"""
        fields = DraftCreate.model_fields
        assert "age" not in fields
        assert "domain" not in fields
        assert "age_stage_label" not in fields
        assert "source_document_id" not in fields  # 由 facade 层独立传参，不属于 Schema

    @pytest.mark.asyncio
    async def test_empty_chunk_skipped(self, config):
        """空 content 的 chunk 应被跳过"""
        from src.service.rag_eval.draft.generator import DraftGenerator
        gen = DraftGenerator()
        gen._config = MagicMock()
        # 按 key 区分不同配置项的返回值
        gen._config.get_config_value.side_effect = lambda key, default=None: {
            "rag.eval.draft.concurrency": 15,
        }.get(key, default)

        chunks = [{"id": "c1", "content": ""}, {"id": "c2", "content": "   "}]
        result = await gen.generate(chunks, config)
        assert result == []

    @pytest.mark.asyncio
    async def test_build_drafts_no_age_domain(self, config):
        """_build_drafts 输出不包含 age/domain"""
        from src.service.rag_eval.draft.generator import DraftGenerator
        gen = DraftGenerator()
        items = [{"query": "测试问题", "description": "描述",
                   "expected_keywords": ["关键词"], "answer_points": ["要点"],
                   "difficulty_level": "easy"}]
        drafts = gen._build_drafts(items, "chunk_1", 1, "原文内容")
        assert len(drafts) == 1
        d = drafts[0]
        assert d.query == "测试问题"
        assert d.source_chunk_id == "chunk_1"
        assert d.source_page == 1
        # 确认 Schema 级别无 age/domain 字段
        assert "age" not in DraftCreate.model_fields
        assert "domain" not in DraftCreate.model_fields
        assert "source_document_id" not in DraftCreate.model_fields  # 由 facade 层传参，非 Schema 字段

    @pytest.mark.asyncio
    async def test_prompt_manager_default_injected(self, config):
        """构造函数默认注入 PromptManager 模块单例"""
        from src.service.rag_eval.draft.generator import DraftGenerator
        gen = DraftGenerator()
        assert gen._prompt_manager is not None, "PromptManager 应默认注入"

    @pytest.mark.asyncio
    async def test_prompt_manager_fallback(self, config):
        """PromptManager 不可用时应使用 fallback prompt"""
        from src.service.rag_eval.draft.generator import DraftGenerator
        gen = DraftGenerator(prompt_manager=None)  # 显式传 None 触发 fallback
        prompt = gen._build_prompt(3, "测试内容")
        assert "3" in prompt
        assert "测试内容" in prompt
        assert "忠实性铁律" in prompt
```

- [ ] **Step 2: 运行 DraftGenerator 测试**

Run: `cd backend && uv run pytest tests/service/rag_eval/draft/test_generator_simplified.py -v`

Expected: 全部通过

- [ ] **Step 3: 编写 FaithfulnessChecker 测试**

```python
"""FaithfulnessChecker 测试 — 验证 answer_points 优先作为对比文本"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.schemas.rag_eval.draft import DraftCreate


class TestFaithfulnessChecker:
    """验证 check() 优先使用 answer_points 拼接作为对比文本"""

    @pytest.mark.asyncio
    async def test_answer_points_used_as_compare_text(self):
        """answer_points 非空时应作为对比文本"""
        from src.service.rag_eval.draft.faithfulness_checker import FaithfulnessChecker
        checker = FaithfulnessChecker()
        checker._embedding_faithfulness_async = AsyncMock(return_value=0.85)

        draft = DraftCreate(
            query="测试问题",
            answer_points=["要点一", "要点二"],
            description="描述文本",
        )
        score = await checker.check(draft, "原文内容" * 100)

        # 验证传入 embedding 的文本包含 answer_points 内容
        call_args = checker._embedding_faithfulness_async.call_args
        compare_text = call_args[0][0]
        assert "要点一" in compare_text
        assert "要点二" in compare_text
        assert score == 0.85

    @pytest.mark.asyncio
    async def test_fallback_to_description(self):
        """answer_points 为空时应回退到 description"""
        from src.service.rag_eval.draft.faithfulness_checker import FaithfulnessChecker
        checker = FaithfulnessChecker()
        checker._embedding_faithfulness_async = AsyncMock(return_value=0.7)

        draft = DraftCreate(
            query="测试问题",
            answer_points=None,
            description="这是描述",
        )
        score = await checker.check(draft, "原文内容" * 100)

        call_args = checker._embedding_faithfulness_async.call_args
        compare_text = call_args[0][0]
        assert "这是描述" in compare_text

    @pytest.mark.asyncio
    async def test_empty_source_returns_default(self):
        """原文为空时返回默认分数 0.5"""
        from src.service.rag_eval.draft.faithfulness_checker import FaithfulnessChecker
        checker = FaithfulnessChecker()

        draft = DraftCreate(query="测试问题", answer_points=["要点"])
        score = await checker.check(draft, "")
        assert score == 0.5
```

- [ ] **Step 4: 运行 FaithfulnessChecker 测试**

Run: `cd backend && uv run pytest tests/service/rag_eval/draft/test_faithfulness_checker.py -v`

Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add backend/tests/service/rag_eval/draft/
git commit -m "test: 添加简化后 DraftGenerator 和 FaithfulnessChecker 的单元测试"
```

- [ ] **Step 5b: 清理旧架构测试文件**

旧文件 `backend/tests/service/test_draft_service.py` 测试的是 `src.service.rag_test.draft_service.DraftService`（旧架构），包含 `_map_domain`、`age_stage` 等已不再适用的断言。新架构使用 `src.service.rag_eval.draft.generator.DraftGenerator`。

```bash
rm backend/tests/service/test_draft_service.py
```

```bash
git add backend/tests/service/test_draft_service.py
git commit -m "chore: 移除旧架构 test_draft_service.py（已被 test_generator_simplified.py 替代）"
```

---

### Task 15: 端到端集成验证

**Files:** 无新文件

- [ ] **Step 1: 重建数据库**

> 项目未上线，直接 DROP + CREATE，无需数据迁移（零迁移原则）。

```bash
cd backend
mysql -u root -p < ../.ai/full_init_script_mysql57.sql
```

- [ ] **Step 2: 启动后端服务**

验证：
- 服务正常启动，无 ImportError
- `/api/v1/rag/eval/drafts` 端点可用
- `POST /api/v1/rag/eval/drafts/generate` 返回 batch_id

- [ ] **Step 3: 使用 curl 验证 API 契约**

```bash
# 列出草稿（无 domain 参数）
curl -s http://localhost:51002/api/v1/rag/eval/drafts?page=1&page_size=10 | python -m json.tool

# 触发生成（仅 document_id + config）
curl -s -X POST http://localhost:51002/api/v1/rag/eval/drafts/generate \
  -H "Content-Type: application/json" \
  -d '{"document_id": "test_doc_id", "config": {"max_qa_per_chunk": 3}}' | python -m json.tool
```

验证响应中不含 age/domain/age_stage_label 字段。

- [ ] **Step 4: 启动前端开发服务器**

验证：
- 草稿生成表单只显示 document_id、max_qa、min_qa 三个字段
- 草稿表格不显示 domain 和年龄段列
- 无 domain 筛选下拉框
- SSE 进度推送正常（使用 `useDraftGenerationProgress.ts`）

- [ ] **Step 5: 执行一次完整的草稿生成流程**

1. 上传一个中文 PDF 文档
2. 选择该文档，点击生成
3. 验证 SSE 进度正常推送
4. 验证生成的草稿：
   - 输出语言与原文一致（不中英混杂）
   - query 可从原文直接找到答案
   - answer_points 来自原文关键短语
   - 忠实度评分 > 0.5（比之前的 28.1% 大幅提升）

- [ ] **Step 6: 运行全量后端测试**

Run: `cd backend && uv run pytest`

- [ ] **Step 7: 运行前端测试和类型检查**

Run: `cd frontend && npm run test && npm run typecheck && npm run lint`

- [ ] **Step 8: Final Commit**

```bash
git commit --allow-empty -m "chore: 草稿生成质量翻新完成，端到端验证通过"
```
