# 权威运动清单约束 — 方案设计

> 需求：Knowledge QA 推荐的**所有运动必须来自**《运动改变大脑_运动清单》
> 原则：不在 LangGraph 图中加节点（后续手工改动频繁，图结构保持稳定）
> 数据格式：xlsx 为人工编辑源，运行时从 JSON 加载（零外部依赖）

---

## 1. 架构决策

### 1.1 数据流：xlsx → JSON → runtime

```
人工编辑 xlsx → 运行转换脚本 → JSON 文件 (项目根目录) → Service 层 json.load() → State
```

- **xlsx**：人工维护的单一真相源（方便编辑、筛选、排序）
- **JSON**：运行时加载格式（`json.load()` 零依赖，80 项仅 ~20KB）
- **转换**：一次性脚本，xlsx 改动后跑一次即可

### 1.2 加载位置：Service 层，非图节点

```
用户请求
  → KnowledgeQAService._run_qa_pipeline()
    → _load_exercise_context(json_path)            ← Service 层加载 JSON
    → initial_state.exercise_context = context     ← 注入初始 State
    → graph.ainvoke(initial_state)                ← 图不变
    → initial_state.exercise_context = context  ← 注入初始 State
    → graph.ainvoke(initial_state)             ← 图不变
```

**为什么不放在图中**：
- xlsx 是人工维护数据，后续改动频繁
- Service 层加载 = 改文件即生效（进程重启后），零代码变更
- 图结构保持稳定，不受数据层变更影响

**为什么不放在每个节点内**：
- 81 行 × 3 Sheet 的 xlsx 重复加载浪费 IO
- Service 层加载一次，全流程复用

### 1.3 缓存策略：模块级缓存 + 可选失效

```python
# 模块级单例，首次加载后缓存
_exercise_context_cache: str | None = None

def get_exercise_context(json_path: str) -> str:
    global _exercise_context_cache
    if _exercise_context_cache is not None:
        return _exercise_context_cache
    _exercise_context_cache = _load_and_format(json_path)
    return _exercise_context_cache
```

- 首次请求加载 JSON → 格式化为 Markdown → 缓存为字符串
- 后续请求命中缓存（零 IO）
- 进程重启后自动刷新
- 后续可按需加文件 mtime 检测做热更新
- JSON 文件 ~20KB，加载 + 格式化 < 1ms

---

## 2. 数据流

```
运动改变大脑_运动清单.json (项目根目录，由 xlsx 转换生成)
  │
  │  Service._load_exercise_context()
  │  json.load() → Markdown 格式化
  │
  ├──→ state.exercise_context (Markdown 字符串)
  │       │
  │       └──→ _build_full_user_message() 追加到 S3/S4 的 user message
  │              │
  │              ├── S3 recommend_types  ★ 硬约束：从列表中选择运动类型
  │              └── S4 plan_expand      ★ 硬约束：方案中的运动必须来自列表
  │
  └──→ (后续迭代) exercise_name_set (Set[str]) → 后处理校验
```

---

## 3. JSON 结构 → Markdown 格式化方案

### 3.1 三表精简注入

完整三表约 6000 tokens。考虑到 S4/S5 累积上下文膨胀，采用**分级注入**：

| 层级 | 内容 | tokens | 注入节点 |
|------|------|--------|---------|
| 全量表 | 81 项运动名称 + 运动类型 + 强度建议 + 书中章节 | ~2500 | S3, S4 (硬约束) |
| 脑区索引 | 脑区→运动序号映射 | ~800 | S3 (辅助选择) |
| 核心原则 | 7 条原则摘要 | ~600 | S4 (方案设计参考) |

S1/S2/S5 不注入（运动清单对他们不相关，节省 token）。

### 3.2 目标 Markdown 格式

```markdown
## 权威运动清单（来源：《运动改变大脑》）

> **硬性约束**：以下清单是本次推荐的唯一权威运动来源。
> 所有推荐的运动名称、运动类型、脑区说明、章节引用必须出自此清单。

### 一、运动全清单

| 序号 | 运动名称 | 运动类型 | 帮助修复的问题/主要益处 | 书中章节 | 强度建议 |
|------|---------|---------|---------------------|---------|--------|
| 1 | 轻松步行/散步 | 行走 | 改善记忆力；激发创造性思维 | 第一、二章 | 低强度 |
| 2 | 大步健走 | 行走 | 提升专注力；改善情绪 | 第一、二章 | 中低强度 |
| ... | ... | ... | ... | ... | ... |

### 二、按脑区索引

| 脑区/神经机制 | 关联运动（序号） | 主要益处 |
|-------------|---------------|--------|
| 海马体 | 1,2,3,6,7,43,63 | 改善记忆力；促进神经新生 |
| 前额叶皮层 | 几乎所有运动，尤其12-26,55-61 | 提升专注力；增强执行功能 |
| ... | ... | ... |

### 三、七条核心原则摘要
1. **挑战地心引力** — 走路/跑步/力量训练刺激骨钙蛋白→记忆增强
2. **节拍同步** — 舞蹈/团体运动通过脑波同步促进合作
...
```

### 3.3 为什么不全量注入

S3 需要脑区索引来按问题选运动，S4 需要完整表来展开方案。S1/S2/S5 不需要。分级注入比全量注入节省 ~2000 tokens/S1/S2/S5。

实现方式：`_build_full_user_message` 接受 `exercise_context` 参数，但只在 S3/S4 调用时传入非空值。其他节点传空字符串。

---

## 4. Prompt 硬约束设计

### 4.1 S3 (recommend_types) 约束

在 `SECTION_3_SYSTEM` 中追加：

```
## 硬性约束：运动推荐来源

你**必须且只能**从下方用户消息中的「权威运动清单」表格中选择运动类型。
- exercise_types[].name 必须精确匹配清单"运动名称"列中的某一项
- exercise_types[].category 必须与清单"运动类型"列一致
- 推荐理由中的脑区说明必须来自清单"按脑区索引"表
- 引用章节必须使用清单"书中章节"列的信息
- **严禁推荐清单中不存在的运动**。如果无法精确匹配，选择最接近的替代并注明
```

### 4.2 S4 (plan_expand) 约束

在 `SECTION_4_OUTLINE_SYSTEM` 和 `SECTION_4_EXPAND_SYSTEM` 中追加：

```
## 硬性约束：运动方案来源

方案中涉及的所有具体运动**必须**来自下方用户消息中的「权威运动清单」。
- 每天安排的"运动名称"必须精确匹配清单中的运动名称
- 强度参考清单"强度建议"列
- 章节引用使用清单"书中章节"列
```

---

## 5. 实施步骤

### Step 1: Schema
**文件**: `schemas/knowledge_qa.py`
- `KnowledgeQAState` 加 `exercise_context: str = Field(default="")`

### Step 2: Service 层加载器
**文件**: `service/knowledge_qa_service.py`
- 新增 `_load_exercise_context()` 方法：`json.load()` → Markdown 格式化 → 模块级缓存
- `_run_qa_pipeline` 中：`initial_state.exercise_context = self._load_exercise_context()`
- 失败时退化为空字符串 + log warning，不阻塞流水线
- 零外部依赖（`json` 为标准库）

### Step 3: user message 注入
**文件**: `nodes/base.py`
- `_build_full_user_message` 加 `exercise_context` 参数
- 在 S3/S4 调用点传入 `state.exercise_context`，其他节点传 `""`

### Step 4: Prompt 更新
**文件**: `prompts/templates.py`
- `SECTION_3_SYSTEM` 加硬约束块
- `SECTION_4_OUTLINE_SYSTEM` 加硬约束块
- `SECTION_4_EXPAND_SYSTEM` 加硬约束块
- user_template 不需要改（exercise_context 由 `_build_full_user_message` 自动追加）

### Step 5: plan_extract_params 更新
**文件**: `nodes/plan_expand.py`
- user_message 追加 `state.exercise_context`

---

## 6. 改动清单

| 文件 | 改动量 | 说明 |
|------|--------|------|
| `运动改变大脑_运动清单.json` | 新增 | 运行时数据源（~20KB），由 xlsx 转换生成 |
| `schemas/knowledge_qa.py` | +3 行 | State 加字段 |
| `service/knowledge_qa_service.py` | +40 行 | JSON 加载 + Markdown 格式化 + 缓存 |
| `nodes/base.py` | +6 行 | `_build_full_user_message` 加参数 + 3 个调用点 |
| `prompts/templates.py` | +20 行 | 3 个 prompt 加硬约束 |
| `nodes/plan_expand.py` | +3 行 | user_message 追加 |
| `pyproject.toml` | 无需改动 | `json` 为标准库，无外部依赖 |

**不改的文件**：`_assembly.py`、`nodes/__init__.py`、图结构不变。

---

## 7. 验证方法

1. **单元测试**：`get_exercise_context()` → Markdown 含 81 行运动 + 脑区索引 + 7 原则
2. **单元测试**：xlsx 缺失 → 返回 `""`，不抛异常
3. **集成测试**：跑 Case B，检查 S3 `exercise_types[].name` 全部在 xlsx 运动名称集合中
4. **边界测试**：xlsx 文件被删除 → 流水线正常完成（无运动约束，但不出错）

---

## 8. 后续迭代（本阶段不做）

| 项目 | 触发条件 |
|------|---------|
| 后处理校验（programmatic validation） | prompt 约束在实际使用中违规率 > 10% |
| xlsx 热更新（文件 mtime 检测） | 运维反馈"改文件后必须重启"不可接受 |
| 多 xlsx 支持 | 知识库新增其他书籍的运动清单 |
| 按脑区过滤注入（只注入相关子集） | token 预算紧张或 LLM 在完整表中选错运动 |
