"""引用核验节点 — 规则校验 + 降级信号检测 + 运动清单约束验证

检查每条 citation 的结构完整性：
1. excerpt 非空且长度 >= 10 字符
2. chapter 非空
3. citation_id 格式正确（C + 数字）

降级信号检测：
4. S4 structured_data 为空
5. 任意节有正文但 citations 为空

运动清单约束 (FR-12)：
6. S3 exercise_types[].name 必须在权威运动清单中
7. S4 phases→weeks→days→main_exercises[].name 必须在权威运动清单中
"""

import json
import logging
import re
from typing import Any, Dict, Optional, Set

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
    """引用核验 — 规则校验 + 降级信号检测。"""
    await push_progress("verify_citations", "正在核验引用依据…")

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
                        partial = True

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
                partial = True

    await push_progress("verify_citations_done", "引用核验完成")

    return {
        "sections": sections,
        "errors": errors,
        "current_step": ["verify_citations_done"],
        "partial": partial,
    }
