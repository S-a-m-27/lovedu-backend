from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class FileUploadResponse(BaseModel):
    id: str
    assistant_id: str
    file_name: str
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    uploaded_at: datetime
    uploaded_by: str
    file_type: Optional[str] = "content"  # 'behavior' or 'content'
    openai_file_id: Optional[str] = None  # OpenAI file ID for reuse

class FileListResponse(BaseModel):
    files: list[FileUploadResponse]
    total: int

