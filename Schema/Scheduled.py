
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from Database import AttemptStatus, TaskStatus

class TaskStatusFilter(str, Enum):
    scheduled = "scheduled"
    posted = "posted"
    failed = "failed"
    cancelled = "cancelled"

class Pagination(BaseModel):
    limit: int = Field(..., ge=1, le=100, description="Number of items per page")
    offset: int = Field(0, ge=0, description="Offset for pagination")

class TaskListResponse(BaseModel):
    tasks: List[dict]
    total: int
    limit: int
    offset: int
    
class ErrorLogListResponse(BaseModel):
    error_logs: List[dict]
    total: int
    limit: int
    offset: int


class PlatformOut(BaseModel):
    platform_id: str
    api_name: str
    api_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class TaskOut(BaseModel):
    task_id: str
    organization_id: Optional[str]
    title: Optional[str]
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    scheduled_at: Optional[datetime]
    time_zone: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True


class PostAttemptOut(BaseModel):
    attempt_id: str
    task_id: Optional[str]
    platform_id: Optional[str]
    platform: Optional[PlatformOut]
    attempted_at: datetime
    status: AttemptStatus
    response: Optional[Dict]
    latency_ms: Optional[int]
    error_log_id: Optional[str]

    class Config:
        from_attributes = True

class ErrorLogOut(BaseModel):
    error_id: str
    task_id: Optional[str]
    platform_id: Optional[str]
    attempt_id: Optional[str]
    error_type: Optional[str]
    error_code: Optional[str]
    message: Optional[str]
    details: Optional[Dict]
    created_at: datetime

    class Config:
        from_attributes = True

class TaskDetailOut(BaseModel):
    task: TaskOut
    post_attempts: List[PostAttemptOut]
    error_logs: List[ErrorLogOut]
    
    image_url: Optional[str] = None
    caption: Optional[str] = None
    caption_with_hashtags: Optional[str] = None
    
    class Config:
        from_attributes = True

