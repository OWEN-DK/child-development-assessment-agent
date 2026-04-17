# 09 - jsonable_encoder 处理 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 09 - jsonable_encoder 处理

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Test: `tests/test_placeholder.py`

- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

## 问题描述

SSE 推送的消息必须是 JSON 可序列化的。直接传递 SQLAlchemy ORM 对象或 Pydantic 模型给 `json.dumps()` 会导致 `TypeError`，进而引发 ASGI `ExceptionGroup` 崩溃。

## 已有保护

现有 `SSEPublisher.publish()` 和 `AsyncTaskManager` 已使用 `jsonable_encoder` 处理：

```python
# sse.py:78-84
from fastapi.encoders import jsonable_encoder
safe_message = jsonable_encoder(message)
```

```python
# async_task.py:62-66
safe_result = jsonable_encoder(result) if result is not None else {}
```

## 需要补充的场景

### 1. case_result 事件

测试用例结果可能包含 SQLAlchemy ORM 对象：

```python
# 错误做法
await SSEPublisher.publish(channel, {
    "type": "case_result",
    "case_result": case_orm_object  # ❌ ORM对象无法序列化
})

# 正确做法
from fastapi.encoders import jsonable_encoder
await SSEPublisher.publish(channel, {
    "type": "case_result",
    "case_result": jsonable_encoder({
        "case_id": case.id,
        "query": case.query,
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "hit_at_5": hit_at_5,
        "hit_rank": hit_rank,
        "retrieved_doc_ids": retrieved_doc_ids,
        "expected_doc_ids": expected_doc_ids,
        "precision": precision,
        "recall": recall,
        "score": score,
        "latency_ms": latency_ms
    })
})
```

### 2. validation_completed 事件

校验结果可能包含复杂对象：

```python
# 正确做法
validation_payload = {
    "layers": [
        {
            "layer": layer_num,
            "name": layer_name,
            "status": status,
            "score": score,
            "threshold": threshold,
            "duration_ms": duration_ms,
            "details": jsonable_encoder(details)  # 嵌套对象也要处理
        }
        for layer_num, layer_name, status, score, threshold, duration_ms, details in layer_results
    ],
    "overall_status": overall_status,
    "total_duration_ms": total_duration_ms
}
await SSEPublisher.publish(channel, validation_payload)
```

### 3. export_ready 事件

导出信息中的 datetime 对象需要处理：

```python
await SSEPublisher.publish(channel, jsonable_encoder({
    "type": "export_ready",
    "export_id": export_id,
    "format": format,
    "download_url": download_url,
    "expires_at": expires_at  # datetime对象，jsonable_encoder会转为ISO字符串
}))
```

## jsonable_encoder 行为说明

| 输入类型 | 输出 |
|----------|------|
| SQLAlchemy ORM | 转为 dict（排除 relationship 字段） |
| Pydantic BaseModel | 转为 dict（调用 .model_dump()） |
| datetime | 转为 ISO 8601 字符串 |
| UUID | 转为字符串 |
| Enum | 转为 value |
| Decimal | 转为 float |
| bytes | 转为 base64 字符串 |
| set/frozenset | 转为 list |

## 注意事项

- `jsonable_encoder` 默认排除以 `_` 开头的私有字段
- relationship 字段默认被排除，如需包含需显式配置
- 嵌套对象会自动递归处理，无需手动逐层调用
- 性能开销：对于大对象（如包含数千条结果），序列化耗时可能达数十毫秒，建议在后台任务中完成后再发布
