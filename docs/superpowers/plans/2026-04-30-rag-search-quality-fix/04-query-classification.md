# 04 P2：统一查询分类器

> 两套独立分类器 + 三个冲突的 QueryType 枚举。
> 与 P1 无硬依赖，可并行实施。

---

## P2-1 合并为单一分类器（问题 3）

### 核实事实

**分类器 A**：`backend/src/core/query_router.py`
- `SIMPLE_PATTERNS`（L42-46）：正则匹配 `有哪些|是什么|怎么办|怎么做` → SIMPLE
- `COMPLEX_KEYWORDS`（L53-58）：`对比|原因|分析|区别|比较`，需 2+ 关键词 → COMPLEX
- 无长度规则

**分类器 B**：`backend/src/core/pipeline/orchestrator.py` `_classify_query()`（L171-192）
- `complex_keywords`：`对比|区别|如何|为什么|原因|分析`
- **单个关键词即判定 COMPLEX**（不等 2+）
- `len(query) > 20` → COMPLEX
- 返回原始字符串 `"simple"/"complex"`，不用 QueryType 枚举

**具体矛盾**：
- `"怎么办"` → A 判 SIMPLE，B 不在关键词中（不触发）
- `"如何训练注意力"` → A 不触发，B 判 COMPLEX（匹配"如何"）
- `"感觉统合失调有哪些表现"` → A 判 SIMPLE（匹配"有哪些"），B 判 COMPLEX（长度 >20）

### 修复

**Step 1**：在 `query_router.py` 中整合两套规则

保留 `QueryRouter` 类作为唯一分类器，吸收 `orchestrator._classify_query()` 的规则：

```python
class QueryRouter:
    # 合并后的 SIMPLE 模式
    SIMPLE_PATTERNS = [
        r".*有哪些.*",
        r".*是什么.*",
        r".*怎么办.*",
        r".*怎么做.*",
    ]

    # 合并后的 COMPLEX 关键词（单个即触发，从 orchestrator 对齐）
    COMPLEX_KEYWORDS = [
        "对比", "区别", "如何", "为什么", "原因", "分析", "比较",
    ]

    # 长度阈值（从 orchestrator 吸收）
    COMPLEX_LENGTH_THRESHOLD = 20

    def classify(self, query: str) -> "QueryType":
        # 优先检查 SIMPLE 模式
        for pattern in self.SIMPLE_PATTERNS:
            if re.match(pattern, query):
                return QueryType.SIMPLE

        # 检查 COMPLEX 关键词（单个即触发）
        for keyword in self.COMPLEX_KEYWORDS:
            if keyword in query:
                return QueryType.COMPLEX

        # 长度阈值
        if len(query) > self.COMPLEX_LENGTH_THRESHOLD:
            return QueryType.COMPLEX

        return QueryType.DEFAULT
```

**Step 2**：`orchestrator.py` 删除 `_classify_query()`

改为导入 `QueryRouter`：
```python
from src.core.query_router import QueryRouter

class PipelineOrchestrator:
    def __init__(self):
        self.query_router = QueryRouter()

    # 原 _classify_query() 调用改为
    classification = self.query_router.classify(context.query)
```

### 验证

- [ ] `"感觉统合失调有哪些表现"` 两条路径都返回 SIMPLE
- [ ] `"如何训练注意力"` 两条路径都返回 COMPLEX
- [ ] `"3岁身高标准"` 两条路径都返回 DEFAULT
- [ ] `grep "_classify_query" backend/src/core/pipeline/orchestrator.py` 返回空

---

## P2-2 统一 QueryType 枚举（问题 13）

### 核实事实

三个文件各自定义 `QueryType`，零共享成员：

| 文件 | 成员 |
|------|------|
| `query_router.py:18` | SIMPLE, COMPLEX, DEFAULT |
| `schemas/query.py:12` | DIRECT, COMPARISON, EXPLORATION |
| `core/rag/query_analyzer.py:18` | SHORT, TERMINOLOGY, DESCRIPTIVE, COMPLEX, DEFAULT |

`query_router.py:13` 导入了 `schemas/query.py` 的 `QueryType` 但 L18 重定义覆盖了导入。
`query_router.py:26-28` 有残留属性（`query_type`, `confidence`, `reasoning`）挂在枚举上。

### 修复

**Step 1**：`schemas/query.py` 作为唯一定义

```python
class QueryType(str, Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"
    DEFAULT = "default"
```

**Step 2**：`query_router.py` 删除 L18-28 的本地定义和残留属性

```python
# 删除本地 QueryType 定义（L18-23）
# 删除残留属性（L26-28）
from src.schemas.query import QueryType  # 使用统一导入
```

**Step 3**：`query_analyzer.py` 删除本地 QueryType

```python
# 删除本地 QueryType 定义（L18-25）
from src.schemas.query import QueryType  # 使用统一导入
```

如果 `query_analyzer.py` 的 SHORT/TERMINOLOGY/DESCRIPTIVE 有调用方，需要映射到 SIMPLE/COMPLEX/DEFAULT（SHORT→SIMPLE, TERMINOLOGY→DEFAULT, DESCRIPTIVE→COMPLEX）。检查调用方后决定。

### 验证

- [ ] `grep -r "class QueryType" backend/src/` 只返回 `schemas/query.py` 一处
- [ ] `grep "QueryType" backend/src/core/query_router.py` 只有 import 行，无 class 定义
- [ ] 所有引用 QueryType 的文件从 `schemas.query` 统一导入

---

## 本阶段完成后的下游能力

P2-1/P2-2 完成后，`QueryRouter.classify()` 成为唯一分类入口，返回统一的 SIMPLE/COMPLEX/DEFAULT。这为复杂查询的**子查询分解**提供了可靠的前置判断：

- SIMPLE/DEFAULT → 直通 RRF 检索
- COMPLEX → 触发 [07 查询分解](07-query-decomposition.md)，拆为多个子查询独立检索后归并

详见 [07-query-decomposition.md](07-query-decomposition.md)。
