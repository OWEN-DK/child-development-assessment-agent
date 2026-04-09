import pytest
from llama_index.core.schema import Document
from src.service.document_ingestion_service import DocumentIngestionService
from src.service.document_manager import DocumentRecord
from src.config.settings import settings

@pytest.fixture
def ingestion_service():
    """创建文档导入服务实例"""
    return DocumentIngestionService()

def test_clean_documents_filters_empty_text(ingestion_service):
    """测试_clean_documents函数正确过滤空文本的文档"""
    # 创建测试文档，包含正常、空、仅空白字符的文档
    documents = [
        Document(text="这是正常内容的文档", metadata={"chapter_title": "第一章"}),
        Document(text="", metadata={"chapter_title": "空文档"}),
        Document(text="   \n\n   \t  ", metadata={"chapter_title": "仅空白字符的文档"}),
        Document(text="这是另一个正常文档", metadata={"chapter_title": "第二章"}),
    ]
    
    cleaned_docs = ingestion_service._clean_documents(documents, "test.epub")
    
    # 验证只有2个正常文档被保留
    assert len(cleaned_docs) == 2
    assert cleaned_docs[0].text == "这是正常内容的文档"
    assert cleaned_docs[1].text == "这是另一个正常文档"
    # 验证metadata被正确保留
    assert cleaned_docs[0].metadata["chapter_title"] == "第一章"
    assert cleaned_docs[1].metadata["chapter_title"] == "第二章"
    # 验证page_label被正确设置
    assert cleaned_docs[0].metadata["page_label"] == "第一章"
    assert cleaned_docs[1].metadata["page_label"] == "第二章"

def test_clean_documents_all_empty(ingestion_service):
    """测试所有文档都是空内容的情况"""
    documents = [
        Document(text="", metadata={"chapter_title": "空文档1"}),
        Document(text="   \n\n  ", metadata={"chapter_title": "空文档2"}),
        Document(text="\t\t  \n", metadata={"chapter_title": "空文档3"}),
    ]
    
    cleaned_docs = ingestion_service._clean_documents(documents, "test.epub")
    
    # 验证所有空文档都被过滤，返回空列表
    assert len(cleaned_docs) == 0

@pytest.mark.asyncio
async def test_ingest_empty_document_raises_error(ingestion_service, mocker):
    """测试导入全空内容的文件时会抛出明确错误"""
    # 模拟文件解析返回的文档都是空的
    mock_documents = [
        Document(text="", metadata={"chapter_title": "封面"}),
        Document(text="   ", metadata={"chapter_title": "版权页"}),
        Document(text="\n\n\n", metadata={"chapter_title": "前言"}),
    ]
    
    # Mock依赖函数
    mock_parser = mocker.MagicMock()
    mock_parser.parse.return_value = mock_documents
    mocker.patch('src.service.document_ingestion_service.get_parser', return_value=mock_parser)
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('src.service.document_manager.document_manager.exists', return_value=False)
    mocker.patch.object(ingestion_service, '_calculate_file_hash', return_value='fake_hash')
    
    # 测试导入时是否抛出预期的错误
    with pytest.raises(ValueError, match="未找到有效内容"):
        await ingestion_service.ingest_book("test.epub", "test.epub")

def test_chunking_with_mixed_empty_and_valid_chapters(ingestion_service):
    """测试混合空章节和有效章节的场景"""
    # 创建混合文档
    documents = [
        Document(text="", metadata={"chapter_title": "封面"}),
        Document(text="这是第一章的正常内容，讲述儿童发展的基本概念。", metadata={"chapter_title": "第一章"}),
        Document(text="   \n\n  ", metadata={"chapter_title": "空白页"}),
        Document(text="这是第二章的内容，包含更多关于儿童认知发展的知识。", metadata={"chapter_title": "第二章"}),
        Document(text="\t", metadata={"chapter_title": "版权页"}),
    ]
    
    # 清理文档
    cleaned_docs = ingestion_service._clean_documents(documents, "test.epub")
    
    # 验证空章节被过滤，仅保留2个有效章节
    assert len(cleaned_docs) == 2
    assert all(len(doc.text.strip()) > 0 for doc in cleaned_docs)
    
    # 测试分块处理
    from src.core.metadata_processor import MetadataProcessor
    chunks = MetadataProcessor.split_chapters_into_chunks(cleaned_docs, chunk_target_size=200, file_hash="test_hash")
    
    # 验证能正常生成分块
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk.text.strip()) > 0
        assert chunk.metadata["file_hash"] == "test_hash"
