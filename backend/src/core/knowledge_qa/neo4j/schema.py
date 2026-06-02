"""Neo4j 节点类型和关系类型常量定义。

包含：
- 原有 8 种业务实体类型 + AutoEntity/AutoCommunity
- D2G 新增 7 种通用实体类型
- CustomRule 自定义知识节点类型
- 关系类型（原有 + D2G + 跨书 + 自定义知识）
- 便捷常量集合
"""

# ── 原有节点类型 ─────────────────────────────────────────────
NODE_BOOK = "Book"
NODE_PROBLEM = "Problem"
NODE_ROOTCAUSE = "RootCause"
NODE_SOLUTION = "Solution"
NODE_EXERCISE = "Exercise"
NODE_PRESCRIPTION = "Prescription"
NODE_BRAINREGION = "BrainRegion"
NODE_CHILDPROFILE = "ChildProfile"
NODE_RISK = "Risk"
NODE_CHAPTER = "Chapter"
NODE_AUTOENTITY = "AutoEntity"
NODE_AUTOCOMMUNITY = "AutoCommunity"

# ── D2G 新增节点类型（§07-4.1） ──────────────────────────────
NODE_COGNITIVEPROCESS = "CognitiveProcess"
NODE_THEORY = "Theory"
NODE_MECHANISM = "Mechanism"
NODE_DEVELOPMENTALSTAGE = "DevelopmentalStage"
NODE_STRATEGY = "Strategy"
NODE_KEYINSIGHT = "KeyInsight"
NODE_RESEARCHFINDING = "ResearchFinding"

# ── D2G v2 新增具体实体类型（人名/地名/物品） ────────────────
NODE_PERSON = "Person"
NODE_LOCATION = "Location"
NODE_OBJECT = "Object"

# ── D2G v3 新增临床/评估/干预/发展类型 ─────────────────────────
NODE_ASSESSMENTTOOL = "AssessmentTool"
NODE_SYMPTOM = "Symptom"
NODE_INTERVENTION = "Intervention"
NODE_DIAGNOSIS = "Diagnosis"
NODE_ORGANIZATION = "Organization"
NODE_STUDY = "Study"
NODE_NEUROTRANSMITTER = "Neurotransmitter"
NODE_MILESTONE = "Milestone"
NODE_ENVIRONMENT = "Environment"

# ── 自定义知识节点类型（§09-2.1） ────────────────────────────
NODE_CUSTOM_RULE = "CustomRule"

# ── 原有关系类型 ─────────────────────────────────────────────
REL_BELONGS_TO = "BELONGS_TO"
REL_CAUSES = "CAUSES"
REL_SOLVES = "SOLVES"
REL_PRESCRIBES = "PRESCRIBES"
REL_TARGETS = "TARGETS"
REL_AFFECTS = "AFFECTS"
REL_REQUIRES = "REQUIRES"
REL_CONTAINS_ENTITY = "CONTAINS_ENTITY"
REL_RELATES_TO = "RELATES_TO"

# ── D2G 新增关系类型（§07-4.1.1） ───────────────────────────
REL_SAME_AS = "SAME_AS"                # 跨书同义实体边（Phase 5）

# ── 自定义知识关系类型（§09-2.1） ────────────────────────────
REL_OVERRIDES = "OVERRIDES"            # CustomRule → 实体：纠正/覆盖
REL_ENHANCES = "ENHANCES"              # CustomRule → 实体：补充细节
REL_SUPPLEMENTS = "SUPPLEMENTS"        # CustomRule → Book：补充书籍知识

# ── 跨书关系类型 ─────────────────────────────────────────────
CROSS_BOOK_CONSENSUS = "CONSENSUS"
CROSS_BOOK_COMPLEMENTS = "COMPLEMENTS"
CROSS_BOOK_CONFLICTS = "CONFLICTS"

# ── 便捷常量集合 ─────────────────────────────────────────────

D2G_ENTITY_TYPES = [
    NODE_PROBLEM, NODE_SOLUTION, NODE_BRAINREGION, NODE_RISK,
    NODE_EXERCISE, NODE_ROOTCAUSE, NODE_PRESCRIPTION, NODE_CHILDPROFILE,
    NODE_COGNITIVEPROCESS, NODE_THEORY, NODE_MECHANISM,
    NODE_DEVELOPMENTALSTAGE, NODE_STRATEGY, NODE_KEYINSIGHT, NODE_RESEARCHFINDING,
    NODE_PERSON, NODE_LOCATION, NODE_OBJECT,
    NODE_ASSESSMENTTOOL, NODE_SYMPTOM, NODE_INTERVENTION, NODE_DIAGNOSIS,
    NODE_ORGANIZATION, NODE_STUDY, NODE_NEUROTRANSMITTER,
    NODE_MILESTONE, NODE_ENVIRONMENT,
]
"""D2G 支持的全部 27 种实体类型（不含 AutoEntity 回退类型），供 cross_relation.py 等模块查询使用。"""

KNOWN_ENTITY_TYPES = set(D2G_ENTITY_TYPES)
"""已知实体类型的集合（含原有 8 种 + D2G 新增 19 种，共 27 种），供 graph_committer.py 等模块快速判断实体类型合法性。"""


# ── 跨书关系类型（v2 新增，§13 方案） ─────────────────────────
# 实体消歧关系
REL_SAME_AS = "SAME_AS"                # 跨书同义实体边

# 跨书语义关系（CROSS_ 前缀）
CROSS_TREATS = "CROSS_TREATS"              # A 治疗/解决 B
CROSS_PREVENTS = "CROSS_PREVENTS"          # A 预防 B
CROSS_ALLEVIATES = "CROSS_ALLEVIATES"      # A 缓解 B
CROSS_ADDRESSES = "CROSS_ADDRESSES"        # A 针对/解决 B
CROSS_IMPROVES = "CROSS_IMPROVES"          # A 改善 B
CROSS_ENHANCES = "CROSS_ENHANCES"          # A 增强 B
CROSS_CAUSES = "CROSS_CAUSES"              # A 导致 B
CROSS_CONTRIBUTES_TO = "CROSS_CONTRIBUTES_TO"  # A 促成 B
CROSS_AFFECTS = "CROSS_AFFECTS"            # A 影响 B
CROSS_INCREASES_RISK = "CROSS_INCREASES_RISK"  # A 增加 B 的风险
CROSS_OCCURS_AT = "CROSS_OCCURS_AT"        # A 发生在 B 阶段
CROSS_SUPPORTED_BY = "CROSS_SUPPORTED_BY"  # A 被 B 支持
CROSS_EXPLAINED_BY = "CROSS_EXPLAINED_BY"  # A 被 B 解释
CROSS_SUPPORTS = "CROSS_SUPPORTS"          # A 支持 B
CROSS_CONTRADICTS = "CROSS_CONTRADICTS"    # A 与 B 矛盾
CROSS_EXTENDS = "CROSS_EXTENDS"            # A 扩展 B
CROSS_COMPLEMENTS = "CROSS_COMPLEMENTS"    # A 补充 B
CROSS_ILLUMINATES = "CROSS_ILLUMINATES"    # A 阐明 B
CROSS_LOCALIZED_IN = "CROSS_LOCALIZED_IN"  # A 定位于 B
CROSS_INVOLVES = "CROSS_INVOLVES"          # A 涉及 B
CROSS_EXPLAINS = "CROSS_EXPLAINS"          # A 解释 B
CROSS_ASSOCIATED_WITH = "CROSS_ASSOCIATED_WITH"  # A 与 B 相关
CROSS_COMBINES_WITH = "CROSS_COMBINES_WITH"  # A 与 B 结合

# 跨书关系类型集合
CROSS_BOOK_RELATION_TYPES = {
    CROSS_TREATS, CROSS_PREVENTS, CROSS_ALLEVIATES, CROSS_ADDRESSES,
    CROSS_IMPROVES, CROSS_ENHANCES, CROSS_CAUSES, CROSS_CONTRIBUTES_TO,
    CROSS_AFFECTS, CROSS_INCREASES_RISK, CROSS_OCCURS_AT,
    CROSS_SUPPORTED_BY, CROSS_EXPLAINED_BY, CROSS_SUPPORTS, CROSS_CONTRADICTS,
    CROSS_EXTENDS, CROSS_COMPLEMENTS, CROSS_ILLUMINATES,
    CROSS_LOCALIZED_IN, CROSS_INVOLVES, CROSS_EXPLAINS,
    CROSS_ASSOCIATED_WITH, CROSS_COMBINES_WITH,
}

# 跨书关系类型组合矩阵（源类型, 目标类型, 可能的关系类型）
CROSS_RELATION_TYPE_COMBOS = [
    ("Solution",    "Problem",           [CROSS_TREATS, CROSS_PREVENTS, CROSS_ALLEVIATES]),
    ("Solution",    "RootCause",         [CROSS_ADDRESSES, CROSS_IMPROVES]),
    ("Exercise",    "Problem",           [CROSS_TREATS, CROSS_ALLEVIATES]),
    ("Exercise",    "BrainRegion",       [CROSS_IMPROVES, CROSS_ENHANCES]),
    ("Exercise",    "RootCause",         [CROSS_ADDRESSES, CROSS_ENHANCES]),
    ("Prescription", "Problem",          [CROSS_TREATS]),
    ("Prescription", "Exercise",         [CROSS_COMBINES_WITH]),
    ("RootCause",   "Problem",           [CROSS_CAUSES, CROSS_CONTRIBUTES_TO]),
    ("RootCause",   "BrainRegion",       [CROSS_AFFECTS]),
    ("Risk",        "Problem",           [CROSS_INCREASES_RISK]),
    ("Risk",        "DevelopmentalStage", [CROSS_OCCURS_AT]),
    ("Theory",      "ResearchFinding",   [CROSS_SUPPORTED_BY]),
    ("Theory",      "Mechanism",         [CROSS_EXPLAINED_BY]),
    ("ResearchFinding", "Theory",        [CROSS_SUPPORTS, CROSS_CONTRADICTS]),
    ("Strategy",    "Problem",           [CROSS_ADDRESSES]),
    ("Strategy",    "Solution",          [CROSS_EXTENDS, CROSS_COMPLEMENTS]),
    ("KeyInsight",  "Problem",           [CROSS_ILLUMINATES]),
    ("KeyInsight",  "Solution",          [CROSS_SUPPORTS]),
    ("CognitiveProcess", "BrainRegion",  [CROSS_LOCALIZED_IN]),
    ("Mechanism",   "BrainRegion",       [CROSS_INVOLVES]),
    ("Mechanism",   "RootCause",         [CROSS_EXPLAINS]),
    ("DevelopmentalStage", "Problem",    [CROSS_ASSOCIATED_WITH]),
    # 可按需扩展
]

# 有效的类型组合集合（用于快速查找）
VALID_CROSS_RELATION_COMBOS = {(src, tgt) for src, tgt, _ in CROSS_RELATION_TYPE_COMBOS}
VALID_CROSS_RELATION_COMBOS_REV = {(tgt, src) for src, tgt, _ in CROSS_RELATION_TYPE_COMBOS}
