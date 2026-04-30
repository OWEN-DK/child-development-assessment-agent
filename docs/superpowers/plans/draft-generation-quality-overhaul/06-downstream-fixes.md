# 下游模块连锁修复

> 前置：阶段 1-5 全部完成（age/domain 已移除、草稿生成管道已简化）。
>
> 本文件修复草稿→测试用例→报告全链路中因 age/domain 改为 Optional 而暴露的下游问题。
>
> **范围限定：** 仅修复 age/domain→Optional 的必要连锁问题。SetService 性能优化（原 D4）和 ReportEngineFacade 分页（原 D5）与本方案核心目标无关，已拆分为独立优化 PR。

---

### Task D1: CaseService 适配 Optional age/domain

**问题：** `CaseService.create()` 始终调用 `calculate_age_stage_label(data.age)`，age 为 None 时 TypeError。`import_from_json()` 跳过无 domain 的记录。

**Files:**
- Modify: `backend/src/service/rag_eval/case/case_service.py`

- [ ] **Step 1: 修改 create() — 防御 age=None**

```python
async def create(self, data: TestCaseCreate) -> TestCaseRead:
    age_stage_label = calculate_age_stage_label(data.age) if data.age is not None else ""
    obj_data = data.model_dump()
    obj_data["id"] = generate_id()
    obj_data["age_stage_label"] = age_stage_label
    obj_data["source"] = "manual"
    orm_obj = await self._repo.create(obj_data)
    return self._mapper.to_read(orm_obj, TestCaseRead)
```

- [ ] **Step 2: 修改 update() — 防御 age=None**

```python
if "age" in update_data and update_data["age"] is not None:
    update_data["age_stage_label"] = calculate_age_stage_label(update_data["age"])
elif "age" in update_data and update_data["age"] is None:
    update_data["age_stage_label"] = ""
```

- [ ] **Step 3: 修改 import_from_json() — domain 可为空**

```python
# 原：if not item.query or not item.domain: continue
# 改：
if not item.query:
    continue
```

同时修改构建 `obj_data` 时处理 `domain=None`：

```python
domain_value = _parse_enum(item.domain, TestDomain) if item.domain else None
if item.domain and domain_value is None:
    continue  # domain 非空但非法才跳过
```

- [ ] **Step 4: 验证**

Run: `cd backend && uv run python -c "from src.service.rag_eval.case.case_service import CaseService; print('OK')"`

- [ ] **Step 5: Commit**

```bash
git add backend/src/service/rag_eval/case/case_service.py
git commit -m "fix: CaseService 适配 Optional age/domain，防御 None 值"
```

---

### Task D2: ReportBuilder + ReportExporter 适配 Optional age/domain

**问题：**
- `builder.py:148` 的 `float(getattr(rc, "age", 0))` 和 `builder.py:157` 的 `float(rc.get("age", 0))` 在 `age=None` 时 TypeError
- `BadCaseEntry.age` 类型为 `float`，不允许 None
- `exporter.py` CSV 导出中直接写 `c.age` / `c.domain`，无 None 防御

**从源头到消费端一并修复。**

**Files:**
- Modify: `backend/src/schemas/rag_eval/report.py`
- Modify: `backend/src/service/rag_eval/report/builder.py`
- Modify: `backend/src/service/rag_eval/report/exporter.py`

- [ ] **Step 1: BadCaseEntry.age 和 domain 改为 Optional**

```python
class BadCaseEntry(BaseModel):
    case_id: str
    query: str
    domain: Optional[str] = None
    age: Optional[float] = None
    expected_keywords: list[str]
    ...
```

- [ ] **Step 2: builder.py 防御 None（ORM 分支 + dict 分支）**

```python
# ORM 分支
raw_age = getattr(rc, "age", None)
age = float(raw_age) if raw_age is not None else None

# dict 分支
raw_age = rc.get("age")
age = float(raw_age) if raw_age is not None else None
```

- [ ] **Step 3: exporter.py CSV 坏案行适配 None**

```python
writer.writerow([
    c.query,
    c.domain or "",
    c.age if c.age is not None else "",
    f"{c.precision:.4f}" if c.precision is not None else "",
    f"{c.recall:.4f}" if c.recall is not None else "",
    c.error_message or "",
])
```

- [ ] **Step 4: 验证**

Run: `cd backend && uv run python -c "from src.service.rag_eval.report.builder import ReportBuilder; from src.service.rag_eval.report.exporter import ReportExporter; print('OK')"`

- [ ] **Step 5: Commit**

```bash
git add backend/src/schemas/rag_eval/report.py backend/src/service/rag_eval/report/builder.py backend/src/service/rag_eval/report/exporter.py
git commit -m "fix: ReportBuilder + Exporter 适配 Optional age/domain，从源头到消费端统一防御 None"
```

---

### Task D3: 修复前端测试文件类型错误

**问题：** `useSSEProgress.test.ts` 和 `sse.test.ts` 类型错误：
- `useSSEProgress.test.ts(141,16)`: `Type 'null' is not assignable to type 'string'`
- `sse.test.ts(17,15)`: `SSECallbacks` 未导出

**Files:**
- Modify: `frontend/src/features/rag-eval/hooks/useSSEProgress.test.ts`
- Modify: `frontend/src/features/rag-eval/utils/sse.test.ts`
- Modify: `frontend/src/features/rag-eval/utils/sse.ts`（可能需导出 SSECallbacks）

- [ ] **Step 1: 修复 useSSEProgress.test.ts — null 赋值类型**

- [ ] **Step 2: 修复 sse.test.ts — 导出 SSECallbacks**

在 `sse.ts` 中导出 `SSECallbacks` 类型，或修改测试中引用方式。

- [ ] **Step 3: 运行 typecheck 验证**

Run: `cd frontend && npm run typecheck`
Expected: 无类型错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/rag-eval/hooks/useSSEProgress.test.ts frontend/src/features/rag-eval/utils/sse.test.ts frontend/src/features/rag-eval/utils/sse.ts
git commit -m "fix: 修复前端 SSE 测试文件的类型错误"
```

---

### Task D4: 验证 BadCaseTable.tsx 对 domain=null 的兼容性

> 前置：Task D2 完成（test_cases.domain 已改为 Optional）。

**问题：** 前端 `BadCaseTable.tsx:30` 使用 `DomainTag` 展示坏案的 domain 字段。当 test_cases 的 domain 从草稿提升时为 None，需确认前端不会崩溃。

**Files:**
- Verify: `frontend/src/features/rag-eval/components/report/BadCaseTable.tsx`
- Verify: `frontend/src/features/rag-eval/components/common/DomainTag.tsx`（如存在）

- [ ] **Step 1: 检查 DomainTag 组件对 null/undefined 的处理**

确认 `DomainTag` 接收 `domain=null` 时显示空或占位文本而非崩溃。如已有 null 防御则无需修改。

- [ ] **Step 2: 运行前端类型检查验证**

Run: `cd frontend && npm run typecheck`
Expected: 无类型错误

---

## 已拆出的独立优化（不属于本方案）

以下任务与"移除 age/domain、简化生成管道"的核心目标无关，已拆分为独立 PR：

| 原编号 | 内容 | 拆出原因 |
|--------|------|---------|
| 原 D4 | SetService.list_sets 批量查询优化 | 纯性能优化，不影响 age/domain 移除 |
| 原 D5 | ReportEngineFacade.list_reports 分页 | API 契约变更，不影响 age/domain 移除 |
