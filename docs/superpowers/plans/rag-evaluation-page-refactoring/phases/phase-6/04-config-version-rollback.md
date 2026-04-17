# 04 - 配置版本回滚 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 04 - 配置版本回滚

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

> **Phase**: 6
> **需求点**: 4
> **需求来源**: spec `04-frontend-pages.md` §4.9

## 目标

实现配置版本回滚功能，原子回滚配置 + 提示词，创建 rolled_back 变更集。

## 方案设计

### 回滚流程

```
用户点击 [回滚到此版本]
     ↓
弹出确认对话框（展示回滚影响）
     ↓
用户确认
     ↓
创建新的 ConfigChangeSet（status=rolled_back）
     ↓
发布 Redis config_changed 事件
     ↓
系统热更新到旧配置和旧提示词
```

### 回滚范围

- ConfigChangeSet 包含配置和提示词的整体版本
- 回滚时两者同时回滚，不可单独回滚配置或提示词
- 回滚不是删除，而是创建一条新的变更集记录，保持完整的审计追踪

### Service 层实现

```python
# backend/src/service/config_rollback_service.py

async def rollback_to_version(
    config_version_id: str,
    user_id: str,
    reason: str,
    session: AsyncSession
) -> ConfigChangeSet:
    """回滚到指定配置版本"""
    # 1. 查询目标配置版本
    result = await session.execute(
        select(ConfigVersion).where(ConfigVersion.id == config_version_id)
    )
    target_version = result.scalar_one_or_none()
    if not target_version:
        raise ValueError("配置版本不存在")
    
    # 2. 查询该版本关联的提示词版本
    prompt_versions = await get_prompts_by_config_version(config_version_id, session)
    
    async with session.begin():
        # 3. 创建新的配置版本（复制目标版本的快照）
        new_version = ConfigVersion(
            version_label=await generate_version_label(session),
            config_snapshot=target_version.config_snapshot,
            created_by=user_id,
            change_summary=f"回滚到 {target_version.version_label}: {reason}",
            created_at=datetime.utcnow()
        )
        session.add(new_version)
        await session.flush()
        
        # 4. 创建变更集（status=rolled_back）
        change_set = ConfigChangeSet(
            change_set_label=await generate_change_set_label(session),
            config_version_id=new_version.id,
            status='rolled_back',
            rollback_reason=reason,
            rolled_back_from_id=config_version_id,
            created_by=user_id,
            created_at=datetime.utcnow()
        )
        session.add(change_set)
        await session.flush()
        
        # 5. 复制提示词版本
        for pv in prompt_versions:
            new_pv = PromptVersion(
                prompt_key=pv.prompt_key,
                version_label=pv.version_label,
                version_number=await next_prompt_version_number(session, pv.prompt_key),
                content=pv.content,
                created_by=user_id,
                change_summary=f"回滚到 {pv.version_label}",
                created_at=datetime.utcnow()
            )
            session.add(new_pv)
            await session.flush()
            
            csp = ConfigChangeSetPrompt(
                change_set_id=change_set.id,
                prompt_version_id=new_pv.id
            )
            session.add(csp)
    
    # 6. 发布 Redis 事件
    await redis.publish("config_changed", json.dumps({
        "event": "config_changed",
        "change_set_id": str(change_set.id),
        "timestamp": datetime.utcnow().isoformat(),
        "changed_by": user_id,
        "rollback": True
    }))
    
    return change_set
```

### API 端点

```
POST /api/config-versions/{version_id}/rollback
Request:
{
  "reason": "配置变更导致指标下降"
}

Response:
{
  "id": "uuid",
  "change_set_label": "CS-20260416-002",
  "status": "rolled_back",
  "rolled_back_from_id": "uuid",
  "created_at": "2026-04-16T11:00:00Z"
}
```

### 确认对话框展示内容

```
┌─────────────────────────────────────────┐
│  确认回滚到 v2.2                         │
├─────────────────────────────────────────┤
│  回滚将影响以下变更:                      │
│                                         │
│  配置变更:                              │
│  • bm25_top_k: 15 → 10                 │
│  • reranker_initial_k: 40 → 30         │
│                                         │
│  提示词变更:                            │
│  • query_rewrite: v4 → v3              │
│                                         │
│  回滚原因: [________________]           │
│                                         │
│  [确认回滚]  [取消]                      │
└─────────────────────────────────────────┘
```

### 验收标准

- [ ] 回滚创建新的 ConfigChangeSet（status=rolled_back）
- [ ] 配置和提示词同时回滚
- [ ] 回滚后发布 Redis 事件触发热重载
- [ ] 回滚记录保持完整的审计追踪
- [ ] 用户需填写回滚原因
