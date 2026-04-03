# RAG 系统完整技术文档

> 文档版本：v1.0  
> 最后更新：2026-04-02  
> 适用对象：后端开发人员、系统架构师

---

## 📑 目录

1. [系统概览](#1-系统概览)
2. [架构设计](#2-架构设计)
3. [核心模块详解](#3-核心模块详解)
   - [3.1 RetrievalService](#31-retrievalservice-检索服务)
   - [3.2 HybridRetrievalMerger](#32-hybridretrievalmerger-混合检索融合器)
   - [3.3 DocumentIngestionService](#33-documentingestionservice-文档导入服务)
   - [3.4 CrossEncoderReranker](#34-crossencodereranker-重排序器)
   - [3.5 CacheService](#35-cacheservice-缓存服务)
   - [3.6 MetadataProcessor](#36-metadataprocessor-元数据处理器)
   - [3.7 PageIndex 混合架构](#37-pageindex-混合架构-规划中)
4. [数据流与工作流程](#4-数据流与工作流程)
5. [配置参数详解](#5-配置参数详解)
6. [技术栈与依赖](#6-技术栈与依赖)
7. [测试与评估](#7-测试与评估)
8. [最佳实践与优化建议](#8-最佳实践与优化建议)
9. [故障排查指南](#9-故障排查指南)
10. [扩展开发指南](#10-扩展开发指南)

---

## 1. 系统概览

### 1.1 系统定位

本 RAG（Retrieval-Augmented Generation，检索增强生成）系统是**儿童发展评估 Agent**的核心知识检索引擎，专门针对儿童发展领域优化，提供精准、年龄适配的知识检索服务。

### 1.2 核心特性

✅ **混合检索架构** - BM25 关键词检索 + 向量语义检索 + Cross-Encoder 重排序  
✅ **年龄适配机制** - 基于儿童发展引擎的年龄过滤和加权  
✅ **多向量存储支持** - Chroma/Pinecone/Milvus/Weaviate 可插拔  
✅ **智能文档处理** - 扫描版 PDF OCR、语义分块、元数据提取  
✅ **生产级工程化** - 原子持久化、备份恢复、缓存、并发控制  
✅ **中文友好优化** - jieba 分词、自定义词典、阿里云 DashScope  
✅ **可评估可优化** - 完整评估指标体系、A/B 测试框架  

### 1.3 技术亮点

| 特性 | 实现方式 | 优势 |
|------|---------|------|
| 高精度检索 | BM25 + Vector + Reranking 三级检索 | 兼顾关键词匹配和语义理解 |
| 年龄适配 | 儿童发展引擎 + 元数据年龄范围 | 双重年龄验证，精准适配 |
| 扫描版 PDF 处理 | Qwen-VL OCR 自动识别 | 无需手动预处理 |
| 断点续传 | 任务状态持久化 | 大文件导入不中断 |
| 内容安全 | 导入 + 检索双重审核 | 确保内容适宜性 |

---

## 2. 架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      前端界面层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ 知识搜索页面 │  │ RAG 测试页面 │  │ 知识库管理页 │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      API 控制器层                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │RAGController│  │TestController│ │UploadController│       │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      服务层 (Service)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │RetrievalSvc │  │IngestionSvc │  │  CacheSvc   │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  IndexMgr   │  │  AuditSvc   │  │  TestMgr    │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      核心引擎层 (Core)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │HybridRetrieval│ │CrossEncoder │ │  Embedding  │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │VectorStore  │  │ChildDevEng  │ │ ABTestFramework│       │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      数据存储层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ Chroma DB   │  │  Redis      │  │  File System│          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 模块依赖关系

```
RetrievalService
├── IndexManagerService (索引管理)
├── CacheService (缓存服务)
├── HybridRetrievalMerger (混合检索融合)
├── CrossEncoderReranker (重排序器)
├── ContentAuditService (内容审核)
├── ChildDevelopmentEngine (儿童发展引擎)
└── ABTestFramework (A/B 测试)

DocumentIngestionService
├── IndexManagerService (索引管理)
├── MetadataProcessor (元数据处理)
├── PDFParser / EPUBParser (文档解析器)
├── ContentAuditService (内容审核)
└── DocumentManager (文档管理)
```

---

## 3. 核心模块详解

### 3.1 RetrievalService (检索服务)

**文件路径**: [`backend/src/service/retrieval_service.py`](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/service/retrieval_service.py)

#### 核心职责
- 处理所有检索请求
- 查询重写与同义词扩展
- 混合检索执行
- 年龄过滤与内容审核
- 结果缓存

#### 关键方法

##### `retrieve_knowledge(query, age, limit, user_id)`
```python
async def retrieve_knowledge(
    self, 
    query: str,           # 用户查询
    age: int,             # 儿童年龄
    limit: int = 3,       # 返回数量限制
    user_id: str = None   # 用户 ID，用于 A/B 测试
) -> List[KnowledgeItem]
```

**执行流程**:
1. 检查缓存（命中则直接返回）
2. A/B 测试变体分配
3. 查询重写（LLM）
4. 同义词扩展（LLM + 词典）
5. 执行混合检索
6. Cross-Encoder 重排序
7. 年龄过滤
8. 内容审核
9. 转换为 KnowledgeItem
10. 缓存结果

##### `search_content(query, limit)`
```python
async def search_content(
    self, 
    query: str,    # 搜索关键词
    limit: int = 20  # 返回数量
) -> List[dict]
```

**特点**: 搜索页面专用，返回更详细的元数据，包含关键词高亮支持

#### 查询优化机制

**1. 查询重写 (Query Rewrite)**
- 使用 LLM（DashScope qwen3-omni-flash）将口语化查询转换为检索友好格式
- 示例：
  - 原始查询："3 岁孩子注意力不集中怎么办？"
  - 重写后："3 岁 注意力 专注力 训练 方法"

**2. 同义词扩展 (Synonym Expansion)**
- LLM 生成相关术语
- 本地词典兜底
- 示例：
  - 原始词："大运动"
  - 扩展后："大运动 粗大动作 运动能力 平衡能力"

**代码实现**:
```python
async def _rewrite_query(self, query: str, age: int) -> str:
    """使用 LLM 重写查询"""
    llm = DashScope(model=settings.model_query_rewrite)
    prompt = QUERY_REWRITE_PROMPT.format(age=age, query=query)
    response = await llm.acomplete(prompt)
    return response.text.strip()

async def _expand_synonyms(self, query: str) -> str:
    """同义词扩展"""
    # 使用 LangChain 结构化输出
    parser = PydanticOutputParser(pydantic_object=SynonymExpansionResult)
    # ... LLM 调用 ...
    synonym_list = result.synonyms
    return " ".join(synonym_list)
```

#### 年龄适配机制

**1. 弹性年龄过滤**
```python
def _build_age_filters(self, age: int):
    tolerance = settings.rag_age_filter_tolerance  # 默认 2 岁
    min_age = max(0, age - tolerance)
    max_age = age + tolerance
    
    filters = [
        MetadataFilter(key="target_age_min", value=max_age, operator=FilterOperator.LTE),
        MetadataFilter(key="target_age_max", value=min_age, operator=FilterOperator.GTE),
    ]
    return MetadataFilters(filters=filters)
```

**2. 年龄适配度计算**
```python
def _calculate_age_fit_score(self, age: int, target_min: int, target_max: int) -> float:
    """计算年龄适配度得分，范围 0-1"""
    if target_min <= age <= target_max:
        return 1.0  # 完全适配
    
    # 超出范围，根据距离计算适配度
    strictness = settings.rag_age_filter_strictness
    diff = target_min - age if age < target_min else age - target_max
    base_score = max(0.5, 1 - diff * 0.1 * strictness)
    return base_score
```

**3. 最终得分融合**
```python
final_score = base_score * (1 - age_weight) + age_fit_score * age_weight
# age_weight 默认 0.3
```

---

### 3.2 HybridRetrievalMerger (混合检索融合器)

**文件路径**: [`backend/src/core/hybrid_retrieval.py`](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/core/hybrid_retrieval.py)

#### 核心问题
BM25 和向量检索的分数分布不同，无法直接相加：
- BM25 分数：无上限，通常 0-20
- 向量分数：余弦相似度，0-1

#### 解决方案

**1. BM25 分数校准 (Sigmoid 压缩)**
```python
@staticmethod
def _calibrate_bm25_score(score: float, corpus_quantile: float = None) -> float:
    """使用 sigmoid 将 BM25 分数压缩到 [0,1] 区间"""
    scale_factor = corpus_quantile or settings.bm25_scale_factor  # 默认 10
    return 1 / (1 + math.exp(-score / scale_factor))
```

**2. 向量分数校准**
```python
@staticmethod
def _calibrate_vector_score(score: float) -> float:
    """向量分数 Sigmoid 校准"""
    scale_factor = settings.get("vector_score_scale_factor", 5.0)
    return 1 / (1 + math.exp(-score * scale_factor))
```

**3. 动态权重调整**
```python
@staticmethod
def get_dynamic_weights(query: str, age: int = None) -> tuple[float, float]:
    """基于查询特征动态返回权重"""
    # 关键词密度计算
    keyword_density = len(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', query)) / len(query)
    
    # 关键词型查询偏重 BM25
    if keyword_density > 0.7:
        bm25_weight = 0.7
        vector_weight = 0.3
    # 语义型查询偏重向量
    elif keyword_density < 0.3:
        bm25_weight = 0.3
        vector_weight = 0.7
    else:
        bm25_weight = 0.5
        vector_weight = 0.5
    
    # 年龄维度适配
    if age and age < 3:
        bm25_weight *= 0.9  # 低龄儿童语义匹配更重要
    
    return bm25_weight, vector_weight
```

**4. 融合算法**
```python
@staticmethod
def merge_results(
    bm25_nodes: List[NodeWithScore],
    vector_nodes: List[NodeWithScore],
    bm25_weight: float = 0.5,
    vector_weight: float = 0.5,
    merge_mode: str = "OR",
    limit: int = 10,
) -> List[NodeWithScore]:
    # 1. 校准 BM25 分数
    for node in bm25_nodes:
        node.score = HybridRetrievalMerger._calibrate_bm25_score(node.score)
    
    # 2. 加权融合
    node_map = {}
    for node in bm25_nodes:
        node.score = node.score * bm25_weight
        node_map[node.node_id] = node
    
    for node in vector_nodes:
        vector_score = node.score * vector_weight
        if node.node_id in node_map:
            node_map[node.node_id].score += vector_score
        else:
            node.score = vector_score
            node_map[node.node_id] = node
    
    # 3. 全局归一化
    all_nodes = list(node_map.values())
    all_nodes = HybridRetrievalMerger._normalize_all_scores(all_nodes)
    
    # 4. 排序返回
    return sorted(all_nodes, key=lambda x: x.score, reverse=True)[:limit]
```

---

### 3.3 DocumentIngestionService (文档导入服务)

**文件路径**: [`backend/src/service/document_ingestion_service.py`](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/service/document_ingestion_service.py)

#### 7 步导入流程

```
1. 去重校验 (MD5 哈希)
   ↓
2. 智能文档解析 (PDF/EPUB)
   ↓
3. 文本清理
   ↓
4. 语义分块
   ↓
5. LLM 元数据提取
   ↓
6. 索引构建
   ↓
7. 重新初始化检索器
```

#### 关键特性

**1. 断点续传支持**
```python
async def ingest_book_resumable(
    self,
    file_path: str,
    task_id: str = None,
    force_restart: bool = False,
) -> str:
    """支持断点续传的书籍导入"""
    # 1. 计算文件哈希
    file_hash = self._calculate_file_hash(file_path)
    
    # 2. 检查是否已导入
    if document_manager.exists(file_hash):
        return file_hash
    
    # 3. 加载已有任务状态
    task_state = self.task_manager.load_task_state(task_id)
    if task_state:
        return await self._resume_import_task(task_state)
    
    # 4. 新任务执行
    return await self._ingest_book_with_state(task_state)
```

**2. 扫描版 PDF 自动 OCR**
```python
def _check_and_use_vl_parsing(self, file_path, documents, parser_cls):
    """检查 PDF 提取质量，必要时使用 VL 解析"""
    # 判断是否为扫描版 PDF
    extraction_rate = len(documents) / total_pages
    avg_text_length = sum(len(doc.text) for doc in documents) / len(documents)
    
    is_scanned_pdf = (
        extraction_rate < settings.rag_ocr_extraction_rate_threshold
        or avg_text_length < settings.rag_ocr_min_avg_length_threshold
    )
    
    if is_scanned_pdf:
        # 使用 Qwen-VL 进行 OCR
        vl_documents = PDFVLParser.parse(file_path)
        return vl_documents
    
    return documents
```

**3. 内容哈希去重 (RAG-013)**
```python
# 内容级去重，而非文件级去重
for node in processed_nodes:
    content = node.get_content()
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    node.metadata["content_hash"] = content_hash
    
    if content_hash not in existing_hashes:
        unique_nodes.append(node)
        existing_hashes.add(content_hash)
```

**4. 原子持久化**
```python
def insert_nodes(self, nodes, progress_callback=None):
    """原子性索引插入"""
    # 1. 写入临时目录
    temp_dir = self.persist_dir / f"temp_{datetime.now().timestamp()}"
    self.index.storage_context.persist(temp_dir)
    
    # 2. 原子替换
    final_dir = self.persist_dir / "index"
    if final_dir.exists():
        shutil.rmtree(final_dir)
    shutil.move(temp_dir, final_dir)
    
    # 3. 备份恢复机制
    self._create_backup()
```

---

### 3.4 CrossEncoderReranker (重排序器)

**文件路径**: [`backend/src/core/reranker.py`](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/core/reranker.py)

#### 作用
对粗检索结果（30 个）进行精细排序，提升 Top-K 准确率

#### 模型
- **模型名称**: BAAI/bge-reranker-v2-m3
- **类型**: Cross-Encoder
- **优势**: 同时考虑 query 和 document，比 Bi-Encoder 更精准

#### 使用方式
```python
class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        initial_k: int = 30,  # 粗检索数量
        final_k: int = 5,     # 精检索数量
    ):
        self.model = CrossEncoder(model_name)
    
    def rerank(self, query: str, nodes: List[NodeWithScore]) -> List[NodeWithScore]:
        # 1. 提取文本对
        query_doc_pairs = [(query, node.node.get_content()) for node in nodes]
        
        # 2. Cross-Encoder 评分
        scores = self.model.predict(query_doc_pairs)
        
        # 3. 更新分数并排序
        for node, score in zip(nodes, scores):
            node.score = float(score)
        
        return sorted(nodes, key=lambda x: x.score, reverse=True)[:self.final_k]
```

---

### 3.5 CacheService (缓存服务)

**文件路径**: [`backend/src/service/cache_service.py`](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/service/cache_service.py)

#### 特性
- LRU 缓存（内存 + Redis）
- TTL 过期
- 防穿透/击穿/雪崩
- 细粒度失效
- 标签管理

#### 缓存键设计
```python
def _get_cache_key(self, query: str, age: int, limit: int) -> tuple:
    """生成包含索引版本和配置指纹的缓存键"""
    return (
        query.strip().lower(),
        age,
        limit,
        self.index_manager.index_version,      # 索引版本号
        self.index_manager.config_fingerprint, # 配置指纹
    )
```

**优势**: 索引更新或配置变更后自动失效

---

### 3.6 MetadataProcessor (元数据处理器)

**文件路径**: [`backend/src/core/metadata_processor.py`](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/core/metadata_processor.py)

#### 提取字段
```python
{
    "summary": "内容摘要",
    "topics": ["关键词 1", "关键词 2"],
    "brain_regions": ["前额叶", "海马体"],
    "target_age_min": 3,
    "target_age_max": 6,
    "activity_type": "Theory",  # Theory/Activity/Assessment
    "benefits": ["能力提升 1", "能力提升 2"],
    "content_hash": "sha256 哈希",
    "file_hash": "文件 MD5",
    "chapter_title": "章节标题",
    "page_label": "页码"
}
```

#### 语义分块
```python
@staticmethod
def split_pages_into_chunks(
    documents: List[Document],
    chunk_size: int = 1536,
    chunk_overlap: int = 20,
) -> List[Document]:
    """基于语义相似度的智能分块"""
    # 1. 比较前后段落语义相似度
    # 2. 在相似度低的位置断点
    # 3. 保持语义完整性
```

---

### 3.7 PageIndex 混合架构 (已实现)

**实现文档**: [`docs/superpowers/solutions/2026-04-02-rag-system-problems-solution.md`](file:///Users/owen/project/ai/child-development-assessment-agent/docs/superpowers/solutions/2026-04-02-rag-system-problems-solution.md)

#### 核心目标
集成 PageIndex 实现**混合推理架构**，在保留现有快速混合检索的同时，增强复杂多步查询能力。

#### 实施状态

✅ **当前状态**: 已实现并集成

**核心组件**:
- ✅ QueryRouter (查询路由器) - `backend/src/core/query_router.py`
- ✅ PageIndexWrapper (PageIndex 包装器) - `backend/src/core/pageindex_wrapper.py`
- ✅ ResultFusion (结果融合器) - `backend/src/core/result_fusion.py`
- ✅ DynamicAgeFilter (动态年龄过滤器) - `backend/src/core/age_filter.py`

**配置项**:
- ✅ PageIndex 配置（熔断、重试、降级）
- ✅ 查询分类器配置
- ✅ 结果融合配置

#### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    用户查询                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  QueryRouter (查询路由器)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 简单查询 (关键词/事实性)                               │   │
│  │ - 包含明确关键词                                        │   │
│  │ - 单步检索可解决                                        │   │
│  │ - 示例："注意力训练的方法有哪些？"                      │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 复杂查询 (推理/分析性)                                 │   │
│  │ - 需要多步推理                                          │   │
│  │ - 跨文档关联                                            │   │
│  │ - 示例："分析小明在前庭觉、精细动作、社交三个维度的      │   │
│  │            发展情况，生成综合评估报告"                 │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                    ↓                        ↓
        ┌────────────────────┐    ┌────────────────────┐
        │   简单查询路径      │    │   复杂查询路径      │
        │  HybridRetrieval    │    │  PageIndex +       │
        │  (BM25 + Vector)    │    │  HybridRetrieval   │
        └────────────────────┘    └────────────────────┘
                    ↓                        ↓
┌─────────────────────────────────────────────────────────────┐
│                ResultFusion (结果融合器)                      │
│  - 统一输出格式                                              │
│  - 去重和排序                                                │
│  - 置信度加权                                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    返回结果                                   │
└─────────────────────────────────────────────────────────────┘
```

#### 核心组件

**1. QueryRouter (查询路由器)**
```python
class QueryRouter:
    """查询分类器，判断查询类型并路由到合适的检索引擎"""
    
    def classify(self, query: str) -> QueryClassification:
        """
        分类查询类型
        :return: QueryClassification (query_type, confidence)
        """
        # 1. 基于规则的快速分类
        if self._regex_classify(query):
            return QueryClassification(QueryType.SIMPLE, 0.9)
        
        # 2. LLM 辅助分类（可选）
        if settings.query_router_llm_enabled:
            return await self._llm_classify(query)
        
        return QueryClassification(QueryType.DEFAULT, 0.5)
```

**2. PageIndexWrapper (PageIndex 包装器)**
```python
class PageIndexWrapper:
    """PageIndex 引擎包装器，封装推理检索能力"""
    
    async def query(
        self, 
        query: str, 
        context: Optional[List[str]] = None,
        max_depth: int = 3
    ) -> List[Dict[str, Any]]:
        """
        使用 PageIndex 进行推理检索
        :param query: 查询字符串
        :param context: 额外上下文
        :param max_depth: 最大推理深度
        :return: 检索结果列表
        """
        # 调用 PageIndex API 进行推理检索
        response = await self.client.reasoning_query(
            query=query,
            context=context,
            max_tree_depth=max_depth
        )
        
        # 解析结果，包含推理路径
        results = []
        for node in response.nodes:
            results.append({
                "content": node.content,
                "source": node.source_document,
                "section": node.section_path,
                "reasoning_path": node.reasoning_trace,  # 可解释的推理路径
                "confidence": node.confidence_score,
            })
        
        return results
```

**3. ResultFusion (结果融合器)**
```python
class ResultFusion:
    """结果融合器，合并混合检索和 PageIndex 的结果"""
    
    def fuse(
        self,
        hybrid_results: List[Dict],
        pageindex_results: List[Dict],
        query_type: QueryType
    ) -> List[Dict]:
        """
        融合两种检索结果
        :param hybrid_results: 混合检索结果
        :param pageindex_results: PageIndex 结果
        :param query_type: 查询类型
        :return: 融合后的结果
        """
        if query_type == QueryType.SIMPLE:
            # 简单查询：仅使用混合检索结果
            return hybrid_results
        
        elif query_type == QueryType.COMPLEX:
            # 复杂查询：融合两种结果
            # 1. 去重（基于内容哈希）
            # 2. PageIndex 结果加分（置信度更高）
            # 3. 统一排序
            fused = self._merge_and_dedup(hybrid_results, pageindex_results)
            fused = self._boost_pageindex_scores(fused)
            return sorted(fused, key=lambda x: x["score"], reverse=True)
        
        else:
            # 默认：混合检索为主，PageIndex 补充
            return hybrid_results[:limit] + pageindex_results[:supplement_limit]
```

#### 与现有系统对比

| 维度 | 现有混合检索 | PageIndex | 混合架构 |
|------|-------------|-----------|---------|
| 检索方式 | 相似度匹配（BM25+ 向量） | LLM 推理导航 | 智能路由 |
| 跨文档关联 | 弱（基于相似度） | 强（基于推理） | 兼顾 |
| 多步推理 | ❌ 需手动组织 | ✅ 自动完成 | ✅ 支持 |
| 透明性 | ⚠️ 黑盒 | ✅ 可解释路径 | ✅ 部分可解释 |
| 性能 | ✅ 快速（毫秒级） | ⚠️ 较慢（秒级） | 智能平衡 |
| 成本 | ✅ 一次性嵌入 | ⚠️ 每次查询调用 LLM | 优化成本 |
| 基础设施 | 需要向量存储 | 无需向量数据库 | 两者兼容 |

#### 配置参数（规划）

```python
# backend/src/config/settings.py

# PageIndex 配置
pageindex_enabled: bool = Field(True, validation_alias="PAGEINDEX_ENABLED")
pageindex_api_key: str = Field("", validation_alias="PAGEINDEX_API_KEY")
pageindex_max_concurrency: int = Field(5, validation_alias="PAGEINDEX_MAX_CONCURRENCY")
pageindex_max_tree_depth: int = Field(3, validation_alias="PAGEINDEX_MAX_TREE_DEPTH")
pageindex_timeout_seconds: int = Field(10, validation_alias="PAGEINDEX_TIMEOUT_SECONDS")

# 查询分类器配置
query_router_llm_enabled: bool = Field(True, validation_alias="QUERY_ROUTER_LLM_ENABLED")
query_router_confidence_threshold: float = Field(0.8, validation_alias="QUERY_ROUTER_CONFIDENCE_THRESHOLD")

# 结果融合配置
fusion_hybrid_supplement_limit: int = Field(5, validation_alias="FUSION_HYBRID_SUPPLEMENT_LIMIT")
fusion_score_boost_for_pageindex: float = Field(1.2, validation_alias="FUSION_SCORE_BOOST_FOR_PAGEINDEX")
```

#### 实施状态

✅ **当前状态**: 已实现并集成（2026-04-02）

**已实现组件**:
- ✅ QueryRouter (查询路由器) - 支持规则 +LLM 双模式分类，带熔断和重试机制
- ✅ PageIndexWrapper (PageIndex 包装器) - 支持熔断器、指数退避重试、降级
- ✅ ResultFusion (结果融合器) - 支持文本归一化去重、动态权重融合
- ✅ DynamicAgeFilter (动态年龄过滤器) - 支持 4 个发展阶段动态适配

**配置项** (已在 `backend/src/config/settings.py` 实现):
- ✅ PageIndex 配置：`pageindex_enabled`, `pageindex_api_key`, `pageindex_max_concurrency` 等
- ✅ 熔断配置：`pageindex_circuit_breaker_failure_threshold`, `pageindex_circuit_breaker_reset_timeout`
- ✅ 重试配置：`pageindex_max_retries`, `pageindex_retry_base_delay`, `pageindex_retry_max_delay`
- ✅ 降级配置：`pageindex_fallback_to_hybrid`
- ✅ 查询分类器：`query_router_llm_enabled`, `query_router_confidence_threshold`
- ✅ 结果融合：`fusion_score_boost_for_pageindex`, `fusion_hybrid_supplement_limit`

**预期收益**:
1. ✅ **复杂查询增强**: 支持多步推理和跨文档关联，准确率从 40% 提升至 85%
2. ✅ **可解释性**: 提供推理路径，增强透明度
3. ✅ **性能平衡**: 简单查询快速响应（<500ms），复杂查询深度推理（<3s）
4. ✅ **向后兼容**: 保留现有混合检索，配置可选（`PAGEINDEX_ENABLED=false` 默认关闭）

**参考文档**:
- [最终改进方案](file:///Users/owen/project/ai/child-development-assessment-agent/docs/final-rag-improvement-solution.md) - 第 4 部分：PageIndex 混合架构
- [实施计划](file:///Users/owen/project/ai/child-development-assessment-agent/docs/superpowers/plans/2026-04-01-pageindex-hybrid-architecture.md)
- [解决方案](file:///Users/owen/project/ai/child-development-assessment-agent/docs/superpowers/solutions/2026-04-02-rag-system-problems-solution.md) - 完整实现方案

---

## 4. 数据流与工作流程

### 4.1 检索工作流程

```mermaid
sequenceDiagram
    participant User
    participant API as RAGController
    participant Cache as CacheService
    participant Retrieval as RetrievalService
    participant Hybrid as HybridRetrievalMerger
    participant Rerank as CrossEncoderReranker
    participant Audit as ContentAuditService
    participant Index as VectorIndex

    User->>API: POST /api/rag/retrieve
    API->>Retrieval: retrieve_knowledge(query, age, limit)
    
    Retrieval->>Cache: get(cache_key)
    alt Cache Hit
        Cache-->>Retrieval: cached_result
        Retrieval-->>API: cached_result
    else Cache Miss
        Retrieval->>Retrieval: 查询重写 (LLM)
        Retrieval->>Retrieval: 同义词扩展 (LLM)
        
        par 并行检索
            Retrieval->>Hybrid: BM25 检索
            Retrieval->>Hybrid: 向量检索
        end
        
        Hybrid->>Hybrid: 分数校准
        Hybrid->>Hybrid: 加权融合
        Hybrid-->>Retrieval: merged_nodes
        
        Retrieval->>Rerank: rerank(query, merged_nodes)
        Rerank-->>Retrieval: reranked_nodes
        
        Retrieval->>Audit: audit_content(content)
        Audit-->>Retrieval: audit_result
        
        Retrieval->>Retrieval: 年龄过滤
        Retrieval->>Retrieval: 转换为 KnowledgeItem
        
        Retrieval->>Cache: set(cache_key, result)
        Retrieval-->>API: knowledge_items
    end
    
    API-->>User: JSON response
```

### 4.2 文档导入工作流程

```mermaid
sequenceDiagram
    participant User
    participant API as UploadController
    participant Ingestion as DocumentIngestionService
    participant TaskMgr as ImportTaskManager
    participant Parser as PDFParser/EPUBParser
    participant Audit as ContentAuditService
    participant Metadata as MetadataProcessor
    participant IndexMgr as IndexManagerService
    participant DocMgr as DocumentManager

    User->>API: POST /api/upload (file)
    API->>Ingestion: ingest_book_resumable(file_path)
    
    Ingestion->>Ingestion: 计算文件 MD5
    Ingestion->>DocMgr: exists(file_hash)
    
    alt 已导入
        DocMgr-->>Ingestion: true
        Ingestion-->>API: file_hash
    else 未导入
        Ingestion->>TaskMgr: load_task_state(task_id)
        
        alt 有任务状态
            TaskMgr-->>Ingestion: task_state
            Ingestion->>Ingestion: 从断点恢复
        else 新任务
            Ingestion->>Parser: parse(file_path)
            Parser-->>Ingestion: documents
            
            Ingestion->>Audit: audit_content(full_text)
            Audit-->>Ingestion: audit_result
            
            alt 审核通过
                Ingestion->>DocMgr: add_document(status="processing")
                Ingestion->>Metadata: split_into_chunks(documents)
                Metadata-->>Ingestion: chunks
                
                Ingestion->>Metadata: process_nodes(chunks)
                Metadata-->>Ingestion: processed_nodes
                
                Ingestion->>IndexMgr: insert_nodes(processed_nodes)
                IndexMgr-->>Ingestion: success
                
                Ingestion->>DocMgr: update_document(status="indexed")
                Ingestion->>TaskMgr: save_task_state(completed)
                Ingestion-->>API: file_hash
            else 审核失败
                Audit-->>Ingestion: failed
                Ingestion-->>API: error
            end
        end
    end
    
    API-->>User: UploadResponse
```

---

## 5. 配置参数详解

### 5.1 混合检索配置

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `rag_hybrid_bm25_weight` | float | 0.5 | BM25 权重 |
| `rag_hybrid_vector_weight` | float | 0.5 | 向量权重 |
| `bm25_scale_factor` | float | 10 | BM25 分数缩放因子 |
| `rag_hybrid_bm25_top_k` | int | 10 | BM25 返回数量 |
| `rag_hybrid_vector_top_k` | int | 10 | 向量返回数量 |
| `rag_hybrid_merge_mode` | str | "OR" | 合并模式 (AND/OR) |

**动态权重配置**:
```python
hybrid_weights = {
    "default": 0.5,           # 默认权重
    "keyword_query": 0.7,     # 关键词型查询 BM25 权重
    "semantic_query": 0.3,    # 语义型查询 BM25 权重
}
```

### 5.2 搜索专用配置

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `rag_search_bm25_weight` | float | 0.7 | 搜索页面 BM25 权重 |
| `rag_search_vector_weight` | float | 0.3 | 搜索页面向量权重 |
| `rag_search_no_match_vector_penalty` | float | 0.3 | BM25 无结果时向量惩罚 |
| `rag_search_score_threshold_hybrid` | float | 0.1 | 混合模式阈值 |
| `rag_search_score_threshold_vector` | float | 0.1 | 向量模式阈值 |
| `rag_search_relative_cutoff_ratio` | float | 0.1 | 相对截断比例 |
| `rag_search_min_similarity_threshold` | float | 0.3 | 最低相似度阈值 |

### 5.3 缓存配置

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `rag_cache_enabled` | bool | True | 启用缓存 |
| `rag_cache_max_size` | int | 1000 | 最大缓存条目数 |
| `rag_cache_ttl_seconds` | int | 3600 | 缓存 TTL（秒） |

### 5.4 分块配置

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `rag_chunk_size` | int | 1024 | 默认分块大小 |
| `rag_pdf_chunk_size` | int | 1536 | PDF 分块大小 |
| `rag_epub_chunk_target_size` | int | 800 | EPUB 目标分块大小 |
| `rag_chunk_overlap` | int | 20 | 分块重叠长度 |
| `semantic_splitter_buffer_size` | int | 3 | 语义分块比较段落数 |
| `semantic_splitter_breakpoint_threshold` | int | 95 | 语义分块相似度阈值 |

### 5.5 年龄过滤配置

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `rag_age_filter_strictness` | float | 0.7 | 年龄过滤严格程度 (0-1) |
| `rag_age_filter_tolerance` | int | 2 | 年龄容忍范围（岁） |
| `rag_age_fit_weight` | float | 0.3 | 年龄适配度权重 |

### 5.6 Embedding 配置

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `embedding_model_name` | str | "text-embedding-v2" | Embedding 模型名称 |
| `embedding_max_text_length` | int | 1536 | 最大文本长度 |

### 5.7 向量存储配置

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `vector_store_type` | str | "chroma" | 向量存储类型 |
| `vector_store_config` | dict | {} | 向量存储配置 |

**支持的向量库**:
- **Chroma**: 本地持久化，默认选项
- **Pinecone**: 云服务，适合大规模
- **Milvus**: 分布式，高性能
- **Weaviate**: 云原生，支持 GraphQL

### 5.8 OCR 配置

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `rag_ocr_extraction_rate_threshold` | float | 0.5 | OCR 触发阈值（提取率） |
| `rag_ocr_min_avg_length_threshold` | int | 100 | OCR 触发阈值（平均长度） |

---

## 6. 技术栈与依赖

### 6.1 核心框架

```toml
# RAG 框架
llama-index==0.14.16
llama-index-vector-stores-chroma>=0.2.0
llama-index-retrievers-bm25>=0.2.3

# LLM 和 Embedding
llama-index-llms-dashscope>=0.2.1
llama-index-embeddings-dashscope>=0.2.1

# 编排
langgraph==1.1.0
```

### 6.2 文档处理

```toml
pymupdf>=1.27.2       # PDF 解析
ebooklib>=0.20        # EPUB 解析
beautifulsoup4>=4.14.3  # HTML 解析

# 中文分词
jieba>=0.42.1

# 重排序
sentence-transformers  # Cross-Encoder
```

### 6.3 向量存储后端

```toml
# Chroma (默认)
chromadb>=0.4.0

# Pinecone (可选)
pinecone-client>=3.0.0

# Milvus (可选)
pymilvus>=2.3.0

# Weaviate (可选)
weaviate-client>=3.0.0
```

### 6.4 缓存

```toml
# 内存缓存 (内置)
# Redis (可选，分布式缓存)
redis>=4.5.0
```

---

## 7. 测试与评估

### 7.1 测试文件结构

```
backend/tests/
├── test_rag_search.py           # 搜索功能测试
├── test_rag_hybrid.py           # 混合检索测试
├── test_rag_ingest.py           # 文档导入测试
├── test_rag_import.py           # 导入功能测试
├── test_rag_optimizations.py    # 优化功能测试
├── test_rag_enhancements.py     # 增强功能测试
├── test_pdf_chunking.py         # PDF 分块测试
├── test_vl_parse.py             # VL OCR 解析测试
├── test_full_workflow.py        # 完整工作流测试
└── test_nodes_scoring.py        # 评分节点测试
```

### 7.2 评估指标

**RAGEvaluator** ([`backend/src/core/rag_evaluator.py`](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/core/rag_evaluator.py)) 提供以下指标：

| 指标 | 说明 | 计算公式 |
|------|------|---------|
| **Precision@K** | 前 K 个结果的准确率 | K 个中相关结果数 / K |
| **Recall@K** | 前 K 个结果的召回率 | K 个中相关结果数 / 总相关结果数 |
| **NDCG@K** | 归一化折损累积增益 | 考虑排序质量的指标 |
| **MRR** | 平均倒数排名 | 第一个相关结果排名的倒数 |
| **MAP** | 平均精度均值 | 多个查询的平均 Precision |

### 7.3 A/B 测试框架

**文件路径**: [`backend/src/core/ab_test_framework.py`](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/core/ab_test_framework.py)

**支持的实验**:
- 检索策略 A/B 测试（不同权重配置）
- 重排序器 A/B 测试
- 缓存策略 A/B 测试

**使用示例**:
```python
# 获取用户所属变体
variant = ab_test_framework.get_variant(user_id, "retrieval_strategy")

# 记录指标
ab_test_framework.track_metric(
    "retrieval_strategy", 
    variant, 
    "latency", 
    latency_value
)
```

---

## 8. 最佳实践与优化建议

### 8.1 性能优化

**1. 缓存策略**
- 启用 Redis 分布式缓存（生产环境）
- 调整 TTL 根据查询频率
- 使用标签管理批量失效

**2. 索引优化**
- 定期重建索引（删除低质量块）
- 使用增量更新而非全量重建
- 监控索引大小和查询延迟

**3. 并发控制**
- 元数据提取使用异步并行（默认 20 并发）
- 文档导入限制最大并发任务数（默认 5）
- VL OCR 限制最大工作线程（默认 2）

### 8.2 质量优化

**1. 查询优化**
- 保持查询重写和同义词扩展启用
- 定期更新 jieba 自定义词典
- 监控 LLM 调用失败率

**2. 分块优化**
- 根据文档类型调整分块大小
- 语义分块阈值根据领域调整
- 监控分块质量（平均长度、元数据完整性）

**3. 重排序优化**
- 调整 initial_k 和 final_k 平衡性能和准确率
- 考虑使用更轻量级的重排序模型（如 bge-reranker-base）

### 8.3 监控建议

**关键指标**:
- 检索延迟（P50/P90/P99）
- 缓存命中率
- 索引大小和增长趋势
- LLM 调用成功率和成本
- 用户满意度（前端反馈）

**日志级别**:
```python
# 开发环境
log_level = "DEBUG"

# 生产环境
log_level = "INFO"
```

---

## 9. 故障排查指南

### 9.1 常见问题

**问题 1: 检索结果为空**
```
可能原因:
1. 索引为空 → 检查文档是否成功导入
2. 阈值过高 → 降低 rag_search_score_threshold
3. 年龄过滤过严 → 调整 rag_age_filter_strictness
4. 查询重写失败 → 检查 LLM API 可用性

排查步骤:
1. 查看日志：grep "Index is empty" logs/app.log
2. 检查索引：调用 /api/rag/status 查看索引状态
3. 测试查询：使用简单关键词测试
```

**问题 2: 导入失败**
```
可能原因:
1. 文件格式不支持 → 仅支持 PDF/EPUB
2. 扫描版 PDF 无法 OCR → 检查 VL 模型配置
3. 内容审核失败 → 查看审核日志
4. 内存不足 → 降低并发数

排查步骤:
1. 查看错误日志：grep "Failed to ingest" logs/app.log
2. 检查文件：手动测试文件解析
3. 监控资源：htop 查看内存使用
```

**问题 3: 缓存失效**
```
可能原因:
1. 索引版本变更 → 预期行为
2. 配置指纹变更 → 检查配置更新
3. TTL 过期 → 调整 rag_cache_ttl_seconds

排查步骤:
1. 查看缓存日志：grep "Cache" logs/app.log
2. 检查索引版本：index_manager.index_version
3. 监控缓存命中率
```

### 9.2 调试工具

**1. 调试脚本**
```bash
# RAG 调试
python backend/debug_rag.py

# PDF 调试
python backend/debug_pdf.py

# 分块调试
python backend/test_chunks_debug.py
```

**2. API 端点**
```bash
# 查看索引状态
curl http://localhost:8000/api/rag/status

# 查看文档列表
curl http://localhost:8000/api/documents

# 测试检索
curl -X POST http://localhost:8000/api/rag/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "注意力训练", "age": 3, "limit": 5}'
```

---

## 10. 扩展开发指南

### 10.1 添加新的向量存储后端

**步骤 1: 实现 VectorStore 接口**
```python
from llama_index.core.vector_stores import VectorStore

class MyCustomVectorStore(VectorStore):
    def __init__(self, config: dict):
        self.client = MyVectorDBClient(**config)
    
    def add(self, nodes: List[NodeWithScore]) -> List[str]:
        # 实现添加逻辑
        pass
    
    def delete(self, node_ids: List[str]) -> None:
        # 实现删除逻辑
        pass
    
    def query(self, query: VectorStoreQuery) -> VectorStoreQueryResult:
        # 实现查询逻辑
        pass
```

**步骤 2: 注册到工厂**
```python
# backend/src/core/vector_store_factory.py
class VectorStoreFactory:
    @staticmethod
    def create(vector_store_type: str, config: dict) -> VectorStore:
        if vector_store_type == "my_custom":
            return MyCustomVectorStore(config)
        # ... 其他类型
```

**步骤 3: 更新配置**
```python
# .env
VECTOR_STORE_TYPE="my_custom"
VECTOR_STORE_CONFIG='{"host": "localhost", "port": 6379}'
```

### 10.2 自定义分块策略

```python
from llama_index.core.node_parser import NodeParser

class CustomNodeParser(NodeParser):
    def _parse_nodes(self, nodes: List[Document]) -> List[Node]:
        # 自定义分块逻辑
        # 例如：按章节 + 段落 + 语义三重分块
        pass

# 在 DocumentIngestionService 中使用
parser = CustomNodeParser()
nodes = parser.get_nodes_from_documents(documents)
```

### 10.3 添加新的评估指标

```python
# backend/src/core/rag_evaluator.py
class RAGEvaluator:
    @staticmethod
    def calculate_custom_metric(
        query_results: List[QueryResult],
        ground_truth: List[RelevantDocument]
    ) -> float:
        # 自定义评估指标
        # 例如：年龄适配度准确率
        pass
```

### 10.4 集成外部知识源

```python
# 示例：集成维基百科
class WikipediaRetriever:
    def retrieve(self, query: str, limit: int) -> List[Document]:
        import wikipedia
        results = wikipedia.search(query, results=limit)
        documents = []
        for title in results:
            page = wikipedia.page(title)
            documents.append(Document(text=page.content))
        return documents

# 在 RetrievalService 中集成
async def retrieve_knowledge(self, query: str, age: int, limit: int):
    # 1. 本地索引检索
    local_results = await self._execute_retrieval(query, limit)
    
    # 2. 维基百科检索
    wiki_results = WikipediaRetriever().retrieve(query, limit=2)
    
    # 3. 融合结果
    return self._merge_results(local_results, wiki_results)
```

---

## 附录 A: 快速参考

### A.1 核心文件路径

| 模块 | 文件路径 |
|------|---------|
| 检索服务 | `backend/src/service/retrieval_service.py` |
| 混合检索 | `backend/src/core/hybrid_retrieval.py` |
| 文档导入 | `backend/src/service/document_ingestion_service.py` |
| 重排序器 | `backend/src/core/reranker.py` |
| 缓存服务 | `backend/src/service/cache_service.py` |
| 索引管理 | `backend/src/service/index_manager_service.py` |
| 配置 | `backend/src/config/settings.py` |
| **查询路由器** (已实现) | `backend/src/core/query_router.py` |
| **PageIndex 包装器** (已实现) | `backend/src/core/pageindex_wrapper.py` |
| **结果融合器** (已实现) | `backend/src/core/result_fusion.py` |
| **动态年龄过滤器** (已实现) | `backend/src/core/age_filter.py` |
| **PageIndex 计划** | `docs/superpowers/plans/2026-04-01-pageindex-hybrid-architecture.md` |
| **PageIndex 解决方案** | `docs/superpowers/solutions/2026-04-02-rag-system-problems-solution.md` |

### A.2 关键配置速查

```bash
# 混合检索权重
RAG_HYBRID_BM25_WEIGHT=0.5
RAG_HYBRID_VECTOR_WEIGHT=0.5

# 缓存
RAG_CACHE_ENABLED=true
RAG_CACHE_TTL_SECONDS=3600

# 分块
RAG_CHUNK_SIZE=1024
RAG_CHUNK_OVERLAP=20

# 年龄过滤
RAG_AGE_FILTER_TOLERANCE=2
RAG_AGE_FIT_WEIGHT=0.3

# 向量存储
VECTOR_STORE_TYPE=chroma
```

### A.3 常用命令

```bash
# 启动后端服务
cd backend
poetry run uvicorn src.main:app --reload

# 运行测试
cd backend
poetry run pytest tests/test_rag_*.py -v

# 查看日志
tail -f logs/app.log

# 导入文档
curl -X POST http://localhost:8000/api/upload \
  -F "file=@/path/to/book.pdf"
```

---

##### 附录 B: 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| v2.0 | 2026-04-02 | PageIndex 混合架构实现：QueryRouter、PageIndexWrapper、ResultFusion、DynamicAgeFilter |
| v1.0 | 2026-04-02 | 初始版本，完整记录 RAG 系统架构 |

---

## 总结

本 RAG 系统是一个**生产就绪**的儿童发展领域知识检索引擎，具有以下核心优势：

1. **高精度检索**: BM25 + Vector + Reranking 三级检索架构
2. **年龄适配**: 专为儿童发展领域设计的年龄过滤和加权机制
3. **工程化完善**: 断点续传、原子持久化、缓存、监控
4. **可扩展性**: 多向量存储支持、插件化架构
5. **中文优化**: jieba 分词、自定义词典、阿里云 DashScope
6. **混合推理架构 (规划中)**: PageIndex 集成，支持复杂多步查询

### 当前系统架构

**已实现的核心功能**:
- ✅ 混合检索（BM25 + 向量）
- ✅ Cross-Encoder 重排序
- ✅ 年龄适配机制（动态年龄过滤器，4 个发展阶段）
- ✅ 智能文档导入（含 OCR）
- ✅ 内容审核
- ✅ 缓存优化（动态 TTL、防穿透/击穿/雪崩）
- ✅ A/B 测试框架
- ✅ PageIndex 混合架构（查询路由器、熔断器、结果融合）
- ✅ 查询分类（规则 +LLM 双模式，支持复杂查询推理）

### 后续开发建议

**短期优先级 (P0)**:
1. 完成 PageIndex 混合架构实现
2. 建立性能监控和告警系统
3. 自动化评估基准测试

**中期优先级 (P1)**:
1. 用户反馈闭环优化
2. Redis 分布式缓存集成
3. 索引质量优化（低质量块识别和清理）

**长期愿景 (P2)**:
1. 多模态检索能力
2. 自动化知识图谱构建
3. 个性化检索优化

---

**文档维护者**: AI Development Team  
**联系方式**: [内部联系方式]  
**反馈渠道**: [Issue Tracker / Email]
