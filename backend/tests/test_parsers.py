import pytest
from unittest.mock import patch, MagicMock
from llama_index.core.schema import Document
from src.core.parsers import PDFParserV2, ParserType, PDFParseError, PDFCorruptedError, get_parser, EPUBParser


@pytest.fixture
def valid_documents():
    return [
        Document(text="This is a valid long text content that passes the min_content_length check." * 5, metadata={})
    ]


@pytest.fixture
def invalid_documents():
    return [
        Document(text="short", metadata={})
    ]


def test_pdf_parser_v2_vlm_success(valid_documents):
    parser = PDFParserV2(fallback_order=[ParserType.VLM, ParserType.TEXT])
    
    with patch.object(parser, '_parse_with_vlm', return_value=valid_documents) as mock_vlm:
        with patch.object(parser, '_parse_with_text') as mock_text:
            result = parser.parse("dummy.pdf")
            
            assert result == valid_documents
            mock_vlm.assert_called_once()
            mock_text.assert_not_called()


def test_pdf_parser_v2_vlm_invalid_fallback_to_text(invalid_documents, valid_documents):
    parser = PDFParserV2(fallback_order=[ParserType.VLM, ParserType.TEXT])
    
    with patch.object(parser, '_parse_with_vlm', return_value=invalid_documents) as mock_vlm:
        with patch.object(parser, '_parse_with_text', return_value=valid_documents) as mock_text:
            with patch('os.path.exists', return_value=True):
                result = parser.parse("dummy.pdf")
                
                assert result == valid_documents
                mock_vlm.assert_called_once()
                mock_text.assert_called_once()


def test_pdf_parser_v2_vlm_exception_fallback_to_text(valid_documents):
    parser = PDFParserV2(fallback_order=[ParserType.VLM, ParserType.TEXT])
    
    with patch.object(parser, '_parse_with_vlm', side_effect=Exception("VLM error")) as mock_vlm:
        with patch.object(parser, '_parse_with_text', return_value=valid_documents) as mock_text:
            with patch('os.path.exists', return_value=True):
                result = parser.parse("dummy.pdf")
                
                assert result == valid_documents
                mock_vlm.assert_called_once()
                mock_text.assert_called_once()


def test_pdf_parser_v2_all_fail():
    parser = PDFParserV2(fallback_order=[ParserType.VLM, ParserType.TEXT])
    
    with patch.object(parser, '_parse_with_vlm', side_effect=Exception("VLM error")):
        with patch.object(parser, '_parse_with_text', side_effect=Exception("TEXT error")):
            with patch('os.path.exists', return_value=True):
                with pytest.raises(PDFParseError, match="All PDF parsers failed"):
                    parser.parse("dummy.pdf")


def test_pdf_parser_v2_corrupted():
    parser = PDFParserV2(fallback_order=[ParserType.VLM, ParserType.TEXT])
    
    with patch.object(parser, '_parse_with_vlm', side_effect=PDFCorruptedError("Corrupted file")):
        with patch.object(parser, '_parse_with_text') as mock_text:
            with patch('os.path.exists', return_value=True):
                with pytest.raises(PDFCorruptedError):
                    parser.parse("dummy.pdf")
                
                mock_text.assert_not_called()


def test_get_parser():
    assert isinstance(get_parser("test.pdf"), PDFParserV2)
    assert get_parser("test.epub") == EPUBParser
    
    with pytest.raises(ValueError):
        get_parser("test.txt")
