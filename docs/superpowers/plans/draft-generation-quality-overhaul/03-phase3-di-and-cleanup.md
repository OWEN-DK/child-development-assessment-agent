# 阶段 3：旧模板清理

> 前置：阶段 2 完成。
>
> **注意：** `PromptManager` 是模块级单例（`prompt_impl/facade.py` 底部的 `prompt_manager = PromptManager()`），不是通过 DI 容器注入的。`DraftGenerator` 构造函数已直接 import 该单例作为默认值，无需修改 `di_container.py`。

---

### Task 9: 确认旧 prompt 模板不影响新流程

> `test_case_generation` 和 `test_case_generation_chunk_grounded` 这两个旧 prompt 仍包含 age/domain 变量。**暂时保留不删**，因为数据库中已有版本记录，且删除可能影响其他引用。

- [ ] **Step 1: 验证旧 prompt 未被 DraftGenerator 引用**

```bash
cd backend && grep -n "test_case_generation" src/service/rag_eval/draft/generator.py
```

Expected: 无匹配（新 generator 只引用 `draft_generation_rag`）

- [ ] **Step 2: 确认 `prompt_manager` 模块单例可用**

```bash
cd backend && uv run python -c "from src.core.prompt_impl.facade import prompt_manager; print(f'OK: {type(prompt_manager).__name__}')"
```

Expected: `OK: PromptManager`

- [ ] **Step 3: 确认 DraftGenerator 默认注入了 prompt_manager**

```bash
cd backend && uv run python -c "from src.service.rag_eval.draft.generator import DraftGenerator; gen = DraftGenerator(); print(f'prompt_manager={gen._prompt_manager}')"
```

Expected: 非 None 的 `PromptManager` 实例

- [ ] **Step 4: 如有残留引用，移除并 Commit**
