import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from src.core.pageindex_wrapper import PageIndexWrapper
from src.config import settings

@pytest.mark.asyncio
async def test_index_document_success():
    # Enable PageIndex for testing
    settings.pageindex_enabled = True
    settings.pageindex_api_key = "test-key"
    
    wrapper = PageIndexWrapper()
    
    with patch('aiohttp.ClientSession.post') as mock_post, \
         patch('os.path.exists', return_value=True), \
         patch('builtins.open', MagicMock()):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_post.return_value.__aenter__.return_value = mock_response
        
        result = await wrapper.index_document("test.pdf", "doc_123")
        
        assert result is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "/api/v1/documents" in args[0]
        assert "data" in kwargs

@pytest.mark.asyncio
async def test_index_document_disabled():
    wrapper = PageIndexWrapper()
    
    # Disable PageIndex for testing
    settings.pageindex_enabled = False
    
    with patch('aiohttp.ClientSession.post') as mock_post:
        result = await wrapper.index_document("test.pdf", "doc_123")
        
        assert result is False
        mock_post.assert_not_called()
