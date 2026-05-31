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
]
"""D2G 支持的全部 15 种实体类型（不含 AutoEntity 回退类型），供 cross_relation.py 等模块查询使用。"""

KNOWN_ENTITY_TYPES = set(D2G_ENTITY_TYPES)
"""已知实体类型的集合（含原有 8 种 + D2G 新增 7 种，共 15 种），供 graph_committer.py 等模块快速判断实体类型合法性。"""
