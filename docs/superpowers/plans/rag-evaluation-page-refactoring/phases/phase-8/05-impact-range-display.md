# 05 - 影响范围展示 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 05 - 影响范围展示

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

> **Phase**: 8
> **需求点**: 5
> **需求来源**: spec `08b-config-frontend-pages.md`

## 目标

实现修改配置时展示影响组件和重载方式。

## 方案设计

### 展示内容

```
┌─────────────────────────────────────────────────────┐
│  修改: BM25 TopK                                    │
├─────────────────────────────────────────────────────┤
│  当前值: 10 → 新值: 15                              │
│                                                     │
│  影响组件:                                          │
│  • BM25 检索器 (src/service/retrieval_service.py)   │
│  • 融合搜索模块 (src/service/fusion_search.py)      │
│                                                     │
│  重载方式: 热重载 (修改后立即生效)                   │
│                                                     │
│  [确认修改]  [取消]                                 │
└─────────────────────────────────────────────────────┘
```

### 数据来源

从 ConfigMetadata 表获取：

```python
class ConfigMetadata:
    affected_components = Column(JSON, nullable=True)
    reload_type = Column(ENUM("hot", "cold"), nullable=False, default="hot")
```

### 验收标准

- [ ] 修改时展示影响组件列表
- [ ] 展示重载方式（热重载/冷重启）
- [ ] 热重载配置修改后立即生效
- [ ] 冷重启配置提示用户需要重启服务
