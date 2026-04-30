# 阶段 4：前端适配

> 前置：阶段 2 完成。

---

### Task 11: 修改前端类型定义

**Files:**
- Modify: `frontend/src/entities/rag-eval/types.ts`

- [ ] **Step 1: 移除 TestCaseDraft 的 age/domain/age_stage_label 字段**

```typescript
export interface TestCaseDraft {
  id: string;
  query: string;
  description: string | null;
  difficulty_level: string | null;
  expected_knowledge_ids: string[];
  expected_keywords: string[];
  answer_points_summary: string | null;
  answer_points: string | null;
  professional_terms: string[];
  source_document_id: string | null;
  source_document_name: string | null;
  faithfulness_score: number | null;
  status: DraftStatus;
  version: number;
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 2: 移除 DraftGenerationConfig 的 age_ranges/domains**

```typescript
export interface DraftGenerationConfig {
  max_qa_per_chunk?: number;
  min_qa_per_chunk?: number;
}
```

- [ ] **Step 3: 移除 DraftFilters 的 domain 字段**

- [ ] **Step 4: Commit**

```bash
git add frontend/src/entities/rag-eval/types.ts
git commit -m "refactor: 前端类型定义移除 age/domain/age_stage_label"
```

---

### Task 12: 修改前端 API、Hooks、组件 + 验证 SSE 进度 hook

**Files:**
- Modify: `frontend/src/api/rag-eval/drafts.ts`
- Modify: `frontend/src/features/rag-eval/hooks/useDrafts.ts`
- Modify: `frontend/src/features/rag-eval/components/draft/DraftGenerationForm.tsx`
- Modify: `frontend/src/features/rag-eval/components/draft/DraftTable.tsx`
- Verify: `frontend/src/features/rag-eval/hooks/useDraftGenerationProgress.ts`（已存在，122 行）

- [ ] **Step 1: 修改 `drafts.ts` API — 移除 domain 参数**

- [ ] **Step 2: 修改 `useDrafts.ts` — 移除 domain filter**

- [ ] **Step 3: 修改 `DraftGenerationForm.tsx` — 移除 age_ranges/domains 表单项**

简化后的表单只保留：
- `document_id` — 选择源文档
- `max_qa_per_chunk` — 每块最大问题数
- `min_qa_per_chunk` — 每块最小问题数

- [ ] **Step 4: 修改 `DraftTable.tsx` — 移除 domain 和年龄段列**

保留的列：`query`、`faithfulness_score`、`status`、`updated_at`、操作列。

- [ ] **Step 5: 验证 `useDraftGenerationProgress.ts` 与新后端 SSE 事件一致**

该文件已存在（122 行），实现了 `progress` / `complete` / `error` 事件处理。需确认：

1. `handleMessage` 中的事件类型字段与新后端 SSE 事件匹配（参见 Task 7 Step 5 的 SSE 契约）
2. 进度百分比计算逻辑与新后端 `chunk_progress` 事件的 `completed/total` 字段一致
3. `complete` 事件处理中无 age/domain 相关字段引用

如需修改，在此 step 中一并修复。

- [ ] **Step 6: 运行前端类型检查**

Run: `cd frontend && npm run typecheck`
Expected: 无类型错误

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/rag-eval/drafts.ts frontend/src/features/rag-eval/hooks/useDrafts.ts frontend/src/features/rag-eval/components/draft/DraftGenerationForm.tsx frontend/src/features/rag-eval/components/draft/DraftTable.tsx
# useDraftGenerationProgress.ts 仅在需要修复时 add
git commit -m "refactor: 前端 API/hooks/组件移除 age/domain 相关逻辑"
```

---

### Task 13: 修改 DraftPage — 移除筛选和详情中的 age/domain

**Files:**
- Modify: `frontend/src/features/rag-eval/pages/DraftPage.tsx`

- [ ] **Step 1: 移除 domainFilter 状态和筛选控件**

- [ ] **Step 2: 修改 handleGenerate — 移除 age_ranges/domains 传参**

```typescript
const handleGenerate = async (values: any) => {
  await startGeneration(values.document_id, {
    max_qa_per_chunk: values.max_qa_per_chunk,
    min_qa_per_chunk: values.min_qa_per_chunk,
  });
};
```

- [ ] **Step 3: 修改详情弹窗 — 移除 DomainTag 和 formatAgeRange**

保留：query、faithfulness_score、expected_keywords、answer_points、status、timestamps。

- [ ] **Step 4: 运行前端类型检查和 lint**

Run: `cd frontend && npm run typecheck && npm run lint`
Expected: 无错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/rag-eval/pages/DraftPage.tsx
git commit -m "refactor: DraftPage 移除 domain 筛选和 age/domain 详情展示"
```
