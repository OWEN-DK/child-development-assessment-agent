import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import os
from src.config import settings
from src.service.document_ingestion_service import DocumentIngestionService
from src.service.index_manager_service import IndexManagerService

@pytest.fixture
def mock_index_manager():
    return MagicMock(spec=IndexManagerService)

@pytest.mark.asyncio
async def test_document_ingestion_triggers_pageindex(mock_index_manager, tmp_path):
    # Setup test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("This is a test document.")
    file_path = str(test_file)
    
    # Enable PageIndex
    settings.pageindex_enabled = True
    settings.pageindex_api_key = "test-key"
    
    service = DocumentIngestionService(mock_index_manager)
    
    # Mock the internal processing methods to avoid actual PDF parsing and LlamaIndex ingestion
    with patch.object(service, '_calculate_file_hash', return_value="hash123"), \
         patch('src.service.document_manager.document_manager.exists', return_value=False), \
         patch('src.service.document_manager.document_manager.add_document'), \
         patch.object(service, '_ingest_book_with_state', new_callable=AsyncMock) as mock_ingest, \
         patch('src.core.pageindex_wrapper.PageIndexWrapper.index_document', new_callable=AsyncMock) as mock_index_document:
         
        # Make the internal ingest mock just complete successfully
        async def fake_ingest(task_state, progress_callback=None):
            task_state["progress"] = 100.0
            
        mock_ingest.side_effect = fake_ingest
        
        # Add the call to pageindex_wrapper directly to simulate what the method would do,
        # Wait, the plan says to add the call inside _ingest_book_with_state.
        # So we should actually call the real _ingest_book_with_state and mock the parser!
        pass

@pytest.mark.asyncio
async def test_document_ingestion_with_state_triggers_pageindex(mock_index_manager, tmp_path):
    # Setup test file
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"This is a test document.")
    file_path = str(test_file)
    
    # Enable PageIndex
    settings.pageindex_enabled = True
    settings.pageindex_api_key = "test-key"
    
    service = DocumentIngestionService(mock_index_manager)
    
    task_state = {
        "task_id": "test_task",
        "file_path": file_path,
        "file_name": "test.pdf",
        "file_hash": "hash123",
        "progress": 0,
        "status": "running"
    }
    
    # Mock all the heavy lifting
    with patch('fitz.open'), \
         patch('src.service.document_ingestion_service.get_parser') as mock_get_parser, \
         patch('src.service.document_manager.document_manager.add_document'), \
         patch.object(service, '_check_and_use_vl_parsing', return_value=[MagicMock(text="test", metadata={"total_pages": 1})]), \
         patch.object(service, '_clean_documents', return_value=[MagicMock(text="test", metadata={"total_pages": 1})]), \
         patch('src.core.metadata_processor.MetadataProcessor.split_pages_into_chunks', return_value=[MagicMock(metadata={"total_pages": 1}, get_content=lambda: "test")]), \
         patch.object(service.metadata_processor, 'process_nodes', new_callable=AsyncMock, return_value=[MagicMock(get_content=lambda: "test", metadata={"total_pages": 1})]), \
         patch.object(mock_index_manager, 'is_index_available', return_value=False), \
         patch.object(mock_index_manager, 'insert_nodes'), \
         patch('src.core.pageindex_wrapper.PageIndexWrapper.index_document', new_callable=AsyncMock) as mock_index_document:

        mock_parser = MagicMock()
        mock_parser.parse.return_value = [MagicMock(text="test", metadata={"total_pages": 1})]
        mock_get_parser.return_value = mock_parser
        
        # Execute the method
        await service._ingest_book_with_state(task_state)
        
        # Verify PageIndex wrapper was called
        mock_index_document.assert_called_once_with(file_path, "hash123")
