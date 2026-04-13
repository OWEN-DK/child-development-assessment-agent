# RAG查询流水线编排实施方案
> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构RAG检索服务为声明式流水线架构，解决现有孤岛问题和Bug，提升简单查询性能50%+，降低Token消耗60%+，同时保持完全向后兼容。
**Architecture:** 采用YAML声明式配置 + PipelineOrchestrator编排 + 可插拔步骤的三层架构，查询路由后选择对应流水线执行，失败自动降级，支持热重载。
**Tech Stack:** Python 3.13, FastAPI, LangChain, LangGraph, Pydantic, Prometheus, aiofiles

---

## 一、文件结构映射
### 新增文件
| 文件路径 | 职责 |
|----------|------|
| `backend/src/config/modules/rag/query_pipeline.py` | 流水线配置模块，支持环境变量覆盖和YAML加载 |
| `backend/src/config/query_pipeline.yaml` | 声明式流水线配置文件 |
| `backend/src/core/query_pipeline_orchestrator.py` | 流水线编排器核心实现，含上下文、步骤协议、单例管理、监控指标 |
| `backend/src/core/pipeline_steps/__init__.py` | 步骤工厂注册表，依赖DI容器 |
| `backend/src/core/pipeline_steps/base.py` | 步骤基类，提供通用日志和指标方法 |
| `backend/src/core/pipeline_steps/cache_check.py` | 缓存检查步骤实现 |
| `backend/src/core/pipeline_steps/query_rewrite.py` | 查询重写步骤实现 |
| `backend/src/core/pipeline_steps/synonym_expand.py` | 同义词扩展步骤实现 |
| `backend/src/core/pipeline_steps/age_filter.py` | 年龄过滤步骤实现 |
| `backend/src/core/pipeline_steps/hybrid_retrieval.py` | 混合检索步骤实现 |
| `backend/src/core/pipeline_steps/rerank.py` | 重排序步骤实现 |
| `backend/src/core/pipeline_steps/dedup.py` | 内容去重步骤实现 |
| `backend/src/core/pipeline_steps/convert_to_knowledge.py` | 转换为KnowledgeItem步骤实现 |
| `backend/src/core/pipeline_steps/pageindex.py` | PageIndex步骤实现（预留，默认不启用） |

### 修改文件
| 文件路径 | 改动内容 |
|----------|----------|
| `backend/src/service/retrieval_service.py` | 重构retrieve_knowledge方法，集成编排器，保留旧逻辑为回退，修复同义词变量Bug，优化缓存Key |
| `backend/src/config/__init__.py` | 聚合QueryPipelineSettings，更新_infer_category映射，修改热重载处理器支持yaml文件 |
| `backend/src/core/pageindex_wrapper.py` | 修复文件句柄泄漏Bug |
| `backend/src/core/di_container.py` | 注册所有流水线步骤类到DI容器 |
| `backend/.env.dev` | 新增流水线相关配置项 |
| `backend/.env.dev.example` | 新增流水线配置示例 |
| `AGENTS.md` | 新增RAG流水线架构说明 |
| `CLAUDE.md` | 新增模块、配置、文件结构说明 |
| `docs/RAG_SYSTEM_COMPLETE_DOCUMENTATION.md` | 同步新的流水线架构 |
| `docs/配置系统文档.md` | 更新新增的流水线配置项 |

---

## 二、任务分解（共7个阶段，总周期14天）

### 🚩 Task 0: 前置准备（1天）
**目标：** 新增开关配置，补充DI注册，搭建测试框架
**文件：**
- 修改：`backend/src/config/__init__.py`
- 修改：`backend/src/core/di_container.py`
- 修改：`backend/.env.dev`
- 修改：`backend/.env.dev.example`
- 新增：`tests/service/test_retrieval_pipeline_compatibility.py`

- [ ] **Step 0.1: 编写兼容性测试用例**
```python
# tests/service/test_retrieval_pipeline_compatibility.py
import pytest
from src.service.retrieval_service import RetrievalService

@pytest.mark.asyncio
async def test_pipeline_switch_off_returns_old_result():
    """开关关闭时返回旧逻辑结果"""
    service = RetrievalService()
    result_old = await service._retrieve_knowledge_old("儿童注意力训练", 3, 5)
    result_new = await service.retrieve_knowledge("儿童注意力训练", 3, 5)
    assert len(result_old) == len(result_new)
    assert [r.id for r in result_old] == [r.id for r in result_new]

@pytest.mark.asyncio
async def test_pipeline_switch_on_returns_consistent_result():
    """开关开启时返回结果与旧逻辑一致"""
    from src.config import settings
    original_value = settings.rag_pipeline_enabled
    settings.rag_pipeline_enabled = True
    
    try:
        service = RetrievalService()
        result_old = await service._retrieve_knowledge_old("儿童注意力训练", 3, 5)
        result_new = await service.retrieve_knowledge("儿童注意力训练", 3, 5)
        assert len(result_old) == len(result_new)
        assert [r.id for r in result_old] == [r.id for r in result_new]
    finally:
        settings.rag_pipeline_enabled = original_value
```

- [ ] **Step 0.2: 运行测试，确认失败（开关还未实现）**
```bash
cd backend
uv run pytest tests/service/test_retrieval_pipeline_compatibility.py -v
# 预期：AttributeError: 'Settings' object has no attribute 'rag_pipeline_enabled'
```

- [ ] **Step 0.3: 新增开关配置到.env.dev和.env.dev.example**
```env
# .env.dev 新增
RAG_PIPELINE_ENABLED=false
RAG_QUERY_PIPELINE_YAML_PATH=""
RAG_PIPELINE_STEP_TIMEOUT=30
RAG_PIPELINE_ENABLE_MONITORING=true
RAG_PIPELINE_FAILURE_STRATEGY=fallback_to_default
```
同步复制到.env.dev.example

- [ ] **Step 0.4: 注册步骤类到DI容器**
```python
# backend/src/core/di_container.py 新增注册
from src.core.pipeline_steps import (
    CacheCheckStep, QueryRewriteStep, SynonymExpandStep,
    AgeFilterStep, HybridRetrievalStep, RerankStep,
    DedupStep, ConvertToKnowledgeStep, PageIndexStep
)

def configure_container(container):
    # 原有注册逻辑...
    
    # 新增流水线步骤注册
    container.register(CacheCheckStep, singleton=True)
    container.register(QueryRewriteStep, singleton=True)
    container.register(SynonymExpandStep, singleton=True)
    container.register(AgeFilterStep, singleton=True)
    container.register(HybridRetrievalStep, singleton=True)
    container.register(RerankStep, singleton=True)
    container.register(DedupStep, singleton=True)
    container.register(ConvertToKnowledgeStep, singleton=True)
    container.register(PageIndexStep, singleton=True)
    
    # 注册LLM实例（如果尚未注册）
    container.register("query_rewrite_llm", factory=lambda: create_llm(model="qwen-plus"), singleton=True)
    container.register("synonym_expand_llm", factory=lambda: create_llm(model="qwen-plus"), singleton=True)
    container.register("hybrid_retriever", factory=lambda: create_hybrid_retriever(), singleton=True)
```

- [ ] **Step 0.5: 运行测试，确认DI注册无问题**
```bash
uv run pytest tests/core/test_di_container.py -v
# 预期：所有测试通过
```

- [ ] **Step 0.6: 提交代码**
```bash
git add backend/src/core/di_container.py backend/.env.dev backend/.env.dev.example tests/service/test_retrieval_pipeline_compatibility.py
git commit -m "feat: add pipeline switch and DI registration for pipeline steps"
```

---

### 🚩 Task 1: Bug修复（1天，优先上线）
**目标：** 修复已知的两个高优先级Bug
**文件：**
- 修改：`backend/src/service/retrieval_service.py`
- 修改：`backend/src/core/pageindex_wrapper.py`

- [ ] **Step 1.1: 编写同义词Bug测试用例**
```python
# tests/service/test_retrieval_service.py 新增
@pytest.mark.asyncio
async def test_synonym_expand_invalid_json_fallback():
    """同义词扩展JSON解析失败时正常降级"""
    service = RetrievalService()
    # Mock LLM返回无效JSON
    original_llm = service._synonym_llm
    service._synonym_llm = MockLLM(return_value='invalid json')
    
    try:
        synonyms = await service._expand_synonyms("儿童训练")
        assert synonyms == []  # 降级返回空列表
    finally:
        service._synonym_llm = original_llm
```

- [ ] **Step 1.2: 运行测试，确认失败**
```bash
uv run pytest tests/service/test_retrieval_service.py::test_synonym_expand_invalid_json_fallback -v
# 预期：NameError: name 'synonyms' is not defined
```

- [ ] **Step 1.3: 修复同义词变量Bug**
```python
# backend/src/service/retrieval_service.py:883 修复前
except json.JSONDecodeError:
    logger.warning(f"同义词 JSON 解析失败: {synonyms}")  # synonyms 未定义

# 修复后
except json.JSONDecodeError:
    logger.warning(f"同义词 JSON 解析失败: {result_text}")  # 使用正确的变量
```

- [ ] **Step 1.4: 运行测试，确认通过**
```bash
uv run pytest tests/service/test_retrieval_service.py::test_synonym_expand_invalid_json_fallback -v
# 预期：PASS
```

- [ ] **Step 1.5: 编写PageIndex文件句柄泄漏测试用例**
```python
# tests/core/test_pageindex_wrapper.py 新增
def test_file_handle_closed_after_upload():
    """上传文件后文件句柄被正确关闭"""
    wrapper = PageIndexWrapper()
    test_file = "/tmp/test.pdf"
    with open(test_file, "w") as f:
        f.write("test content")
    
    # Mock上传成功
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.return_value.__aenter__.return_value.status = 200
        await wrapper.ingest_document(test_file)
    
    # 验证文件句柄已关闭
    with pytest.raises(ValueError, match="I/O operation on closed file"):
        f.read()
```

- [ ] **Step 1.6: 运行测试，确认失败**
```bash
uv run pytest tests/core/test_pageindex_wrapper.py::test_file_handle_closed_after_upload -v
# 预期：文件句柄未关闭，读取不报错
```

- [ ] **Step 1.7: 修复文件句柄泄漏Bug**
```python
# backend/src/core/pageindex_wrapper.py:243-253 修复前
with open(file_path, 'rb') as f:
    pass  # 空操作，f 在此处关闭

# 文件句柄泄漏：open() 创建的文件对象从未关闭
data.add_field('file',
              open(file_path, 'rb'),
              filename=os.path.basename(file_path))

# 修复后：使用 try/finally 确保文件关闭
file_handle = open(file_path, 'rb')
try:
    data.add_field('file', file_handle, filename=os.path.basename(file_path))
    
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            f"{self.base_url}/api/v1/documents",
            data=data,
            headers=headers
        ) as response:
            if response.status not in (200, 201):
                error_text = await response.text()
                logger.error(f"PageIndex document ingestion failed: {response.status} - {error_text}")
                return False
            return True
finally:
    file_handle.close()  # 确保文件关闭
```

- [ ] **Step 1.8: 运行测试，确认通过**
```bash
uv run pytest tests/core/test_pageindex_wrapper.py::test_file_handle_closed_after_upload -v
# 预期：PASS
```

- [ ] **Step 1.9: 提交代码**
```bash
git add backend/src/service/retrieval_service.py backend/src/core/pageindex_wrapper.py
git commit -m "fix: resolve synonym variable undefined and pageindex file handle leak"
```

---

### 🚩 Task 2: 基础设施搭建（2天）
**目标：** 完成配置模块、编排器、步骤目录等基础架构
**文件：**
- 新增：`backend/src/config/modules/rag/query_pipeline.py`
- 新增：`backend/src/config/query_pipeline.yaml`
- 新增：`backend/src/core/query_pipeline_orchestrator.py`
- 新增：`backend/src/core/pipeline_steps/__init__.py`
- 新增：`backend/src/core/pipeline_steps/base.py`
- 修改：`backend/src/config/__init__.py`

- [ ] **Step 2.1: 编写配置模块测试用例**
```python
# tests/config/test_query_pipeline_config.py
from src.config.modules.rag.query_pipeline import load_pipeline_config, _resolve_env_vars

def test_resolve_env_vars():
    """测试环境变量替换"""
    import os
    os.environ["TEST_VAR"] = "test_value"
    result = _resolve_env_vars("value: ${TEST_VAR:default}")
    assert result == "value: test_value"
    
    # 测试不存在的变量使用默认值
    result = _resolve_env_vars("value: ${NON_EXIST:default}")
    assert result == "value: default"

def test_load_pipeline_config_default():
    """测试加载默认配置"""
    config = load_pipeline_config()
    assert "pipelines" in config
    assert "simple" in config["pipelines"]
    assert "complex" in config["pipelines"]
    assert "default" in config["pipelines"]
```

- [ ] **Step 2.2: 实现配置模块（完全按照规格文档代码）**
复制规格文档中`backend/src/config/modules/rag/query_pipeline.py`的完整代码

- [ ] **Step 2.3: 运行配置模块测试，确认通过**
```bash
uv run pytest tests/config/test_query_pipeline_config.py -v
# 预期：所有测试通过
```

- [ ] **Step 2.4: 创建YAML配置文件**
复制规格文档中`backend/src/config/query_pipeline.yaml`的完整配置

- [ ] **Step 2.5: 编写编排器测试用例**
```python
# tests/core/test_query_pipeline_orchestrator.py
from src.core.query_pipeline_orchestrator import PipelineContext, PipelineOrchestrator, get_orchestrator
from src.core.pipeline_steps import get_step_factory

@pytest.mark.asyncio
async def test_orchestrator_simple_pipeline():
    """测试简单查询流水线执行"""
    context = PipelineContext(
        query="儿童训练",
        age=3,
        limit=5,
        query_type="simple"
    )
    orchestrator = get_orchestrator(get_step_factory())
    result = await orchestrator.execute(context)
    assert len(result.final_results) <= 5
    assert result.query_type == "simple"
```

- [ ] **Step 2.6: 实现编排器（完全按照规格文档代码）**
复制规格文档中`backend/src/core/query_pipeline_orchestrator.py`的完整代码

- [ ] **Step 2.7: 更新配置聚合入口**
按照规格文档修改`backend/src/config/__init__.py`，新增QueryPipelineSettings继承和_infer_category映射，修改热重载处理器支持yaml文件

- [ ] **Step 2.8: 创建步骤基类和注册表**
复制规格文档中`backend/src/core/pipeline_steps/base.py`和`backend/src/core/pipeline_steps/__init__.py`的代码

- [ ] **Step 2.9: 运行基础设施测试，确认通过**
```bash
uv run pytest tests/core/test_query_pipeline_orchestrator.py -v
# 预期：测试通过
```

- [ ] **Step 2.10: 提交代码**
```bash
git add backend/src/config/modules/rag/query_pipeline.py backend/src/config/query_pipeline.yaml backend/src/core/query_pipeline_orchestrator.py backend/src/core/pipeline_steps/ backend/src/config/__init__.py
git commit -m "feat: add pipeline infrastructure: config, orchestrator, step base"
```

---

### 🚩 Task 3: 步骤类实现（3天）
**目标：** 逐个实现所有流水线步骤类，完成单元测试
**文件：** 各个步骤类文件

#### 子任务3.1: CacheCheckStep
- [ ] 编写`tests/core/pipeline_steps/test_cache_check.py`测试用例
- [ ] 实现`backend/src/core/pipeline_steps/cache_check.py`
- [ ] 运行测试，确认通过
- [ ] 提交代码

#### 子任务3.2: QueryRewriteStep
- [ ] 编写`tests/core/pipeline_steps/test_query_rewrite.py`测试用例
- [ ] 实现`backend/src/core/pipeline_steps/query_rewrite.py`
- [ ] 运行测试，确认通过
- [ ] 提交代码

#### 子任务3.3: SynonymExpandStep
- [ ] 编写`tests/core/pipeline_steps/test_synonym_expand.py`测试用例
- [ ] 实现`backend/src/core/pipeline_steps/synonym_expand.py`
- [ ] 运行测试，确认通过
- [ ] 提交代码

#### 子任务3.4: AgeFilterStep
- [ ] 编写`tests/core/pipeline_steps/test_age_filter.py`测试用例
- [ ] 实现`backend/src/core/pipeline_steps/age_filter.py`
- [ ] 运行测试，确认通过
- [ ] 提交代码

#### 子任务3.5: HybridRetrievalStep
- [ ] 编写`tests/core/pipeline_steps/test_hybrid_retrieval.py`测试用例
- [ ] 实现`backend/src/core/pipeline_steps/hybrid_retrieval.py`
- [ ] 运行测试，确认通过
- [ ] 提交代码

#### 子任务3.6: RerankStep
- [ ] 编写`tests/core/pipeline_steps/test_rerank.py`测试用例
- [ ] 实现`backend/src/core/pipeline_steps/rerank.py`
- [ ] 运行测试，确认通过
- [ ] 提交代码

#### 子任务3.7: DedupStep
- [ ] 编写`tests/core/pipeline_steps/test_dedup.py`测试用例
- [ ] 实现`backend/src/core/pipeline_steps/dedup.py`
- [ ] 运行测试，确认通过
- [ ] 提交代码

#### 子任务3.8: ConvertToKnowledgeStep
- [ ] 编写`tests/core/pipeline_steps/test_convert_to_knowledge.py`测试用例
- [ ] 实现`backend/src/core/pipeline_steps/convert_to_knowledge.py`
- [ ] 运行测试，确认通过
- [ ] 提交代码

#### 子任务3.9: PageIndexStep（预留）
- [ ] 实现`backend/src/core/pipeline_steps/pageindex.py`（仅骨架，不启用）
- [ ] 提交代码

---

### 🚩 Task 4: 检索服务重构与集成（2天）
**目标：** 重构retrieve_knowledge方法，集成编排器，保持兼容
**文件：**
- 修改：`backend/src/service/retrieval_service.py`
- 新增：`tests/service/test_retrieval_pipeline_integration.py`

- [ ] **Step 4.1: 编写集成测试用例**
```python
# tests/service/test_retrieval_pipeline_integration.py
@pytest.mark.asyncio
async def test_simple_query_skips_llm_calls():
    """简单查询不执行LLM调用"""
    from src.config import settings
    original_value = settings.rag_pipeline_enabled
    settings.rag_pipeline_enabled = True
    
    try:
        service = RetrievalService()
        with patch.object(service._query_llm, 'ainvoke') as mock_rewrite, \
             patch.object(service._synonym_llm, 'ainvoke') as mock_synonym:
            result = await service.retrieve_knowledge("儿童训练", 3, 5, query_type="simple")
            mock_rewrite.assert_not_called()
            mock_synonym.assert_not_called()
            assert len(result) <= 5
    finally:
        settings.rag_pipeline_enabled = original_value

@pytest.mark.asyncio
async def test_complex_query_executes_full_pipeline():
    """复杂查询执行完整流水线"""
    from src.config import settings
    original_value = settings.rag_pipeline_enabled
    settings.rag_pipeline_enabled = True
    
    try:
        service = RetrievalService()
        with patch.object(service._query_llm, 'ainvoke', return_value=MockResponse("儿童注意力训练")) as mock_rewrite, \
             patch.object(service._synonym_llm, 'ainvoke', return_value=MockResponse('["专注力训练", "感统训练"]')) as mock_synonym:
            result = await service.retrieve_knowledge("孩子坐不住怎么办", 3, 5, query_type="complex")
            mock_rewrite.assert_called_once()
            mock_synonym.assert_called_once()
            assert len(result) <= 5
    finally:
        settings.rag_pipeline_enabled = original_value
```

- [ ] **Step 4.2: 重构retrieve_knowledge方法**
按照规格文档重构`retrieve_knowledge`方法，保留原有逻辑为`_retrieve_knowledge_old`，新增开关逻辑，集成编排器

- [ ] **Step 4.3: 优化缓存Key，包含query_type**
实现规格文档中的`_get_cache_key`方法，包含query_type避免缓存污染

- [ ] **Step 4.4: 运行集成测试，确认通过**
```bash
uv run pytest tests/service/test_retrieval_pipeline_integration.py -v
# 预期：所有测试通过
```

- [ ] **Step 4.5: 运行兼容性测试，确认结果一致**
```bash
uv run pytest tests/service/test_retrieval_pipeline_compatibility.py -v
# 预期：所有测试通过
```

- [ ] **Step 4.6: 提交代码**
```bash
git add backend/src/service/retrieval_service.py tests/service/test_retrieval_pipeline_integration.py
git commit -m "feat: refactor retrieval service to use pipeline orchestrator"
```

---

### 🚩 Task 5: 测试与灰度验证（3天）
**目标：** 完成所有测试，验证性能和兼容性
- [ ] **Step 5.1: 运行全量单元测试，覆盖率>80%**
```bash
uv run pytest --cov=src.core.pipeline_steps --cov=src.core.query_pipeline_orchestrator tests/
# 预期：覆盖率>80%
```

- [ ] **Step 5.2: 性能测试，验证指标达标**
```bash
# 运行性能测试脚本
uv run scripts/performance/test_pipeline_performance.py
# 预期：简单查询P95<2s，Token消耗降低60%+
```

- [ ] **Step 5.3: 灰度验证10%流量，监控指标**
配置监控大盘，监控错误率、延迟、Token消耗指标，确认无异常

- [ ] **Step 5.4: 结果一致性对比，差异率<0.1%**
运行流量回放测试，对比新旧逻辑返回结果，差异率<0.1%

---

### 🚩 Task 6: 文档同步（1天）
**目标：** 同步所有架构和配置文档
- [ ] 更新`AGENTS.md`新增RAG流水线架构说明
- [ ] 更新`CLAUDE.md`新增模块、配置、文件结构说明
- [ ] 更新`docs/RAG_SYSTEM_COMPLETE_DOCUMENTATION.md`同步新架构
- [ ] 更新`docs/配置系统文档.md`补充新增配置项说明
- [ ] 提交文档变更

---

### 🚩 Task 7: 全量上线与收尾（1天）
**目标：** 全量上线新流水线，验证无问题
- [ ] 逐步提升灰度流量到50%、100%，监控24小时无异常
- [ ] 确认性能指标达标：简单查询延迟降低50%+，Token消耗降低60%+
- [ ] 输出上线报告，汇总性能提升数据

---

## ✅ 验收标准
1. **功能验收**：所有检索场景功能正常，与旧逻辑返回结果一致性>99.9%
2. **性能验收**：简单查询P95延迟降低50%以上，Token消耗降低60%以上
3. **可观测性验收**：所有指标正常上报，错误日志包含完整上下文
4. **兼容性验收**：配置修改热重载生效，失败降级策略正常执行
5. **文档验收**：所有架构文档、配置文档同步更新完毕

---

## 🎯 回滚方案
1. **紧急回滚：** 设置`RAG_PIPELINE_ENABLED=false`，立即切回原有硬编码逻辑
2. **代码回滚：** 保留原有`_retrieve_knowledge_old`方法，随时可恢复
3. **自动回滚：** 配置错误率>1%、延迟超过阈值时自动触发告警，10分钟内未恢复自动回滚
