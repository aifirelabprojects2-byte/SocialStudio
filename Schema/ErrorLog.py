from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class ErrorLogResponse(BaseModel):
    error_id: str
    task_id: Optional[str] = None
    platform_id: Optional[str] = None
    attempt_id: Optional[str] = None
    error_type: Optional[str] = None
    error_code: Optional[str] = None
    message: Optional[str] = None
    details: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True  

class ErrorLogListResponse(BaseModel):
    error_logs: List[ErrorLogResponse]
    total: int
    limit: int
    offset: int
