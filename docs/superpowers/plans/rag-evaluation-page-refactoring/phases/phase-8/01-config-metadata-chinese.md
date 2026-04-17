# 01 - 配置元数据中文补充 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 01 - 配置元数据中文补充

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
> **需求点**: 1
> **需求来源**: spec `08a-config-metadata.md`

## 目标

所有配置项新增 name_zh, description_zh, 取值范围, 推荐范围。

## 方案设计

### 数据模型

```python
# backend/src/models/rag_eval.py

class ConfigMetadata(Base):
    """配置元数据记录"""
    __tablename__ = "config_metadata"
    
    id = Column(CHAR(36), primary_key=True, default=uuid4)
    config_key = Column(VARCHAR(255), unique=True, nullable=False, index=True)
    name_zh = Column(VARCHAR(255), nullable=False)
    description_zh = Column(TEXT, nullable=False)
    category = Column(VARCHAR(64), nullable=False)  # rag_retrieval, rag_chunking, llm, database, redis, logging, business_rule
    value_type = Column(ENUM("string", "number", "boolean", "json"), nullable=False)
    min_value = Column(FLOAT, nullable=True)
    max_value = Column(FLOAT, nullable=True)
    recommended_min = Column(FLOAT, nullable=True)
    recommended_max = Column(FLOAT, nullable=True)
    unit = Column(VARCHAR(32), nullable=True)
    affected_components = Column(JSON, nullable=True)  # 影响组件列表
    reload_type = Column(ENUM("hot", "cold"), nullable=False, default="hot")  # 重载方式
    is_system = Column(BOOLEAN, nullable=False, default=True)
    created_at = Column(DATETIME, nullable=False, default=datetime.utcnow)
    updated_at = Column(DATETIME, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 配置分组

| 分组 | 包含配置 |
|------|---------|
| RAG 检索配置 | BM25 权重、向量权重、融合模式、重排序、查询路由、年龄过滤 |
| RAG 分块配置 | PDF 分块大小、语义分割器、分块重叠 |
| LLM 模型配置 | 凭证管理、场景配置、定价配置 |
| 数据库配置 | 连接池配置、慢查询阈值 |
| Redis 配置 | 连接配置、缓存配置 |
| 日志配置 | 日志级别、日志格式 |
| 业务规则配置 | 发展领域、年龄模式、难度阈值 |

### 初始化数据示例

| config_key | name_zh | description_zh | category | value_type | min | max | recommended_min | recommended_max |
|-----------|---------|---------------|----------|------------|-----|-----|-----------------|-----------------|
| bm25_top_k | BM25 TopK | BM25 检索返回的文档数量 | rag_retrieval | number | 1 | 100 | 5 | 50 |
| vector_top_k | 向量检索 TopK | 向量检索返回的文档数量 | rag_retrieval | number | 1 | 100 | 5 | 50 |
| fusion_threshold | 融合阈值 | 融合搜索的分数阈值 | rag_retrieval | number | 0 | 1 | 0.15 | 0.35 |

### 验收标准

- [ ] ConfigMetadata 表创建成功
- [ ] 所有配置项有中文名称和用途说明
- [ ] 取值范围和推荐范围正确设置
- [ ] 影响组件和重载方式正确标注
