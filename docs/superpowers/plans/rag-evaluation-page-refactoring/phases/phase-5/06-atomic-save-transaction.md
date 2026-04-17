# 06 - 原子保存事务 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 06 - 原子保存事务

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

> **Phase**: 5
> **需求点**: 6
> **需求来源**: spec `04-frontend-pages.md` §4.2

## 目标

实现 ConfigChangeSet 事务，配置和提示词作为整体版本保存，部分失败时全部回滚。

## 方案设计

### 后端实现

#### Service 层

```python
# backend/src/service/config_change_set_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import json

async def save_config_change_set(
    config_data: dict,
    prompt_data: list[dict],
    user_id: str,
    session: AsyncSession
) -> ConfigChangeSet:
    """原子保存配置+提示词变更集"""
    async with session.begin():
        # 1. 创建配置版本
        config_version = ConfigVersion(
            version_label=await generate_version_label(session),
            config_snapshot=config_data,
            created_by=user_id,
            change_summary=generate_config_summary(config_data),
            created_at=datetime.utcnow()
        )
        session.add(config_version)
        await session.flush()  # 获取 ID
        
        # 2. 创建变更集
        change_set = ConfigChangeSet(
            change_set_label=await generate_change_set_label(session),
            config_version_id=config_version.id,
            status='committed',
            created_by=user_id,
            created_at=datetime.utcnow()
        )
        session.add(change_set)
        await session.flush()  # 获取 change_set.id
        
        # 3. 创建提示词版本并关联
        for prompt in prompt_data:
            pv = PromptVersion(
                prompt_key=prompt['key'],
                version_label=prompt['version_string'],
                version_number=await next_prompt_version_number(session, prompt['key']),
                content=prompt['content'],
                created_by=user_id,
                change_summary=prompt.get('summary', ''),
                created_at=datetime.utcnow()
            )
            session.add(pv)
            await session.flush()  # 获取 pv.id
            
            csp = ConfigChangeSetPrompt(
                change_set_id=change_set.id,
                prompt_version_id=pv.id
            )
            session.add(csp)
        # async with session.begin() 块结束时自动 commit
        # 任何异常自动 rollback
    
    return change_set
```

#### API 端点

```python
# backend/src/api/v1/rag_eval.py

@router.post("/config-change-sets")
async def create_config_change_set(
    request: ConfigChangeSetCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """创建配置变更集（原子保存配置+提示词）"""
    try:
        change_set = await save_config_change_set(
            config_data=request.config_snapshot,
            prompt_data=request.prompts,
            user_id=current_user.id,
            session=session
        )
        
        # 事务提交成功后发布 Redis 事件
        await redis.publish("config_changed", json.dumps({
            "event": "config_changed",
            "change_set_id": str(change_set.id),
            "timestamp": datetime.utcnow().isoformat(),
            "changed_by": current_user.id
        }))
        
        return {
            "id": str(change_set.id),
            "change_set_label": change_set.change_set_label,
            "config_version_id": str(change_set.config_version_id),
            "status": change_set.status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
```

### 请求/响应格式

```typescript
// 请求
interface ConfigChangeSetCreateRequest {
  config_snapshot: Record<string, any>  // 完整配置快照
  prompts: {
    key: string
    version_string: string
    content: string
    summary?: string
  }[]
  change_summary?: string               // 变更摘要
}

// 响应
interface ConfigChangeSetResponse {
  id: string
  change_set_label: string
  config_version_id: string
  status: 'committed' | 'rolled_back'
  created_at: string
}
```

### 事务时序保证

```
执行顺序（严格保证）:
  1. async with session.begin() 块结束 → 自动 commit    ← MySQL 事务提交，数据持久化
  2. 发布 Redis Pub/Sub 事件              ← 事务已提交，其他实例一定能读到新数据
  3. 返回前端成功响应

错误顺序（会导致不一致）:
  ❌ 先发布 Redis 事件 → 再 commit        ← 其他实例可能读到旧数据（事务未提交）
  ❌ commit 和发布事件并行                ← 竞态条件，无法保证顺序
```

### 验收标准

- [ ] 使用 `async with session.begin()` 实现自动 commit/rollback
- [ ] 配置和提示词在同一事务中保存
- [ ] 部分失败时全部回滚
- [ ] 事务提交后才发布 Redis 事件
- [ ] API 返回新版本号和变更集 ID
- [ ] 错误时返回具体失败项信息
