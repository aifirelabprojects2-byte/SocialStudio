from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, field_validator, ValidationError
from ImgGen import ImageGenClient
import PostGen,ManagePlatform
from celery_app import Capp
import os
import base64
import io
from datetime import datetime
from typing import List, Optional, Literal
from pathlib import Path
from enum import Enum
from fastapi import FastAPI, Form, Query, Request, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import json
from Database import AttemptStatus, ErrorLog, OAuthToken, Platform, PostAttempt, PublishStatus, TaskStatus, get_db, init_db, Task, GeneratedContent, Media, PlatformSelection
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, update, delete,desc
from sqlalchemy.orm import selectinload,joinedload
from fastapi.responses import StreamingResponse

load_dotenv()

image_client = ImageGenClient(api_key=os.getenv("IMG_API_KEY"))   

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Set OPENAI_API_KEY in .env")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount media folder for serving images
media_dir = Path("static/media")
media_dir.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory="static/media"), name="media")

templates = Jinja2Templates(directory="templates")


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok"}

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


PostGen.init(app)    
ManagePlatform.init(app)



import pytz
from tasks import execute_posting 

execute_posting = Capp.tasks["tasks.execute_posting"]
execute_posting = Capp.task(name="tasks.execute_posting")(execute_posting)

ist = pytz.timezone("Asia/Kolkata")

class ScheduleTaskRequest(BaseModel):
    task_id: str
    platform_ids: List[str]
    scheduled_at: datetime  
    notes: Optional[str] = None

@app.post("/schedule-task", response_model=dict)
async def schedule_task(
    request: ScheduleTaskRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:

    if request.scheduled_at.tzinfo is None:
        request.scheduled_at = ist.localize(request.scheduled_at)
    else:
        # Ensure it's IST
        request.scheduled_at = request.scheduled_at.astimezone(ist)

    # Get and validate task
    stmt = select(Task).options(selectinload(Task.generated_contents)).where(Task.task_id == request.task_id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in (TaskStatus.draft, TaskStatus.draft_approved):
        raise HTTPException(status_code=400, detail="Task must be in draft or draft_approved status")
    if not task.generated_contents:
        raise HTTPException(status_code=400, detail="Task must have generated content")

    # Update task
    task.status = TaskStatus.scheduled
    task.scheduled_at = request.scheduled_at
    task.time_zone = "Asia/Kolkata"
    task.notes = request.notes
    task.updated_at = datetime.now(ist) 

    # Validate and create platform selections
    existing_platforms = set()
    for platform_id in request.platform_ids:
        if platform_id in existing_platforms:
            raise HTTPException(status_code=400, detail="Duplicate platform selected")
        existing_platforms.add(platform_id)

        platform = await db.get(Platform, platform_id)
        if not platform:
            raise HTTPException(status_code=404, detail=f"Platform {platform_id} not found")

        # Check unique constraint (optional, DB will enforce)
        existing_sel = await db.execute(
            select(PlatformSelection).where(
                PlatformSelection.task_id == task.task_id,
                PlatformSelection.platform_id == platform_id
            )
        )
        if existing_sel.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Platform {platform_id} already selected for task")

        sel = PlatformSelection(
            task_id=task.task_id,
            platform_id=platform_id,
            publish_status=PublishStatus.scheduled,
            scheduled_at=request.scheduled_at,
        )
        db.add(sel)

    await db.commit()
    await db.refresh(task)  # Optional

    # Schedule Celery task (eta in UTC)
    scheduled_utc = request.scheduled_at.astimezone(pytz.UTC)
    execute_posting.apply_async(args=(task.task_id,), eta=scheduled_utc)

    return {
        "message": "Task scheduled successfully",
        "task_id": task.task_id,
        "scheduled_at": request.scheduled_at.isoformat(),
        "platforms": len(request.platform_ids),
    }



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


from sqlalchemy.orm import selectinload
from sqlalchemy import select, desc
from fastapi import HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
#
class PlatformOut(BaseModel):
    platform_id: str
    name: str
    api_name: Optional[str]
    meta: Optional[Dict]
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


@app.get("/api/tasks-scheduled", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[TaskStatusFilter] = Query(None, description="Filter by specific status (scheduled, posted, failed, cancelled)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    query = select(Task).order_by(desc(Task.created_at))

    if status is None:
        query = query.where(Task.status.in_([TaskStatus.scheduled, TaskStatus.posted, TaskStatus.failed, TaskStatus.cancelled]))
    else:
        query = query.where(Task.status == TaskStatus[status])

    count_query = select(func.count(Task.task_id)).where(query.whereclause)
    total_result = await db.execute(count_query)
    total = total_result.scalar_one_or_none() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    tasks = result.scalars().all()

    # Extract only mapped columns to dict, excluding internal state
    task_dicts = []
    for task in tasks:
        task_dict = {column.name: getattr(task, column.name) for column in Task.__table__.columns}
        task_dicts.append(task_dict)
    
    return TaskListResponse(tasks=task_dicts, total=total, limit=limit, offset=offset)

@app.get("/view/tasks-scheduled/{task_id}", response_model=TaskDetailOut)
async def get_task_detail(task_id: str, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Task)
        .options(
            selectinload(Task.generated_contents),
            selectinload(Task.media),
            selectinload(Task.platform_selections).selectinload(PlatformSelection.platform),
            selectinload(Task.post_attempts).selectinload(PostAttempt.platform),
        )
        .where(Task.task_id == task_id)
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Fetch error logs separately (no relationship, so kept simple)
    error_stmt = (
        select(ErrorLog)
        .where(ErrorLog.task_id == task_id)
        .order_by(desc(ErrorLog.created_at))
    )
    error_result = await db.execute(error_stmt)
    error_logs = error_result.scalars().all()

    return TaskDetailOut(
        task=TaskOut.model_validate(task),
        post_attempts=[PostAttemptOut.model_validate(pa) for pa in task.post_attempts],
        error_logs=[ErrorLogOut.model_validate(el) for el in error_logs],
    )


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

@app.get("/error-logs", response_model=ErrorLogListResponse)
async def list_error_logs(
    from_date: Optional[datetime] = Query(None, description="Filter from this date (YYYY-MM-DDTHH:MM:SS)"),
    to_date: Optional[datetime] = Query(None, description="Filter up to this date (YYYY-MM-DDTHH:MM:SS)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):

    query = select(ErrorLog).order_by(desc(ErrorLog.created_at))


    if from_date:
        query = query.where(ErrorLog.created_at >= from_date)
    if to_date:
        query = query.where(ErrorLog.created_at <= to_date)

    # Total count
    count_query = select(func.count(ErrorLog.error_id)).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0


    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    error_logs = result.scalars().all()

    return ErrorLogListResponse(
        error_logs=error_logs,  
        total=total,
        limit=limit,
        offset=offset
    )
    

class FormatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000, description="The text to format")
    style: Optional[Literal["professional", "concise", "formal"]] = Field(
        None, description="Predefined style (optional if custom_instruction is used)"
    )
    custom_instruction: Optional[str] = Field(
        None,
        max_length=1000,
        description="Custom formatting instructions. If provided, overrides 'style'."
    )

    @field_validator("custom_instruction")
    @classmethod
    def validate_custom_instruction(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) < 5:
                raise ValueError("custom_instruction must be at least 5 characters long")
        return v

    @field_validator("style")
    @classmethod
    def validate_style_with_custom(cls, v: Optional[str], info):
        # This runs after all fields are parsed
        values = info.data
        custom = values.get("custom_instruction")
        if v is None and (custom is None or custom.strip() == ""):
            raise ValueError("Either 'style' or 'custom_instruction' must be provided")
        return v


PREDEFINED_STYLES = {
    "professional": "Rewrite in clear, polished, professional business tone. Keep it natural and confident.",
    "concise": "Make it significantly shorter while keeping all key information. Be direct and crisp.",
    "formal": "Use formal language suitable for official letters or academic writing. Avoid contractions.",
}


async def generate_formatted_text_stream(text: str, instruction: str):
    system_prompt = (
        "You are an expert editor. "
        "Rewrite the given text exactly according to the user's instruction. "
        "Output ONLY the formatted text — no quotes, no explanations, no markdown, "
        "no headers, no 'Here is...', nothing except the clean final text."
    )

    user_prompt = f"Instruction: {instruction}\n\nText to rewrite:\n{text}"

    try:
        stream = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            stream=True,
            max_tokens=2000,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    except Exception as e:
        error_msg = json.dumps({"error": "Generation failed", "details": str(e)})
        yield error_msg


@app.post("/format-text")
async def format_text(request: FormatRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # Determine instruction
    if request.custom_instruction and request.custom_instruction.strip():
        instruction = request.custom_instruction.strip()
    elif request.style:
        instruction = PREDEFINED_STYLES.get(request.style, PREDEFINED_STYLES["professional"])
    else:
        raise HTTPException(status_code=400, detail="Either 'style' or 'custom_instruction' is required")

    return StreamingResponse(
        generate_formatted_text_stream(request.text, instruction),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Content-Type-Options": "nosniff",
            "Access-Control-Allow-Origin": "*",
        },
    )