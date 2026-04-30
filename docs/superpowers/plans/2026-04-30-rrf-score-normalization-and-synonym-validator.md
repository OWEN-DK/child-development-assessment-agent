# RAG 检索质量修复：分数归一化 + 同义词验证

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复检索结果分数全部显示 98% 的问题，以及同义词验证器误杀真正同义词的问题。

**Architecture:** 两个独立修复。(1) Per-Query Min-Max 归一化替代固定阈值映射，改动集中在 `result_processor.py`。(2) 用 Embedding 余弦相似度替换 jieba 分词交集，涉及 `synonym_validator.py` async 化和调用链适配。

**Tech Stack:** Python 3.13, Pydantic Settings, DashScope Embedding API, pytest

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/src/service/retrieval/result_processor.py` | 修改 | 分数映射逻辑从固定阈值改为 per-query min-max |
| `backend/src/config/modules/rag/core.py` | 修改 | 移除 `max_expected_score`，新增 `score_spread_min` |
| `backend/tests/test_result_processor_score.py` | 新建 | 分数归一化单元测试 |
| `backend/src/core/rag/synonym_validator.py` | 修改 | `_has_semantic_overlap` 改为 embedding 余弦相似度，`validate()` 改为 async |
| `backend/src/service/retrieval/query_rewriter.py` | 修改 | `_local_expand_synonyms` 改为 async，调用点加 await |
| `backend/src/service/retrieval/facade.py` | 修改 | 注入 EmbeddingHelper 到 SynonymValidator |
| `backend/src/config/modules/rag/retrieval.py` | 修改 | 新增 `rag_synonym_similarity_threshold` 配置项 |
| `backend/tests/test_synonym_validator.py` | 修改 | 适配 async + 新增 embedding 相关用例 |

---

## Phase 1: Per-Query Min-Max 分数归一化

### Task 1: 编写分数归一化测试

**Files:**
- Create: `backend/tests/test_result_processor_score.py`
- Read: `backend/src/service/retrieval/result_processor.py` (参考 `_process_search_results` 签名)

- [ ] **Step 1: 创建测试文件，编写失败测试**

```python
"""ResultProcessor 分数归一化单元测试

测试 per-query min-max 归一化逻辑：
- 多结果时分数有区分度（不再全部 98%）
- 分数分布极窄时统一给高分（不制造虚假区分）
- 单结果时取 max_display_score
- 所有结果保留 raw_score 供调试
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from src.service.retrieval.result_processor import ResultProcessor


def _make_node_with_score(score: float, content: str = "测试内容", file_name: str = "test.pdf"):
    """构造模拟的 NodeWithScore 对象"""
    node = MagicMock()
    node.score = score
    node.node.node_id = f"node-{score}"
    node.node.metadata = {"file_name": file_name, "file_hash": None}
    node.node.get_content.return_value = content
    return node


@pytest.fixture
def processor():
    return ResultProcessor()


@pytest.fixture
def mock_settings(monkeypatch):
    """模拟配置，使用默认值"""
    monkeypatch.setattr("src.service.retrieval.result_processor.settings.rag_scoring_base_display_score", 0.55)
    monkeypatch.setattr("src.service.retrieval.result_processor.settings.rag_scoring_max_display_score", 0.98)
    monkeypatch.setattr("src.service.retrieval.result_processor.settings.rag_scoring_keyword_bonus_log_weight", 0.08)
    monkeypatch.setattr("src.service.retrieval.result_processor.settings.rag_scoring_keyword_bonus_max", 0.12)
    monkeypatch.setattr("src.service.retrieval.result_processor.settings.rag_scoring_score_spread_min", 0.002)
    # 确保旧的 max_expected_score 不再被使用
    monkeypatch.setattr("src.service.retrieval.result_processor.settings.rag_scoring_max_expected_score", 0.03, raising=False)


class TestPerQueryMinMaxNormalization:
    """Per-Query Min-Max 归一化测试"""

    @pytest.mark.asyncio
    async def test_multiple_results_have_score_variation(self, processor, mock_settings):
        """多结果时分数应有区分度，不再全部 98%"""
        nodes = [
            _make_node_with_score(0.032),  # 双源 rank-1
            _make_node_with_score(0.025),  # 双源 rank-3
            _make_node_with_score(0.010),  # 单源
        ]

        results = await processor._process_search_results(
            nodes=nodes,
            original_keywords=[],
            threshold=0.003,
            relative_cutoff=0.001,
            document_manager=AsyncMock(),
        )

        assert len(results) == 3
        scores = [r["score"] for r in results]
        # 最高分不应超过 max_display_score
        assert all(s <= 0.98 for s in scores)
        # 最低分不应低于 base_display_score
        assert all(s >= 0.55 for s in scores)
        # 分数应有区分度（不全相同）
        assert len(set(round(s, 4) for s in scores)) > 1
        # 第一个分数最高（保持排序）
        assert scores[0] > scores[-1]

    @pytest.mark.asyncio
    async def test_narrow_spread_gives_uniform_high_score(self, processor, mock_settings):
        """分数分布极窄时统一给高分，不制造虚假区分"""
        # 所有结果分数极接近（差异 < score_spread_min=0.002）
        nodes = [
            _make_node_with_score(0.030),
            _make_node_with_score(0.031),
            _make_node_with_score(0.0305),
        ]

        results = await processor._process_search_results(
            nodes=nodes,
            original_keywords=[],
            threshold=0.003,
            relative_cutoff=0.001,
            document_manager=AsyncMock(),
        )

        assert len(results) == 3
        scores = [r["score"] for r in results]
        # 所有分数应相同（统一给 max_display_score）
        assert scores[0] == pytest.approx(scores[1], abs=0.001)
        assert scores[1] == pytest.approx(scores[2], abs=0.001)

    @pytest.mark.asyncio
    async def test_single_result_gets_max_display(self, processor, mock_settings):
        """单结果时给 max_display_score"""
        nodes = [_make_node_with_score(0.032)]

        results = await processor._process_search_results(
            nodes=nodes,
            original_keywords=[],
            threshold=0.003,
            relative_cutoff=0.001,
            document_manager=AsyncMock(),
        )

        assert len(results) == 1
        assert results[0]["score"] == pytest.approx(0.98, abs=0.01)

    @pytest.mark.asyncio
    async def test_raw_score_preserved(self, processor, mock_settings):
        """raw_score 保留原始值，不受归一化影响"""
        nodes = [_make_node_with_score(0.032)]

        results = await processor._process_search_results(
            nodes=nodes,
            original_keywords=[],
            threshold=0.003,
            relative_cutoff=0.001,
            document_manager=AsyncMock(),
        )

        assert len(results) == 1
        assert results[0]["raw_score"] == pytest.approx(0.032, abs=0.001)

    @pytest.mark.asyncio
    async def test_below_threshold_filtered(self, processor, mock_settings):
        """低于阈值的结果被过滤"""
        nodes = [
            _make_node_with_score(0.032),
            _make_node_with_score(0.001),  # 低于 threshold 0.003
        ]

        results = await processor._process_search_results(
            nodes=nodes,
            original_keywords=[],
            threshold=0.003,
            relative_cutoff=0.001,
            document_manager=AsyncMock(),
        )

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_keyword_bonus_affects_raw_not_display_order(self, processor, mock_settings):
        """关键词加成影响 raw_score，display_score 基于 raw_score 做归一化"""
        nodes = [
            _make_node_with_score(0.032, content="注意力训练的方法"),  # 会有关键词加成
            _make_node_with_score(0.032, content="完全不同的内容"),   # 无关键词加成
        ]

        results = await processor._process_search_results(
            nodes=nodes,
            original_keywords=["注意力"],
            threshold=0.003,
            relative_cutoff=0.001,
            document_manager=AsyncMock(),
        )

        assert len(results) == 2
        # raw_score 应不同（第一个有关键词加成）
        assert results[0]["raw_score"] >= results[1]["raw_score"]
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && uv run pytest tests/test_result_processor_score.py -v`
Expected: FAIL（`_process_search_results` 签名可能不匹配，且 `score_spread_min` 属性不存在）

---

### Task 2: 实现 Per-Query Min-Max 归一化

**Files:**
- Modify: `backend/src/service/retrieval/result_processor.py:200-221`

- [ ] **Step 1: 修改 `_process_search_results`，两遍扫描 + per-query min-max**

将 result_processor.py 的 lines 145-277 改为两遍扫描：第一遍收集所有 final_score，第二遍做归一化并输出。

在 line 145 处，将单次循环改为两阶段处理。替换 lines 145-277：

```python
        # === 第一阶段：收集所有通过过滤的结果及其 final_score ===
        scored_items = []
        logger.info(f"_process_search_results: 开始处理 {len(nodes)} 个搜索结果")
        for i, node_with_score in enumerate(nodes):
            node = node_with_score.node
            metadata = node.metadata or {}
            content = node.get_content()
            raw_score = float(node_with_score.score or 0.0)
            logger.debug(
                f"Processing result {i}: 原始分数={raw_score:.4f}, 内容长度={len(content)}, 来源={metadata.get('file_name', 'Unknown')}"
            )

            # 过滤无效内容
            if (
                not content
                or content.startswith("[General Information]")
                or "书名=" in content
                or "SS 号=" in content
                or (
                    "参考文献" in content and len(content) < 100
                )
            ):
                logger.debug(f"Filtered result {i}: 无效内容，分数={raw_score:.4f}")
                continue

            # 阈值过滤
            if raw_score < threshold or raw_score < relative_cutoff:
                logger.debug(
                    f"Filtered result {i}: 分数 {raw_score:.4f} 低于阈值 {threshold} 或相对截断 {relative_cutoff:.4f}"
                )
                continue

            # 关键词频次加成（对数压缩）
            import math

            keyword_bonus = 0.0
            if original_keywords:
                content_lower = content.lower()
                total_occurrences = sum(
                    content_lower.count(kw) for kw in original_keywords
                )
                log_occurrences = math.log(1 + total_occurrences)
                normalized_density = log_occurrences / max(len(content_lower) / 500, 1)
                keyword_bonus = min(
                    normalized_density * settings.rag_scoring_keyword_bonus_log_weight,
                    settings.rag_scoring_keyword_bonus_max,
                )
                logger.debug(
                    f"Processing result {i}: 关键词总出现={total_occurrences}次, 对数值={log_occurrences:.2f}, 密度={normalized_density:.2f}, 加成={keyword_bonus:.4f}"
                )

            final_score = min(raw_score + keyword_bonus, 1.0)
            logger.debug(
                f"Processing result {i}: 内部绝对分数={final_score:.4f} (原始={raw_score:.4f} + 加成={keyword_bonus:.4f})"
            )

            scored_items.append({
                "node": node,
                "metadata": metadata,
                "content": content,
                "raw_score": raw_score,
                "final_score": final_score,
                "index": i,
            })

        # === 第二阶段：Per-Query Min-Max 归一化 ===
        base_display_score = settings.rag_scoring_base_display_score
        max_display_score = settings.rag_scoring_max_display_score
        score_spread_min = getattr(settings, "rag_scoring_score_spread_min", 0.002)

        if scored_items:
            scores = [item["final_score"] for item in scored_items]
            score_min = min(scores)
            score_max = max(scores)
            score_spread = score_max - score_min

            # 分数分布足够宽时才做区分，否则统一给高分
            do_normalize = score_spread >= score_spread_min

            for item in scored_items:
                if do_normalize and len(scored_items) > 1:
                    ratio = (item["final_score"] - score_min) / score_spread
                    display_score = base_display_score + ratio * (max_display_score - base_display_score)
                else:
                    display_score = max_display_score

                display_score = min(max(display_score, base_display_score), max_display_score)
                item["display_score"] = display_score
        else:
            logger.info("_process_search_results: 无有效结果")

        # === 第三阶段：去重 + 构建输出 ===
        results = []
        for item in scored_items:
            content = item["content"]
            metadata = item["metadata"]

            # 检查重复内容
            is_duplicate = False
            for existing_item in results:
                if self._is_content_duplicate(content, existing_item["content"]):
                    is_duplicate = True
                    break

            if is_duplicate:
                logger.debug(f"Filtered result {item['index']}: 重复内容，分数={item['final_score']:.4f}")
                continue

            # 获取源书名
            file_hash = metadata.get("file_hash")
            source_book = metadata.get("file_name", "Unknown Source")
            if file_hash:
                doc = await document_manager.get_document(file_hash)
                if doc:
                    source_book = doc["file_name"]

            # 处理页码显示
            page_label = metadata.get("page_label")
            if page_label:
                if "index_split" in str(page_label) or ".html" in str(page_label):
                    page_label = metadata.get("chapter_title") or "Section"
                elif len(str(page_label)) > 10 and not str(page_label).isdigit():
                    page_label = f"章节: {page_label}"

            results.append({
                "id": item["node"].node_id,
                "content": content,
                "score": item["display_score"],
                "raw_score": item["final_score"],
                "source_book": source_book,
                "chapter_title": metadata.get("chapter_title"),
                "page_label": page_label,
                "brain_regions": metadata.get("brain_regions", []),
                "topics": metadata.get("topics", []),
                "file_hash": metadata.get("file_hash"),
            })
            logger.debug(
                f"Added result {item['index']}: 分数={item['final_score']:.4f}, 展示={item['display_score']:.4f}, 来源={source_book}"
            )

        logger.info(f"_process_search_results: 处理完成，返回 {len(results)} 个结果")
        if results:
            top_scores = [f"{r['score']:.4f}" for r in results[:3]]
            logger.info(f"_process_search_results: Top 3 结果分数：{top_scores}")
        return results
```

- [ ] **Step 2: 运行测试，确认通过**

Run: `cd backend && uv run pytest tests/test_result_processor_score.py -v`
Expected: 全部 PASS

---

### Task 3: 更新配置（移除 max_expected_score，新增 score_spread_min）

**Files:**
- Modify: `backend/src/config/modules/rag/core.py:90-104`

- [ ] **Step 1: 替换 `rag_scoring_max_expected_score` 为 `rag_scoring_score_spread_min`**

在 `backend/src/config/modules/rag/core.py`，将 lines 90-94（`rag_scoring_max_expected_score`）替换为：

```python
    rag_scoring_score_spread_min: float = Field(
        default=0.002,
        validation_alias="RAG_SCORING_SCORE_SPREAD_MIN",
        description="Per-Query 分数展开最小值（结果集内 min-max 差值小于此值时统一给高分）",
    )
```

- [ ] **Step 2: 检查其他文件是否引用了 `rag_scoring_max_expected_score`**

Run: `grep -rn "max_expected_score\|RAG_SCORING_MAX_EXPECTED_SCORE" backend/src/ backend/config/`

Expected: 仅在 `result_processor.py` 中有旧引用（已在 Task 2 中移除）。如果有其他引用，也需要更新。

- [ ] **Step 3: 运行测试确认配置变更无破坏**

Run: `cd backend && uv run pytest tests/test_result_processor_score.py -v`
Expected: 全部 PASS

- [ ] **Step 4: 提交 Phase 1**

```bash
cd backend
git add src/service/retrieval/result_processor.py src/config/modules/rag/core.py tests/test_result_processor_score.py
git commit -m "fix: RRF 分数归一化改为 per-query min-max，解决全部 98% 问题

- 移除固定 max_expected_score 阈值映射
- 新增 score_spread_min 防止窄分布时制造虚假区分
- 两遍扫描：先收集 final_score，再做归一化"
```

---

## Phase 2: 同义词验证器 Embedding 升级

### Task 4: 新增配置项

**Files:**
- Modify: `backend/src/config/modules/rag/retrieval.py:132`

- [ ] **Step 1: 在 `retrieval.py` 的 `RagRetrievalSettings` 类中追加新配置项**

在 line 132 之后（`rag_search_min_similarity_threshold` 之后）添加：

```python
    rag_synonym_similarity_threshold: float = Field(
        default=0.6,
        validation_alias="RAG_SYNONYM_SIMILARITY_THRESHOLD",
        description="同义词语义验证的 embedding 余弦相似度阈值（>= 此值视为语义相关）",
    )
```

- [ ] **Step 2: 验证配置可加载**

Run: `cd backend && uv run python -c "from src.config import settings; print(settings.rag_synonym_similarity_threshold)"`
Expected: 输出 `0.6`

---

### Task 5: 编写同义词验证器 embedding 测试

**Files:**
- Modify: `backend/tests/test_synonym_validator.py`

- [ ] **Step 1: 在测试文件末尾追加新的测试类**

在 `test_synonym_validator.py` 末尾添加：

```python
class TestSynonymValidatorEmbedding:
    """Embedding 语义验证测试"""

    @pytest.fixture
    def mock_embedding_helper(self):
        """模拟 EmbeddingHelper，使用预设的余弦相似度"""
        helper = MagicMock()
        # embed_batch 返回与文本对应的伪向量
        # 通过共享分量控制余弦相似度
        def fake_embed_batch(texts):
            results = []
            for text in texts:
                if text == "儿童":
                    results.append([1.0, 0.0, 0.0, 0.0])
                elif text == "孩子":
                    results.append([0.9, 0.1, 0.0, 0.0])  # 与"儿童"相似度 ≈ 0.994
                elif text == "幼儿":
                    results.append([0.85, 0.15, 0.0, 0.0])  # 与"儿童"相似度 ≈ 0.985
                elif text == "青少年":
                    results.append([0.5, 0.5, 0.0, 0.0])  # 与"儿童"相似度 ≈ 0.707
                elif text == "数学能力":
                    results.append([0.0, 0.0, 1.0, 0.0])  # 与"儿童"相似度 = 0.0
                elif text == "专注力":
                    results.append([1.0, 0.0, 0.0, 0.0])
                elif text == "注意力":
                    results.append([0.95, 0.05, 0.0, 0.0])
                elif text == "感统":
                    results.append([1.0, 0.0, 0.0, 0.0])
                elif text == "感觉整合":
                    results.append([0.9, 0.1, 0.0, 0.0])
                elif text == "编程":
                    results.append([0.0, 0.0, 0.0, 1.0])
                else:
                    results.append([0.1, 0.1, 0.1, 0.1])
            return results

        helper.embed_batch = AsyncMock(side_effect=fake_embed_batch)
        helper.cosine_similarity = MagicMock(side_effect=lambda a, b: _cosine_sim(a, b))
        return helper

    @pytest.mark.asyncio
    async def test_real_synonym_passes_with_embedding(self, mock_embedding_helper, tmp_path):
        """真正的同义词通过 embedding 验证"""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("{}")
        validator = SynonymValidator(
            validation_file=str(empty_file),
            embedding_helper=mock_embedding_helper,
        )

        report = await validator.validate(["孩子", "幼儿"], original_query="儿童")
        assert "孩子" in report.valid_terms
        assert "幼儿" in report.valid_terms

    @pytest.mark.asyncio
    async def test_unrelated_term_rejected_with_embedding(self, mock_embedding_helper, tmp_path):
        """无关词仍被拒绝"""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("{}")
        validator = SynonymValidator(
            validation_file=str(empty_file),
            embedding_helper=mock_embedding_helper,
        )

        report = await validator.validate(["数学能力"], original_query="儿童")
        assert "数学能力" in [t for t, _ in report.rejected_terms]

    @pytest.mark.asyncio
    async def test_fail_open_when_no_embedding(self, tmp_path):
        """EmbeddingHelper 不可用时 fail-open（放过而非误杀）"""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("{}")
        validator = SynonymValidator(validation_file=str(empty_file))

        # 不传 embedding_helper，仍应有合理行为
        report = await validator.validate(["孩子"], original_query="儿童")
        # fail-open：无 embedding 时应通过（不误杀）
        assert "孩子" in report.valid_terms

    @pytest.mark.asyncio
    async def test_jieba_fast_path_preserved(self, mock_embedding_helper, tmp_path):
        """jieba 分词有交集时走快速路径，不调 embedding API"""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("{}")
        validator = SynonymValidator(
            validation_file=str(empty_file),
            embedding_helper=mock_embedding_helper,
        )

        # "注意力" 和 "注意力集中" 有分词交集
        report = await validator.validate(["注意力集中"], original_query="注意力")
        assert "注意力集中" in report.valid_terms


def _cosine_sim(a, b):
    """纯 Python 余弦相似度"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
```

注意：测试文件顶部需要添加 `from unittest.mock import AsyncMock, MagicMock` import。

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && uv run pytest tests/test_synonym_validator.py::TestSynonymValidatorEmbedding -v`
Expected: FAIL（`SynonymValidator.__init__` 不接受 `embedding_helper` 参数，`validate` 不是 async）

---

### Task 6: 实现 Embedding 语义验证

**Files:**
- Modify: `backend/src/core/rag/synonym_validator.py`

- [ ] **Step 1: 修改构造函数，接受可选 EmbeddingHelper**

将 `synonym_validator.py` 的 import 区域（lines 1-15）和构造函数（lines 33-46）修改为：

```python
"""同义词质量验证器

多维度验证 LLM 生成的同义词质量，防止引入不相关或太宽泛的词汇。
支持三级降级加载：数据库 → 本地 JSON → 空词典
Embedding 语义验证：使用余弦相似度判断语义重叠，解决 jieba 分词对同义词的误杀问题。
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

from src.config import settings
from src.utils.logger import logger

if TYPE_CHECKING:
    from src.utils.embedding_helper import EmbeddingHelper
```

将构造函数（line 33-46）改为：

```python
    def __init__(
        self,
        validation_file: Optional[str] = None,
        embedding_helper: Optional["EmbeddingHelper"] = None,
    ):
        self._validation_rules = self._load_rules(validation_file)
        self._blacklist_set = set(self._validation_rules.get("domain_blacklist", []))
        self._whitelist_set = set(self._validation_rules.get("domain_whitelist", []))
        self._domain_terms = self._validation_rules.get("domain_terms", {})
        self._embedding_helper = embedding_helper

        self._chinese_pattern = re.compile(r"[一-龥]")
        self._valid_char_pattern = re.compile(r"^[一-龥a-zA-Z0-9\s]+$")

        if not SynonymValidator._ever_initialized:
            SynonymValidator._ever_initialized = True
            emb_status = "已启用" if self._embedding_helper else "未启用"
            logger.info(
                f"SynonymValidator 初始化完成，黑名单 {len(self._blacklist_set)} 个词，"
                f"白名单 {len(self._whitelist_set)} 个词，Embedding {emb_status}"
            )
```

- [ ] **Step 2: 将 `validate` 改为 async，批量 embed 后传入 `_check_term`**

将 lines 48-90 的 `validate` 方法替换为：

```python
    async def validate(
        self,
        synonym_list: List[str],
        original_query: str,
    ) -> ValidationReport:
        """
        验证同义词列表质量

        Args:
            synonym_list: 待验证的同义词列表
            original_query: 原始查询词

        Returns:
            ValidationReport: 验证报告
        """
        # 批量预计算 embedding
        embedding_map: dict[str, list[float]] = {}
        if self._embedding_helper:
            try:
                all_texts = list(set(synonym_list + [original_query]))
                embeddings = await self._embedding_helper.embed_batch(all_texts)
                embedding_map = dict(zip(all_texts, embeddings))
            except Exception as e:
                logger.warning(f"Embedding 批量计算失败，将降级到分词检查: {e}")

        valid_terms = []
        rejected_terms = []

        for term in synonym_list:
            if term == original_query:
                valid_terms.append(term)
                continue

            reason = self._check_term(term, original_query, embedding_map)
            if reason is None:
                valid_terms.append(term)
            else:
                rejected_terms.append((term, reason))
                if getattr(settings, "rag_synonym_log_rejected", True):
                    logger.debug(f"同义词被拒绝: '{term}'，原因: {reason}")

        total = len(synonym_list)
        valid_count = len(valid_terms)
        confidence = valid_count / total if total > 0 else 0.0

        threshold = getattr(settings, "rag_synonym_quality_threshold", 0.8)

        return ValidationReport(
            is_valid=confidence >= threshold,
            valid_terms=valid_terms,
            rejected_terms=rejected_terms,
            confidence=confidence,
        )
```

- [ ] **Step 3: 修改 `_check_term` 签名，接受 embedding_map**

将 lines 92-120 的 `_check_term` 改为：

```python
    def _check_term(
        self,
        term: str,
        original_query: str,
        embedding_map: Optional[dict[str, list[float]]] = None,
    ) -> Optional[str]:
        """检查单个扩展词，返回 None 表示通过，否则返回拒绝原因"""
        if len(term) < 2:
            return "太短（单字）"

        if len(term) > 25:
            return "太长（超过 25 字）"

        if not self._valid_char_pattern.match(term):
            return "包含非法字符"

        if term in self._blacklist_set:
            return "在黑名单中（不相关领域）"

        if self._is_too_broad(term, original_query):
            return "太宽泛（粒度不如原词）"

        if term in self._whitelist_set:
            return None

        if self._matches_query_specific_rule(term, original_query):
            return None

        if not self._has_semantic_overlap(term, original_query, embedding_map):
            return "与原词语义无重叠"

        return None
```

- [ ] **Step 4: 重写 `_has_semantic_overlap`，使用 embedding 余弦相似度**

将 lines 139-155 的 `_has_semantic_overlap` 替换为：

```python
    def _has_semantic_overlap(
        self,
        term: str,
        original_query: str,
        embedding_map: Optional[dict[str, list[float]]] = None,
    ) -> bool:
        """检查扩展词与原词是否有语义重叠

        三层检查：
        1. jieba 分词有交集 → 快速通过（分词重叠一定语义相关）
        2. embedding 余弦相似度 >= threshold → 通过
        3. 无 embedding 时 fail-open → 通过（宁可放过不可误杀）
        """
        # 快速路径：分词交集
        if self._chinese_pattern.search(original_query):
            import jieba

            term_words = set(jieba.lcut(term))
            query_words = set(jieba.lcut(original_query))
            if term_words & query_words:
                return True

        if re.search(r"[a-zA-Z]", original_query):
            term_words = set(re.findall(r"[a-zA-Z]{3,}", term.lower()))
            query_words = set(re.findall(r"[a-zA-Z]{3,}", original_query.lower()))
            if term_words & query_words:
                return True

        # Embedding 语义路径
        if embedding_map and self._embedding_helper:
            term_emb = embedding_map.get(term)
            query_emb = embedding_map.get(original_query)
            if term_emb and query_emb:
                similarity = self._embedding_helper.cosine_similarity(term_emb, query_emb)
                sim_threshold = getattr(
                    settings, "rag_synonym_similarity_threshold", 0.6
                )
                logger.debug(
                    f"Embedding 相似度: '{term}' vs '{original_query}' = {similarity:.3f} (阈值={sim_threshold})"
                )
                return similarity >= sim_threshold

            # embedding_map 存在但缺失对应向量 → fail-open
            logger.warning(f"Embedding 缺失: term='{term}', query='{original_query}'，降级通过")
            return True

        # 无 embedding helper → fail-open
        return True
```

- [ ] **Step 5: 运行新增测试**

Run: `cd backend && uv run pytest tests/test_synonym_validator.py::TestSynonymValidatorEmbedding -v`
Expected: 全部 PASS

---

### Task 7: 更新调用链（query_rewriter.py）

**Files:**
- Modify: `backend/src/service/retrieval/query_rewriter.py:220-264`

- [ ] **Step 1: 将 `_local_expand_synonyms` 改为 async**

将 line 253 的 `def _local_expand_synonyms` 改为：

```python
    async def _local_expand_synonyms(self, query: str) -> str:
        """本地同义词扩展兜底逻辑"""
        if not self._local_expander:
            return query

        synonyms = self._local_expander.expand(query)

        if self._synonym_validator:
            report = await self._synonym_validator.validate(synonyms, query)
            synonyms = report.valid_terms

        return " ".join(synonyms)
```

- [ ] **Step 2: 在 `_expand_synonyms` 中给 `validate` 和 `_local_expand_synonyms` 调用加 await**

在 `_expand_synonyms` 方法中，修改 3 处调用：

1. Line 221 的 `validate` 调用加 `await`：
```python
                report = await self._synonym_validator.validate(all_terms, query)
```

2. Line 232 的 `_local_expand_synonyms` 调用加 `await`：
```python
                        return await self._local_expand_synonyms(query)
```

3. Line 244 的 `_local_expand_synonyms` 调用加 `await`：
```python
                return await self._local_expand_synonyms(query)
```

4. Line 251 的 `_local_expand_synonyms` 调用加 `await`（在 except 块中）：
```python
            return await self._local_expand_synonyms(query)
```

- [ ] **Step 3: 更新原有测试适配 async**

原有 `test_synonym_validator.py` 中所有测试都需要改为 `async` 并加 `await`。需要修改：

1. 文件顶部添加 `import pytest`（已有）和确认 `pytest-asyncio` 可用
2. 所有 `TestSynonymValidator` 类中的 `def test_xxx` 改为 `async def test_xxx`
3. 所有 `validator.validate(...)` 调用改为 `await validator.validate(...)`
4. 所有测试方法加 `@pytest.mark.asyncio` 装饰器

具体改动清单（20 个测试方法）：

```python
# 每个方法都需要：
# 1. 添加 @pytest.mark.asyncio 装饰器
# 2. def → async def
# 3. validate() 调用加 await

# 例如 test_blacklist_rejection：
@pytest.mark.asyncio
async def test_blacklist_rejection(self):
    validator = SynonymValidator()
    report = await validator.validate(
        ["注意力", "专注力", "集中力", "视力", "听力"], original_query="注意力"
    )
    # ... assertions 不变
```

所有 20 个方法（`test_blacklist_rejection` 到 `test_single_term_list`）都需做同样的 async 改造。

- [ ] **Step 4: 运行全部同义词相关测试**

Run: `cd backend && uv run pytest tests/test_synonym_validator.py -v`
Expected: 全部 PASS（包括原有 20 个测试 + 新增 4 个 embedding 测试）

---

### Task 8: 在 facade.py 中注入 EmbeddingHelper

**Files:**
- Modify: `backend/src/service/retrieval/facade.py:33-36`

- [ ] **Step 1: 导入 EmbeddingHelper 并注入到 SynonymValidator**

将 lines 31-36 改为：

```python
        from src.core.rag.local_synonym_expander import LocalSynonymExpander
        from src.core.rag.query_analyzer import QueryAnalyzer
        from src.core.rag.synonym_validator import SynonymValidator
        from src.utils.embedding_helper import EmbeddingHelper

        query_analyzer = QueryAnalyzer()
        embedding_helper = EmbeddingHelper(
            model_name=settings.embedding_model_name,
            api_key=settings.dashscope_api_key,
            embed_batch_size=settings.embedding_batch_size,
        )
        synonym_validator = SynonymValidator(embedding_helper=embedding_helper)
        local_expander = LocalSynonymExpander()
```

注意：这里直接创建 `EmbeddingHelper` 而非从 DI 容器获取，因为 `RetrievalFacade` 目前不使用 injector。如果后续统一 DI，可改为注入。

- [ ] **Step 2: 运行检索相关测试，确保无破坏**

Run: `cd backend && uv run pytest tests/test_synonym_validator.py tests/test_local_synonym_expander.py -v`
Expected: 全部 PASS

- [ ] **Step 3: 提交 Phase 2**

```bash
cd backend
git add src/core/rag/synonym_validator.py src/service/retrieval/query_rewriter.py src/service/retrieval/facade.py src/config/modules/rag/retrieval.py tests/test_synonym_validator.py
git commit -m "fix: SynonymValidator 用 embedding 余弦相似度替代 jieba 分词交集

- validate() 改为 async，批量预计算 embedding
- _has_semantic_overlap 三层检查：jieba 快速路径 → embedding 语义 → fail-open
- 新增 rag_synonym_similarity_threshold 配置项（默认 0.6）
- query_rewriter.py 调用链适配 async"
```

---

### Task 9: 全量回归测试

**Files:** 无新增

- [ ] **Step 1: 运行后端全部测试**

Run: `cd backend && uv run pytest --tb=short -q`
Expected: 全部 PASS，无 regression

- [ ] **Step 2: 手动验证检索页面**

启动后端 `cd backend && uv run start`，在前端搜索页搜索"儿童"或"幼儿"：
1. 确认搜索结果分数不再全部 98%
2. 确认同义词扩展日志中不再全部拒绝
3. 确认黑名单、白名单规则仍然生效
