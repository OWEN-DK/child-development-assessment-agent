# RAG 系统时序图

> 本文档包含 RAG 系统的核心时序图,展示文档导入和知识检索的完整流程。

---

## 时序图 1: 文档导入流水线 (Ingestion Pipeline)

```mermaid
sequenceDiagram
    participant User as 用户
    participant Controller as rag_controller.py
    participant RagService as RagService
    participant DocManager as DocumentManager
    participant IngestionService as DocumentIngestionService
    participant Parser as Parser Service
    participant Chunking as Chunking Service
    participant Metadata as Metadata Extractor
    participant IndexManager as IndexManagerService
    participant VectorStore as VectorStore (Chroma)

    User->>Controller: POST /rag/upload (PDF/EPUB)
    Controller->>Controller: 验证文件扩展名
    Controller->>Controller: 生成 task_id (UUID)
    Controller->>Controller: 保存到临时目录
    Controller-->>User: 返回 task_id
    
    Controller->>RagService: ingest_book()
    RagService->>RagService: 计算文件 MD5 哈希
    RagService->>DocManager: 检查文档是否已存在
    DocManager-->>RagService: 返回检查结果
    RagService->>DocManager: 注册文档
    
    RagService->>IngestionService: ingest_book_resumable()
    
    Note over IngestionService,Parser: 阶段 1: 文档解析
    IngestionService->>Parser: 检测是否为扫描版 PDF
    alt 扫描版 PDF
        Parser->>Parser: PDFVLParser (Qwen-VL OCR)
        Parser->>Parser: 逐页渲染为图片
        Parser->>Parser: 调用多模态 LLM
    else 非扫描版 PDF
        Parser->>Parser: PDFParserV2 (三级降级)
        Parser->>Parser: VLM 解析 → 文本提取
    end
    Parser-->>IngestionService: 返回解析后的文档节点
    
    Note over IngestionService,Chunking: 阶段 2: 智能分块
    IngestionService->>Chunking: 选择分块策略
    alt EPUB/带书签 PDF
        Chunking->>Chunking: split_chapters_into_chunks()
    else 普通 PDF
        Chunking->>Chunking: split_pages_into_chunks()
    end
    Chunking->>Chunking: 语义分块 (SemanticSplitter)
    Chunking->>Chunking: 合并相邻小块
    Chunking->>Chunking: 二次细分 (SentenceSplitter)
    Chunking-->>IngestionService: 返回分块结果
    
    Note over IngestionService,Metadata: 阶段 3: 元数据提取
    alt 标准模式
        Metadata->>Metadata: 每个节点调用 LLM
    else 分层模式 (高性能)
        Metadata->>Metadata: 提取文档级元数据 (1次)
        Metadata->>Metadata: 识别关键块
        Metadata->>Metadata: 关键块 LLM 提取
        Metadata->>Metadata: 普通块规则提取
    end
    Metadata-->>IngestionService: 返回带元数据的节点
    
    Note over IngestionService: 阶段 4: 内容去重
    IngestionService->>IngestionService: 计算 content_hash (MD5)
    IngestionService->>IngestionService: 跳过重复块
    
    Note over IngestionService,IndexManager: 阶段 5: 索引插入
    IngestionService->>IndexManager: insert_nodes()
    IndexManager->>IndexManager: 分批插入 (batch_size=100)
    IndexManager->>VectorStore: 存储向量索引
    IndexManager->>IndexManager: 触发自动持久化
    
    IngestionService-->>RagService: 导入完成
    RagService->>Controller: 更新任务状态为 success
```

---

## 时序图 2: 知识检索流水线 (Retrieval Pipeline)

```mermaid
sequenceDiagram
    participant User as 用户
    participant Controller as rag_controller.py
    participant RagService as RagService
    participant QueryRouter as QueryRouter
    participant RetrievalService as RetrievalService
    participant CacheService as CacheService
    participant BM25 as BM25Retriever
    participant VectorRetriever as VectorRetriever
    participant Merger as HybridRetrievalMerger
    participant Reranker as Cross-Encoder Reranker
    participant PageIndex as PageIndexWrapper
    participant ResultFusion as ResultFusion

    User->>Controller: GET /rag/search?query=&age=&limit=
    Controller->>RagService: retrieve_knowledge(query, age, limit)
    
    Note over RagService,QueryRouter: 步骤 1: 查询路由
    RagService->>QueryRouter: classify_query(query)
    QueryRouter->>QueryRouter: LLM 分类 (简单/复杂)
    QueryRouter->>QueryRouter: 检查置信度 (threshold=0.8)
    QueryRouter-->>RagService: 返回 query_type
    
    Note over RagService,CacheService: 步骤 2: 检索服务
    RagService->>RetrievalService: retrieve_knowledge()
    RetrievalService->>CacheService: 检查缓存
    alt 缓存命中
        CacheService-->>RetrievalService: 返回缓存结果
        RetrievalService-->>RagService: 返回结果
    else 缓存未命中
        Note over RetrievalService: 2.1 查询重写 (可选)
        RetrievalService->>RetrievalService: _rewrite_query()
        RetrievalService->>RetrievalService: LLM 重写为关键词短语
        
        Note over RetrievalService: 2.2 同义词扩展
        RetrievalService->>RetrievalService: _expand_synonyms()
        RetrievalService->>RetrievalService: LLM 生成同义词列表
        RetrievalService->>RetrievalService: 质量验证 + 查询扩展
        
        Note over RetrievalService: 2.3 年龄过滤器构建
        RetrievalService->>RetrievalService: _build_age_filters(age)
        RetrievalService->>RetrievalService: 确定发展阶段
        RetrievalService->>RetrievalService: 构建 MetadataFilter
        
        Note over RetrievalService,BM25: 2.4 混合检索执行
        par 并行检索
            RetrievalService->>BM25: aretrieve(query)
            BM25->>BM25: jieba 分词
            BM25-->>RetrievalService: 返回 BM25 结果
        and
            RetrievalService->>VectorRetriever: aretrieve(query)
            VectorRetriever->>VectorRetriever: DashScope Embedding
            VectorRetriever-->>RetrievalService: 返回向量结果
        end
        
        Note over RetrievalService,Merger: 2.5 结果融合
        RetrievalService->>Merger: merge_results()
        Merger->>Merger: BM25 分数校准 (Sigmoid)
        Merger->>Merger: 向量分数校准 (分段)
        Merger->>Merger: 动态权重计算
        Merger->>Merger: 加权融合 + 全局归一化
        Merger-->>RetrievalService: 返回融合结果
        
        Note over RetrievalService,Reranker: 2.6 Cross-Encoder 重排序
        RetrievalService->>Reranker: rerank(query, nodes)
        Reranker->>Reranker: 取 Top 30 候选
        Reranker->>Reranker: Cross-Encoder 评分
        Reranker->>Reranker: 返回 Top 5
        Reranker-->>RetrievalService: 返回重排序结果
        
        Note over RetrievalService: 2.7 转换为 KnowledgeItem
        RetrievalService->>RetrievalService: 年龄适配度计算
        RetrievalService->>RetrievalService: 内容去重
        RetrievalService->>RetrievalService: 阈值过滤
        
        Note over RetrievalService,CacheService: 2.8 缓存结果
        RetrievalService->>CacheService: cache_result()
        RetrievalService-->>RagService: 返回检索结果
    end
    
    Note over RagService,ResultFusion: 步骤 3: 复杂查询增强
    alt query_type == "complex"
        RagService->>PageIndex: search(query, age, limit)
        PageIndex->>PageIndex: 熔断检查
        PageIndex->>PageIndex: 外部知识图谱检索
        PageIndex-->>RagService: 返回 PageIndex 结果
        
        RagService->>ResultFusion: fuse(base_results, pageindex_results)
        ResultFusion->>ResultFusion: 去重 (内容哈希)
        ResultFusion->>ResultFusion: PageIndex 分数 * 1.2
        ResultFusion->>ResultFusion: 混合补充 (最多 5 个)
        ResultFusion->>ResultFusion: 重新归一化
        ResultFusion-->>RagService: 返回融合结果
    end
    
    RagService-->>Controller: 返回 List[KnowledgeItem]
    Controller-->>User: 返回检索结果 JSON
```

---

## 时序图 3: PDFParserV2 三级降级解析流程

```mermaid
sequenceDiagram
    participant Client as 调用方
    participant ParserV2 as PDFParserV2
    participant VLM as PDFVLParser (VLM)
    participant Text as PDFParser (文本提取)
    participant Validator as Content Validator

    Client->>ParserV2: parse(file_path)
    
    Note over ParserV2: 第一级: VLM 解析
    ParserV2->>VLM: _parse_with_vlm()
    VLM->>VLM: 逐页渲染为图片
    VLM->>VLM: 调用 Qwen-VL OCR
    VLM-->>ParserV2: 返回 VLM 解析结果
    
    ParserV2->>Validator: _is_content_valid()
    Validator->>Validator: 检查平均内容长度 >= 100
    Validator->>Validator: 检查乱码比例 (非 ASCII < 80%)
    
    alt 校验通过
        Validator-->>ParserV2: 验证通过
        ParserV2-->>Client: 返回解析结果
    else 校验失败
        Validator-->>ParserV2: 验证失败
        
        Note over ParserV2: 第二级: 传统文本提取
        ParserV2->>Text: _parse_with_text()
        Text->>Text: PyMuPDF 提取文本
        Text->>Text: 书签分割 (如有 TOC)
        Text-->>ParserV2: 返回文本提取结果
        
        ParserV2->>Validator: _is_content_valid()
        
        alt 校验通过
            Validator-->>ParserV2: 验证通过
            ParserV2-->>Client: 返回解析结果
        else 校验失败
            Validator-->>ParserV2: 验证失败
            ParserV2->>ParserV2: 抛出 PDFParseError
            ParserV2-->>Client: 异常
        end
    end
```

---

## 使用说明

这些时序图使用 Mermaid 语法编写,可以通过以下方式查看:

1. **VS Code / Trae IDE**: 安装 Mermaid 插件后直接预览
2. **GitHub / GitLab**: 原生支持 Mermaid 渲染
3. **在线编辑器**: 访问 https://mermaid.live/ 粘贴代码查看
4. **Markdown 编辑器**: Typora、Obsidian 等支持 Mermaid 的编辑器
