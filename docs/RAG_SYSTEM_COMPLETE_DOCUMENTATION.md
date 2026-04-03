# RAG 系统完整技术文档

> 本文档详细记录儿童发展评估 Agent 中 RAG（检索增强生成）系统的完整架构、每一块逻辑、每一个配置的使用方式。

---

## 目录

1. [系统架构概览](#1-系统架构概览)
2. [核心数据流](#2-核心数据流)
3. [文档解析层](#3-文档解析层)
4. [分块策略与元数据提取](#4-分块策略与元数据提取)
5. [索引管理与向量存储](#5-索引管理与向量存储)
6. [检索服务](#6-检索服务)
7. [高级检索功能](#7-高级检索功能)
8. [RAG 门面服务](#8-rag-门面服务)
9. [API 控制器](#9-api-控制器)
10. [配置系统完整说明](#10-配置系统完整说明)
11. [技术栈清单](#11-技术栈清单)

---

## 1. 系统架构概览

### 1.1 整体架构

RAG 系统采用**分层架构**，由以下核心模块组成：

```
┌─────────────────────────────────────────────────────────────────┐
│                        API 控制器层                               │
│              rag_controller.py (FastAPI Router)                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      RAG 门面服务层                               │
│                  rag_service.py (RagService)                     │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ QueryRouter  │  │PageIndexWrapper  │  │  ResultFusion    │  │
│  └──────────────┘  └──────────────────┘  └──────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      检索服务层                                   │
│             retrieval_service.py (RetrievalService)              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │  Cache   │ │  Query   │ │   Age    │ │  Content         │   │
│  │ Service  │ │  Rewrite │ │  Filter  │ │  Deduplication   │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      混合检索层                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  BM25 Retriever  │  │ Vector Retriever │  │  Reranker    │  │
│  │  (jieba 分词)     │  │  (Chroma)        │  │(Cross-Encoder)│  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────┬───────┘  │
│           └─────────────────────┼────────────────────┘           │
│                    ┌────────────▼────────────┐                   │
│                    │  HybridRetrievalMerger  │                   │
│                    └─────────────────────────┘                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      索引管理层                                   │
│           index_manager_service.py (IndexManagerService)         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  VectorStore     │  │   DocStore       │  │  Auto        │  │
│  │  Factory         │  │   Manager        │  │  Persist     │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      文档导入层                                   │
│       document_ingestion_service.py (DocumentIngestionService)   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │  Parser  │ │ Chunking │ │ Metadata │ │  Resumable       │   │
│  │  Service │ │ Service  │ │ Extract  │ │  Import          │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 两大核心流水线

RAG 系统包含两条独立的流水线：

**流水线 A：文档导入流水线（Ingestion Pipeline）**
```
用户上传 PDF/EPUB → 文档解析 → 智能分块 → 元数据提取 → 向量 Embedding → 索引插入 → 持久化存储
```

**流水线 B：知识检索流水线（Retrieval Pipeline）**
```
用户查询 → 查询路由 → 缓存检查 → 查询重写 → 同义词扩展 → 混合检索(BM25+Vector) → 结果融合 → Cross-Encoder 重排序 → 年龄过滤 → 内容去重 → 返回 KnowledgeItem
```

---

## 2. 核心数据流

### 2.1 文档导入数据流

```
用户上传 PDF/EPUB
    │
    ▼
[rag_controller.py] POST /rag/upload
    │
    ├── 生成 task_id (UUID)
    ├── 保存文件到临时目录 (./temp_uploads/)
    ├── 初始化任务状态 (pending)
    └── 后台异步执行 process_book_background()
            │
            ▼
[RagService.ingest_book()]
    │
    ├── 计算文件 MD5 哈希 (幂等性校验)
    ├── 检查文档是否已存在 (防止重复导入)
    ├── 注册文档到 DocumentManager
    │
    ▼
[DocumentIngestionService.ingest_book_resumable()]
    │
    ├── 加载或创建导入状态 (支持断点续传)
    ├── 阶段 1: 解析 (parsing)
    │       │
    │       ├── 检测是否为扫描版 PDF (OCR 检测)
    │       │       │
    │       │       ├── 检测逻辑: 文本提取率 < 50% 或 平均文本长度 < 100
    │       │       └── 检测配置: settings.rag_ocr_extraction_rate_threshold
    │       │                   settings.rag_ocr_min_avg_length_threshold
    │       │
    │       ├── 扫描版 → PDFVLParser (Qwen-VL 多模态 OCR)
    │       │       │
    │       │       ├── 使用 fitz.Matrix(1.0, 1.0) 渲染页面为图片
    │       │       ├── 调用 dashscope.MultiModalConversation (qwen3-omni-flash)
    │       │       ├── ThreadPoolExecutor 并行处理 (rag_vl_max_workers=2)
    │       │       └── 每页生成临时 PNG → VL 解析 → 删除临时文件
    │       │
    │       └── 非扫描版 → PDFParserV2 (三级降级)
    │               │
    │               ├── 第一级: VLM 解析 (PDFVLParser)
    │               ├── 第二级: 传统文本提取 (PDFParser - PyMuPDF)
    │               └── 内容校验: _is_content_valid() 检查平均长度和乱码比例
    │
    ├── 阶段 2: 分块 (chunking)
    │       │
    │       ├── EPUB/带书签 PDF → split_chapters_into_chunks()
    │       │       │
    │       │       ├── 预切分: 按章节内容长度切分超长章节
    │       │       │       └── 阈值: epub_chapter_split_threshold = 3000
    │       │       │
    │       │       ├── 语义分块: get_semantic_splitter()
    │       │       │       │
    │       │       │       ├── 语言检测: detect_language() (中/英文字母占比 > 70%)
    │       │       │       ├── 中文配置: buffer_size=5, breakpoint_threshold=90
    │       │       │       ├── 英文配置: buffer_size=3, breakpoint_threshold=75
    │       │       │       └── 分隔符: ["\n## ", "\n### ", "\n#### ", "\n\n", "\n",
    │       │       │                   "。", "！", "？", ". ", "! ", "? "]
    │       │       │
    │       │       └── 合并相邻小块 + 二次细分
    │       │               ├── 合并阈值: min_chunk_size = 200
    │       │               └── 细分阈值: max_chunk_size = 2000
    │       │
    │       ├── 普通 PDF → split_pages_into_chunks()
    │       │       │
    │       │       ├── 语义分块 (同上)
    │       │       └── 降级: SentenceSplitter (chunk_size=1536, chunk_overlap=200)
    │       │
    │       └── 父子块策略 → hierarchical_chunking()
    │               │
    │               ├── 父块: 原始大块 (提供上下文)
    │               ├── 子块: 按段落分割的小块 (用于精确检索)
    │               └── 子块引用父块 ID 作为 parent_node
    │
    ├── 阶段 3: 元数据提取 (metadata_extraction)
    │       │
    │       ├── 标准模式: _process_nodes_standard()
    │       │       │
    │       │       ├── 每个节点调用 LLM 提取元数据
    │       │       ├── 并发数: rag_metadata_extraction_concurrency = 20
    │       │       └── 提取字段: topics, brain_regions, target_age_min/max,
    │       │           developmental_domains, difficulty_level
    │       │
    │       └── 分层模式: _process_nodes_hierarchical()
    │               │
    │               ├── 文档级元数据: 从第一个节点提取一次 (复用给所有节点)
    │               ├── 关键块识别: _identify_key_chunks()
    │               │       ├── 章节开头 (page_label == "1")
    │               │       ├── 内容突变处 (内容长度变化 > 50%)
    │               │       └── 均匀采样 (每 10 个块选 1 个)
    │               ├── 关键块: LLM 提取元数据
    │               ├── 普通块: 规则提取 (正则匹配年龄、领域标签映射)
    │               └── 性能提升: 约 80 倍 (相比标准模式)
    │
    ├── 阶段 4: 内容去重 (deduplication)
    │       │
    │       ├── 计算每个块的 content_hash (MD5)
    │       └── 跳过 content_hash 已存在的块
    │
    ├── 阶段 5: 索引插入 (indexing)
    │       │
    │       ├── IndexManagerService.insert_nodes()
    │       │       │
    │       │       ├── 初始化索引 (如未初始化)
    │       │       ├── 分批插入 (batch_size=100)
    │       │       └── 触发自动持久化
    │       │
    │       └── 分层内容生成 (可选)
    │               │
    │               ├── LayeredContentGenerator.generate_layers()
    │               ├── L0 摘要 (~100 字) + L1 概览 (~500 字) + L2 详情 (原始内容)
    │               └── 降级链: LLM → summa TextRank → 直接截断
    │
    └── 阶段 6: 完成 (completed)
            │
            ├── 保存导入状态
            ├── 清理临时文件
            └── 更新任务状态为 success
```

### 2.2 知识检索数据流

```
用户查询 (query + age)
    │
    ▼
[RagService.retrieve_knowledge(query, age, limit)]
    │
    ├── 步骤 1: 查询路由 (QueryRouter)
    │       │
    │       ├── LLM 分类: 简单查询 vs 复杂查询
    │       │       │
    │       │       ├── 简单查询: 事实性、定义性、单一概念
    │       │       ├── 复杂查询: 比较分析、多步骤、综合评估
    │       │       └── 模型: qwen3-omni-flash (MODEL_QUERY_CLASSIFICATION)
    │       │
    │       ├── 置信度阈值: query_router_confidence_threshold = 0.8
    │       ├── 重试机制: 最多 2 次 (query_router_llm_max_retries)
    │       └── 降级: 解析失败 → 默认复杂查询
    │
    ├── 步骤 2: 检索服务 (RetrievalService.retrieve_knowledge)
    │       │
    │       ├── 2.1 缓存检查 (CacheService)
    │       │       │
    │       │       ├── 缓存键: md5(query + age + limit)
    │       │       ├── 缓存容量: rag_cache_max_size = 1000
    │       │       ├── 缓存 TTL: rag_cache_ttl_seconds = 3600 (1 小时)
    │       │       └── 命中 → 直接返回缓存结果
    │       │
    │       ├── 2.2 查询重写 (可选)
    │       │       │
    │       │       ├── 触发条件: rag_query_rewrite_enabled = True
    │       │       ├── LLM 重写: DashScope (qwen3-omni-flash)
    │       │       └── 目标: 将自然语言转为更适合检索的关键词短语
    │       │
    │       ├── 2.3 同义词扩展
    │       │       │
    │       │       ├── LLM 生成同义词列表 (结构化 JSON 输出)
    │       │       ├── 质量验证: 过滤单字、过长词、非中文字符
    │       │       └── 扩展查询: 原始查询 + 同义词组合
    │       │
    │       ├── 2.4 年龄过滤器构建
    │       │       │
    │       │       ├── 根据 age 判断发展阶段:
    │       │       │       infant (0-1), toddler (1-3), preschool (3-6), school_age (6-12)
    │       │       ├── 各阶段配置:
    │       │       │       infant:     tolerance=1,  strictness=0.9, weight=0.5
    │       │       │       toddler:    tolerance=2,  strictness=0.8, weight=0.4
    │       │       │       preschool:  tolerance=2,  strictness=0.7, weight=0.3
    │       │       │       school_age: tolerance=3,  strictness=0.6, weight=0.25
    │       │       └── 构建 MetadataFilter: target_age_min/max 范围过滤
    │       │
    │       ├── 2.5 混合检索执行 (_execute_retrieval)
    │       │       │
    │       │       ├── BM25 检索 (并行)
    │       │       │       │
    │       │       │       ├── BM25Retriever (llama_index.retrievers.bm25)
    │       │       │       ├── 分词器: jieba (含自定义词典)
    │       │       │       ├── Top-K: rag_hybrid_bm25_top_k = 10
    │       │       │       └── 相似度函数: bm25_similarity (自定义)
    │       │       │
    │       │       ├── 向量检索 (并行)
    │       │       │       │
    │       │       │       ├── VectorRetriever (Chroma)
    │       │       │       ├── Embedding: DashScope text-embedding-v4
    │       │       │       ├── Top-K: rag_hybrid_vector_top_k = 10
    │       │       │       └── 相似度函数: chroma_similarity (余弦相似度)
    │       │       │
    │       │       └── 结果融合 (HybridRetrievalMerger)
    │       │               │
    │       │               ├── BM25 分数校准: Sigmoid 校准到 [0,1]
    │       │               │       └── scale_factor: bm25_scale_factor = 5
    │       │               │               score_calibrated = 1 / (1 + exp(-score * 5))
    │       │               │
    │       │               ├── 向量分数校准: 分段校准
    │       │               │       └── score >= 0.5: 0.5 + (score-0.5)*2*0.5
    │       │               │           score <  0.5: score * 0.5
    │       │               │
    │       │               ├── 动态权重计算 (基于查询特征)
    │       │               │       │
    │       │               │       ├── 关键词密度高 → BM25 权重 0.7
    │       │               │       ├── 语义查询 → BM25 权重 0.3
    │       │               │       └── 默认 → BM25 权重 0.5
    │       │               │
    │       │               ├── 加权融合: final_score = bm25_score * bm25_weight +
    │       │               │                      vector_score * (1 - bm25_weight)
    │       │               │
    │       │               ├── 全局归一化: _normalize_all_scores()
    │       │               └── 去重: 按 node_id 去重，保留最高分
    │       │
    │       ├── 2.6 Cross-Encoder 重排序
    │       │       │
    │       │       ├── 模型: BAAI/bge-reranker-v2-m3 (懒加载)
    │       │       ├── 初始候选: rag_reranker_initial_k = 30
    │       │       ├── 最终返回: rag_reranker_final_k = 5
    │       │       └── 流程: 粗检索 30 个 → Cross-Encoder 评分 → 返回 Top 5
    │       │
    │       ├── 2.7 转换为 KnowledgeItem
    │       │       │
    │       │       ├── 年龄适配度计算 (child_development_engine)
    │       │       ├── 内容去重 (精确匹配 + 包含关系 + difflib 相似度)
    │       │       └── 阈值过滤
    │       │
    │       └── 2.8 缓存结果
    │
    ├── 步骤 3: 复杂查询增强 (PageIndex + ResultFusion)
    │       │
    │       ├── 触发条件: query_type == "complex" 且 pageindex_enabled = True
    │       ├── PageIndex 检索: 外部知识图谱检索
    │       │       │
    │       │       ├── 熔断机制: 连续失败 5 次 → 熔断 60 秒
    │       │       ├── 重试机制: 最多 3 次，指数退避 (0.5s → 1s → 2s)
    │       │       └── 降级: 熔断/超时 → 回退到混合检索
    │       │
    │       └── 结果融合 (ResultFusion)
    │               │
    │               ├── 去重: 按内容哈希去重
    │               ├── 分数提升: PageIndex 结果 * 1.2
    │               ├── 混合补充: 最多补充 5 个混合检索结果
    │               └── 重新归一化
    │
    └── 返回 List[KnowledgeItem]
```

---

## 3. 文档解析层

### 3.1 解析器架构

文件: `backend/src/core/parsers.py`

系统提供 **4 种解析器**，通过工厂函数 `get_parser()` 根据文件扩展名自动选择：

| 解析器 | 适用格式 | 解析方式 | 说明 |
|--------|----------|----------|------|
| `PDFParser` | PDF | PyMuPDF 文本提取 | 传统文本提取，支持书签分割 |
| `PDFVLParser` | PDF | Qwen-VL 多模态 OCR | 扫描版 PDF 专用，逐页 OCR |
| `PDFParserV2` | PDF | 三级降级 | 默认 PDF 解析器，智能降级 |
| `EPUBParser` | EPUB | EbookLib + BeautifulSoup | 支持 TOC 层级结构 |

### 3.2 PDFParser - 传统 PDF 解析

**核心逻辑**:

1. **书签检测**: 调用 `fitz.open(file_path).get_toc()` 获取 PDF 目录
2. **书签处理** (有 TOC):
   - 过滤无效 TOC 条目 (页码不在 1~total_pages 范围内)
   - 构建层级标题路径: 维护 `level_path` 栈，按层级拼接完整标题
   - 计算每个书签的结束页: 查找下一个同级或更高级书签的起始页 - 1
   - 合并书签范围内所有页面文本，创建 Document
   - 元数据包含: `chapter_title`(完整层级标题), `section_title`(当前小节标题), `page_label`, `toc_level`
3. **逐页处理** (无 TOC):
   - 逐页提取文本，过滤空白页 (文本长度 < 10)
   - 元数据包含: `page_label`, `total_pages`

### 3.3 PDFVLParser - VLM OCR 解析

**核心逻辑**:

1. **页面渲染**: 使用 `fitz.Matrix(1.0, 1.0)` 将 PDF 页面渲染为 PNG 图片
2. **临时文件**: 每页生成临时 PNG 文件 (`tempfile.NamedTemporaryFile`)
3. **VL 调用**: 调用 `dashscope.MultiModalConversation.call()`
   - 模型: `settings.model_vl_parsing` (qwen3-omni-flash)
   - Prompt: "请提取这张图片中的所有文字内容，保持原有的段落结构..."
4. **并行处理**: `ThreadPoolExecutor(max_workers=rag_vl_max_workers)` 并行解析多页
5. **结果排序**: 按 `page_label` 排序，保证页面顺序
6. **资源清理**: 每页解析完成后删除临时 PNG 文件

### 3.4 PDFParserV2 - 三级降级解析器

**核心逻辑**:

```
PDFParserV2.parse(file_path)
    │
    ├── 降级顺序: [VLM, TEXT] (可配置)
    │
    ├── 第一级: VLM 解析 (_parse_with_vlm)
    │       │
    │       ├── 调用 PDFVLParser.parse()
    │       ├── 内容校验: _is_content_valid()
    │       │       ├── 平均内容长度 >= min_content_length (100)
    │       │       └── 乱码检测: 非 ASCII 比例 > 80% 且无中文字符 → 判定为乱码
    │       └── 校验通过 → 返回结果
    │
    ├── 第二级: 传统文本提取 (_parse_with_text)
    │       │
    │       ├── 调用 PDFParser.parse()
    │       └── 内容校验 (同上)
    │
    └── 所有解析失败 → 抛出 PDFParseError
```

**异常处理策略**:
- `PDFCorruptedError`: PDF 文件本身损坏 → 直接抛出，不降级
- `ParserServiceError`: 解析服务不可用 → 记录警告，继续降级
- 其他异常: 记录警告，继续降级

### 3.5 EPUBParser - EPUB 解析

**核心逻辑**:

1. **TOC 检测**: 检查 `book.toc` 是否存在
2. **TOC 处理** (有 TOC):
   - 递归遍历 TOC 树 (`_traverse_toc`)
   - 支持两种 TOC 节点类型:
     - `epub.Link`: 叶子节点 (章节链接)
     - `tuple(Link, [children])`: 父节点 (包含子章节)
   - 构建完整层级标题路径 (与 PDF 书签处理类似)
   - 通过 `item.get_name()` 匹配 href 获取内容
3. **逐 Item 处理** (无 TOC):
   - 遍历所有 `ITEM_DOCUMENT` 类型
   - 尝试从 `<h1>`, `<h2>`, `<title>` 提取章节标题

---

## 4. 分块策略与元数据提取

### 4.1 分块策略总览

文件: `backend/src/core/metadata_processor.py`

系统提供 **3 种分块策略**，根据文档类型自动选择：

| 策略 | 适用场景 | 核心方法 |
|------|----------|----------|
| 章节级分块 | EPUB / 带书签 PDF | `split_chapters_into_chunks()` |
| 页面级分块 | 普通 PDF (无书签) | `split_pages_into_chunks()` |
| 父子块分块 | 需要上下文关联 | `hierarchical_chunking()` |

### 4.2 语义分块器 (Semantic Splitter)

**语言检测逻辑** (`detect_language`):
```python
# 中文字符占比
chinese_ratio = len(re.findall(r'[\u4e00-\u9fa5]', text)) / len(text)
# 英文字母占比
english_ratio = len(re.findall(r'[a-zA-Z]', text)) / len(text)
# 中文字母占比 > 70% → 中文，否则 → 英文
```

**中文分块配置**:
- `buffer_size`: 5 (比较前后 5 段落的语义变化)
- `breakpoint_threshold`: 90 (语义相似度 < 90% 时分割)
- `chunk_size`: 1024
- `chunk_overlap`: 200

**英文分块配置**:
- `buffer_size`: 3
- `breakpoint_threshold`: 75
- `chunk_size`: 1024
- `chunk_overlap`: 200

**长章节分块配置** (用于 `get_chapter_splitter`):
- `buffer_size`: 3 (`semantic_splitter_chapter_buffer_size`)
- `breakpoint_threshold`: 75 (`semantic_splitter_chapter_breakpoint_threshold`)

**分隔符优先级** (`semantic_splitter_separators`):
```
1. "\n## "     → 二级标题
2. "\n### "    → 三级标题
3. "\n#### "   → 四级标题
4. "\n\n"      → 段落边界
5. "\n"        → 换行边界
6. "。" "！" "？" → 中文句子结束
7. ". " "! " "? "  → 英文句子结束
```

### 4.3 章节级分块 (`split_chapters_into_chunks`)

**处理流程**:

1. **预切分超长章节**:
   - 检测条件: 章节内容长度 > `epub_chapter_split_threshold` (3000)
   - 切分方法: 使用 `get_chapter_splitter()` (长章节优化分块器)
   - 目标: 避免单个章节过大导致语义分块效果差

2. **语义分块**:
   - 调用 `get_semantic_splitter(content_text)` 获取分块器
   - 使用 `SemanticSplitterNodeParser` 进行语义感知分块

3. **合并相邻小块**:
   - 遍历分块结果
   - 如果当前块大小 < `min_chunk_size` (200)，尝试与下一个块合并
   - 合并后大小 <= `max_chunk_size` (2000) 则合并，否则保留当前块

4. **二次细分**:
   - 对合并后仍超过 `max_chunk_size` (2000) 的块
   - 使用 `SentenceSplitter` 进行规则细分

### 4.4 页面级分块 (`split_pages_into_chunks`)

**处理流程**:

1. 尝试语义分块 (`get_semantic_splitter`)
2. 如果语义分块失败或返回空结果 → 降级为 `SentenceSplitter`
   - `chunk_size`: `rag_pdf_chunk_size` (1536)
   - `chunk_overlap`: `rag_chunk_overlap` (200)

### 4.5 父子块分块 (`hierarchical_chunking`)

**设计目的**: 同时支持上下文感知和精确检索

**处理流程**:

1. **父块创建**: 原始大块作为父块，保留完整上下文
2. **子块分割**: 按段落 (`\n\n`) 分割父块为子块
3. **关联建立**: 子块的 `parent_node` 字段指向父块 ID
4. **过滤**: 子块文本长度 < 50 的块被过滤掉

**检索时的使用**:
- 检索阶段使用子块 (精确匹配)
- 返回结果时可通过 `parent_node` 获取父块上下文

### 4.6 元数据提取

文件: `backend/src/core/metadata_processor.py`

系统提供 **2 种元数据提取模式**:

#### 标准模式 (`_process_nodes_standard`)

**适用场景**: 节点数量较少，需要高精度元数据

**处理流程**:
1. 对每个节点调用 LLM 提取元数据
2. 并发数: `rag_metadata_extraction_concurrency` (20)
3. 提取字段:
   - `topics`: 主题关键词列表
   - `brain_regions`: 脑区/发展领域
   - `target_age_min`: 目标年龄下限
   - `target_age_max`: 目标年龄上限
   - `developmental_domains`: 发展领域标签
   - `difficulty_level`: 难度等级 (easy/medium/hard)

#### 分层模式 (`_process_nodes_hierarchical`)

**适用场景**: 节点数量较多，需要高性能元数据提取

**性能提升**: 约 80 倍 (相比标准模式)

**处理流程**:

1. **文档级元数据提取**:
   - 仅从第一个节点提取一次
   - 复用给所有节点 (避免重复 LLM 调用)

2. **关键块识别** (`_identify_key_chunks`):
   - 章节开头: `page_label == "1"`
   - 内容突变处: 当前块长度与前一块长度差异 > 50%
   - 均匀采样: 每 10 个块选 1 个

3. **关键块 LLM 提取**:
   - 对识别出的关键块调用 LLM 提取元数据

4. **普通块规则提取**:
   - 复用文档级元数据
   - 年龄提取: 正则匹配 (`rule_metadata_age_patterns`)
     - `(\d+)~(\d+)个月`, `(\d+)-(\d+)个月`, `适合(\d+)到(\d+)岁`
     - `(\d+)岁左右`, `(\d+)月龄`, `(\d+)岁`
   - 领域标签: 关键词匹配 (`rule_metadata_development_domains`)
     - 粗大动作, 精细动作, 认知能力, 语言发展, 社交情感, 感觉统合
   - 难度等级: 基于内容长度
     - < `rule_metadata_difficulty_easy_threshold` (300) → easy
     - > `rule_metadata_difficulty_hard_threshold` (1000) → hard
     - 其他 → medium

### 4.7 内容去重

**去重策略**:
1. 计算每个块的 `content_hash` (MD5)
2. 检查 `content_hash` 是否已存在于 `existing_hashes` 集合
3. 已存在 → 跳过该块
4. 不存在 → 加入集合，保留该块

---

## 5. 索引管理与向量存储

### 5.1 IndexManagerService

文件: `backend/src/service/index_manager_service.py`

**核心职责**: 向量索引的生命周期管理

#### 5.1.1 索引初始化 (`_initialize_index`)

**初始化流程**:

1. **检查已有索引**:
   - 检查 `storage_dir` 下是否存在 `docstore.json`
   - 存在 → 调用 `_load_index()` 加载

2. **加载失败处理**:
   - 尝试从备份目录 (`backup/`) 恢复
   - 备份恢复失败 → 删除损坏索引，创建新索引

3. **创建新索引**:
   - 调用 `_create_index()` 创建空的 `VectorStoreIndex`
   - 配置: `Settings.embed_model` (SafeDashScopeEmbedding)

4. **重试机制**:
   - 最多重试 3 次，间隔 2 秒
   - 重试失败 → 抛出异常

#### 5.1.2 节点插入 (`insert_nodes`)

**插入流程**:

1. **索引检查**: 如未初始化，自动调用 `_initialize_index()`
2. **分批插入**:
   - 批次大小: 100
   - 每批插入后调用 `progress_callback` 报告进度
3. **自动持久化**: 插入完成后触发 `_trigger_auto_persist()`

#### 5.1.3 文档删除 (`delete_document`)

**删除流程**:

1. 从 `docstore` 获取所有节点
2. 筛选 `file_name` 匹配的节点
3. 调用 `index.delete_node(node_id)` 逐个删除
4. 调用 `_persist_index()` 持久化删除

#### 5.1.4 自动持久化 (`_start_auto_persist`)

**工作机制**:

1. **触发条件**:
   - `rag_auto_persist_enabled` = True
   - 距离上次持久化时间 >= `rag_auto_persist_interval` (300 秒)

2. **后台线程**:
   - 使用 `threading.Thread` 运行后台持久化
   - 工作线程: `_auto_persist_worker()`
   - 检查间隔: 60 秒

3. **持久化流程** (`_persist_index`):
   - 创建临时目录 (`temp_persist/`)
   - 写入 `docstore.json` 到临时目录
   - 备份当前索引到 `backup/` 目录
   - 原子替换: 删除旧索引 → 移动临时目录到正式目录
   - 清理备份 (保留最近 3 个)

#### 5.1.5 分块查询 API

**`get_document_chunks(file_hash, page, page_size)`**:
- 从 `docstore` 获取所有节点
- 筛选 `file_hash` 匹配的节点
- 分页返回 (支持 page, page_size 参数)
- 返回字段: `chunk_id`, `content`, `metadata`, `score`

**`get_chunk_detail(chunk_id)`**:
- 从 `docstore` 获取指定节点
- 返回完整节点信息

### 5.2 VectorStoreFactory

文件: `backend/src/core/vector_store_factory.py`

**支持的向量存储**:

| 类型 | 类 | 说明 |
|------|-----|------|
| chroma | `ChromaVectorStore` | 默认，本地持久化 |
| pinecone | `PineconeVectorStore` | 云端向量存储 |
| milvus | `MilvusVectorStore` | 高性能向量数据库 |
| weaviate | `WeaviateVectorStore` | 多模态向量数据库 |

**当前配置** (Chroma):
```python
ChromaVectorStore.from_params(
    persist_dir="./storage/chroma_db",
    collection_name="child_development",
)
```

### 5.3 SafeDashScopeEmbedding

文件: `backend/src/core/embedding.py`

**安全特性**:

1. **空文本处理**: 空字符串替换为占位符 `"[EMPTY]"`
2. **超长截断**: 文本长度 > `embedding_max_text_length` (1536) 时截断
3. **指数退避重试**:
   - 最多重试 3 次
   - 退避时间: `2^retry_count * 1` 秒 (1s → 2s → 4s)
4. **空 Embedding 检测**: 检测全零或接近全零的 Embedding 向量
5. **同步/异步双版本**: `get_text_embedding()` + `aget_text_embedding()`

---

## 6. 检索服务

### 6.1 RetrievalService

文件: `backend/src/service/retrieval_service.py`

**核心检索流程** (`retrieve_knowledge`):

```
retrieve_knowledge(query, age, limit, user_id)
    │
    ├── 1. 缓存检查
    │       └── cache_service.get_cached_result(cache_key)
    │
    ├── 2. 查询重写 (可选)
    │       └── _rewrite_query(query, age)
    │
    ├── 3. 同义词扩展
    │       └── _expand_synonyms(query)
    │
    ├── 4. 年龄过滤器构建
    │       └── _build_age_filters(age)
    │
    ├── 5. 混合检索执行
    │       └── _execute_retrieval(query, age, limit, filters, user_id)
    │
    ├── 6. 重排序
    │       └── reranker.rerank(query, nodes)
    │
    ├── 7. 转换为 KnowledgeItem
    │       └── _convert_to_knowledge_items(nodes, user_age)
    │
    └── 8. 缓存结果
            └── cache_service.cache_result(cache_key, result)
```

### 6.2 查询重写 (`_rewrite_query`)

**触发条件**: `rag_query_rewrite_enabled` = True

**重写逻辑**:
1. 构建 Prompt: 将自然语言查询转为关键词短语
2. 调用 LLM: `DashScope.acomplete()` (qwen3-omni-flash)
3. 解析响应: 提取重写后的查询
4. 降级: LLM 失败 → 使用原始查询

### 6.3 同义词扩展 (`_expand_synonyms`)

**扩展逻辑**:

1. **LLM 生成**:
   - Prompt: 要求 LLM 返回 JSON 格式的同义词列表
   - 输出格式: `{"synonyms": ["词1", "词2", ...]}`

2. **质量验证**:
   - 过滤单字词 (长度 < 2)
   - 过滤过长词 (长度 > 10)
   - 过滤非中文字符为主的词

3. **查询扩展**:
   - 原始查询 + 同义词组合
   - 用于 BM25 和向量检索

### 6.4 混合检索执行 (`_execute_retrieval`)

**并行检索**:

```python
# BM25 和向量检索并行执行
bm25_task = bm25_retriever.aretrieve(query)
vector_task = vector_retriever.aretrieve(query)
bm25_nodes, vector_nodes = await asyncio.gather(bm25_task, vector_task)
```

**BM25 检索**:
- 使用 `BM25Retriever` (llama_index)
- 分词器: jieba
- Top-K: `rag_hybrid_bm25_top_k` (10)

**向量检索**:
- 使用 `VectorRetriever` (Chroma)
- Embedding: DashScope text-embedding-v4
- Top-K: `rag_hybrid_vector_top_k` (10)

**结果融合**:
- 调用 `HybridRetrievalMerger.merge_results()`
- 详见 [7.1 混合检索融合](#71-混合检索融合)

### 6.5 内容去重 (`_is_content_duplicate`)

**去重策略** (三级):

1. **精确匹配**: `content1 == content2`
2. **包含关系**: `content1 in content2` 或 `content2 in content1`
3. **相似度匹配**: `difflib.SequenceMatcher.ratio()` > 0.85

### 6.6 搜索页面专用检索 (`search_content`)

**与知识检索的区别**:

| 特性 | 知识检索 | 搜索页面检索 |
|------|----------|--------------|
| 初始候选 | 10 + 10 | `rag_reranker_initial_k` (30) |
| 重排序 | 是 | 是 |
| 年龄过滤 | 是 | 否 |
| 融合策略 | 标准融合 | 搜索专用融合 (`merge_for_search`) |
| 阈值 | 标准阈值 | 搜索专用阈值 |
| 纯向量惩罚 | 无 | 有 (`no_match_vector_penalty`) |

---

## 7. 高级检索功能

### 7.1 混合检索融合

文件: `backend/src/core/hybrid_retrieval.py`

#### 7.1.1 BM25 分数校准

**Sigmoid 校准**:
```python
def _calibrate_bm25_score(score):
    scale_factor = 5  # bm25_scale_factor
    return 1 / (1 + math.exp(-score * scale_factor))
```

**效果**: 将 BM25 原始分数 (可能为负数或大于 1) 映射到 [0, 1] 区间

#### 7.1.2 向量分数校准

**分段校准**:
```python
def _calibrate_vector_score(score):
    if score >= 0.5:
        return 0.5 + (score - 0.5) * 2 * 0.5  # 映射到 [0.5, 1.0]
    else:
        return score * 0.5  # 映射到 [0, 0.25]
```

#### 7.1.3 动态权重计算

**查询特征分析**:
```python
def get_dynamic_weights(query, age):
    # 关键词密度: 中文字符数 / 总字符数
    keyword_density = len(re.findall(r'[\u4e00-\u9fa5]', query)) / len(query)
    
    if keyword_density > 0.5:
        return "keyword_query"  # BM25 权重 0.7
    elif keyword_density < 0.2:
        return "semantic_query"  # BM25 权重 0.3
    else:
        return "default"  # BM25 权重 0.5
```

#### 7.1.4 融合算法

```
merge_results(bm25_nodes, vector_nodes, query, age)
    │
    ├── 1. 分数校准
    │       ├── BM25: Sigmoid 校准
    │       └── Vector: 分段校准
    │
    ├── 2. 动态权重计算
    │       └── 基于查询关键词密度
    │
    ├── 3. 加权融合
    │       └── final_score = bm25_score * bm25_weight + vector_score * (1 - bm25_weight)
    │
    ├── 4. 全局归一化
    │       └── score = score / max_score (归一化到 [0, 1])
    │
    └── 5. 去重排序
            └── 按 node_id 去重，保留最高分，按分数降序
```

#### 7.1.5 搜索专用融合 (`merge_for_search`)

**与标准融合的区别**:

1. **纯向量惩罚**:
   ```python
   if node_id not in bm25_scores:
       score *= (1 - no_match_vector_penalty)  # 默认惩罚 50%
   ```

2. **阈值过滤**:
   - 混合模式阈值: `rag_search_score_threshold_hybrid` (0.35)
   - 向量模式阈值: `rag_search_score_threshold_vector` (0.35)

3. **相对截断**:
   - 保留 Top 50% 的结果 (`rag_search_relative_cutoff_ratio` = 0.5)

### 7.2 Cross-Encoder 重排序

文件: `backend/src/core/reranker.py`

**模型**: `BAAI/bge-reranker-v2-m3` (sentence-transformers)

**懒加载机制**:
```python
def _load_model(self):
    if self._model is None:
        self._model = CrossEncoder(self.model_name)
```

**重排序流程**:
1. 取前 `rag_reranker_initial_k` (30) 个候选
2. 构建 `(query, node_content)` 对列表
3. 调用 `CrossEncoder.predict()` 获取相关性分数
4. 按新分数排序，返回 Top `rag_reranker_final_k` (5)

### 7.3 查询路由器 (QueryRouter)

文件: `backend/src/core/query_router.py`

**分类逻辑**:

1. **LLM 分类**:
   - 模型: `qwen3-omni-flash`
   - 输出格式: `{"query_type": "simple/complex", "confidence": 0.9, "reason": "..."}`
   - 简单查询: 事实性、定义性、单一概念
   - 复杂查询: 比较分析、多步骤、综合评估

2. **置信度检查**:
   - 置信度 >= `query_router_confidence_threshold` (0.8) → 接受分类
   - 置信度 < 阈值 → 默认复杂查询 (保守策略)

3. **重试机制**:
   - 最多重试 `query_router_llm_max_retries` (2) 次
   - JSON 解析失败 → 重试

### 7.4 PageIndex 包装器

文件: `backend/src/core/pageindex_wrapper.py`

**功能**: 集成 PageIndex 外部知识图谱检索

**熔断机制**:
```python
# 连续失败 5 次 → 熔断 60 秒
failure_threshold = 5
reset_timeout = 60
```

**重试机制**:
- 最多重试 3 次
- 指数退避: 0.5s → 1s → 2s
- 最大延迟: 10 秒

**降级策略**:
- 熔断触发 → 回退到混合检索
- 超时 → 回退到混合检索
- 配置: `pageindex_fallback_to_hybrid` = True

### 7.5 结果融合器 (ResultFusion)

文件: `backend/src/core/result_fusion.py`

**融合策略**:

1. **去重**: 按内容哈希去重
2. **分数提升**: PageIndex 结果分数 * `fusion_score_boost_for_pageindex` (1.2)
3. **混合补充**: 从混合检索结果中补充最多 `fusion_hybrid_supplement_limit` (5) 个
4. **重新归一化**: `fusion_dedup_normalize` = True

### 7.6 动态年龄过滤器

文件: `backend/src/core/age_filter.py`

**发展阶段划分**:

| 阶段 | 年龄范围 | tolerance | strictness | weight |
|------|----------|-----------|------------|--------|
| 婴儿期 (INFANT) | 0-1 岁 | 1 | 0.9 | 0.5 |
| 幼儿期 (TODDLER) | 1-3 岁 | 2 | 0.8 | 0.4 |
| 学龄前 (PRESCHOOL) | 3-6 岁 | 2 | 0.7 | 0.3 |
| 学龄期 (SCHOOL_AGE) | 6-12 岁 | 3 | 0.6 | 0.25 |

**年龄过滤构建**:
```python
filters = MetadataFilters(
    filters=[
        MetadataFilter(key="target_age_min", value=max_age, operator=LTE),
        MetadataFilter(key="target_age_max", value=min_age, operator=GTE),
    ]
)
# min_age = max(0, age - tolerance)
# max_age = age + tolerance
```

**年龄适配度计算**:
```python
def calculate_age_fit_score(age, target_min, target_max):
    if target_min <= age <= target_max:
        return 1.0  # 完全适配
    
    diff = target_min - age if age < target_min else age - target_max
    base_score = max(0.5, 1 - diff * 0.1 * strictness)
    return base_score
```

### 7.7 缓存服务

文件: `backend/src/service/cache_service.py`

**缓存策略**:

1. **缓存键**: `md5(query + age + limit)`
2. **缓存容量**: `rag_cache_max_size` (1000)
3. **缓存 TTL**: `rag_cache_ttl_seconds` (3600 秒 = 1 小时)
4. **淘汰策略**: LRU (超过容量时删除最久未使用的条目)

**缓存数据结构**:
```python
{
    cache_key: {
        "result": [...],      # 缓存的检索结果
        "timestamp": time.time(),  # 缓存时间戳
        "access_count": 0,    # 访问计数
    }
}
```

### 7.8 分层内容生成器

文件: `backend/src/core/layered_content_generator.py`

**三层结构**:

| 层级 | 名称 | 最大长度 | 生成方式 |
|------|------|----------|----------|
| L0 | 摘要 | 100 字 | LLM → summa TextRank → 直接截断 |
| L1 | 概览 | 500 字 | LLM → summa TextRank → 直接截断 |
| L2 | 详情 | 原始内容 | 直接使用原始内容 |

**批量生成策略**:

1. **动态批次大小**:
   - 节点数 > `large_batch_threshold` (1000) → `large_batch_size` (10)
   - 否则 → `batch_size` (20)

2. **LLM 批量调用**:
   - 将多个内容合并到一个 Prompt
   - 格式: `内容1：...\n内容2：...\n...`
   - 解析响应: 按 `---` 分隔符拆分

3. **降级为并发调用**:
   - 批量调用失败 → 并发单个调用
   - 并发限制: `concurrency_limit` (8)
   - 合并 L0+L1 到一个调用 (减少一半 API 次数)

4. **本地兜底**:
   - summa TextRank 摘要
   - 最终兜底: 直接截断

### 7.9 上下文压缩器

文件: `backend/src/core/context_compressor.py`

**压缩流程**:

```
compress(nodes, query)
    │
    ├── 1. 相关性过滤
    │       └── 过滤 score < relevance_threshold (0.3) 的节点
    │
    ├── 2. 语义去重
    │       └── Jaccard 相似度 > similarity_threshold (0.9) 视为重复
    │
    └── 3. Token 预算控制
            └── 按分数排序，优先保留高相关度节点
                直到总 Token 数 <= max_tokens (4000)
```

**Token 估算**:
- 中文字符: 每个约 1.5 token
- 英文单词: 每个约 1.3 token
- 其他字符: 每个约 0.5 token

---

## 8. RAG 门面服务

### 8.1 RagService

文件: `backend/src/service/rag_service.py`

**核心职责**: 作为 RAG 系统的统一入口，聚合所有子服务

**依赖注入**:
```python
RagService(
    index_manager: IndexManagerService,
    retrieval_service: RetrievalService,
    document_manager: DocumentManager,
    ingestion_service: DocumentIngestionService,
    query_router: QueryRouter,
    pageindex_wrapper: PageIndexWrapper,
    result_fusion: ResultFusion,
)
```

**核心方法**:

#### `retrieve_knowledge(query, age, limit)`

**知识检索入口**:

```python
async def retrieve_knowledge(query, age, limit):
    # 1. 查询路由
    query_type, confidence = await query_router.classify_query(query)
    
    # 2. 基础检索
    if query_type == "simple":
        results = await retrieval_service.retrieve_knowledge(query, age, limit)
    else:
        # 复杂查询: 基础检索 + PageIndex 增强
        base_results = await retrieval_service.retrieve_knowledge(query, age, limit)
        pageindex_results = await pageindex_wrapper.search(query, age, limit)
        results = result_fusion.fuse(base_results, pageindex_results)
    
    return results
```

#### `ingest_book(file_path, ...)`

**文档导入入口**:

```python
async def ingest_book(file_path, original_filename, progress_callback):
    # 1. 计算文件哈希
    file_hash = calculate_file_hash(file_path)
    
    # 2. 检查重复
    if document_manager.document_exists(file_hash):
        raise ValueError("文档已存在")
    
    # 3. 注册文档
    document_manager.register_document(file_hash, original_filename)
    
    # 4. 执行导入
    await ingestion_service.ingest_book_resumable(
        file_path, original_filename, file_hash, progress_callback
    )
```

#### `delete_document(file_name)`

**文档删除**:

```python
def delete_document(file_name):
    # 1. 从索引中删除
    index_manager.delete_document(file_name)
    # 2. 从文档管理器中删除
    document_manager.remove_document(file_name)
```

#### `search_content(query, limit)`

**搜索页面专用检索**:

```python
async def search_content(query, limit):
    return await retrieval_service.search_content(query, limit)
```

#### `get_document_chunks(file_hash, page, page_size)`

**获取分块列表**:

```python
def get_document_chunks(file_hash, page, page_size):
    return index_manager.get_document_chunks(file_hash, page, page_size)
```

#### `get_chunk_detail(chunk_id)`

**获取分块详情**:

```python
def get_chunk_detail(chunk_id):
    return index_manager.get_chunk_detail(chunk_id)
```

---

## 9. API 控制器

### 9.1 路由概览

文件: `backend/src/controller/rag_controller.py`

**路由前缀**: `/rag`

### 9.2 端点详细说明

#### `POST /rag/upload`

**功能**: 上传 PDF/EPUB 并后台索引

**请求**:
- Content-Type: `multipart/form-data`
- 参数: `file` (UploadFile)

**响应**:
```json
{
    "status": "accepted",
    "task_id": "uuid-string",
    "filename": "example.pdf",
    "message": "文件已上传，正在后台处理中，可通过任务ID查询处理状态"
}
```

**处理流程**:
1. 验证文件扩展名 (.pdf / .epub)
2. 生成唯一文件名 (UUID)
3. 保存到临时目录 (`./temp_uploads/`)
4. 生成 task_id
5. 初始化任务状态 (pending)
6. 添加到后台任务队列 (`BackgroundTasks`)
7. 后台执行 `process_book_background()`

**并发控制**:
- 使用 `asyncio.Semaphore(MAX_CONCURRENT_TASKS)` 限制并发数
- `MAX_CONCURRENT_TASKS` = `rag_upload_max_concurrent_tasks` (5)

**任务状态流转**:
```
pending → processing → success/failed/cancelled
```

**任务状态字段**:
- `status`: pending / processing / success / failed / cancelled
- `stage`: pending / parsing / chunking / embedding / indexing / completed
- `progress`: 0.0 ~ 100.0
- `message`: 人类可读的状态描述

#### `POST /rag/tasks/{task_id}/cancel`

**功能**: 取消正在进行的上传任务

**处理流程**:
1. 检查任务是否存在
2. 检查任务状态 (success/failed/cancelled 无需取消)
3. 标记为 cancelled
4. 后台任务检测到 cancelled 后中断并清理

#### `GET /rag/tasks`

**功能**: 列出所有上传任务

**响应**: 按创建时间倒序排列的任务列表

#### `GET /rag/tasks/{task_id}`

**功能**: 查询单个任务状态

**响应**: 包含 task_id, status, filename, progress, stage, message 等字段

#### `GET /rag/status`

**功能**: 获取 RAG 服务状态

**响应**:
```json
{
    "index_ready": true,
    "storage_dir": "/absolute/path/to/storage",
    "document_count": 5
}
```

**索引就绪条件**:
- `docstore.json` 存在
- 至少有一个已索引文档

#### `DELETE /rag/documents/{filename}`

**功能**: 删除文档及其索引

**处理流程**:
1. 调用 `rag_service.delete_document(filename)`
2. 清理相关的导入任务状态文件
3. 返回删除结果

#### `GET /rag/documents`

**功能**: 列出所有已索引文档

**响应**:
```json
{
    "documents": [
        {
            "file_hash": "md5-hash",
            "file_name": "example.pdf",
            "uploaded_at": "2024-01-01T00:00:00",
            "total_pages": 100
        }
    ]
}
```

#### `GET /rag/search?query=&limit=`

**功能**: 搜索知识库内容

**参数**:
- `query`: 搜索关键词 (必填)
- `limit`: 返回结果数量 (1-100, 默认 20)

**响应**:
```json
{
    "status": "success",
    "total": 10,
    "results": [...]
}
```

#### `GET /rag/documents/{file_hash}/chunks`

**功能**: 获取文档分块列表 (分页)

**参数**:
- `file_hash`: 文档哈希
- `page`: 页码 (从 1 开始, 默认 1)
- `page_size`: 每页数量 (1-100, 默认 20)

#### `GET /rag/chunks/{chunk_id}`

**功能**: 获取分块详情

#### `GET /rag/layered-progress/{task_id}`

**功能**: 查询分层内容生成任务进度

---

## 10. 配置系统完整说明

### 10.1 配置文件

文件: `backend/src/config/settings.py`

**配置加载方式**:
- 使用 `pydantic-settings` 的 `BaseSettings`
- 从 `.env.dev` 文件加载环境变量
- 支持环境变量覆盖 (通过 `validation_alias`)

### 10.2 RAG 配置分类详解

#### 10.2.1 混合检索配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `rag_hybrid_bm25_weight` | `RAG_HYBRID_BM25_WEIGHT` | 0.5 | BM25 基础权重 |
| `rag_hybrid_vector_weight` | `RAG_HYBRID_VECTOR_WEIGHT` | 0.5 | 向量基础权重 |
| `bm25_scale_factor` | `BM25_SCALE_FACTOR` | 5 | BM25 Sigmoid 校准缩放因子 |
| `rag_hybrid_merge_mode` | `RAG_HYBRID_MERGE_MODE` | "OR" | 合并模式 (AND/OR) |
| `rag_hybrid_bm25_top_k` | `RAG_HYBRID_BM25_TOP_K` | 10 | BM25 检索 Top-K |
| `rag_hybrid_vector_top_k` | `RAG_HYBRID_VECTOR_TOP_K` | 10 | 向量检索 Top-K |

**动态权重配置** (`hybrid_weights`):
```python
{
    "default": 0.5,        # 默认 BM25 权重
    "keyword_query": 0.7,  # 关键词查询 BM25 权重 (关键词密度 > 0.5)
    "semantic_query": 0.3  # 语义查询 BM25 权重 (关键词密度 < 0.2)
}
```

#### 10.2.2 缓存配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `rag_cache_enabled` | `RAG_CACHE_ENABLED` | True | 是否启用缓存 |
| `rag_cache_max_size` | `RAG_CACHE_MAX_SIZE` | 1000 | 最大缓存条目数 |
| `rag_cache_ttl_seconds` | `RAG_CACHE_TTL_SECONDS` | 3600 | 缓存过期时间 (秒) |

#### 10.2.3 查询重写配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `rag_query_rewrite_enabled` | `RAG_QUERY_REWRITE_ENABLED` | True | 是否启用查询重写 |

#### 10.2.4 分块配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `rag_chunk_size` | `RAG_CHUNK_SIZE` | 1024 | 通用分块大小 |
| `rag_epub_chunk_target_size` | `RAG_EPUB_CHUNK_TARGET_SIZE` | 1024 | EPUB 分块目标大小 |
| `rag_pdf_chunk_size` | `RAG_PDF_CHUNK_SIZE` | 1536 | PDF 分块大小 |
| `rag_chunk_overlap` | `RAG_CHUNK_OVERLAP` | 200 | 分块重叠大小 |

#### 10.2.5 OCR 检测配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `rag_ocr_extraction_rate_threshold` | `RAG_OCR_EXTRACTION_THRESHOLD` | 0.5 | 文本提取率阈值 |
| `rag_ocr_min_avg_length_threshold` | `RAG_OCR_MIN_AVG_TEXT_LENGTH` | 100 | 最小平均文本长度 |

**检测逻辑**:
```python
is_scanned = (extraction_rate < 0.5) or (avg_text_length < 100)
```

#### 10.2.6 搜索页面专用配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `rag_search_bm25_weight` | `RAG_SEARCH_BM25_WEIGHT` | 0.5 | 搜索 BM25 权重 |
| `rag_search_vector_weight` | `RAG_SEARCH_VECTOR_WEIGHT` | 0.5 | 搜索向量权重 |
| `rag_search_no_match_vector_penalty` | `RAG_SEARCH_NO_MATCH_VECTOR_PENALTY` | 0.5 | 纯向量结果惩罚力度 |
| `rag_search_score_threshold_hybrid` | `RAG_SEARCH_SCORE_THRESHOLD_HYBRID` | 0.35 | 混合检索阈值 |
| `rag_search_score_threshold_vector` | `RAG_SEARCH_SCORE_THRESHOLD_VECTOR` | 0.35 | 向量检索阈值 |
| `rag_search_relative_cutoff_ratio` | `RAG_SEARCH_RELATIVE_CUTOFF_RATIO` | 0.5 | 相对截断比例 (保留 Top 50%) |
| `rag_search_min_similarity_threshold` | `RAG_SEARCH_MIN_SIMILARITY_THRESHOLD` | 0.2 | 最低相似度阈值 |

#### 10.2.7 年龄过滤配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `rag_age_filter_strictness` | `RAG_AGE_FILTER_STRICTNESS` | 0.7 | 严格程度 (0-1) |
| `rag_age_filter_tolerance` | `RAG_AGE_FILTER_TOLERANCE` | 2 | 弹性容忍范围 (岁) |
| `rag_age_fit_weight` | `RAG_AGE_FIT_WEIGHT` | 0.3 | 年龄适配度权重 |

#### 10.2.8 重排序配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `rag_reranker_model` | `RAG_RERANKER_MODEL` | "BAAI/bge-reranker-v2-m3" | Cross-Encoder 模型名称 |
| `rag_reranker_initial_k` | `RAG_RERANKER_INITIAL_K` | 30 | 重排序前初始候选数 |
| `rag_reranker_final_k` | `RAG_RERANKER_FINAL_K` | 5 | 重排序后最终返回数 |

#### 10.2.9 Embedding 配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `embedding_model_name` | `EMBEDDING_MODEL_NAME` | "text-embedding-v4" | Embedding 模型名称 |
| `embedding_max_text_length` | `EMBEDDING_MAX_TEXT_LENGTH` | 1536 | 最大文本长度 (字符) |
| `embedding_batch_size` | `EMBEDDING_BATCH_SIZE` | 10 | 批处理大小 |

#### 10.2.10 向量存储配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `vector_store_type` | `VECTOR_STORE_TYPE` | "chroma" | 向量存储类型 |
| `vector_store_config` | `VECTOR_STORE_CONFIG` | {} | 向量存储配置 |

#### 10.2.11 语义分块配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `semantic_splitter_buffer_size` | `SEMANTIC_SPLITTER_BUFFER_SIZE` | 5 | 语义分块比较段落数 |
| `semantic_splitter_breakpoint_threshold` | `SEMANTIC_SPLITTER_BREAKPOINT_THRESHOLD` | 90 | 语义分块相似度阈值 (%) |
| `semantic_splitter_chapter_buffer_size` | `SEMANTIC_SPLITTER_CHAPTER_BUFFER_SIZE` | 3 | 长章节比较段落数 |
| `semantic_splitter_chapter_breakpoint_threshold` | `SEMANTIC_SPLITTER_CHAPTER_BREAKPOINT_THRESHOLD` | 75 | 长章节相似度阈值 (%) |
| `semantic_splitter_separators` | - | 见下方 | 分隔符列表 |

**分隔符列表** (`semantic_splitter_separators`):
```python
["\n## ", "\n### ", "\n#### ", "\n\n", "\n", "。", "！", "？", ". ", "! ", "? "]
```

#### 10.2.12 规则元数据提取配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `rule_metadata_development_domains` | ["粗大动作", "精细动作", "认知能力", "语言发展", "社交情感", "感觉统合"] | 儿童发展领域标签 |
| `rule_metadata_age_patterns` | 正则列表 (见下方) | 年龄提取正则表达式 |
| `rule_metadata_difficulty_easy_threshold` | 300 | 简单难度内容长度阈值 |
| `rule_metadata_difficulty_hard_threshold` | 1000 | 困难难度内容长度阈值 |

**年龄正则表达式** (`rule_metadata_age_patterns`):
```python
[
    r"(\d+)~(\d+)个月",
    r"(\d+)-(\d+)个月",
    r"适合(\d+)到(\d+)岁",
    r"(\d+)岁左右",
    r"(\d+)月龄",
    r"(\d+)岁"
]
```

#### 10.2.13 PageIndex 配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `pageindex_enabled` | `PAGEINDEX_ENABLED` | False | 是否启用 PageIndex |
| `pageindex_base_url` | `PAGEINDEX_BASE_URL` | "https://api.pageindex.ai" | PageIndex API 地址 |
| `pageindex_api_key` | `PAGEINDEX_API_KEY` | "" | PageIndex API 密钥 |
| `pageindex_max_concurrency` | `PAGEINDEX_MAX_CONCURRENCY` | 5 | 最大并发数 |
| `pageindex_max_tree_depth` | `PAGEINDEX_MAX_TREE_DEPTH` | 3 | 最大树深度 |
| `pageindex_timeout_seconds` | `PAGEINDEX_TIMEOUT_SECONDS` | 10 | 超时时间 (秒) |
| `pageindex_circuit_breaker_failure_threshold` | `PAGEINDEX_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | 5 | 熔断失败阈值 |
| `pageindex_circuit_breaker_reset_timeout` | `PAGEINDEX_CIRCUIT_BREAKER_RESET_TIMEOUT` | 60 | 熔断重置超时 (秒) |
| `pageindex_max_retries` | `PAGEINDEX_MAX_RETRIES` | 3 | 最大重试次数 |
| `pageindex_retry_base_delay` | `PAGEINDEX_RETRY_BASE_DELAY` | 0.5 | 重试基础延迟 (秒) |
| `pageindex_retry_max_delay` | `PAGEINDEX_RETRY_MAX_DELAY` | 10.0 | 重试最大延迟 (秒) |
| `pageindex_fallback_to_hybrid` | `PAGEINDEX_FALLBACK_TO_HYBRID` | True | 是否降级到混合检索 |

#### 10.2.14 查询路由器配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `query_router_llm_enabled` | `QUERY_ROUTER_LLM_ENABLED` | True | 是否启用 LLM 分类 |
| `model_query_classification` | `MODEL_QUERY_CLASSIFICATION` | "qwen3-omni-flash" | 分类模型 |
| `query_router_confidence_threshold` | `QUERY_ROUTER_CONFIDENCE_THRESHOLD` | 0.8 | 置信度阈值 |
| `query_router_llm_max_retries` | `QUERY_ROUTER_LLM_MAX_RETRIES` | 2 | 最大重试次数 |

#### 10.2.15 结果融合配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `fusion_score_boost_for_pageindex` | `FUSION_SCORE_BOOST_FOR_PAGEINDEX` | 1.2 | PageIndex 分数提升倍数 |
| `fusion_hybrid_supplement_limit` | `FUSION_HYBRID_SUPPLEMENT_LIMIT` | 5 | 混合补充数量限制 |
| `fusion_dedup_normalize` | `FUSION_DEDUP_NORMALIZE` | True | 是否去重并归一化 |

#### 10.2.16 分层内容生成配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `rag_layered_content_enabled` | `RAG_LAYERED_CONTENT_ENABLED` | True | 是否启用分层内容 |
| `rag_layered_content_enable_llm_generation` | `RAG_LAYERED_CONTENT_ENABLE_LLM_GENERATION` | True | 是否启用 LLM 生成 |
| `rag_layered_content_enable_local_fallback` | `RAG_LAYERED_CONTENT_ENABLE_LOCAL_FALLBACK` | True | 是否启用本地兜底 |
| `rag_layered_content_l0_max_length` | `RAG_LAYERED_CONTENT_L0_MAX_LENGTH` | 100 | L0 摘要最大长度 |
| `rag_layered_content_l1_max_length` | `RAG_LAYERED_CONTENT_L1_MAX_LENGTH` | 500 | L1 概览最大长度 |
| `rag_layered_content_batch_size` | `RAG_LAYERED_CONTENT_BATCH_SIZE` | 20 | 批次大小 |
| `rag_layered_content_large_batch_threshold` | `RAG_LAYERED_CONTENT_LARGE_BATCH_THRESHOLD` | 1000 | 大批次阈值 |
| `rag_layered_content_large_batch_size` | `RAG_LAYERED_CONTENT_LARGE_BATCH_SIZE` | 10 | 大批次大小 |
| `rag_layered_content_concurrency_limit` | `RAG_LAYERED_CONTENT_CONCURRENCY_LIMIT` | 8 | 并发限制 |

#### 10.2.17 自动持久化配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `rag_auto_persist_enabled` | `RAG_AUTO_PERSIST_ENABLED` | True | 是否启用自动持久化 |
| `rag_auto_persist_interval` | `RAG_AUTO_PERSIST_INTERVAL` | 300 | 持久化间隔 (秒) |

#### 10.2.18 性能配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `rag_vl_max_workers` | `RAG_VL_MAX_WORKERS` | 2 | VL 解析最大线程数 |
| `rag_upload_max_concurrent_tasks` | `RAG_UPLOAD_MAX_CONCURRENT_TASKS` | 5 | 上传最大并发任务数 |
| `rag_temp_upload_dir` | `RAG_TEMP_UPLOAD_DIR` | "./temp_uploads" | 临时上传目录 |
| `rag_metadata_extraction_concurrency` | `RAG_METADATA_EXTRACTION_CONCURRENCY` | 20 | 元数据提取并发数 |

#### 10.2.19 模型配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `dashscope_api_key` | `DASHSCOPE_API_KEY` | "" | DashScope API 密钥 |
| `model_report_generation` | `MODEL_REPORT_GENERATION` | "qwen3.5-plus" | 报告生成模型 |
| `model_assessment` | `MODEL_ASSESSMENT` | "qwen3.5-plus" | 评估模型 |
| `model_validation` | `MODEL_VALIDATION` | "qwen3-turbo" | 验证模型 |
| `model_query_rewrite` | `MODEL_QUERY_REWRITE` | "qwen3-omni-flash" | 查询重写模型 |
| `model_metadata_extraction` | `MODEL_METADATA_EXTRACTION` | "qwen3-omni-flash" | 元数据提取模型 |
| `model_vl_parsing` | `MODEL_VL_PARSING` | "qwen3-omni-flash" | VL 解析模型 |

---

## 11. 技术栈清单

### 11.1 核心框架

| 组件 | 技术选型 | 版本/说明 |
|------|----------|-----------|
| **Web 框架** | FastAPI | Python 异步 Web 框架 |
| **RAG 框架** | LlamaIndex | RAG 编排框架 |
| **配置管理** | pydantic-settings | 环境变量配置 |

### 11.2 向量与 Embedding

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| **向量存储** | Chroma | 本地持久化，支持扩展到 Pinecone/Milvus/Weaviate |
| **Embedding** | DashScope text-embedding-v4 | 阿里云通义 Embedding API |
| **相似度计算** | 余弦相似度 | Chroma 内置 |

### 11.3 检索与重排序

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| **BM25 检索** | llama_index.retrievers.bm25 + jieba | 稀疏检索 + 中文分词 |
| **重排序** | Cross-Encoder (BAAI/bge-reranker-v2-m3) | sentence-transformers |
| **分词** | jieba | 中文分词，含自定义词典 |

### 11.4 文档解析

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| **PDF 解析** | PyMuPDF (fitz) | 传统文本提取 |
| **PDF OCR** | Qwen-VL (qwen3-omni-flash) | 扫描版 PDF OCR |
| **EPUB 解析** | EbookLib + BeautifulSoup | EPUB 解析 |

### 11.5 分块与摘要

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| **语义分块** | SemanticSplitterNodeParser (LlamaIndex) | 语义感知分块 |
| **规则分块** | SentenceSplitter (LlamaIndex) | 规则分块 |
| **本地摘要** | summa (TextRank) | 本地摘要生成兜底 |

### 11.6 LLM 模型

| 用途 | 模型 | 说明 |
|------|------|------|
| **报告生成** | qwen3.5-plus | 高质量生成 |
| **评估** | qwen3.5-plus | 高质量评估 |
| **验证** | qwen3-turbo | 快速验证 |
| **查询重写** | qwen3-omni-flash | 多模态模型 |
| **元数据提取** | qwen3-omni-flash | 多模态模型 |
| **VL 解析** | qwen3-omni-flash | 多模态 OCR |
| **查询分类** | qwen3-omni-flash | 多模态模型 |

### 11.7 去重与压缩

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| **内容去重** | difflib.SequenceMatcher | 字符串相似度 |
| **语义去重** | Jaccard 相似度 | 集合相似度 |
| **上下文压缩** | 自定义 ContextCompressor | 相关性过滤 + 去重 + Token 预算 |

---

## 附录：关键设计决策说明

### A. 为什么使用混合检索？

BM25 擅长精确关键词匹配，向量检索擅长语义理解。两者结合可以：
- 覆盖专业术语、专有名词 (BM25 优势)
- 覆盖语义相似但表述不同的内容 (向量优势)
- 通过动态权重根据查询特征自动调整侧重

### B. 为什么需要 Cross-Encoder 重排序？

粗检索 (BM25 + 向量) 速度快但精度有限。Cross-Encoder 对查询和文档进行深度交互建模，可以：
- 更准确地评估查询-文档相关性
- 过滤粗检索中的噪声结果
- 提升 Top 结果的精度

### C. 为什么需要年龄过滤？

儿童发展评估领域的特殊性：
- 不同年龄段的发展差异巨大
- 婴儿期 (0-1 岁) 每月都有显著变化
- 学龄期 (6-12 岁) 发展相对平稳
- 动态过滤策略确保返回适龄内容

### D. 为什么需要分层元数据提取？

标准模式对每个节点调用 LLM 提取元数据，成本高、速度慢。分层模式：
- 文档级元数据只需提取一次
- 关键块识别减少 LLM 调用次数
- 普通块使用规则提取 (零成本)
- 性能提升约 80 倍

### E. 为什么需要断点续传？

文档导入可能耗时较长 (大文件、网络波动)：
- 支持中断后从断点继续
- 避免重复解析和索引
- 提升用户体验和系统可靠性