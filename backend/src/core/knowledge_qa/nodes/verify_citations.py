"""引用核验节点 — 规则校验 + 降级信号检测 + 运动清单约束验证 + Bundle 增强

原有校验层:
1. excerpt 非空且长度 >= 10 字符
2. chapter 非空
3. citation_id 格式正确（C + 数字）
4. S4 structured_data 为空检测
5. 任意节有正文但 citations 为空检测
6. S3 运动名称在权威清单中
7. S4 运动名称在权威清单中

Bundle 模式新增校验层 (Phase 3):
L2: book_title 白名单校验（必须在 bundle.book_index 中）
L3: excerpt 溯源校验（必须在 bundle.passage_index 原文中找到匹配）
L4: 图谱验证（excerpt 中的实体在 Neo4j 中存在？）
L5: 语义一致性校验（excerpt 与正文引用位置语义匹配——仅标记不剔除）
"""

import difflib
import json
import logging
import re
from typing import Any, Dict, Optional, Set

from src.core.knowledge_qa.bundle import CitationVerdict, KnowledgeBundle, normalize_book_title
from src.core.knowledge_qa.nodes.base import fuzzy_match_exercise, get_exercise_json_path
from src.schemas.knowledge_qa import KnowledgeQAState, SectionOutput, push_progress

logger = logging.getLogger(__name__)

# 运动清单缓存 (模块级，进程重启自动刷新)
_exercise_name_set_cache: Optional[Set[str]] = None
_exercise_json_path = get_exercise_json_path()


def _backfill_exercise_from_json(et: dict) -> bool:
    """如果运动名称被模糊纠正，从运动清单 JSON 回填缺失字段。
    
    Returns: True if any field was backfilled.
    """
    # 检查是否需要回填（category/citation_ids 为空且 name 已修正）
    needs_backfill = (
        not et.get("category")
        or not et.get("target_skills")
        or not et.get("recommendation_rationale")
        or not et.get("citation_ids")
    )
    if not needs_backfill:
        return False
    
    name = et.get("name", "")
    if not name:
        return False
    
    try:
        import json
        ex_data = _load_exercise_data()
        if not ex_data:
            return False
        exercises = ex_data.get("exercises", [])
        for ex in exercises:
            if ex.get("name") == name:
                backed = False
                if not et.get("category") and ex.get("type"):
                    et["category"] = ex["type"]
                    backed = True
                if not et.get("recommendation_rationale") and ex.get("benefits"):
                    et["recommendation_rationale"] = ex["benefits"]
                    backed = True
                if not et.get("citation_ids"):
                    et["citation_ids"] = []
                    backed = True
                return backed
    except Exception:
        pass
    return False


def _load_exercise_data() -> dict | None:
    """加载运动清单 JSON（带缓存）"""
    if hasattr(_load_exercise_data, "_cache"):
        return _load_exercise_data._cache
    try:
        import json
        path = get_exercise_json_path()
        with open(path, "r", encoding="utf-8") as f:
            _load_exercise_data._cache = json.load(f)
        return _load_exercise_data._cache
    except Exception:
        return None



def _get_exercise_name_set() -> set[str]:
    """加载权威运动清单的运动名称集合 (模块级缓存)。"""
    global _exercise_name_set_cache
    if _exercise_name_set_cache is not None:
        return _exercise_name_set_cache
    try:
        with open(_exercise_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _exercise_name_set_cache = set(data.get("exercise_name_set", []))
        logger.info(f"运动清单已加载: {len(_exercise_name_set_cache)} 项运动名称")
    except Exception as e:
        logger.warning(f"加载运动清单失败: {e}，跳过运动约束校验")
        _exercise_name_set_cache = set()
    return _exercise_name_set_cache


def _fuzzy_match_exercise(name: str, valid_set: set[str]) -> Optional[str]:
    """模糊匹配运动名称 — 委托给 base.fuzzy_match_exercise 公共实现。"""
    return fuzzy_match_exercise(name, list(valid_set))


async def verify_citations_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """引用核验 — 规则校验 + 降级信号检测 + Bundle 增强。"""
    await push_progress("verify_citations", "正在核验引用依据…")

    # ── Bundle 模式: 四层校验 ──
    bundle = _get_bundle_from_state(state)
    if bundle is not None:
        logger.info("引用校验: Bundle 模式（四层校验）")
        return await _verify_citations_with_bundle(state, bundle)

    # ── 旧版校验 ──
    return await _verify_citations_legacy(state)


async def _verify_citations_legacy(state: KnowledgeQAState) -> Dict[str, Any]:
    """旧版引用校验逻辑（不动现有实现）。"""
    removed_ids: Set[str] = set()
    auto_fixed_ids: dict[str, str] = {}
    sections = dict(state.sections)
    errors = list(state.errors)
    partial = state.partial

    for i in range(1, 6):
        sec = sections.get(i)
        if not sec:
            continue

        valid_citations = []
        citation_counter = 0
        section_auto_fixed: dict[str, str] = {}

        for c in sec.citations:
            if not c.get("excerpt") or len(c["excerpt"].strip()) < 10:
                removed_ids.add(c.get("citation_id", "unknown"))
                continue
            if not c.get("chapter") or not c["chapter"].strip():
                removed_ids.add(c.get("citation_id", "unknown"))
                continue
            citation_counter += 1
            cid = str(c.get("citation_id", "")) if c.get("citation_id") is not None else ""
            if not re.match(r'^C\d+$', cid):
                new_cid = f"C{citation_counter}"
                section_auto_fixed[cid or "(empty)"] = new_cid
                auto_fixed_ids[cid or "(empty)"] = new_cid
                c = dict(c)
                c["citation_id"] = new_cid
            valid_citations.append(c)

        # 需要重建 SectionOutput 的条件:
        # (a) 有 citation 被剔除或 auto-fix
        # (b) 正文不为空但 citations 始终为空（LLM 未生成引用，0<0 不触发条件(a)）
        citation_count_dropped = len(valid_citations) < len(sec.citations)
        citations_never_generated = bool(
            sec.content and not sec.citations and not valid_citations
        )
        need_rebuild = citation_count_dropped or section_auto_fixed or citations_never_generated

        if need_rebuild:
            new_content = sec.content

            body_ref_matches = list(re.finditer(r'\[?(C\d+)\]?', new_content))
            final_ids = [c.get("citation_id", "") or c["citation_id"] for c in valid_citations]

            if body_ref_matches and final_ids:
                for j in range(min(len(body_ref_matches), len(final_ids)) - 1, -1, -1):
                    match = body_ref_matches[j]
                    old_text = match.group(0)
                    new_id = final_ids[j]
                    new_text = (
                        f"[{new_id}]"
                        if old_text.startswith("[") and old_text.endswith("]")
                        else new_id
                    )
                    new_content = (
                        new_content[:match.start()] + new_text + new_content[match.end():]
                    )
                if len(body_ref_matches) > len(final_ids):
                    for match in body_ref_matches[len(final_ids):]:
                        new_content = (
                            new_content[:match.start()] + new_content[match.end():]
                        )
            elif body_ref_matches and not final_ids:
                for match in reversed(body_ref_matches):
                    new_content = (
                        new_content[:match.start()] + new_content[match.end():]
                    )

            if not valid_citations:
                logger.warning(f"section {i}: 所有引用被剔除，正文保持不变")
                errors.append(f"section_{i}_citations_all_rejected")
                # 仅当 content 也为空时才标记 partial（内容缺失）。
                # citations 被剔除是引用质量问题，不等于数据不完整。
                if not sec.content or len(sec.content.strip()) < 20:
                    partial = True

            sections[i] = SectionOutput(
                index=sec.index,
                title=sec.title,
                content=new_content,
                citations=valid_citations,
                structured_data=sec.structured_data,
            )

        # S4 结构化数据检测（仅在遍历到 i==4 时执行一次）
        if i == 4:
            s4 = sections.get(4)
            if s4 and s4.content and (not s4.structured_data or s4.structured_data == {}):
                if "section_4_structured_data_empty" not in errors:
                    errors.append("section_4_structured_data_empty")
                    partial = True

    if auto_fixed_ids:
        fixed_msg = "; ".join(
            f"{old} → {new}" for old, new in sorted(auto_fixed_ids.items())
        )
        logger.info(f"引用 ID 自动补全: {fixed_msg}")
        errors.append(f"引用 ID 自动补全 ({len(auto_fixed_ids)} 条): {fixed_msg}")
    if removed_ids:
        errors.append(f"核验剔除引用: {', '.join(sorted(removed_ids))}")

    # ---- 运动清单约束校验 (FR-12) ----
    exercise_name_set = _get_exercise_name_set()
    if exercise_name_set:
        s3 = sections.get(3)
        if s3 and s3.structured_data:
            ets = s3.structured_data.get("exercise_types", [])
            for et in ets:
                original = et.get("name", "")
                if not original:
                    continue
                if original not in exercise_name_set:
                    corrected = _fuzzy_match_exercise(original, exercise_name_set)
                    if corrected:
                        et["name"] = corrected
                        et["_original_name"] = original
                        # 回填缺失字段（category、rationale 等）
                        if _backfill_exercise_from_json(et):
                            errors.append(
                                f"运动名称模糊纠正+回填: '{original}' → '{corrected}' (S3)"
                            )
                        else:
                            errors.append(
                                f"运动名称模糊纠正: '{original}' → '{corrected}' (S3)"
                            )
                    else:
                        errors.append(
                            f"运动名称不在清单中: '{original}' (S3, type_id={et.get('type_id', '?')})"
                        )

        s4 = sections.get(4)
        if s4 and s4.structured_data and s4.structured_data != {}:
            phases = s4.structured_data.get("phases", [])
            s4_exercise_violations = 0
            s4_exercise_corrected = 0
            for ph in phases:
                for wk in ph.get("weeks", []):
                    for day in wk.get("days", []):
                        for ex in day.get("main_exercises", []):
                            original = ex.get("name", "")
                            if not original:
                                continue
                            if original not in exercise_name_set:
                                corrected = _fuzzy_match_exercise(
                                    original, exercise_name_set
                                )
                                if corrected:
                                    ex["name"] = corrected
                                    ex["_original_name"] = original
                                    s4_exercise_corrected += 1
                                else:
                                    s4_exercise_violations += 1
            if s4_exercise_corrected:
                errors.append(
                    f"运动名称模糊纠正 (S4): {s4_exercise_corrected} 项"
                )
            if s4_exercise_violations:
                errors.append(
                    f"运动名称不在清单中 (S4): {s4_exercise_violations} 项"
                )

    await push_progress("verify_citations_done", "引用核验完成")

    return {
        "sections": sections,
        "errors": errors,
        "current_step": ["verify_citations_done"],
        "partial": partial,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3: Bundle-enhanced citation verification
# ═══════════════════════════════════════════════════════════════════════════════


def _get_bundle_from_state(state: KnowledgeQAState) -> KnowledgeBundle | None:
    """从 state 中提取 KnowledgeBundle（如果可用）。"""
    return getattr(state, "knowledge_bundle", None)


async def _verify_citations_with_bundle(
    state: KnowledgeQAState,
    bundle: KnowledgeBundle,
) -> Dict[str, Any]:
    """四层引用校验: 结构 → 白名单 → 溯源 → 图谱验证 → 语义一致性（仅标记）。

    先执行旧版结构校验，再叠加三层新增校验。
    """
    # ── 先执行 Legacy 校验（结构 + 降级信号 + 运动清单）──
    legacy_result = await _verify_citations_legacy(state)
    sections = legacy_result["sections"]
    errors = legacy_result["errors"]
    partial = legacy_result["partial"]

    # ── 叠加 Bundle 校验（L2-L5）──
    total_verified = 0
    total_corrected = 0
    total_rejected = 0
    total_semantic_mismatch = 0

    for i in range(1, 6):
        sec = sections.get(i)
        if not sec:
            continue

        verified_citations = []
        for citation in sec.citations:
            verdict = _check_citation_enhanced(citation, bundle, sec.content)

            if verdict.passed:
                # 标记校验元数据（前端展示用）
                if verdict.corrected_book_title:
                    citation["_book_title_corrected"] = True
                    citation["_original_book_title"] = citation.get("book_title", "")
                if verdict.source_passage_id:
                    citation["_source_passage_id"] = verdict.source_passage_id
                if verdict.neo4j_verified_entities:
                    citation["_neo4j_verified_entities"] = verdict.neo4j_verified_entities
                if verdict.semantic_mismatch:
                    citation["_semantic_mismatch"] = True
                    total_semantic_mismatch += 1
                citation["_trust_level"] = verdict.trust_level
                verified_citations.append(citation)
                total_verified += 1
                if verdict.corrected_book_title:
                    total_corrected += 1
            else:
                errors.append(
                    f"section_{i}_citation_{citation.get('citation_id', '?')}: "
                    f"{verdict.reason}"
                )
                total_rejected += 1

        # 重建 SectionOutput（剔除不合格引用）
        if len(verified_citations) < len(sec.citations):
            sections[i] = SectionOutput(
                index=sec.index, title=sec.title,
                content=sec.content,
                citations=verified_citations,
                structured_data=sec.structured_data,
            )

    logger.info(
        "Bundle 引用校验完成: %d 通过, %d 修正, %d 剔除, %d 语义存疑",
        total_verified, total_corrected, total_rejected, total_semantic_mismatch,
    )

    return {
        "sections": sections,
        "errors": errors,
        "current_step": ["verify_citations_done"],
        "partial": partial,
    }


def _check_citation_enhanced(
    citation: dict,
    bundle: KnowledgeBundle,
    sec_content: str = "",
) -> CitationVerdict:
    """单条引用五层校验: 结构 → 白名单 → 溯源 → 图谱验证 → 语义一致性。"""

    # ── L1: 结构完整性（已在 legacy 中过筛，此处兜底）──
    if not citation.get("excerpt") or len(citation["excerpt"].strip()) < 10:
        return CitationVerdict(False, "excerpt 过短或为空")
    if not citation.get("chapter") or not citation["chapter"].strip():
        return CitationVerdict(False, "chapter 为空")

    # ── L2: 白名单校验 ──
    book_title = citation.get("book_title", "")
    norm_title = normalize_book_title(book_title)
    valid_titles = {
        meta.normalized_title for meta in bundle.book_index.values()
    }
    valid_titles.update(m.title for m in bundle.book_index.values())

    corrected_title = ""
    if norm_title not in valid_titles:
        # 模糊匹配修正
        matched = _fuzzy_match_book(norm_title, bundle.book_index)
        if matched:
            citation["book_title"] = matched.title
            corrected_title = matched.title
        else:
            return CitationVerdict(False, f"book_title '{book_title}' 不在白名单中")

    # ── L3: 溯源校验 ──
    excerpt = citation["excerpt"].strip()
    source_verified = False
    source_passage_id = ""

    for pid, passage in bundle.passage_index.items():
        if excerpt in passage.content:
            source_verified = True
            source_passage_id = pid
            break

    if not source_verified:
        # 模糊匹配（substring similarity）
        for pid, passage in bundle.passage_index.items():
            if _fuzzy_excerpt_match(excerpt, passage.content) >= 0.85:
                source_verified = True
                source_passage_id = pid
                break

    if not source_verified:
        return CitationVerdict(
            False, f"excerpt 在原文中未找到匹配（可能被 LLM 改写）",
        )

    # ── L4: 图谱验证 ──
    neo4j_entities = _extract_entity_names_from_bundle(excerpt, bundle)

    # ── L5: 语义一致性校验（仅标记不剔除）──
    semantic_mismatch = False
    citation_id = citation.get("citation_id", "")
    if citation_id and sec_content:
        marker_pattern = re.compile(rf"\[?{re.escape(citation_id)}\]?")
        marker_match = marker_pattern.search(sec_content)
        if marker_match:
            start = max(0, marker_match.start() - 80)
            end = min(len(sec_content), marker_match.end() + 80)
            nearby_text = sec_content[start:end]
            # 简单 token overlap 判定（低阈值只过滤明显错配）
            overlap = _token_overlap(excerpt, nearby_text)
            if overlap < 0.25:
                semantic_mismatch = True

    return CitationVerdict(
        passed=True,
        corrected_book_title=corrected_title,
        source_passage_id=source_passage_id,
        neo4j_verified_entities=neo4j_entities,
        semantic_mismatch=semantic_mismatch,
    )


# ── L2-L5 helpers ──


def _fuzzy_match_book(
    normalized: str,
    book_index: dict,
) -> Any | None:
    """模糊匹配书名——从白名单中找最佳匹配。"""
    if not normalized or normalized == "未知":
        return None

    valid_entries: list[tuple[str, Any]] = []
    for bid, meta in book_index.items():
        valid_entries.append((meta.normalized_title, meta))
        if meta.title != meta.normalized_title:
            valid_entries.append((meta.title, meta))

    # 精确匹配
    for name, meta in valid_entries:
        if normalized == name:
            return meta

    # 子串匹配
    for name, meta in valid_entries:
        if normalized in name or name in normalized:
            return meta

    # 编辑距离匹配
    names = [v[0] for v in valid_entries]
    matches = difflib.get_close_matches(normalized, names, n=1, cutoff=0.7)
    if matches:
        for name, meta in valid_entries:
            if name == matches[0]:
                return meta

    return None


def _fuzzy_excerpt_match(excerpt: str, passage_content: str) -> float:
    """计算 excerpt 与 passage 内容的模糊匹配度。

    使用最长公共子串比例 + token overlap 的组合。
    """
    if not excerpt or not passage_content:
        return 0.0

    # 最长公共子串
    seq = difflib.SequenceMatcher(None, excerpt, passage_content)
    lcs_ratio = seq.ratio()

    # token overlap
    tok_overlap = _token_overlap(excerpt, passage_content)

    return max(lcs_ratio, tok_overlap)


def _token_overlap(text1: str, text2: str) -> float:
    """计算两个文本的 token 重叠比例。"""
    tokens1 = set(text1)
    tokens2 = set(text2)
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1 & tokens2
    return len(intersection) / min(len(tokens1), len(tokens2))


def _extract_entity_names_from_bundle(
    text: str,
    bundle: KnowledgeBundle,
) -> list[str]:
    """从文本中提取在 Neo4j 中存在的实体名。"""
    found: list[str] = []
    text_lower = text.lower()

    for etype, entities in bundle.neo4j_entities.items():
        for entity in entities:
            if entity.name and entity.name.lower() in text_lower:
                found.append(entity.name)

    return list(set(found))
