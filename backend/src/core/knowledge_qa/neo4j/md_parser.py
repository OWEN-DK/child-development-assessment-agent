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
        elif section.startswith("核心论点"):
            _parse_key_arguments(section, result)
        elif section.startswith("案例"):
            _parse_case_studies(section, result)
        elif section.startswith("数据"):
            _parse_data_points(section, result)
        elif section.startswith("章节摘要"):
            _parse_chapter_summary(section, result)

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


# 已知实体类型（全部映射为 Neo4j label）
KNOWN_ENTITY_TYPES = {
    "Problem", "Solution", "BrainRegion", "Risk",
    "CognitiveProcess", "Theory", "Mechanism",
    "DevelopmentalStage", "Strategy", "KeyInsight", "ResearchFinding",
    "Exercise", "RootCause",
}


def _parse_concepts(section: str, result: MDParseResult):
    """解析概念 → 所有已知实体类型，未知类型回退到 AutoEntity。"""
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
        elif entity_type == "Theory":
            params["key_figures"] = props.get("key_figures", "")
            extra_sets = ", n.key_figures = $key_figures"
        elif entity_type == "Mechanism":
            params["mechanism_detail"] = props.get("mechanism", "")
            extra_sets = ", n.mechanism_detail = $mechanism_detail"
        elif entity_type == "CognitiveProcess":
            params["brain_regions"] = props.get("brain_regions", "")
            extra_sets = ", n.brain_regions = $brain_regions"
        elif entity_type == "ResearchFinding":
            params["evidence"] = props.get("evidence", "")
            extra_sets = ", n.evidence = $evidence"
        elif entity_type == "KeyInsight":
            extra_sets = ""  # description 已足够
        elif entity_type == "Strategy":
            extra_sets = ""
        elif entity_type == "DevelopmentalStage":
            extra_sets = ""
        else:
            entity_type = "AutoEntity"

        label = entity_type if entity_type in KNOWN_ENTITY_TYPES else "AutoEntity"

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


def parse_md_to_cypher(content: str, book_id: str) -> MDParseResult:
    """解析 MD 内容生成 Cypher 语句（无需 YAML front matter）。

    支持 _placeholder_md 产出的格式：
    ## 问题 (Problem) / 方案 (Solution) / 脑区 (BrainRegion) / 运动 (Exercise) / 处方 (Prescription) / 根因 (RootCause)

    Args:
        content: MD 文件内容
        book_id: 书籍 ID

    Returns:
        MDParseResult 包含所有待执行的 Cypher 语句
    """
    result = MDParseResult(
        book_id=book_id,
        book_title="",
        status="draft",
        version=1,
    )

    # 确保 Book 节点存在
    result.cypher_statements.append(CypherStatement(
        query="MERGE (b:Book {book_id: $book_id}) SET b.title = $title",
        params={"book_id": book_id, "title": book_id},
        description=f"MERGE Book {book_id}",
    ))

    sections = re.split(r'^## ', content, flags=re.MULTILINE)
    for section in sections:
        if not section.strip():
            continue
        header = section.split('\n')[0].strip()

        if 'Problem' in header or '问题' in header:
            _parse_entities(section, result, 'Problem')
        elif 'Solution' in header or '方案' in header:
            _parse_entities(section, result, 'Solution')
        elif 'BrainRegion' in header or '脑区' in header:
            _parse_entities(section, result, 'BrainRegion')
        elif 'Exercise' in header or '运动' in header:
            _parse_entities(section, result, 'Exercise')
        elif 'Prescription' in header or '处方' in header:
            _parse_prescriptions_md(section, result)
        elif 'RootCause' in header or '根因' in header:
            _parse_entities(section, result, 'RootCause')

    return result


def _parse_entities(section: str, result: MDParseResult, entity_type: str):
    """从 MD 段落解析实体并生成 Cypher。"""
    subsections = re.split(r'^### ', section, flags=re.MULTILINE)
    for i, sub in enumerate(subsections):
        if not sub.strip():
            continue
        # 跳过第一个子段（它是 ## section header 的内容）
        if i == 0:
            continue
        name = sub.split('\n')[0].strip()
        props = _extract_props(sub)
        if not name:
            continue

        label = entity_type
        params = {
            "name": name,
            "book_id": result.book_id,
            "description": props.get("description", sub.split('\n')[-1].strip() if '\n' in sub else ""),
        }

        extra_sets = ""
        if entity_type == "Problem":
            params["severity"] = props.get("severity", "medium")
            extra_sets = ", n.severity = $severity"
        elif entity_type == "Solution":
            params["effectiveness"] = props.get("有效性", props.get("effectiveness", "medium"))
            extra_sets = ", n.effectiveness = $effectiveness"
        elif entity_type == "BrainRegion":
            params["function_desc"] = props.get("功能", props.get("function", ""))
            extra_sets = ", n.function_desc = $function_desc"
        elif entity_type == "Exercise":
            params["intensity"] = props.get("强度", props.get("intensity", "medium"))
            params["duration"] = props.get("时长", props.get("duration", ""))
            extra_sets = ", n.intensity = $intensity, n.duration = $duration"
        elif entity_type == "RootCause":
            params["associated_problems"] = props.get("关联问题", props.get("associated_problems", ""))
            extra_sets = ", n.associated_problems = $associated_problems"

        result.cypher_statements.append(CypherStatement(
            query=f"MERGE (n:{label} {{name: $name, book_id: $book_id}}) SET n.description = $description{extra_sets}",
            params=params,
            description=f"MERGE {label} {name}",
        ))

        # Link to Book
        result.cypher_statements.append(CypherStatement(
            query=f"""
                MATCH (b:Book {{book_id: $book_id}})
                MATCH (n:{label} {{name: $name, book_id: $book_id}})
                MERGE (b)-[:CONTAINS_ENTITY]->(n)
            """,
            params={"book_id": result.book_id, "name": name},
            description=f"Link Book → {name}",
        ))


def _parse_prescriptions_md(section: str, result: MDParseResult):
    """解析处方段落生成 Cypher。"""
    subsections = re.split(r'^### ', section, flags=re.MULTILINE)
    for i, sub in enumerate(subsections):
        if not sub.strip():
            continue
        # 跳过第一个子段（它是 ## section header 的内容）
        if i == 0:
            continue
        name = sub.split('\n')[0].strip()
        props = _extract_props(sub)

        target_problem = props.get("target_problem", name)
        exercise = props.get("exercise", "")
        frequency = props.get("frequency", "")

        rx_id = f"RX_{result.book_id}_{name.replace(' ', '_')[:30]}"

        result.cypher_statements.append(CypherStatement(
            query="""
                MERGE (rx:Prescription {prescription_id: $rx_id})
                SET rx.target_problem = $target_problem, rx.exercise = $exercise,
                    rx.frequency = $frequency
            """,
            params={
                "rx_id": rx_id,
                "target_problem": target_problem,
                "exercise": exercise,
                "frequency": frequency,
            },
            description=f"MERGE Prescription {name}",
        ))

        result.cypher_statements.append(CypherStatement(
            query="""
                MATCH (b:Book {book_id: $book_id})
                MATCH (rx:Prescription {prescription_id: $rx_id})
                MERGE (b)-[:HAS_PRESCRIPTION]->(rx)
            """,
            params={"book_id": result.book_id, "rx_id": rx_id},
            description=f"Link Book → Prescription {name}",
        ))


def _parse_key_arguments(section: str, result: MDParseResult):
    """解析核心论点 → KeyInsight 节点。"""
    args = re.split(r'^### ', section, flags=re.MULTILINE)
    for arg in args:
        if not arg.strip():
            continue
        props = _extract_yaml_list_props(arg)
        argument = props.get("argument", arg.split('\n')[0].strip())
        if not argument:
            continue

        evidence = props.get("supporting_evidence", [])
        counter = props.get("counterarguments", [])
        desc = argument
        if evidence:
            desc += f" | 支撑: {'; '.join(evidence)}"
        if counter:
            desc += f" | 局限: {'; '.join(counter)}"

        name = argument[:60]
        result.cypher_statements.append(CypherStatement(
            query="MERGE (n:KeyInsight {name: $name, book_id: $book_id}) SET n.description = $description",
            params={"name": name, "book_id": result.book_id, "description": desc},
            description=f"MERGE KeyInsight {name}",
        ))
        result.cypher_statements.append(CypherStatement(
            query="""
                MATCH (b:Book {book_id: $book_id})
                MATCH (n:KeyInsight {name: $name, book_id: $book_id})
                MERGE (b)-[:CONTAINS_ENTITY]->(n)
            """,
            params={"book_id": result.book_id, "name": name},
            description=f"Link Book → KeyInsight {name}",
        ))


def _parse_case_studies(section: str, result: MDParseResult):
    """解析案例 → KeyInsight 节点 + 关系。"""
    cases = re.split(r'^### ', section, flags=re.MULTILINE)
    for case in cases:
        if not case.strip():
            continue
        props = _extract_yaml_list_props(case)
        title = props.get("title", case.split('\n')[0].strip())
        summary = props.get("summary", "")
        takeaway = props.get("takeaway", "")
        related = props.get("related_concepts", [])

        name = title[:60]
        desc = summary
        if takeaway:
            desc += f" → {takeaway}"

        result.cypher_statements.append(CypherStatement(
            query="MERGE (n:KeyInsight {name: $name, book_id: $book_id}) SET n.description = $description",
            params={"name": name, "book_id": result.book_id, "description": desc},
            description=f"MERGE CaseStudy {name}",
        ))
        result.cypher_statements.append(CypherStatement(
            query="""
                MATCH (b:Book {book_id: $book_id})
                MATCH (n:KeyInsight {name: $name, book_id: $book_id})
                MERGE (b)-[:CONTAINS_ENTITY]->(n)
            """,
            params={"book_id": result.book_id, "name": name},
            description=f"Link Book → CaseStudy {name}",
        ))


def _parse_data_points(section: str, result: MDParseResult):
    """解析数据点 → ResearchFinding 节点。"""
    points = re.split(r'^### ', section, flags=re.MULTILINE)
    for point in points:
        if not point.strip():
            continue
        props = _extract_yaml_list_props(point)
        metric = props.get("metric", point.split('\n')[0].strip())
        value = props.get("value", "")
        context = props.get("context", "")
        source_attr = props.get("source_attribution", "")

        name = f"{metric}: {value}" if value else metric
        name = name[:80]
        desc = f"{context}"
        if source_attr:
            desc += f" (来源: {source_attr})"

        result.cypher_statements.append(CypherStatement(
            query="MERGE (n:ResearchFinding {name: $name, book_id: $book_id}) SET n.description = $description",
            params={"name": name, "book_id": result.book_id, "description": desc},
            description=f"MERGE DataPoint {name}",
        ))
        result.cypher_statements.append(CypherStatement(
            query="""
                MATCH (b:Book {book_id: $book_id})
                MATCH (n:ResearchFinding {name: $name, book_id: $book_id})
                MERGE (b)-[:CONTAINS_ENTITY]->(n)
            """,
            params={"book_id": result.book_id, "name": name},
            description=f"Link Book → DataPoint {name}",
        ))


def _parse_chapter_summary(section: str, result: MDParseResult):
    """解析章节摘要 → 附加到 Book 节点。"""
    props = _extract_yaml_list_props(section)
    theme = props.get("central_theme", "")
    takeaways = props.get("key_takeaways", [])
    connection = props.get("connection_to_book", "")

    if not theme:
        return

    # 将摘要信息附加为 Book 节点的属性
    summary_text = theme
    if takeaways:
        summary_text += " | 要点: " + "; ".join(takeaways)
    if connection:
        summary_text += " | 关联: " + connection

    # 创建一个 KeyInsight 存储章节核心主题
    result.cypher_statements.append(CypherStatement(
        query="MERGE (n:KeyInsight {name: $name, book_id: $book_id}) SET n.description = $description",
        params={"name": f"[章节核心] {theme[:50]}", "book_id": result.book_id, "description": summary_text},
        description=f"MERGE ChapterSummary {theme[:30]}",
    ))


def _extract_yaml_list_props(text: str) -> dict:
    """从可能包含 YAML 列表格式的文本中提取 key-value。"""
    props = {}
    for line in text.split('\n'):
        match = re.match(r'^\s*-\s*\*\*(.+?)\*\*:\s*(.+)$', line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            # 尝试解析 YAML 列表
            if value.startswith('[') and value.endswith(']'):
                try:
                    import yaml as _yaml
                    value = _yaml.safe_load(value)
                except Exception:
                    pass
            props[key] = value
    return props
