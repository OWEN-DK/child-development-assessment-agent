# 测试用例汇总

## 测试目录结构
所有测试用例统一放在 `backend/tests/` 目录下。

---

## 测试用例列表

### 1. 工作流测试
- **文件名**: `test_full_workflow.py`
- **功能**: 完整评估流程端到端测试，覆盖从输入到生成报告的全链路

### 2. 节点测试
- **文件名**: `test_nodes_assessment.py`
- **功能**: 评估节点（Node2）功能测试，验证儿童发展状态评估逻辑
- **文件名**: `test_nodes_scoring.py`
- **功能**: 评分节点（Node4）功能测试，验证计划多维度评分逻辑

### 3. RAG 相关测试
- **文件名**: `test_rag_import.py`
- **功能**: RAG 文档导入测试，验证文档解析、分块、元数据提取功能
- **文件名**: `test_rag_ingest.py`
- **功能**: RAG 知识库构建测试，验证索引创建、存储功能
- **文件名**: `test_rag_search.py`
- **功能**: RAG 基础检索测试，验证关键词检索功能
- **文件名**: `test_rag_hybrid.py`
- **功能**: RAG 混合检索测试，验证BM25+向量检索融合逻辑
- **文件名**: `test_rag_optimizations.py`
- **功能**: RAG 检索优化测试，验证召回率、准确率优化效果

### 4. PDF 处理测试
- **文件名**: `test_pdf_chunking.py`
- **功能**: PDF 文档分块测试，验证分块大小、重叠逻辑正确性
- **文件名**: `test_pdf_search.py`
- **功能**: PDF 内容搜索测试，验证扫描版OCR识别、文本检索功能

### 5. ML 评分测试
- **文件名**: `test_ml_scoring.py`
- **功能**: 机器学习评分模型测试，验证预测准确性、一致性

### 6. 多模态解析测试
- **文件名**: `test_vl_parse.py`
- **功能**: 视觉语言多模态解析测试，验证图片、视频内容识别功能

### 7. 流式输出测试
- **文件名**: `run_stream_test.py`
- **功能**: 报告流式生成测试，验证流式输出功能正确性

---

## 运行方法
### 运行所有测试
```bash
pytest tests/
```

### 运行单个测试文件
```bash
pytest tests/<test_file_name>.py
```

### 运行带详细输出
```bash
pytest tests/ -v
```

### 生成覆盖率报告
```bash
pytest tests/ --cov=src
```
