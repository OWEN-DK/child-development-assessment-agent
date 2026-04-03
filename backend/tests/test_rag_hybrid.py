import pytest
import asyncio
import os
from unittest.mock import patch, MagicMock, AsyncMock

# Mock api key before importing modules that instantiate DashScope
os.environ["DASHSCOPE_API_KEY"] = "test-key"

from src.config.settings import settings
settings.dashscope_api_key = "test-key"

from src.service.rag_service import RagService
from src.core.query_router import QueryType, QueryClassification

@pytest.fixture
def mock_injector():
    injector = MagicMock()
    # Mocking getting dependencies
    injector.get.return_value = MagicMock()
    return injector

@pytest.mark.asyncio
async def test_retrieve_knowledge_complex_query(mock_injector):
    service = RagService(mock_injector)
    
    # Enable PageIndex
    settings.pageindex_enabled = True
    
    # Mock the internal components
    with patch.object(service.query_router, 'classify', return_value=QueryClassification(query_type=QueryType.COMPLEX, confidence=0.9, reasoning="test")) as mock_classify, \
         patch.object(service.retrieval_service, 'retrieve_knowledge', new_callable=AsyncMock, return_value=[{"id": 1, "content": "hybrid"}]) as mock_retrieve, \
         patch.object(service.pageindex_wrapper, 'query', new_callable=AsyncMock, return_value=[{"id": 2, "content": "pageindex"}]) as mock_query, \
         patch.object(service.result_fusion, 'fuse', return_value=[{"id": 1, "content": "hybrid"}, {"id": 2, "content": "pageindex"}]) as mock_fuse:
         
        results = await service.retrieve_knowledge("complex query test", age=3, limit=5)
        
        mock_classify.assert_called_once_with("complex query test")
        mock_retrieve.assert_called_once_with("complex query test", 3, 5, None)
        mock_query.assert_called_once_with("complex query test")
        mock_fuse.assert_called_once()
        
        assert len(results) == 2

@pytest.mark.asyncio
async def test_retrieve_knowledge_simple_query(mock_injector):
    service = RagService(mock_injector)
    
    # Enable PageIndex
    settings.pageindex_enabled = True
    
    # Mock the internal components
    with patch.object(service.query_router, 'classify', return_value=QueryClassification(query_type=QueryType.SIMPLE, confidence=0.9, reasoning="test")) as mock_classify, \
         patch.object(service.retrieval_service, 'retrieve_knowledge', new_callable=AsyncMock, return_value=[{"id": 1, "content": "hybrid"}]) as mock_retrieve, \
         patch.object(service.pageindex_wrapper, 'query', new_callable=AsyncMock) as mock_query, \
         patch.object(service.result_fusion, 'fuse') as mock_fuse:
         
        results = await service.retrieve_knowledge("simple query test", age=3, limit=5)
        
        mock_classify.assert_called_once_with("simple query test")
        mock_retrieve.assert_called_once_with("simple query test", 3, 5, None)
        mock_query.assert_not_called()
        mock_fuse.assert_not_called()
        
        assert len(results) == 1
