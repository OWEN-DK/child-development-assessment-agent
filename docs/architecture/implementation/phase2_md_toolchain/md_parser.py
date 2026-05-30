"""MD → Cypher 解析器 — 解析审核后的 MD 文件，生成 Cypher MERGE 语句。

放置位置: backend/src/core/knowledge_qa/neo4j/md_parser.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml


@dataclass
class CypherStatement:
    """一条 Cypher 语句。"""
    query: str
    params: dict
    description: str = ""


@dataclass
class MDParseResult:
    """MD 解析结果。"""
    book_id: str
    book_title: str
    status: str
    version: int
    cypher_statements: list[CypherStatement] = field(default_factory=list)


def parse_md(content: str) -> MDParseResult:
    """解析 MD 文件（YAML front matter + Markdown body），生成 Cypher。

    Args:
        content: MD 文件完整内容

    Returns:
        MDParseResult 包含所有待执行的 Cypher 语句

    Raises:
        ValueError: 缺少 YAML front matter
    """
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

    sections = re.split(r'^## ', body, flags=re.MULTILINE)
    for section in sections:
        if section.startswith("概念"):
            _parse_concepts(section, result)
        elif section.startswith("主张"):
            _parse_claims(section, result)
        elif section.startswith("运动处方"):
            _parse_prescriptions(section, result)

    return result


def to_cypher_list(result: MDParseResult) -> list[str]:
    """将 MDParseResult 转换为可执行的 Cypher 字符串列表。"""
    return [stmt.query.strip() for stmt in result.cypher_statements]


def execute_cypher(result: MDParseResult, neo4j_session, dry_run: bool = False) -> int:
    """在 Neo4j session 中执行所有 Cypher 语句。

    Args:
        result: 解析结果
        neo4j_session: Neo4j session
        dry_run: 仅打印不执行

    Returns:
        执行成功的语句数
    """
    executed = 0
    for stmt in result.cypher_statements:
        if dry_run:
            print(f"[DRY RUN] {stmt.description}")
            print(f"  Query: {stmt.query[:100]}...")
            print(f"  Params: {stmt.params}")
            executed += 1
        else:
            try:
                neo4j_session.run(stmt.query, **stmt.params)
                executed += 1
            except Exception as e:
                print(f"❌ 执行失败: {stmt.description} — {e}")

    return executed


def _parse_concepts(section: str, result: MDParseResult):
    """解析概念 → Problem/Solution/BrainRegion/Risk。"""
    concepts = re.split(r'^### ', section, flags=re.MULTILINE)
    for concept in concepts:
        if not concept.strip():
            continue
        name = concept.split('\n')[0].strip()
        props = _extract_props(concept)
        entity_type = props.get("entity_type", "AutoEntity")

        params = {
            "name": name,
            "book_id": result.book_id,
            "description": props.get("description", ""),
        }

        extra_sets = ""
        if entity_type == "Problem":
            params["severity"] = props.get("severity", "medium")
            symptoms = props.get("symptoms", "")
            if isinstance(symptoms, str):
                symptoms = [s.strip() for s in symptoms.split("、") if s.strip()]
            params["symptoms"] = symptoms
            extra_sets = ", p.severity = $severity, p.symptoms = $symptoms"
        elif entity_type == "Solution":
            params["category"] = props.get("category", "")
            extra_sets = ", s.category = $category"

        label = entity_type if entity_type in ("Problem", "Solution", "BrainRegion", "Risk") else "AutoEntity"

        result.cypher_statements.append(CypherStatement(
            query=f"MERGE (n:{label} {{name: $name, book_id: $book_id}}) SET n.description = $description{extra_sets}",
            params=params,
            description=f"MERGE {label} {name}",
        ))

        result.cypher_statements.append(CypherStatement(
            query=f"""
                MATCH (b:Book {{book_id: $book_id}})
                MATCH (n:{label} {{name: $name, book_id: $book_id}})
                MERGE (b)-[:CONTAINS_ENTITY]->(n)
            """,
            params={"book_id": result.book_id, "name": name},
            description=f"Link Book → {name}",
        ))


def _parse_claims(section: str, result: MDParseResult):
    """解析主张 → 关系。"""
    claims = re.split(r'^### ', section, flags=re.MULTILINE)
    for claim in claims:
        if not claim.strip():
            continue
        props = _extract_props(claim)
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
            description=f"CLAIM {src} → {tgt}",
        ))


def _parse_prescriptions(section: str, result: MDParseResult):
    """解析运动处方 → Exercise + Prescription。"""
    prescriptions = re.split(r'^### ', section, flags=re.MULTILINE)
    for rx in prescriptions:
        if not rx.strip():
            continue
        props = _extract_props(rx)
        exercise_name = props.get("exercise", "")
        if not exercise_name:
            continue

        rx_id = f"RX_{result.book_id}_{exercise_name.replace(' ', '_')[:30]}"
        result.cypher_statements.append(CypherStatement(
            query="""
                MERGE (rx:Prescription {prescription_id: $rx_id})
                SET rx.frequency = $frequency, rx.duration = $duration,
                    rx.intensity = $intensity, rx.age_range = $age_range
                WITH rx
                MERGE (e:Exercise {name: $exercise_name, book_id: $book_id})
                ON CREATE SET e.curation_status = 'pending'
                MERGE (rx)-[:PRESCRIBES]->(e)
            """,
            params={
                "rx_id": rx_id,
                "exercise_name": exercise_name,
                "book_id": result.book_id,
                "frequency": props.get("frequency", ""),
                "duration": props.get("duration", ""),
                "intensity": props.get("intensity", ""),
                "age_range": props.get("age_range", ""),
            },
            description=f"PRESCRIPTION {exercise_name}",
        ))


def _extract_props(text: str) -> dict:
    """从 Markdown 列表提取 key-value 属性。"""
    props = {}
    for line in text.split('\n'):
        match = re.match(r'^\s*-\s*\*\*(.+?)\*\*:\s*(.+)$', line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            if value.startswith('[') and value.endswith(']'):
                try:
                    value = yaml.safe_load(value)
                except Exception:
                    pass
            props[key] = value
    return props
