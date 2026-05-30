# Phase 2: MD 工具链与知识生产

> **工期**: 4 人天 | **风险**: 中 | **依赖**: Phase 1（Neo4j 已运行，Schema 已创建）  
> **目标**: AI 生成结构化 MD → 人工审核 → 入库 Neo4j，形成知识生产闭环
>
> **模型选择**: 全线使用 `qwen3.7-max`（精度优先），`qwen3.5-27b` 作为 fallback。

---

## 2.1 工具链全景

```
EPUB 书籍
  │
  ├──▶ 阶段 0: 章节解析 (chapter_parser.py)
  │     ebooklib 解析 → 按章节拆分 → HTML 清洗 → token 估算 → 超长拆分
  │     输出: list[Chapter], 每章 ~2000-6000 tokens
  │
  ├──▶ 阶段 1: 逐章并行生成 (md_generator.py)
  │     3 并发 │ qwen3.7-max │ with_structured_output
  │     每章 120s 超时 │ 3 次指数退避重试 │ SSE 进度回调
  │
  ├──▶ 阶段 2: 跨章聚合 (aggregator.py)
  │     同名/语义合并 │ 章间矛盾检测 │ 置信度计算
  │
  ├──▶ 阶段 3: 跨书检测 (cross_relation.py)
  │     Neo4j 查询已有实体 → embedding 粗筛 → LLM 精判
  │
  ├──▶ MD 渲染 (md_renderer.py) → MD 草稿
  │
  ├──▶ 人工审核 Web UI → 状态: draft → reviewed → published
  │
  └──▶ MD 入库 Neo4j (import_md.py)
```

---

## 2.2 MD 格式规范

```markdown
---
book_id: "exercise_book_001"
book_title: "运动改变大脑"
status: "draft"
version: 1
generated_at: "2026-06-01T10:00:00Z"
reviewed_by: null
reviewed_at: null
---

# 运动改变大脑 — 结构化知识

## 概念

### 注意力缺陷 (ADHD)
- **entity_type**: Problem
- **severity**: high
- **symptoms**: 注意力不集中、多动、冲动控制困难
- **brain_regions**: ["前额叶皮层", "基底核"]
- **source**: 第二章

### 有氧运动
- **entity_type**: Solution
- **category**: 运动干预
- **mechanism**: 提升 BDNF 水平，促进海马体神经新生
- **source**: 第三章

## 主张

### 有氧运动改善 ADHD 注意力
- **claim_type**: causal
- **confidence**: high
- **source_problem**: "注意力缺陷 (ADHD)"
- **source_solution**: "有氧运动"
- **evidence**: "30分钟中等强度有氧运动后，前额叶皮层激活显著增强 (第3章, p.87)"

## 运动处方

### 中等强度有氧运动 — ADHD
- **exercise**: "有氧运动"
- **frequency**: "每天1次"
- **duration**: "30分钟"
- **intensity**: "中等（心率 130-150 bpm）"
- **age_range**: "6-18岁"
- **contraindications**: ["严重心脏病", "急性哮喘发作"]
```

---

## 2.3 AI MD 生成器 — 四阶段流水线

### 阶段 0: 章节解析

```python
# backend/src/core/knowledge_qa/neo4j/chapter_parser.py
"""EPUB 章节解析 — 从 EPUB 提取结构化章节列表。"""

import re
from dataclasses import dataclass, field
from typing import Optional

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup


@dataclass
class Chapter:
    id: str
    title: str
    raw_html: str
    markdown: str = ""
    order: int = 0
    token_count: int = 0


@dataclass
class ChapterParseResult:
    book_id: str
    book_title: str
    chapters: list[Chapter] = field(default_factory=list)
    total_tokens: int = 0


def parse_epub(file_path: str, book_id: str) -> ChapterParseResult:
    """解析 EPUB 文件，返回按章节组织的结构化结果。"""
    book = epub.read_epub(file_path)
    book_title = book.get_metadata("DC", "title")[0][0] if book.get_metadata("DC", "title") else "Unknown"

    result = ChapterParseResult(book_id=book_id, book_title=book_title)
    chapter_idx = 0

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        html = item.get_content().decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        # 提取章节标题
        heading = soup.find(["h1", "h2", "h3"])
        title = heading.get_text(strip=True) if heading else f"Chapter {chapter_idx + 1}"

        # HTML → 简化 Markdown
        markdown = _html_to_markdown(soup)
        if not markdown.strip():
            continue

        token_count = _estimate_tokens(markdown)

        chapter = Chapter(
            id=f"{book_id}_ch{chapter_idx:03d}",
            title=title,
            raw_html=html,
            markdown=markdown,
            order=chapter_idx,
            token_count=token_count,
        )
        result.chapters.append(chapter)
        result.total_tokens += token_count
        chapter_idx += 1

    # 超长章节拆分（> 6000 tokens）
    result.chapters = _split_long_chapters(result.chapters, max_tokens=6000)

    return result


def _html_to_markdown(soup: BeautifulSoup) -> str:
    """简单 HTML → Markdown 转换。"""
    lines = []
    for elem in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote"]):
        tag = elem.name
        text = elem.get_text(strip=True)
        if not text:
            continue
        if tag.startswith("h"):
            level = int(tag[1])
            lines.append(f"{'#' * level} {text}")
        elif tag == "li":
            lines.append(f"- {text}")
        elif tag == "blockquote":
            lines.append(f"> {text}")
        else:
            lines.append(text)
    return "\n\n".join(lines)


def _estimate_tokens(text: str) -> int:
    """粗略 token 估算（中文约 1.5 char/token）。"""
    return max(1, len(text) * 2 // 3)


def _split_long_chapters(chapters: list[Chapter], max_tokens: int) -> list[Chapter]:
    """超长章节按段落边界拆分。"""
    result = []
    for ch in chapters:
        if ch.token_count <= max_tokens:
            result.append(ch)
            continue
        paragraphs = ch.markdown.split("\n\n")
        current_text = ""
        current_tokens = 0
        part_idx = 0
        for para in paragraphs:
            para_tokens = _estimate_tokens(para)
            if current_tokens + para_tokens > max_tokens and current_text:
                result.append(Chapter(
                    id=f"{ch.id}_p{part_idx}",
                    title=f"{ch.title} (Part {part_idx + 1})",
                    raw_html=ch.raw_html,
                    markdown=current_text.strip(),
                    order=ch.order,
                    token_count=current_tokens,
                ))
                part_idx += 1
                current_text = ""
                current_tokens = 0
            current_text += para + "\n\n"
            current_tokens += para_tokens
        if current_text.strip():
            result.append(Chapter(
                id=f"{ch.id}_p{part_idx}",
                title=f"{ch.title} (Part {part_idx + 1})" if part_idx > 0 else ch.title,
                raw_html=ch.raw_html,
                markdown=current_text.strip(),
                order=ch.order,
                token_count=current_tokens,
            ))
    return result
```

### 阶段 1: 逐章并行生成

```python
# backend/src/core/knowledge_qa/neo4j/md_generator.py
"""AI MD 生成器 — 四阶段流水线。"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable

from core.knowledge_qa.neo4j.chapter_parser import Chapter, ChapterParseResult

logger = logging.getLogger(__name__)


@dataclass
class ChapterResult:
    chapter_id: str
    success: bool
    md_content: str = ""
    error: Optional[str] = None


@dataclass
class GenerationProgress:
    total_chapters: int = 0
    completed: int = 0
    failed: int = 0
    current_chapter: str = ""


KG_EXTRACTION_PROMPT = """你是一位儿童发展与教育领域的知识提取专家。
从以下章节内容中提取结构化知识，输出 YAML 格式。

提取内容：
1. **概念** (concepts): Problem / Solution / BrainRegion / Risk 等实体
2. **主张** (claims): 实体之间的因果/相关关系
3. **运动处方** (prescriptions): 如有运动相关建议，提取频率/时长/强度/年龄

章节标题: {chapter_title}
章节内容:
{chapter_content}

输出格式严格按 YAML：
concepts:
  - name: "概念名"
    entity_type: Problem|Solution|BrainRegion|Risk
    description: "简要描述"
    symptoms: ["症状1"]  # 仅 Problem
    source: "章节名"

claims:
  - source_concept: "概念A"
    target_concept: "概念B"
    claim_type: causal|correlational|supports
    confidence: high|medium|low
    evidence: "证据摘要"

prescriptions:
  - exercise: "运动名称"
    frequency: "频率"
    duration: "时长"
    intensity: "强度"
    age_range: "年龄范围"
    contraindications: ["禁忌1"]
"""


async def generate_chapter_md(
    chapter: Chapter,
    llm_client,
    model: str = "qwen3.7-max",
    timeout: int = 120,
    max_retries: int = 3,
) -> ChapterResult:
    """为单个章节生成结构化 MD。"""
    prompt = KG_EXTRACTION_PROMPT.format(
        chapter_title=chapter.title,
        chapter_content=chapter.markdown[:8000],  # 防止超长
    )

    for attempt in range(max_retries):
        try:
            response = await asyncio.wait_for(
                llm_client.generate(prompt=prompt, model=model),
                timeout=timeout,
            )
            return ChapterResult(chapter_id=chapter.id, success=True, md_content=response)
        except asyncio.TimeoutError:
            logger.warning("Chapter %s timeout (attempt %d/%d)", chapter.id, attempt + 1, max_retries)
        except Exception as e:
            logger.warning("Chapter %s error: %s (attempt %d/%d)", chapter.id, e, attempt + 1, max_retries)
        await asyncio.sleep(2 ** attempt)

    return ChapterResult(chapter_id=chapter.id, success=False, error="Max retries exceeded")


async def generate_book_md(
    parse_result: ChapterParseResult,
    llm_client,
    model: str = "qwen3.7-max",
    concurrency: int = 3,
    on_progress: Optional[Callable[[GenerationProgress], None]] = None,
) -> list[ChapterResult]:
    """并行为整本书的所有章节生成 MD。"""
    progress = GenerationProgress(total_chapters=len(parse_result.chapters))
    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async def _gen(ch: Chapter) -> ChapterResult:
        async with semaphore:
            progress.current_chapter = ch.title
            if on_progress:
                on_progress(progress)
            result = await generate_chapter_md(ch, llm_client, model)
            if result.success:
                progress.completed += 1
            else:
                progress.failed += 1
            if on_progress:
                on_progress(progress)
            return result

    tasks = [_gen(ch) for ch in parse_result.chapters]
    results = await asyncio.gather(*tasks)
    return list(results)
```

### 阶段 2: 跨章聚合

```python
# backend/src/core/knowledge_qa/neo4j/aggregator.py
"""跨章聚合 — 合并同名实体、检测章间矛盾。"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AggregatedEntity:
    name: str
    entity_type: str
    descriptions: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.0
    merged_from: list[str] = field(default_factory=list)  # 原始章节 ID 列表


@dataclass
class AggregatedBook:
    book_id: str
    book_title: str
    entities: list[AggregatedEntity] = field(default_factory=list)
    claims: list[dict] = field(default_factory=list)
    prescriptions: list[dict] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)


def aggregate_chapters(chapter_results: list[dict], book_id: str, book_title: str) -> AggregatedBook:
    """将多个章节的提取结果聚合为一本书的结构化知识。"""
    book = AggregatedBook(book_id=book_id, book_title=book_title)

    # 按实体名分组
    entity_map: dict[str, AggregatedEntity] = {}

    for result in chapter_results:
        if not result.get("success"):
            continue

        for concept in result.get("concepts", []):
            key = f"{concept['entity_type']}::{concept['name']}"
            if key in entity_map:
                entity_map[key].descriptions.append(concept.get("description", ""))
                entity_map[key].sources.append(concept.get("source", ""))
                entity_map[key].merged_from.append(result.get("chapter_id", ""))
            else:
                entity_map[key] = AggregatedEntity(
                    name=concept["name"],
                    entity_type=concept["entity_type"],
                    descriptions=[concept.get("description", "")],
                    sources=[concept.get("source", "")],
                    confidence=concept.get("confidence", 0.8),
                    merged_from=[result.get("chapter_id", "")],
                )

        for claim in result.get("claims", []):
            book.claims.append(claim)

        for rx in result.get("prescriptions", []):
            book.prescriptions.append(rx)

    book.entities = list(entity_map.values())

    # 检测章间矛盾（同名实体描述冲突）
    book.contradictions = _detect_contradictions(book.entities)

    return book


def _detect_contradictions(entities: list[AggregatedEntity]) -> list[dict]:
    """检测同一实体在不同章节中的描述矛盾。"""
    contradictions = []
    for ent in entities:
        if len(ent.descriptions) < 2:
            continue
        # 简单关键词矛盾检测（实际应用中可用 LLM 判断）
        severity_keywords = {"高": ["high", "严重", "重度"], "低": ["low", "轻微", "轻度"]}
        has_high = any(kw in d for d in ent.descriptions for kw in severity_keywords["高"])
        has_low = any(kw in d for d in ent.descriptions for kw in severity_keywords["低"])
        if has_high and has_low:
            contradictions.append({
                "entity_name": ent.name,
                "type": "severity_conflict",
                "descriptions": ent.descriptions,
                "sources": ent.sources,
            })
    return contradictions
```

---

## 2.4 跨书关系检测

```python
# backend/src/core/knowledge_qa/neo4j/cross_relation.py
"""跨书关系检测 — Neo4j 查询已有实体 → embedding 粗筛 → LLM 精判。"""

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CrossBookRelationType(Enum):
    CONSENSUS = "CONSENSUS"        # 共识：两书观点一致
    COMPLEMENTS = "COMPLEMENTS"    # 互补：两书观点互补
    CONFLICTS = "CONFLICTS"        # 冲突：两书观点矛盾


@dataclass
class CrossBookRelation:
    source_entity: str
    source_book: str
    target_entity: str
    target_book: str
    relation_type: CrossBookRelationType
    confidence: float
    explanation: str


async def detect_cross_book_relations(
    new_entities: list[dict],
    new_book_id: str,
    neo4j_session,
    llm_client,
    embedding_model=None,
    similarity_threshold: float = 0.7,
) -> list[CrossBookRelation]:
    """检测新书实体与 Neo4j 中已有实体的跨书关系。"""
    relations = []

    # Step 1: 从 Neo4j 获取所有已有实体
    existing = neo4j_session.run("""
        MATCH (ae:AutoEntity)
        WHERE ae.book_id <> $book_id
        RETURN ae.name AS name, ae.entity_type AS type, ae.description AS desc, ae.book_id AS book_id
    """, book_id=new_book_id).data()

    if not existing:
        logger.info("Neo4j 中无其他书的实体，跳过跨书检测")
        return []

    # Step 2: embedding 粗筛（同类型实体按语义相似度匹配）
    candidates = []
    for new_ent in new_entities:
        for old_ent in existing:
            if new_ent.get("entity_type") != old_ent["type"]:
                continue
            # 计算相似度（可用 sentence-transformers 或 LLM）
            sim = _compute_similarity(
                new_ent.get("name", ""), old_ent["name"],
                new_ent.get("description", ""), old_ent.get("desc", ""),
                embedding_model,
            )
            if sim >= similarity_threshold:
                candidates.append((new_ent, old_ent, sim))

    # Step 3: LLM 精判
    for new_ent, old_ent, sim in candidates:
        relation = await _llm_judge_cross_relation(
            new_ent, old_ent, llm_client,
        )
        if relation:
            relations.append(relation)

    logger.info("跨书检测完成: %d 个候选，%d 个确认关系", len(candidates), len(relations))
    return relations


def _compute_similarity(name_a, name_b, desc_a, desc_b, embedding_model) -> float:
    """计算两个实体的语义相似度。"""
    # 简化版：名称完全匹配或包含关系
    if name_a == name_b:
        return 1.0
    if name_a in name_b or name_b in name_a:
        return 0.9
    # 实际应用中用 embedding 余弦相似度
    return 0.0


async def _llm_judge_cross_relation(new_ent, old_ent, llm_client) -> CrossBookRelation | None:
    """LLM 判断两个实体的关系类型。"""
    prompt = f"""判断以下两个来自不同书籍的实体之间的关系。

实体 A（新书）: {new_ent.get('name')} - {new_ent.get('description', '')}
实体 B（已有）: {old_ent['name']} - {old_ent.get('desc', '')}

选项:
- CONSENSUS: 两书观点一致
- COMPLEMENTS: 两书观点互补（各补充不同方面）
- CONFLICTS: 两书观点矛盾
- UNRELATED: 无关

仅输出 JSON: {{"type": "CONSENSUS|COMPLEMENTS|CONFLICTS|UNRELATED", "confidence": 0.0-1.0, "explanation": "简要说明"}}"""

    try:
        response = await llm_client.generate(prompt=prompt, model="qwen3.7-max")
        import json
        result = json.loads(response)
        if result.get("type") == "UNRELATED":
            return None
        return CrossBookRelation(
            source_entity=new_ent.get("name", ""),
            source_book=new_ent.get("book_id", ""),
            target_entity=old_ent["name"],
            target_book=old_ent["book_id"],
            relation_type=CrossBookRelationType(result["type"]),
            confidence=result.get("confidence", 0.5),
            explanation=result.get("explanation", ""),
        )
    except Exception as e:
        logger.warning("LLM 跨书判断失败: %s", e)
        return None
```

---

## 2.5 MD → Cypher 解析器

```python
# backend/src/core/knowledge_qa/neo4j/md_parser.py
"""MD Parser — 解析审核后的 MD 文件，生成 Cypher MERGE 语句。"""

import re
import yaml
from dataclasses import dataclass, field


@dataclass
class CypherStatement:
    query: str
    params: dict
    description: str = ""


@dataclass
class MDParseResult:
    book_id: str
    book_title: str
    status: str
    version: int
    cypher_statements: list[CypherStatement] = field(default_factory=list)


def parse_md(content: str) -> MDParseResult:
    """解析 MD 文件（YAML front matter + Markdown body），生成 Cypher。"""
    # 1. 提取 YAML front matter
    fm_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
    if not fm_match:
        raise ValueError("MD 文件缺少 YAML front matter")
    front_matter = yaml.safe_load(fm_match.group(1))
    body = content[fm_match.end():]

    result = MDParseResult(
        book_id=front_matter["book_id"],
        book_title=front_matter["book_title"],
        status=front_matter.get("status", "draft"),
        version=front_matter.get("version", 1),
    )

    # 2. 按 section 解析 body
    sections = re.split(r'^## ', body, flags=re.MULTILINE)
    for section in sections:
        if section.startswith("概念"):
            _parse_concepts(section, result)
        elif section.startswith("主张"):
            _parse_claims(section, result)
        elif section.startswith("运动处方"):
            _parse_prescriptions(section, result)

    return result


def _parse_concepts(section: str, result: MDParseResult):
    """解析概念 → Problem/Solution/BrainRegion/Risk Cypher。"""
    concepts = re.split(r'^### ', section, flags=re.MULTILINE)
    for concept in concepts:
        if not concept.strip():
            continue
        name = concept.split('\n')[0].strip()
        props = _extract_yaml_props(concept)
        entity_type = props.get("entity_type", "AutoEntity")

        params = {
            "name": name,
            "book_id": result.book_id,
            "description": props.get("description", ""),
        }
        extra_sets = ""
        if entity_type == "Problem":
            params["severity"] = props.get("severity", "medium")
            params["symptoms"] = props.get("symptoms", "").split("、") if isinstance(props.get("symptoms"), str) else []
            extra_sets = ", p.severity = $severity, p.symptoms = $symptoms"
        elif entity_type == "Solution":
            params["category"] = props.get("category", "")
            extra_sets = ", s.category = $category"

        # MERGE Book
        result.cypher_statements.append(CypherStatement(
            query="MERGE (b:Book {book_id: $book_id})",
            params={"book_id": result.book_id},
            description=f"MERGE Book {result.book_id}",
        ))

        # MERGE Entity
        label = entity_type if entity_type in ("Problem", "Solution", "BrainRegion", "Risk") else "AutoEntity"
        result.cypher_statements.append(CypherStatement(
            query=f"MERGE (n:{label} {{name: $name, book_id: $book_id}}) SET n.description = $description{extra_sets}",
            params=params,
            description=f"MERGE {label} {name}",
        ))

        # MERGE CONTAINS relationship
        result.cypher_statements.append(CypherStatement(
            query=f"MATCH (b:Book {{book_id: $book_id}}) MATCH (n:{label} {{name: $name, book_id: $book_id}}) MERGE (b)-[:CONTAINS_ENTITY]->(n)",
            params={"book_id": result.book_id, "name": name},
            description=f"Link Book → {name}",
        ))


def _parse_claims(section: str, result: MDParseResult):
    """解析主张 → REQUIRES / TREATS / CAUSES 关系。"""
    claims = re.split(r'^### ', section, flags=re.MULTILINE)
    for claim in claims:
        if not claim.strip():
            continue
        props = _extract_yaml_props(claim)
        src = props.get("source_problem") or props.get("source_concept", "")
        tgt = props.get("source_solution") or props.get("target_concept", "")
        if not src or not tgt:
            continue

        rel_type = {
            "causal": "CAUSES",
            "correlational": "CORRELATES_WITH",
            "supports": "TREATS",
        }.get(props.get("claim_type", ""), "RELATES_TO")

        result.cypher_statements.append(CypherStatement(
            query=f"""
                MATCH (a {{name: $src, book_id: $book_id}})
                MATCH (b {{name: $tgt, book_id: $book_id}})
                MERGE (a)-[r:{rel_type}]->(b)
                SET r.confidence = $confidence, r.evidence = $evidence
            """,
            params={
                "src": src, "tgt": tgt, "book_id": result.book_id,
                "confidence": props.get("confidence", "medium"),
                "evidence": props.get("evidence", ""),
            },
            description=f"CLAIM {src} -[{rel_type}]-> {tgt}",
        ))


def _parse_prescriptions(section: str, result: MDParseResult):
    """解析运动处方 → Exercise + Prescription 节点。"""
    prescriptions = re.split(r'^### ', section, flags=re.MULTILINE)
    for rx in prescriptions:
        if not rx.strip():
            continue
        props = _extract_yaml_props(rx)
        exercise_name = props.get("exercise", "")
        if not exercise_name:
            continue

        rx_id = f"RX_{result.book_id}_{exercise_name.replace(' ', '_')[:30]}"
        result.cypher_statements.append(CypherStatement(
            query="""
                MERGE (rx:Prescription {prescription_id: $rx_id})
                SET rx.frequency = $frequency, rx.duration = $duration,
                    rx.intensity = $intensity, rx.age_range = $age_range,
                    rx.contraindications = $contraindications
                WITH rx
                MATCH (e:Exercise {name: $exercise_name})
                MERGE (rx)-[:PRESCRIBES]->(e)
            """,
            params={
                "rx_id": rx_id,
                "exercise_name": exercise_name,
                "frequency": props.get("frequency", ""),
                "duration": props.get("duration", ""),
                "intensity": props.get("intensity", ""),
                "age_range": props.get("age_range", ""),
                "contraindications": props.get("contraindications", []),
            },
            description=f"PRESCRIPTION {exercise_name}",
        ))


def _extract_yaml_props(text: str) -> dict:
    """从 Markdown 列表中提取 key-value 属性。"""
    props = {}
    for line in text.split('\n'):
        match = re.match(r'^\s*-\s*\*\*(.+?)\*\*:\s*(.+)$', line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            # 尝试解析列表
            if value.startswith('[') and value.endswith(']'):
                try:
                    import yaml as _yaml
                    value = _yaml.safe_load(value)
                except Exception:
                    pass
            props[key] = value
    return props


def to_cypher(result: MDParseResult, dry_run: bool = False) -> list[str]:
    """将 MDParseResult 转换为可执行的 Cypher 语句列表。"""
    return [stmt.query for stmt in result.cypher_statements]
```

---

## 2.6 增量更新（已入库实体编辑）

已入库知识支持编辑后增量更新 Neo4j，方案对标项目已有的提示词管理体系（`PromptVersion` / `PromptImpactAnalyzer`）。

### 核心流程

```
已有 published MD (v1)
  │
  ▼
编辑/重新生成 → 新 draft MD (v2)
  │
  ▼
MDDiffAnalyzer.analyze(v1, v2)
  → added / modified / deleted / unchanged
  │
  ▼
Diff 预览 UI → 用户确认
  │
  ▼
DeltaCypherGenerator → 仅变更部分写入 Neo4j
  │
  ▼
MDMetadata 版本历史可回溯
```

### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/src/models/md_metadata.py` | MD 元数据 ORM |
| `backend/src/models/md_version.py` | MD 版本 ORM |
| `backend/src/core/knowledge_qa/neo4j/md_diff_analyzer.py` | 结构化 Diff 引擎 |
| `backend/src/core/knowledge_qa/neo4j/delta_cypher.py` | Delta Cypher 生成器 |

---

## 2.7 命令行脚本

```bash
# 为一本书生成 MD 草稿
cd backend && uv run python scripts/generate_draft.py --book-id "exercise_book_001"

# 将审核过的 MD 入库 Neo4j
cd backend && uv run python scripts/import_md.py --file "运动改变大脑_v1_reviewed.md"

# 预览 Cypher（不执行）
cd backend && uv run python scripts/import_md.py --file "运动改变大脑_v1_reviewed.md" --dry-run
```

---

## 2.8 验证清单

- [ ] `chapter_parser.py` 正确解析 EPUB → 章节列表
- [ ] `md_generator.py` 可对单本书生成 MD 草稿（人工检查 3 份质量 ≥ 80%）
- [ ] `aggregator.py` 同名实体合并正确，章间矛盾检出
- [ ] `md_parser.py` 解析标准 MD → 正确生成 Cypher
- [ ] `cross_relation.py` 对已知矛盾 case 召回率 ≥ 70%
- [ ] `import_md.py` 入库后 Neo4j 数据可查询
- [ ] 增量更新：修改实体属性不破坏跨书关系

### 质量门禁

| Gate | 条件 | 通过标准 |
|------|------|---------|
| Gate 1 | MD 生成质量 | 人工评审 3 份草稿，实体提取准确率 ≥ 80% |
| Gate 2 | 跨书关系召回率 | 10 个已知 case，召回率 ≥ 70%，误报率 ≤ 30% |

---

## 2.9 预计产出

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/src/core/knowledge_qa/neo4j/chapter_parser.py` | 新增 | EPUB 章节解析 |
| `backend/src/core/knowledge_qa/neo4j/md_generator.py` | 新增 | 四阶段 MD 生成流水线 |
| `backend/src/core/knowledge_qa/neo4j/aggregator.py` | 新增 | 跨章聚合 + 矛盾检测 |
| `backend/src/core/knowledge_qa/neo4j/md_renderer.py` | 新增 | MD 渲染 |
| `backend/src/core/knowledge_qa/neo4j/md_parser.py` | 新增 | MD → Cypher 解析器 |
| `backend/src/core/knowledge_qa/neo4j/cross_relation.py` | 新增 | 跨书关系检测 |
| `backend/src/core/knowledge_qa/neo4j/synonym_registry.py` | 新增 | 同义词注册表 |
| `backend/src/core/knowledge_qa/neo4j/pending_queue.py` | 新增 | 待提炼队列 |
| `backend/src/core/knowledge_qa/neo4j/md_diff_analyzer.py` | 新增 | 增量 Diff 引擎 |
| `backend/src/core/knowledge_qa/neo4j/delta_cypher.py` | 新增 | Delta Cypher 生成 |
| `backend/src/scripts/generate_draft.py` | 新增 | MD 生成 CLI |
| `backend/src/scripts/import_md.py` | 新增 | MD 入库 CLI |
| `backend/src/models/md_metadata.py` | 新增 | MD 元数据 ORM |
| `backend/src/models/md_version.py` | 新增 | MD 版本 ORM |
