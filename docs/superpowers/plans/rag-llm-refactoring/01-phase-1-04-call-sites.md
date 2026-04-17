# Phase 1.1: 调用点改造

> **前置文档:** [Overview](./01-phase-1-00-overview.md) | [工厂类重构](./01-phase-1-02-factory-refactor.md)
> **状态:** ⚠️ 部分实现

### 🟠 1.4 调用点改造（⚠️ 部分实现）
> 说明：当前核心节点已完成基础工厂模式改造，但尚未支持provider参数选择、热更新等能力，所有调用仍固定使用Dashscope提供商。

#### Task 1.4.1: 核心节点文件改造
**Files:**
- Modify: `src/core/nodes/preprocessing.py`
- Modify: `src/core/nodes/validation.py`
- Modify: `src/core/nodes/assessment.py`
- Modify: `src/core/nodes/retrieval.py`
- Modify: `src/core/nodes/scoring.py`
- Modify: `src/core/nodes/reporting.py`

- [ ] **Step 1: 统一修改模式**
所有节点文件统一修改导入和LLM实例获取方式：
```python
# 移除旧导入
# from langchain_community.chat_models import ChatTongyi
# from src.config import settings

# 添加新导入
from src.core.llm.factory import llm_service_factory

# 替换LLM实例创建（注意使用 await）
# llm = ChatTongyi(model="qwen-plus", api_key=settings.dashscope_api_key)
llm = await llm_service_factory.create("report_generation", framework="langchain")  # 对应场景名称
```

- [ ] **Step 2: 逐文件修改**
| 文件 | 对应场景 |
|------|----------|
| validation.py | validation |
| assessment.py | assessment |
| reporting.py | report_generation |
| scoring.py | ml_scoring |

- [ ] **Step 3: 运行节点测试**
Run: `pytest tests/core/nodes/ -v`
Expected: All tests pass



#### Task 1.4.2: 其他LLM调用点改造
**Files:**
- Modify: `src/core/query_router.py`
- Modify: `src/core/metadata_extractor.py`
- Modify: `src/core/layered_content_generator.py`
- Modify: `src/core/memory_manager.py`
- Modify: `src/service/retrieval_service.py`
- Modify: `src/service/rag_test_manager.py`
- Modify: `src/controller/task_controller.py`

- [ ] **Step 1: 替换所有硬编码DashScope调用**
统一替换为工厂模式获取实例（注意使用 await）：
```python
# 旧代码
# from langchain_community.embeddings import DashScopeEmbeddings
# embeddings = DashScopeEmbeddings(model="text-embedding-v4", api_key=settings.dashscope_api_key)

# 新代码
from src.core.llm.embedding_factory import embedding_factory
embeddings = await embedding_factory.create(framework="langchain")
# 使用完毕后释放引用
# await embedding_factory.release(framework="langchain")
```

各文件对应场景：
| 文件 | 对应场景 |
|------|----------|
| metadata_extractor.py | metadata_extraction |
| query_router.py | query_routing |
| layered_content_generator.py | content_generation |
| retrieval_service.py | query_routing / synonym_expansion |
| rag_test_manager.py | test_case_draft_generation |
| task_controller.py | report_generation |

- [ ] **Step 2: 运行服务测试**
Run: `pytest tests/service/ -v`
Expected: All tests pass



#### Task 1.4.3: 改造 VL 解析器
**Files:**
- Modify: `src/core/parsers.py`

- [ ] **Step 1: 修改VL解析器实现**
```python
# 旧代码
# from llama_index.multi_modal_llms.dashscope import DashScopeMultiModal
# llm = DashScopeMultiModal(model="qwen-vl-plus", api_key=settings.dashscope_api_key)

# 新代码（注意使用 await）
from src.core.llm.factory import llm_service_factory
llm = await llm_service_factory.create("vl_parsing", framework="llamaindex")
# 使用完毕后释放引用
# await llm_service_factory.release("vl_parsing", framework="llamaindex")
```

- [ ] **Step 2: 运行解析器测试**
Run: `pytest tests/core/test_parsers.py -v`
Expected: All tests pass



#### Task 1.4.4: 改造 ML 评分器
**Files:**
- Modify: `src/core/ml/qwen_scorer.py`

- [ ] **Step 1: 修改评分器实现**
```python
# 旧代码
# from langchain_community.chat_models import ChatTongyi
# llm = ChatTongyi(model="qwen-plus", api_key=settings.dashscope_api_key)

# 新代码（注意使用 await）
from src.core.llm.factory import llm_service_factory
llm = await llm_service_factory.create("ml_scoring", framework="langchain")
# 使用完毕后释放引用
# await llm_service_factory.release("ml_scoring", framework="langchain")
```

- [ ] **Step 2: 运行评分器测试**
Run: `pytest tests/core/ml/test_qwen_scorer.py -v`
Expected: All tests pass



#### Task 1.4.5: 改造 Task Controller
**Files:**
- Modify: `src/controller/task_controller.py`

- [ ] **Step 1: 修改 Task Controller 实现**
```python
# 旧代码
# from langchain_community.chat_models import ChatTongyi
# from src.config import settings
# llm = ChatTongyi(model="qwen-plus", api_key=settings.dashscope_api_key)

# 新代码（注意使用 await）
from src.core.llm.factory import llm_service_factory
llm = await llm_service_factory.create("report_generation", framework="langchain")
# 使用完毕后释放引用
# await llm_service_factory.release("report_generation", framework="langchain")
```

- [ ] **Step 2: 运行控制器测试**
Run: `pytest tests/controller/test_task_controller.py -v`
Expected: All tests pass
