# 知识问答系统 Bug 报告

**日期**: 2026-05-29  
**测试问题**: 我儿子8岁，上课注意力不集中，写作业坐不住，经常被老师投诉，有什么运动可以帮助改善？  
**Task ID**: 2f824e5d-fee9-44b8-96f8-dd9387cce85f  
**总耗时**: 313s  
**状态**: partial=True

---

## 知识库现状

| 书名 | 状态 | 搜索命中 |
|---|---|---|
| 运动改变大脑 | indexed | ✅ 被搜索到（top-15 全部来自此书） |
| 孩子如何思考 | indexed | ⚠️ 偶尔命中（排名靠后） |
| 学习如何学习 | indexed | ❌ 未命中（需特定关键词才能搜到） |
| 学习之道 | indexed | ❌ 未命中（可能索引内容太少） |
| 由内而外的教养 | indexed | ❌ 未命中（需"亲子教养"等关键词） |

---

## Bug #1：多书引用失败 — 搜索结果只包含 1 本书

### 现象
所有 section 的 citations 全部来自"运动改变大脑"，其余 4 本书零引用。

### 根因
RAG 搜索 top-15 全部来自"运动改变大脑"，其他书根本排不进结果。

**验证**：
```
limit=15: 15 results → 运动改变大脑: 15
limit=50: 17 results → 运动改变大脑: 17
```

### 搜索链路分析
```
用户问题
  → match_books（_analyze_and_search_books，无 book_ids 过滤）
    → RAG /rag/search limit=15（纯相关度排序）
      → top-15 全部来自"运动改变大脑"
        → 候选书籍 = ['运动改变大脑', '孩子如何思考']（仅 2 本）
          → search_book_ids = [这 2 本的 file_hash]
            → 后续所有 section 搜索都用这个 book_ids 过滤
              → 其他 3 本书永远无法被搜到
```

### 其他书的可达性
用不同关键词可以搜到其他书：
- "学习方法 记忆技巧" → 能命中"学习如何学习"
- "亲子教养 父母 情绪" → 能命中"由内而外的教养"
- "儿童认知 意识" → 能命中"孩子如何思考"

但 `_analyze_and_search_books` 的 3 次搜索 + domain_keywords 扩展不足以覆盖所有书。

### 修复方向
match_books 阶段改为：先获取全部已索引书籍列表，对每本书做一次针对性搜索，确保每本书都有机会被匹配。

---

## Bug #2：运动方案只有 1 个阶段（预期 2 个）

### 现象
S4 structured_data 中只有 1 个 phase，phase_name="阶段"，总天数 13 天。

### 根因
Pydantic 字段名不匹配导致降级。

**证据链**：
```
outline prompt 告诉 LLM 用 "name" 字段
  → LLM 输出 {"phase_id": "PH01", "name": "适应期", ...}
    → plan_assemble 尝试 Phase(**data)
      → Pydantic 报错: phases.0.phase_name Field required
        → 进入降级路径（只保留 1 个 phase）
          → phase_name 默认值 = "阶段"
```

**日志证据**：
```
plan_assemble: Pydantic 校验失败: 1 validation error for Section4StructuredData
phases.0.phase_name
  Field required [type=missing, input_value={'phase_id': 'PH01', 'nam...}]
```

### 涉及文件
- `schemas/knowledge_qa.py` — `Phase` 模型定义 `phase_name: str`（期望 phase_name）
- `prompts/templates.py` — SECTION_4_OUTLINE prompt 使用 `name` 字段
- `nodes/plan_assemble.py` — Pydantic 校验处

### 修复方向
方案 A：给 `Phase.phase_name` 加 `alias="name"`  
方案 B：outline prompt 改为使用 `phase_name`  
推荐方案 A（影响最小）。

---

## Bug #3：运动方案总时长不是 4 周

### 现象
当前生成 13 天（约 2 周），预期 4 周（28 天）。

### 根因
outline prompt 说"至少 2 个阶段，每阶段 1-4 周"，但没有约束总时长为 4 周。LLM 自行决定阶段数和周数。

### 修复方向
outline prompt 加硬性约束："总时长固定为 4 周（28 天），分为 2 个阶段，每阶段 2 周"。

---

## Bug #4：S4 Markdown 渲染出现"阶段"栏目

### 现象
Markdown 中显示 `### 第1阶段：阶段`，phase_name 是无意义的"阶段"。

### 根因
与 Bug #2 相同。降级路径默认 `phase_name="阶段"`，`_render_s4_markdown` 直接渲染此值。

### 修复方向
修复 Bug #2 后自然消失。

---

## Bug #5：S4 执行要点（description）生成不完全

### 现象
部分 exercise 的 description 字段有内容（2-3 句），但用户反馈"执行要点生成不完全"。

### 分析
当前 S4 走了降级路径（plan_assemble fallback），exercise 数据来自 plan_expand_parallel 的 LLM 输出。description 字段实际由 LLM 生成，内容看起来完整。

**需进一步确认**：用户指的"不完全"是 Markdown 渲染截断，还是 LLM 生成内容本身不足。

---

## 附件

- `result.json` — 完整 API 响应 JSON
- `result.md` — 从 JSON 渲染的 Markdown 报告
