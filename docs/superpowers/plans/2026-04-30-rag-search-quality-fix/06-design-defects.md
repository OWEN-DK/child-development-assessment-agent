# 06 P4：消除设计缺陷

> 6 个设计缺陷，影响检索质量但不直接导致崩溃。
> 与 P1/P2/P3 无硬依赖，6 项之间也无依赖，可并行。

---

## P4-1 分块质量校验（问题 4）

### 核实事实

`chunk_chapter.py` 只检查：
- `_is_poorly_formatted()`：单行超 1500 字符
- `_filter_empty_nodes()`：空内容
- `_refine_chunks()`：最小尺寸（40% of target）和相邻合并

缺失：信息密度、碎片检测、语义连贯性。

`chunking_indexing.py:119-120` 元数据失败回退 `target_age_min=0, target_age_max=18`（年龄过滤已在 01 移除，此处需同步删除）。

EPUB 默认 `chunk_target_size=1024`，PDF 默认 `chunk_size=1536`，不一致。

### 修复

**Step 1**：`chunk_chapter.py` 增加碎片块检测

在 `_refine_chunks()` 之前新增过滤步骤：

```python
@staticmethod
def _is_low_density(text: str, threshold: float = 0.3) -> bool:
    """检测信息密度过低的碎片块"""
    if not text or len(text.strip()) < 20:
        return True
    chinese_chars = len(re.findall(r'[一-龥]', text))
    total_chars = len(text.strip())
    if total_chars == 0:
        return True
    chinese_ratio = chinese_chars / total_chars
    unique_chars = len(set(re.findall(r'[一-龥]', text)))
    uniqueness = unique_chars / chinese_chars if chinese_chars > 0 else 0
    # 中文占比过低 或 唯一字符占比过高（>0.7 = 重复内容少但信息密度低）
    return chinese_ratio < threshold or (chinese_chars > 10 and uniqueness > 0.85)
```

在 `chunk_chapter()` 流程中调用：
```python
nodes = [n for n in nodes if not ChapterChunker._is_low_density(n.get_content())]
```

**Step 2**：`chunking_indexing.py` 删除年龄回退

```python
# 删除这两行（年龄过滤已在 01 移除）
# node.metadata["target_age_min"] = 0
# node.metadata["target_age_max"] = 18
```

**Step 3**：统一 EPUB/PDF chunk size

统一为 1024（EPUB 章节通常较短，1024 更合适；PDF 也用 1024 保持一致）。

### 验证

- [ ] 上传含页眉页脚/版权声明的文档，碎片块被过滤
- [ ] 正常内容块不被误删
- [ ] `grep "target_age" chunking_indexing.py` 返回空

---

## P4-2 替换中文去重算法（问题 6）

### 核实事实

`context_compressor.py`：
- L144-174 用单字 Jaccard：`set(re.findall(r'[一-龥]', text))`
- `"感觉统合失调"` 和 `"表现感觉的统合失调"` → Jaccard = 1.0（字集相同）
- `sklearn.cosine_similarity` 已导入未使用（L10）
- L82 阈值以下强制返回前 5 个不相关结果

### 修复

**Step 1**：替换为 jieba 分词 + 词级 Jaccard

```python
import jieba

def _text_similarity(self, text1: str, text2: str) -> float:
    def tokenize(text: str) -> set:
        chinese_segments = re.findall(r'[一-龥]+', text)
        english_words = set(re.findall(r'[a-zA-Z]{2,}', text.lower()))
        chinese_words = set()
        for seg in chinese_segments:
            chinese_words.update(jieba.cut(seg))
        # 过滤单字停用词
        return (chinese_words | english_words) - {' ', '', '\n', '的', '了', '是', '在', '和', '有', '为'}

    tokens1 = tokenize(text1)
    tokens2 = tokenize(text2)
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    return len(intersection) / len(union)
```

**Step 2**：删除未使用的 sklearn 导入

```python
# 删除
# from sklearn.metrics.pairwise import cosine_similarity
```

**Step 3**：阈值以下返回空列表

```python
# L82 修改
if not filtered_nodes:
    return []  # 不强制返回不相关结果
```

### 验证

- [ ] `"感觉统合失调的表现"` vs `"表现感觉的统合失调"` Jaccard < 0.5（字序不同，词级区分）
- [ ] `"感觉统合训练方法"` vs `"感觉统合训练技巧"` Jaccard > 0.7（语义相近，保留其一即可）
- [ ] `grep "sklearn" context_compressor.py` 返回空

---

## P4-3 跨源去重 hash 统一（问题 16）

### 核实事实

代码库中存在多种 hash 算法和归一化策略：

| 文件 | 算法 | 长度 | 归一化 |
|------|------|------|--------|
| `chunking_indexing.py:149` | SHA-256 | 全长(64) | 无 |
| `result_fusion.py:153` | SHA-256 | 截断(16) | 可选 `_normalize_text` |
| `dedup_engine.py:183` | **MD5** | 全长(32) | 无 |
| `metadata_extractor.py:160` | **MD5** | 全长 | 仅前 2000 字符 |

同一内容在不同模块产生不同 hash → 跨模块去重永远不生效。

### 修复

**Step 1**：提取统一 hash 工具函数

新增 `backend/src/utils/hash_utils.py`：

```python
import hashlib

def content_hash(text: str) -> str:
    """统一内容哈希：SHA-256 全长，strip 后计算"""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
```

**Step 2**：所有 hash 计算点替换

| 文件 | 修改 |
|------|------|
| `chunking_indexing.py` | `content_hash` 调用 → `from src.utils.hash_utils import content_hash` |
| `result_fusion.py` | `_content_hash()` 方法 → 调用统一函数 |
| `dedup_engine.py` | MD5 → `content_hash` |
| `metadata_extractor.py` | MD5 + 截断 → `content_hash`（全文本） |

**Step 3**：删除 `result_fusion.py` 中的 `_normalize_text` 和截断逻辑

统一归一化为 `strip()` 后 hash，在 `content_hash()` 中处理。

### 验证

- [ ] `grep -r "md5\|sha256\|sha512\|hashlib" backend/src/ --include="*.py"` 只返回 `hash_utils.py`
- [ ] 相同内容在索引和去重引擎中产生相同 hash

---

## P4-4 放宽同义词验证（问题 20）

### 核实事实

`synonym_validator.py:139-152`：
- 中文用字符级交集：`set(term) & set(original_query)`
- "注意力" → "凝视"（无共享字符）→ 被拒绝
- 长度上限 15 字符（L99），专业术语如 "sensory integration dysfunction" (33字符) 被拒绝

### 修复

**Step 1**：中文改为词级交集

```python
import jieba

def _has_semantic_overlap(self, term: str, original_query: str) -> bool:
    # 白名单直接通过
    if term in self.domain_terms:
        return True

    if self._chinese_pattern.search(original_query):
        # 词级交集（替代字符级）
        term_words = set(jieba.cut(term))
        query_words = set(jieba.cut(original_query))
        # 过滤停用词
        stopwords = {'的', '了', '是', '在', '和', '有', '为', '不', '都', '也'}
        term_words -= stopwords
        query_words -= stopwords
        if term_words & query_words:
            return True

    # 英文词级交集（保持不变，但放宽最小长度为 2）
    if re.search(r"[a-zA-Z]", original_query):
        term_words = set(re.findall(r"[a-zA-Z]{2,}", term.lower()))
        query_words = set(re.findall(r"[a-zA-Z]{2,}", original_query.lower()))
        if term_words & query_words:
            return True

    return False
```

**Step 2**：长度上限放宽

```python
# L99 修改
if len(term) > 25:  # 从 15 放宽到 25
    return "太长（超过 25 字）"
```

### 验证

- [ ] "凝视" 作为 "注意力" 的同义词不再被字符级拒绝（注意：如果词级交集仍为空，还是会被拒绝——这是预期行为，"凝视"和"注意力"无词级重叠，需通过白名单或 LLM 兜底）
- [ ] "感觉统合" 作为 "感觉统合训练" 的同义词通过验证（共享"感觉统合"词）
- [ ] 长度 20 字符的专业术语不被拒绝

---

## P4-5 Pipeline YAML 清理 age_filter 步骤

### 修复

已在 `01-age-filter-removal.md` 中覆盖。从 complex pipeline 中删除 `age_filter` 步骤。

---

## P4-6 分层生成 fallback

### 修复

已在 `02-runtime-crashes.md` P0-4 中覆盖。`layered_config` 变量引用修复。
