import os
import shutil
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from src.service.rag_service import rag_service

router = APIRouter(prefix="/rag", tags=["RAG"])

UPLOAD_DIR = "./temp_uploads"

# Ensure upload directory exists
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@router.post("/upload")
async def upload_book(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    上传书籍文件（PDF/EPUB）并进行 RAG 索引。
    """
    if not (file.filename.endswith(".pdf") or file.filename.endswith(".epub")):
        raise HTTPException(status_code=400, detail="Only PDF and EPUB files are supported currently.")
    
    # Generate a unique filename to avoid collisions
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    try:
        # Save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Process ingestion
        # Note: Depending on file size, this might take time. 
        # For very large files, this should be a background task.
        # Here we do it in the request loop for simplicity/feedback, 
        # or use BackgroundTasks if we want to return immediately.
        # Given "ingest_book" is async, let's await it to provide immediate feedback on success/failure.
        
        await rag_service.ingest_book(file_path)
        
        # Clean up temp file
        background_tasks.add_task(os.remove, file_path)
        
        return {
            "status": "success", 
            "filename": file.filename, 
            "message": "File uploaded and indexed successfully."
        }
        
    except Exception as e:
        # Clean up if failed
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

@router.get("/status")
async def get_rag_status():
    """
    获取 RAG 服务状态
    """
    return {
        "index_ready": rag_service.index is not None,
        "storage_dir": os.path.abspath("./storage")
    }
