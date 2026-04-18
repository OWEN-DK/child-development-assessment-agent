# Phase 2-3: MetadataProcessor 拆分

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `3.3.3` 节
> **所属 Phase**: Phase 2

## 需求定义

将 `MetadataProcessor`（1063 行）按单一职责拆分为 7 个子服务 + 1 个门面类。

## 验收标准

- [ ] 单类不超过 200 行
- [ ] 门面类对外 API 保持兼容
- [ ] 子服务通过依赖注入获取
- [ ] 现有测试全部通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/metadata_processor.py` | 删除 | 原 1063 行文件 |
| `backend/src/core/chunking/__init__.py` | 新增 | 模块入口 |
| `backend/src/core/chunking/metadata_extractor.py` | 新增 | MetadataExtractor（元数据提取，~250 行） |
| `backend/src/core/chunking/content_cleaner.py` | 新增 | ContentCleaner（内容清理，~50 行） |
| `backend/src/core/chunking/chapter_chunker.py` | 新增 | ChapterChunker（章节级分块，~250 行） |
| `backend/src/core/chunking/page_chunker.py` | 新增 | PageChunker（页面级分块，~150 行） |
| `backend/src/core/chunking/hierarchical_chunker.py` | 新增 | HierarchicalChunker（父子块关联，~150 行） |
| `backend/src/core/chunking/splitter_factory.py` | 新增 | SplitterFactory（分块器工厂，~100 行） |
| `backend/src/core/chunking/key_chunk_identifier.py` | 新增 | KeyChunkIdentifier（关键分块识别，~80 行） |

## 拆分方案

### 职责划分

| 子服务 | 职责 | 原 MetadataProcessor 方法 |
|--------|------|-------------------------|
| `MetadataExtractor` | 节点元数据提取、文档信息解析 | `extract_metadata`, `_parse_document_info` |
| `ContentCleaner` | 节点内容清理、空白处理 | `clean_content` |
| `ChapterChunker` | 章节级分块、目录解析 | `chunk_by_chapter`, `_parse_toc` |
| `PageChunker` | 页面级分块、页码处理 | `chunk_by_page`, `_handle_page_boundaries` |
| `HierarchicalChunker` | 父子块关联、层次结构 | `create_hierarchical_chunks`, `_link_parent_child` |
| `SplitterFactory` | 分块器工厂、策略选择 | `get_splitter`, `_select_strategy` |
| `KeyChunkIdentifier` | 关键分块识别、标记 | `is_key_chunk`, `_identify_key_chunks` |

### 门面类实现

```python
"""
分块处理门面类

协调各分块子服务，对外提供统一分块 API。
"""

from typing import Optional

from src.core.chunking.metadata_extractor import MetadataExtractor
from src.core.chunking.content_cleaner import ContentCleaner
from src.core.chunking.chapter_chunker import ChapterChunker
from src.core.chunking.page_chunker import PageChunker
from src.core.chunking.hierarchical_chunker import HierarchicalChunker
from src.core.chunking.splitter_factory import SplitterFactory
from src.core.chunking.key_chunk_identifier import KeyChunkIdentifier


class ChunkingFacade:
    """分块处理门面类"""

    def __init__(
        self,
        metadata_ext: MetadataExtractor,
        content_cleaner: ContentCleaner,
        chapter_chunker: ChapterChunker,
        page_chunker: PageChunker,
        hierarchical_chunker: HierarchicalChunker,
        splitter_factory: SplitterFactory,
        key_chunk_id: KeyChunkIdentifier,
    ):
        self._metadata_ext = metadata_ext
        self._content_cleaner = content_cleaner
        self._chapter_chunker = chapter_chunker
        self._page_chunker = page_chunker
        self._hierarchical_chunker = hierarchical_chunker
        self._splitter_factory = splitter_factory
        self._key_chunk_id = key_chunk_id

    async def process_document(self, document, strategy: str = "chapter") -> list:
        """统一文档分块入口"""
        metadata = self._metadata_ext.extract(document)
        cleaned = self._content_cleaner.clean(document.content)

        splitter = self._splitter_factory.get_splitter(strategy)
        chunks = await splitter.split(cleaned, metadata)

        chunks = self._hierarchical_chunker.create_hierarchy(chunks)
        chunks = self._key_chunk_id.mark_key_chunks(chunks)

        return chunks


# 单例
chunking_facade: Optional[ChunkingFacade] = None


def get_chunking_facade() -> ChunkingFacade:
    global chunking_facade
    if chunking_facade is None:
        chunking_facade = ChunkingFacade(
            metadata_ext=MetadataExtractor(),
            content_cleaner=ContentCleaner(),
            chapter_chunker=ChapterChunker(),
            page_chunker=PageChunker(),
            hierarchical_chunker=HierarchicalChunker(),
            splitter_factory=SplitterFactory(),
            key_chunk_id=KeyChunkIdentifier(),
        )
    return chunking_facade
```

## 测试方案

1. 各分块策略输出与拆分前一致
2. 父子块关联正确
3. 关键分块标记正确
4. 元数据提取完整

## 注意事项

- 分块策略（chapter/page/hierarchical）通过工厂模式选择
- 元数据提取需处理不同文档格式（PDF/EPUB/TXT）
- 内容清理不影响分块边界
