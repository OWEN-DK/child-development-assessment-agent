# RAG 文档管理与语义切分设计方案 (修正版)

## 1. 核心目标
- **文档管理**: 引入 `document_store.json` 实现文件级元数据管理（支持增删查）。
- **语义切分**: 采用“本地 PDF/EPUB 解析 + LLM 语义识别”策略，提取章节结构。
- **高精检索**: 支持基于 `Topic`、`Age Group`、`Brain Regions` 的混合检索。
- **物理删除**: 实现基于 `ref_doc_id` 的向量索引物理删除。
- **原文存储**: 向量索引中直接存储完整文本内容，便于前端展示和 LLM 生成。

## 2. 数据结构设计

### 2.1 文档注册表 (`storage/document_store.json`)
```json
{
  "docs": {
    "d41d8cd98f00b204e9800998ecf8427e": { // MD5 Hash
      "file_name": "感统训练实操手册.pdf",
      "upload_date": "2024-03-20T10:00:00",
      "ref_doc_ids": ["uuid-1", "uuid-2"], // LlamaIndex 中的 ref_doc_id (对应原始文档)
      "metadata": {
        "title": "感统训练实操手册",
        "category": "家庭游戏",
        "total_pages": 120
      },
      "status": "indexed"
    }
  }
}
```

### 2.2 向量索引 Metadata Schema (Nodes)
每个切片 (Node) 将包含以下额外字段，直接对应 `KnowledgeItem` 的定义：
- `file_name`: 源文件名 (str)
- `content`: **[新增]** 完整原文文本 (str, stored in index)
- `chapter_title`: "第三章 前庭觉训练" (str)
- `page_label`: "P15" (str)
- `topics`: ["前庭觉", "平衡感"] (List[str])
- `brain_regions`: ["小脑", "前庭核"] (List[str])
- `target_age_min`: 3 (int)
- `target_age_max`: 6 (int)
- `activity_type`: "游戏" (str)

## 3. 核心流程详解

### 3.1 智能摄入 (Smart Ingestion)
1. **查重**: 计算 MD5，若已存在提示覆盖。
2. **解析 (Parsing)**:
   - **PDF**: `PyMuPDF` 提取文本。
   - **EPUB**: `EbookLib` 提取章节。
3. **语义切分与提取 (Extraction)**:
   - **Level 1**: 按章节粗切分。
   - **Level 2 (LLM)**: 对每个 TextChunk 调用 LLM，提取结构化元数据：
     ```json
     {
       "summary": "...",
       "topics": ["前庭觉"],
       "brain_regions": ["小脑"],
       "target_age_min": 3,
       "target_age_max": 6
     }
     ```
   - **Level 3 (Node Construction)**:
     - 创建 `TextNode(text=original_text)`。
     - 将提取的元数据注入 `node.metadata`。
     - **关键**: 确保 `node.text` 包含完整的原始文本，以便检索时直接获取。
4. **索引构建**: `index.insert_nodes(nodes)`。
5. **注册**: 更新 `document_store.json`。

### 3.2 高级检索 (Hybrid Retrieval)
1. **Query Rewriting**: LLM 将 Query 转为 Filter 条件 (e.g., `age=5` -> `target_age_min <= 5 <= target_age_max`).
2. **执行检索**:
   - `VectorStoreIndex.as_retriever(filters=...)`。
   - 返回包含完整 `content` 和 `metadata` 的 Nodes。
3. **结果封装**: 将 Node 转换为 `KnowledgeItem` 对象返回给前端。

### 3.3 文档删除
1. **查询**: 根据 `filename` 查找 `ref_doc_ids`。
2. **执行**: `index.delete_ref_doc(ref_id, delete_from_docstore=True)`。
3. **清理**: 更新 JSON 注册表。

## 4. 依赖库新增
- `pymupdf`: PDF 解析。
- `pydantic`: Schema 定义。
