"""实体提取器

每本书导入完成后调用一次：用已有 topic 标签做种子，一次 LLM 调用同时完成实体归类 + 关系提取。
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.core.llm.factory import LLMServiceFactoryCompat

logger = logging.getLogger(__name__)

# 领域实体类型（7 类）
ENTITY_TYPES = [
    "development_concept",    # 发展概念
    "symptom_behavior",       # 症状/行为
    "intervention_method",    # 干预方法
    "assessment_tool",        # 评估工具
    "brain_region",           # 脑区
    "age_milestone",          # 年龄里程碑
    "clinical_population",    # 临床人群
]

# 关系类型（6 类）
RELATION_TYPES = [
    "causes",                 # X 导致 Y
    "treats",                 # X 治疗 Y
    "assesses",               # X 评估 Y
    "related_to",             # X 关联 Y
    "contraindicates",        # X 禁忌 Y
    "develops_at",            # X 在 Y 年龄发展
]


@dataclass
class Entity:
    name: str
    entity_type: str
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    book_id: str = ""
    chunk_ids: list[str] = field(default_factory=list)


@dataclass
class Relation:
    source: str
    target: str
    relation_type: str
    description: str = ""
    confidence: float = 1.0


EXTRACTION_SYSTEM_PROMPT = """你是一个儿童发展领域专家。你的任务是从给定的主题标签和文本段落中提取结构化的知识图谱实体和关系。

## 实体类型
{entity_types}

## 关系类型
{relation_types}

## 规则
1. 将每个主题标签归类到上述实体类型之一
2. 补充文本中出现但标签未覆盖的实体
3. 为每个实体提供简洁描述（1-2 句）
4. 识别实体间的关系，关系必须用上述关系类型之一
5. 有名称为空的实体、源/目标不存在的关系，都丢弃

## 输出格式
严格按以下 JSON 格式输出：
```json
{{
  "entities": [
    {{"name": "实体名", "type": "development_concept", "description": "简要描述", "aliases": ["别名"]}}
  ],
  "relations": [
    {{"source": "实体A", "target": "实体B", "type": "causes", "description": "关系描述"}}
  ]
}}
```"""


def _build_extraction_prompt(
    topics: list[str],
    sample_texts: list[str],
) -> str:
    topics_list = "\n".join(f"- {t}" for t in topics[:80])
    texts = "\n\n---\n\n".join(sample_texts[:6])

    entity_types_str = "\n".join(f"- {t}" for t in ENTITY_TYPES)
    relation_types_str = "\n".join(f"- {t}" for t in RELATION_TYPES)

    system = EXTRACTION_SYSTEM_PROMPT.format(
        entity_types=entity_types_str,
        relation_types=relation_types_str,
    )

    user = f"""## 已有主题标签（种子）
{topics_list}

## 代表性文本段落
{texts}

请提取实体和关系，输出 JSON。"""

    return system, user


def _parse_extraction_result(raw: str, book_id: str) -> tuple[list[Entity], list[Relation]]:
    """解析 LLM 返回的 JSON，提取 Entity 和 Relation 列表"""
    # 去掉可能的 markdown code block 标记
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
    if clean.endswith("```"):
        clean = clean.rsplit("\n", 1)[0] if "\n" in clean else clean[:-3]

    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        import json_repair
        data = json_repair.loads(clean)

    entities = []
    for e in data.get("entities", []):
        if not e.get("name"):
            continue
        entities.append(Entity(
            name=e["name"],
            entity_type=e.get("type", "development_concept"),
            description=e.get("description", ""),
            aliases=e.get("aliases", []),
            book_id=book_id,
        ))

    relations = []
    entity_names = {e.name for e in entities}
    for r in data.get("relations", []):
        if not r.get("source") or not r.get("target"):
            continue
        if r["source"] not in entity_names or r["target"] not in entity_names:
            continue
        relations.append(Relation(
            source=r["source"],
            target=r["target"],
            relation_type=r.get("type", "related_to"),
            description=r.get("description", ""),
            confidence=float(r.get("confidence", 1.0)),
        ))

    return entities, relations


def _assign_chunk_ids_by_topics(
    entities: list[Entity],
    chunks: list[Any],
    topics_per_chunk: list[list[str]],
) -> None:
    """通过 topic 标签反查，将实体的名称/别名匹配到包含该 topic 的 chunks。"""
    # 构建 topic → chunk_ids 映射
    topic_to_chunks: dict[str, list[str]] = {}
    for i, topics in enumerate(topics_per_chunk):
        chunk_id = str(i)
        if hasattr(chunks[i], "node_id"):
            chunk_id = chunks[i].node_id
        elif hasattr(chunks[i], "id_"):
            chunk_id = chunks[i].id_
        for t in topics:
            if t:
                topic_to_chunks.setdefault(t, []).append(chunk_id)

    for entity in entities:
        # 用实体名和别名匹配 topic
        names_to_check = [entity.name] + entity.aliases
        matched_chunks = set()
        for name in names_to_check:
            if name in topic_to_chunks:
                matched_chunks.update(topic_to_chunks[name])
        if matched_chunks:
            entity.chunk_ids = list(matched_chunks)


async def extract_entities_relations(
    book_id: str,
    chunks: list[Any],
    topics_per_chunk: list[list[str]],
    model_name: str = "qwen3.5-27b",
) -> tuple[list[Entity], list[Relation]]:
    """每本书导入完成后调用。一次 LLM 调用完成实体归类 + 关系提取。

    Args:
        book_id: 书籍 ID
        chunks: 文档块列表（Node 对象）
        topics_per_chunk: 每个块的 topic 标签列表
        model_name: 用于提取的 LLM 模型

    Returns:
        (entities, relations) 元组
    """
    # 汇聚种子数据
    all_topics = list(dict.fromkeys(
        t for topics in topics_per_chunk for t in topics if t
    ))

    # 采样代表性文本（最长 12000 字符）
    sample_texts = []
    total_chars = 0
    for chunk in chunks:
        text = chunk.get_content() if hasattr(chunk, "get_content") else str(chunk)
        if total_chars + len(text) > 12000:
            remaining = 12000 - total_chars
            if remaining > 200:
                sample_texts.append(text[:remaining])
            break
        sample_texts.append(text)
        total_chars += len(text)

    if not all_topics and not sample_texts:
        logger.warning(f"书籍 {book_id} 无 topic 标签和文本，跳过实体提取")
        return [], []

    system, user = _build_extraction_prompt(all_topics, sample_texts)

    try:
        raw_model = LLMServiceFactoryCompat.create_raw(
            model_name=model_name,
            temperature=0.2,
        )
        from langchain_core.messages import HumanMessage, SystemMessage

        response = await raw_model.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=user),
        ])
        content = response.content if hasattr(response, "content") else str(response)
        entities, relations = _parse_extraction_result(content, book_id)

        # 通过 topic 标签反查 chunk_ids：实体名或别名匹配某 chunk 的 topic 时，关联该 chunk
        _assign_chunk_ids_by_topics(entities, chunks, topics_per_chunk)

        logger.info(
            f"书籍 {book_id} 实体提取完成: {len(entities)} 个实体, {len(relations)} 条关系"
        )
        return entities, relations

    except Exception as e:
        logger.exception(f"书籍 {book_id} 实体提取失败: {e}")
        return [], []
