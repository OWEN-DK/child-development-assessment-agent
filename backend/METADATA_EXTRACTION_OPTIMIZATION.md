# 元数据提取性能优化

## 问题背景

在处理大型文档（如 4000+ 分块的书籍）时，元数据提取过程非常缓慢：

- **原始方式**：每个分块都调用 LLM 提取元数据
- **问题**：4000 个分块 = 4000 次 LLM 调用
- **耗时**：按每次 LLM 调用 3-10 秒计算，总耗时 3-11 小时

## 优化方案

### 1. 分层元数据提取策略

核心思想：**文档级统一元数据 + 关键分块单独提取 + 普通分块规则提取**

```
4000 个分块 → 1 次文档级 LLM + 50 次关键块 LLM + 3949 次规则提取
            ↓
         从 4000 次 LLM 调用 → 51 次 LLM 调用
         速度提升约 80 倍
```

#### 关键分块识别策略

1. **章节开头**：每个章节的前 2 个分块（内容最丰富）
2. **均匀采样**：每隔 N 个分块取一个（确保覆盖全文）
3. **内容突变**：长度明显变化的分块（可能是新主题）

### 2. LLM 响应缓存

- **机制**：使用 MD5 哈希缓存已提取的文本
- **效果**：相同或相似内容不重复调用 LLM
- **缓存大小**：最多 10000 条，LRU 淘汰

### 3. 规则提取优化

- **默认使用规则提取**：毫秒级速度（3-5ms/块）
- **规则提取器**：基于关键词、正则表达式
- **兜底机制**：规则提取质量低时使用 LLM

### 4. 并发度提升

- **并发配置**：从 20 提升到 50
- **超时优化**：从 10 秒降低到 8 秒
- **重试次数**：从 2 次减少到 1 次（加速失败处理）

## 性能对比

### 理论推算（4000 分块）

| 方式 | LLM 调用次数 | 预计耗时 | 平均每块 |
|------|-------------|----------|----------|
| 原始方式 | 4000 次 | 3-11 小时 | 3-10 秒 |
| 分层方式 | 51 次 | ~19 秒 | ~5ms |
| **提升** | **98.7% 减少** | **约 80 倍** | **600 倍** |

### 实际测试

运行测试脚本查看实际性能：

```bash
cd backend
python test_hierarchical_metadata.py
```

## 使用方式

### 自动分层（推荐）

```python
from src.core.metadata_processor import MetadataProcessor

processor = MetadataProcessor(concurrency=50)

# 自动根据分块数量选择策略（>100 块自动使用分层）
nodes = await processor.process_nodes(
    nodes=chunk_nodes,
    file_hash="doc_hash",
    progress_callback=callback,
    use_hierarchical=True  # 启用分层
)
```

### 强制标准方式

```python
# 小文档（<100 块）可使用标准方式
nodes = await processor.process_nodes(
    nodes=small_chunk_nodes,
    file_hash="doc_hash",
    use_hierarchical=False  # 不启用分层
)
```

### 预提取文档级元数据

```python
# 提前提取文档级元数据，避免重复计算
doc_meta = await MetadataExtractor.extract(sample_text)

# 传递给分层处理
nodes = await processor._process_nodes_hierarchical(
    nodes=chunk_nodes,
    file_hash="doc_hash",
    doc_level_metadata=doc_meta.model_dump()
)
```

## 配置项

在 `.env.dev` 中添加：

```bash
# RAG 元数据提取配置
RAG_METADATA_EXTRACTION_CONCURRENCY=50  # 最大并发数
```

## 元数据来源标记

每个分块的 metadata 中会标记来源：

- `metadata_source: "llm_key_chunk"` - LLM 提取（关键分块）
- `metadata_source: "rule_based"` - 规则提取（普通分块）
- `metadata_source: "llm"` - 标准方式 LLM 提取
- `metadata_extraction_failed: true` - 提取失败

## 质量保障

### 元数据继承

普通分块虽然使用规则提取，但会继承文档级的关键信息：

```python
# 如果规则提取的 topics 为空，继承文档级的 topics
if not meta_dict.get("topics") and doc_level_metadata.get("topics"):
    meta_dict["topics"] = doc_level_metadata["topics"]

# 脑区信息同理
if not meta_dict.get("brain_regions") and doc_level_metadata.get("brain_regions"):
    meta_dict["brain_regions"] = doc_level_metadata["brain_regions"]
```

### 降级机制

三层降级保障：

1. LLM 提取（优先）
2. 规则提取（兜底）
3. 默认元数据（最后保障）

## 优化效果总结

- ✅ **速度提升**：从小时级 → 分钟级（约 80 倍）
- ✅ **成本降低**：LLM 调用减少 98.7%
- ✅ **质量保障**：关键分块保留 LLM 提取质量
- ✅ **向后兼容**：支持标准方式和分层方式切换
- ✅ **智能选择**：自动根据分块数量选择最优策略

## 适用场景

### 分层方式（推荐）
- ✅ 大型文档（>100 分块）
- ✅ 书籍导入（4000+ 分块）
- ✅ 批量文档处理

### 标准方式
- ✅ 小型文档（<100 分块）
- ✅ 对元数据质量要求极高的场景
- ✅ 测试和调试

## 后续优化方向

1. **语义去重**：对相似分块只提取一次
2. **增量更新**：只处理新增或修改的分块
3. **分布式处理**：支持多节点并行处理
4. **GPU 加速**：规则提取的向量化优化
