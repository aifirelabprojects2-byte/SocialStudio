import asyncio
from decimal import Decimal
from functools import lru_cache
import hashlib
import random
import re
import subprocess
import time
import aiohttp
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, field_validator, ValidationError
import requests
import yt_dlp
from Auth import create_session, get_current_user_from_token, hash_password, invalidate_all_sessions, verify_password
from CostCalc import calculate_llm_cost, count_tokens
from ImgGen import ImageGenClient
import PostGen,ManagePlatform,Referencer,ManageTheme,UsageTracker
import os
from datetime import datetime
from typing import List, AsyncGenerator, Dict, Any, Annotated, Optional, Literal, Tuple
from pathlib import Path
from enum import Enum
from fastapi import Body, Cookie, FastAPI, Form, Query, Request, Depends, HTTPException, logger, status, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
import json
from Database import AsyncSessionLocal, AttemptStatus, ErrorLog, LLMUsage, LoginSession, OAuthToken, Platform, PostAttempt, PublishStatus, TaskStatus, User, gen_uuid_str, get_db, init_db, Task, GeneratedContent, Media, PlatformSelection
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, update, delete,desc
from sqlalchemy.orm import selectinload,joinedload
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from werkzeug.utils import secure_filename
from PIL import Image
import unicodedata
import pytz
from urllib.parse import urlparse
import itertools
from gallery_dl import config, job
import instaloader
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


load_dotenv()
GPT_MODEL="gpt-4o-mini"
image_client = ImageGenClient(api_key=os.getenv("IMG_API_KEY"))   
IMG_BB_API_KEY = os.getenv('IMGBB_API')
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Set OPENAI_API_KEY in .env")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.exception_handler(401)
async def auth_exception_handler(request: Request, exc: HTTPException):
    return RedirectResponse(url="/login")

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    session_token: Optional[str] = Cookie(None, alias="session_token")
):
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = await get_current_user_from_token(db, session_token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    return user

@app.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    message: Optional[str] = None,
    session_token: Optional[str] = Cookie(None, alias="session_token")
):
    if session_token:
        async with AsyncSessionLocal() as db:
            user = await get_current_user_from_token(db, session_token)
            if user:
                return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "message": message}
    )
@app.post("/login")
async def login_post(
    request: Request,
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.is_active == True))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid password"}, status_code=400)

    token = await create_session(
        db=db,
        user_id=user.user_id,
        ip=request.client.host,
        ua=str(request.headers.get("user-agent")),
        days=30
    )
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=True,         
        samesite="lax",
        max_age=30*24*60*60   # 30 days
    )
    return response

@app.post("/logout")
async def logout(
    db: AsyncSession = Depends(get_db),
    session_token: Optional[str] = Cookie(None, alias="session_token")
):
    if session_token:
        await db.execute(delete(LoginSession).where(LoginSession.token == session_token))
        await db.commit()
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_token")
    return response

@app.post("/logout-all")
async def logout_all_devices(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await invalidate_all_sessions(db, user.user_id)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_token")
    return response

@app.post("/change-password")
async def change_password(
    old_password: str = Form(...),
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not verify_password(old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Old password incorrect")
    if new_password != new_password_confirm:
        raise HTTPException(status_code=400, detail="New passwords do not match")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="New password too short")

    user.password_hash = hash_password(new_password)
    await invalidate_all_sessions(db, user.user_id)
    await db.commit()

    # Force re-login
    response = JSONResponse({"detail": "Password changed successfully. Please log in again."})
    response.delete_cookie("session_token")
    return response

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/setting", response_class=HTMLResponse)
async def settings(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request})

PostGen.init(app)    
ManagePlatform.init(app)
ManageTheme.init(app)
Referencer.init(app)
UsageTracker.init(app)


from tasks import execute_posting 
from celery_app import celery_app

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
        request.scheduled_at = request.scheduled_at.astimezone(ist)
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
    await db.refresh(task)
    scheduled_utc = request.scheduled_at.astimezone(pytz.UTC)
    execute_posting.apply_async(args=(task.task_id,), eta=scheduled_utc)  # Use directly
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
    
    image_url: Optional[str] = None
    caption: Optional[str] = None
    caption_with_hashtags: Optional[str] = None
    
    class Config:
        from_attributes = True


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
            selectinload(Task.generated_contents).selectinload(GeneratedContent.media),
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

    # Error logs
    error_result = await db.execute(
        select(ErrorLog)
        .where(ErrorLog.task_id == task_id)
        .order_by(desc(ErrorLog.created_at))
    )
    error_logs = error_result.scalars().all()

    image_url: str | None = None

    for m in task.media:
        if m.img_url:
            image_url = m.img_url
            break

    if not image_url:
        for gc in task.generated_contents:
            for m in gc.media:
                if m.img_url:
                    image_url = m.img_url
                    break
            if image_url:
                break

    print(image_url)
    caption: str | None = None
    caption_with_hashtags: str | None = None

    if task.generated_contents:
        latest = max(task.generated_contents, key=lambda x: x.created_at)
        caption = latest.caption
        hashtags = latest.hashtags or []

        if caption:
            if hashtags:
                tags_str = " ".join(f"#{tag.strip('# ')}" for tag in hashtags if tag)
                caption_with_hashtags = f"{caption.strip()} {tags_str}".strip()
            else:
                caption_with_hashtags = caption.strip()

    return TaskDetailOut(
        task=TaskOut.model_validate(task),
        post_attempts=[PostAttemptOut.model_validate(pa) for pa in task.post_attempts],
        error_logs=[ErrorLogOut.model_validate(el) for el in error_logs],
        image_url=image_url,                   
        caption=caption,
        caption_with_hashtags=caption_with_hashtags,
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


async def generate_formatted_text_stream(text: str, instruction: str,db: AsyncSession):
    system_prompt = (
        "You are an expert editor. "
        "Rewrite the given text exactly according to the user's instruction. "
        "Output ONLY the formatted text — no quotes, no explanations, no markdown, "
        "no headers, no 'Here is...', nothing except the clean final text."
    )

    user_prompt = f"Instruction: {instruction}\n\nText to rewrite:\n{text}"
    input_text = user_prompt+system_prompt
    input_tokens = count_tokens(input_text,GPT_MODEL)
    output_tokens = 0
    generated_text = []
    start = time.time()
    strm_status = "success"
    try:
        stream = await client.chat.completions.create(
            model=GPT_MODEL,
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
                text = chunk.choices[0].delta.content
                yield text
                output_tokens += count_tokens(text,GPT_MODEL)
                generated_text.append(text)
                
    except Exception as e:
        strm_status = "failed"
        error_msg = json.dumps({"error": "Generation failed", "details": str(e)})
        yield error_msg
        
    finally:
        latency_ms = int((time.time() - start) * 1000)
        total_cost = calculate_llm_cost(
            model=GPT_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        db.add(LLMUsage(
            feature="text_formating",
            model=GPT_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=total_cost,
            latency_ms=latency_ms,
            status=strm_status,
        ))
        await db.commit()

@app.post("/format-text")
async def format_text(request: FormatRequest,db: AsyncSession = Depends(get_db)):
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
        generate_formatted_text_stream(request.text, instruction,db),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Content-Type-Options": "nosniff",
            "Access-Control-Allow-Origin": "*",
        },
    )



DOWNLOADS_DIR = Path("./downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)
INSTALOADER_AVAILABLE = True
FFMPEG_AVAILABLE = False

try:
    subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    FFMPEG_AVAILABLE = True
except (subprocess.CalledProcessError, FileNotFoundError):
    print("FFmpeg not available")

class DownloadRequest(BaseModel):
    url: str
    quality: Optional[str] = "best"
    audio_only: Optional[bool] = False

class ImageConfig:
    INSTAGRAM_RATE_LIMIT_DELAY_MIN = 1.0
    INSTAGRAM_RATE_LIMIT_DELAY_MAX = 3.0
    INSTAGRAM_RETRY_ATTEMPTS = 5
    AIOHTTP_TIMEOUT = 60
    CHUNK_SIZE = 1024 * 1024

HEADERS_CYCLE = itertools.cycle([
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.instagram.com/"},
    {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.instagram.com/"},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"},
])

def get_headers() -> dict:
    return next(HEADERS_CYCLE)

def detect_platform(url: str) -> str:
    if "youtube.com" in url or "youtu.be" in url:
        return "YouTube"
    elif "instagram.com" in url:
        return "Instagram"
    elif "facebook.com" in url or "fb.watch" in url:
        return "Facebook"
    elif "tiktok.com" in url:
        return "TikTok"
    elif "twitter.com" in url or "x.com" in url:
        return "Twitter/X"
    elif "reddit.com" in url:
        return "Reddit"
    elif "vimeo.com" in url:
        return "Vimeo"
    elif "twitch.tv" in url:
        return "Twitch"
    else:
        return "Unknown"

def is_x_url(url: str) -> bool:
    domain = urlparse(url).netloc.lower()
    return "x.com" in domain or "twitter.com" in domain

def is_instagram_url(url: str) -> bool:
    domain = urlparse(url).netloc.lower()
    return "instagram.com" in domain

def slugify_filename(text: str, max_length: int = 100) -> str:
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', text)
    text = re.sub(r'[\[\](){}]', '', text)
    text = re.sub(r'[^\w\s\-.£€$!&+]', '', text)
    text = re.sub(r'\s+', '_', text)
    text = re.sub(r'_+', '_', text)
    text = text.strip('_.- ')
    
    if not text:
        text = "media"
    
    if len(text) > max_length:
        text = text[:max_length]
    
    return text

async def download_x_images(url: str) -> Tuple[str, list]:

    loop = asyncio.get_event_loop()
    
    def _sync_download():
        old_files = set(str(f) for f in DOWNLOADS_DIR.rglob("*"))
        config.set(("extractor", "twitter"), "videos", False)
        config.set((), "base-directory", str(DOWNLOADS_DIR))
        download_job = job.DownloadJob(url)
        download_job.run()
        new_files = [f for f in DOWNLOADS_DIR.rglob("*") if f.is_file() and str(f) not in old_files]
        
        moved_files = []
        for f in new_files:
            dest_name = f.name
            dest = DOWNLOADS_DIR / dest_name
            counter = 1
            while dest.exists():
                if '.' in dest_name:
                    name, ext = dest_name.rsplit('.', 1)
                    dest_name = f"{name}_{counter}.{ext}"
                else:
                    dest_name = f"{dest_name}_{counter}"
                dest = DOWNLOADS_DIR / dest_name
                counter += 1
            f.rename(dest)
            moved_files.append(dest)
        
        return moved_files
    
    downloaded_files = await loop.run_in_executor(None, _sync_download)
    
    return "success", downloaded_files

# Instagram image downloader
def extract_instagram_shortcode(url: str) -> str:
    url = url.split('?')[0].rstrip('/')
    match = re.search(r'/p/([A-Za-z0-9_-]{11})', url) or re.search(r'/reel/([A-Za-z0-9_-]{11})', url)
    if match:
        return match.group(1)
    raise ValueError("Invalid Instagram URL")

if INSTALOADER_AVAILABLE:
    @retry(
        stop=stop_after_attempt(ImageConfig.INSTAGRAM_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((
            instaloader.exceptions.ConnectionException,
            instaloader.exceptions.QueryReturnedNotFoundException
        ))
    )
    async def fetch_instagram_post(shortcode: str) -> Optional[instaloader.Post]:
        loop = asyncio.get_event_loop()
        
        def _sync_fetch():
            L = instaloader.Instaloader(
                dirname_pattern=str(DOWNLOADS_DIR),
                filename_pattern="{shortcode}_{date_utc}",
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                compress_json=False,
                post_metadata_txt_pattern="",
                request_timeout=30,
            )
            session = L.context._session
            session.headers.update(get_headers())
            return instaloader.Post.from_shortcode(L.context, shortcode)
        
        return await loop.run_in_executor(None, _sync_fetch)

async def download_single_image(image_url: str, filename: str):
    timeout = aiohttp.ClientTimeout(total=ImageConfig.AIOHTTP_TIMEOUT)
    async with aiohttp.ClientSession(headers=get_headers(), timeout=timeout) as session:
        async with session.get(image_url) as resp:
            if resp.status == 200:
                ext = image_url.split('?')[0].split('.')[-1]
                if len(ext) > 4:
                    ext = "jpg"
                filepath = DOWNLOADS_DIR / f"{filename}.{ext}"
                counter = 1
                while filepath.exists():
                    if '.' in str(filepath.name):
                        name, e = str(filepath.name).rsplit('.', 1)
                        new_name = f"{name}_{counter}.{e}"
                    else:
                        new_name = f"{str(filepath.name)}_{counter}"
                    filepath = DOWNLOADS_DIR / new_name
                    counter += 1
                with open(filepath, "wb") as f:
                    async for chunk in resp.content.iter_chunked(ImageConfig.CHUNK_SIZE):
                        f.write(chunk)
                return str(filepath)
    return None

async def download_instagram_images(url: str) -> Tuple[str, list]:
    try:
        shortcode = extract_instagram_shortcode(url)
        post = await fetch_instagram_post(shortcode)
        
        if not post:
            raise HTTPException(status_code=400, detail="Failed to fetch Instagram post")
        
        # NEW: Detect if this is a video post or has video content – fallback to yt-dlp if so
        is_video_post = False
        if post.typename == 'GraphVideo':
            is_video_post = True
        elif post.typename == 'GraphSidecar':
            # Check nodes for any video
            for node in post.get_sidecar_nodes():
                if node.is_video:
                    is_video_post = True
                    break
        
        if is_video_post:
            # Raise to trigger fallback to yt-dlp (videos/reels work better there)
            raise ValueError("Instagram video/reel detected – routing to video downloader")
        
        downloaded_files = []
        tasks = []
        
        if post.typename == 'GraphSidecar':
            for idx, node in enumerate(post.get_sidecar_nodes()):
                if not node.is_video:  # Already skips videos, but now we caught above
                    tasks.append(download_single_image(
                        node.display_url,
                        f"{shortcode}_{idx}"
                    ))
        elif post.typename == 'GraphImage':
            tasks.append(download_single_image(
                post.url,
                f"{shortcode}_0"
            ))
        
        if tasks:
            results = await asyncio.gather(*tasks)
            downloaded_files = [f for f in results if f]
        
        await asyncio.sleep(random.uniform(
            ImageConfig.INSTAGRAM_RATE_LIMIT_DELAY_MIN,
            ImageConfig.INSTAGRAM_RATE_LIMIT_DELAY_MAX
        ))
        
        if not downloaded_files:
            raise ValueError("No images found in post – may be video-only")
        
        return "success", downloaded_files
        
    except ValueError as ve:  # NEW: Re-raise ValueError for fallback (video or empty)
        if "video" in str(ve).lower() or "no images" in str(ve).lower():
            raise  # Triggers endpoint fallback to yt-dlp
        raise HTTPException(status_code=500, detail=f"Instagram fetch failed: {str(ve)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Instagram image download failed: {str(e)}")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
]

REFERERS = [
    "https://www.youtube.com/",
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://www.youtube.com/results?search_query=music",
    "https://www.youtube.com/feed/trending",
]

LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-US,en;q=0.8",
    "de-DE,de;q=0.9,en;q=0.8",
    "fr-FR,fr;q=0.9,en;q=0.8",
]

def get_random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": random.choice(REFERERS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": random.choice(LANGUAGES),
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
    }

def get_ydl_format(quality: str, audio_only: bool) -> dict:
    base_formats = {
        "best": "best",
        "720p": "best[height<=720]",
        "1080p": "best[height<=1080]",
        "4k": "best[height<=2160]"
    }
    
    if audio_only:
        if FFMPEG_AVAILABLE:
            return {"format": "bestaudio/best", "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]}
        else:
            return {"format": "bestaudio[ext=m4a]/bestaudio"}
    
    fmt = base_formats.get(quality, "best")
    if FFMPEG_AVAILABLE:
        return {"format": f"{fmt}+bestaudio/best" if not audio_only else "bestaudio/best"}
    else:
        return {"format": f"{fmt}[ext=mp4]/{fmt}"}

async def download_video(url: str, quality: str, audio_only: bool) -> Tuple[str, list, list]:
    loop = asyncio.get_event_loop()

    base_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 20,
        "fragment_retries": 20,
        "extractor_retries": 10,
        "sleep_interval": 3,
        "max_sleep_interval": 15,
        "http_headers": get_random_headers(),
        "geo_bypass": True,
        "concurrent_fragment_downloads": 3,
        "continuedl": True,
        "retries_sleep": 5,
        "extractor_args": {
            "youtube": {
                "player_client": "android",
                "player_skip": ["webpage", "configs"],
                "skip": ["dash"]
            }
        },
    }

    cookies_path = Path("cookies.txt")
    if cookies_path.exists():
        base_opts["cookiefile"] = str(cookies_path)
    else:
        try:
            base_opts["cookiefile"] = yt_dlp.utils.browser_cookie_file()
        except:
            pass

    with yt_dlp.YoutubeDL(base_opts) as ydl:
        info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))

    if not info:
        raise HTTPException(status_code=400, detail="Failed to extract video info")

    raw_title = info.get("title", "video")
    vid_id = info.get("id", "unknown")[:11]
    safe_title = slugify_filename(raw_title, max_length=90)
    final_base = f"{safe_title}_{vid_id}"

    ext = "mp3" if audio_only and FFMPEG_AVAILABLE else "m4a" if audio_only else "mp4"
    final_filename = f"{final_base}.{ext}"
    filepath = DOWNLOADS_DIR / final_filename

    download_opts = base_opts.copy()
    download_opts.update({
        "format": get_ydl_format(quality, audio_only)["format"],
        "outtmpl": str(filepath.with_suffix(".%(ext)s")),
        "merge_output_format": "mp4" if not audio_only and FFMPEG_AVAILABLE else None,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }] if audio_only and FFMPEG_AVAILABLE else [],
        "http_headers": get_random_headers(),
    })

    try:
        with yt_dlp.YoutubeDL(download_opts) as ydl:
            await loop.run_in_executor(None, lambda: ydl.download([url]))
        
        if not filepath.exists():
            matches = list(DOWNLOADS_DIR.glob(f"{final_base}.*"))
            if matches:
                matches[0].rename(filepath)

        file_paths = [str(filepath)]
        file_names = [final_filename]
        return "success", file_paths, file_names

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Sign in to confirm you're not a bot" in error_msg:
            raise HTTPException(status_code=429, detail="Bot detection triggered. Update your cookies.txt")
        if "Private video" in error_msg or "unavailable" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Video is private or region-locked")
        raise HTTPException(status_code=500, detail=f"Download failed: {error_msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/download", response_model=dict)
async def download_endpoint(request: DownloadRequest = Body(...)):
    platform = detect_platform(request.url)

    if is_x_url(request.url):
        try:
            status, file_paths, file_names = await download_video(request.url, request.quality, request.audio_only)
            download_urls = [f"/downloads/{name}" for name in file_names]
            
            return {
                "status": status,
                "platform": "Twitter/X (Video)",
                "download_method": "yt-dlp",
                "download_url": download_urls,
                "file_paths": file_paths,
                "files": file_names,
                "file_count": len(file_paths),
                "message": f"Downloaded to {file_paths[0]} ({'MP3' if request.audio_only and FFMPEG_AVAILABLE else 'M4A/MP4'})"
            }
        except Exception as e:
            print(f"X video download failed, trying images: {e}")
            try:
                status, files = await download_x_images(request.url)
                file_paths = [str(f) for f in files]
                file_names = [f.name for f in files]
                download_urls = [f"/downloads/{name}" for name in file_names]
                return {
                    "status": status,
                    "platform": "Twitter/X (Images)",
                    "download_method": "gallery-dl",
                    "download_url": download_urls,
                    "file_paths": file_paths,
                    "files": file_names,
                    "file_count": len(files),
                    "message": f"Downloaded {len(files)} image(s) from X/Twitter"
                }
            except Exception as img_error:
                raise HTTPException(status_code=500, detail=f"Failed to download from X: Video error: {str(e)}, Image error: {str(img_error)}")
    

    if is_instagram_url(request.url):
        try:
            status, files = await download_instagram_images(request.url)
            file_paths = [f for f in files if f]  # already str
            file_names = [Path(f).name for f in file_paths]
            download_urls = [f"/downloads/{name}" for name in file_names]
            return {
                "status": status,
                "platform": "Instagram (Images)",
                "download_method": "instaloader",
                "download_url": download_urls,
                "file_paths": file_paths,
                "files": file_names,
                "file_count": len(file_paths),
                "message": f"Downloaded {len(file_paths)} image(s) from Instagram"
            }
        except ValueError as ve:  # NEW: Catch video/empty cases explicitly
            print(f"Instagram images skipped (video detected): {ve} – falling back to yt-dlp")
        except Exception as e:
            print(f"Instagram images failed, falling back to yt-dlp: {e}")
        # Fall through to yt-dlp below
    
    # Use yt-dlp for other platforms or as fallback
    try:
        status, file_paths, file_names = await download_video(request.url, request.quality, request.audio_only)
        download_urls = [f"/downloads/{name}" for name in file_names]
        
        return {
            "status": status,
            "platform": platform,
            "download_method": "yt-dlp",
            "download_url": download_urls,
            "file_paths": file_paths,
            "files": file_names,
            "file_count": len(file_paths),
            "message": f"Downloaded to {file_paths[0]} ({'MP3' if request.audio_only and FFMPEG_AVAILABLE else 'M4A/MP4'})"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
    
import logging

logger = logging.getLogger(__name__)

DEFAULT_CONCURRENT_LIMIT = 5
DEFAULT_RPM = 60
CACHE_TTL_SECONDS = 86400
API_TIMEOUT = 30.0
MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 10.0
SEARCH_IMAGE_LIMIT = 3
SEARCH_NUM_RESULTS = 5
DEEP_RESEARCH_NUM_RESULTS = 10

perplexity_client = AsyncOpenAI(
    api_key=os.getenv("PERPLEXITY_API_KEY"),
    base_url="https://api.perplexity.ai"
)

class AsyncRateLimiter:
    def __init__(self, concurrent_limit: int = DEFAULT_CONCURRENT_LIMIT, rpm: int = DEFAULT_RPM):
        self.semaphore = asyncio.Semaphore(concurrent_limit)
        self.rpm = rpm
        self.tokens = rpm
        self.last_refill = time.time()
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def acquire(self):
        async with self.semaphore:
            async with self.lock:
                now = time.time()
                elapsed = now - self.last_refill
                self.tokens = min(self.rpm, self.tokens + (elapsed / 60) * self.rpm)
                self.last_refill = now
                
                while self.tokens < 1:
                    await asyncio.sleep(60 / self.rpm)
                    now = time.time()
                    elapsed = now - self.last_refill
                    self.tokens = min(self.rpm, self.tokens + (elapsed / 60) * self.rpm)
                    self.last_refill = now
                
                self.tokens -= 1


from functools import lru_cache
@lru_cache(maxsize=1)
def get_rate_limiter() -> AsyncRateLimiter:
    concurrent = int(os.getenv("RATE_LIMIT_CONCURRENT", DEFAULT_CONCURRENT_LIMIT))
    rpm = int(os.getenv("RATE_LIMIT_RPM", DEFAULT_RPM))
    return AsyncRateLimiter(concurrent, rpm)


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    return AsyncOpenAI(api_key=api_key)


async def retry_on_failure(coro_func, max_retries: int = MAX_RETRIES, base_delay: float = BASE_DELAY, max_delay: float = MAX_DELAY):
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await coro_func()
        except Exception as e:
            last_exception = e
            if attempt == max_retries:
                raise
            
            delay = min(base_delay * (2 ** attempt) + (time.time() % 1.0), max_delay)
            await asyncio.sleep(delay)
    
    raise last_exception


conversation_memory: Dict[str, List[str]] = {}

def _normalize_key(product_company: str) -> str:
    return "".join(c.lower() for c in product_company if c.isalnum())


async def validate_and_extract(
    product_company: str,
    clarification: Optional[str] = None,
    client: AsyncOpenAI = Depends(get_openai_client),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    key = _normalize_key(product_company)
    print(product_company, clarification)
    if key not in conversation_memory:
        conversation_memory[key] = []
    accumulated_clarifications = " ".join(conversation_memory[key])
    context_part = f"\nPrevious clarifications provided: \"{accumulated_clarifications}\"" if accumulated_clarifications else ""
    clarif_part = f"\nUser clarification: '{clarification}'." if clarification else ""
   
    system_prompt = (
        "You are a precise input validator and extractor for product reviews. Your task is to identify the main product and its company from user input, "
        "handling natural language, variations, models (e.g., 'iPhone 16'), comparisons, and contextual descriptions.\n\n"
        "Key Rules:\n"
        "- Be flexible but decisive: Infer company confidently for well-known products (e.g., iPhone/Galaxy/ChatGPT → Apple/Samsung/OpenAI).\n"
        "- Common inferences (high confidence): iPhone/Mac/Book → Apple; Galaxy/Pixel → Samsung/Google; Maggi → Nestle; Yippee → ITC; ChatGPT/GPT → OpenAI.\n"
        "- For comparisons (e.g., 'compare Maggi and Yippee'), extract the primary/obvious product-company (usually the first mentioned) with high confidence.\n"
        "- Ignore case, fillers ('the', 'from', 'by'), and minor typos.\n"
        "- Always prefer extraction with high confidence if a reasonable product reference exists, even if company is inferred or loosely mentioned.\n"
        "- Only use low confidence + clarification for: greetings/chit-chat ('hi', 'hello'), completely vague inputs ('some gadget'), or truly unknown/niche products without clear context.\n"
        "- Never clarify if a plausible extraction is possible—err strongly toward high confidence for any product-like reference.\n\n"
        "Self-Evaluation Step (think internally first):\n"
        "1. Does the input mention or describe a recognizable product? → If yes, extract + high confidence.\n"
        "2. Can company be reasonably inferred? → If yes, do so.\n"
        "3. Is it purely social/non-product? → If yes, low confidence + clarify.\n"
        "Rate your extraction certainty: high if plausible, low only if impossible.\n\n"
        "Output Format (strict JSON only, no extra text; always include ALL fields):\n"
        "{\n"
        " \"is_valid\": true,\n"
        " \"product\": \"extracted product name (or null)\",\n"
        " \"company\": \"extracted/inferred company (or null)\",\n"
        " \"confidence\": \"high\" or \"low\",\n"
        " \"needs_clarification\": true or false,\n"
        " \"question\": \"helpful clarification question if needs_clarification=true (friendly, specific; else null)\",\n"
        " \"reason\": \"brief explanation of extraction or why clarification needed\"\n"
        "}\n\n"
        "Examples:\n"
        "- Input: 'iPhone' → {\"is_valid\": true, \"product\": \"iPhone\", \"company\": \"Apple\", \"confidence\": \"high\", \"needs_clarification\": false, \"question\": null, \"reason\": \"Direct product reference with inferred company\"}\n"
        "- Input: 'compare maggi and yippee' → {\"is_valid\": true, \"product\": \"Maggi\", \"company\": \"Nestle\", \"confidence\": \"high\", \"needs_clarification\": false, \"question\": null, \"reason\": \"Primary product extracted from comparison\"}\n"
        "- Input: 'latest smartphone from Apple' → {\"is_valid\": true, \"product\": \"iPhone\", \"company\": \"Apple\", \"confidence\": \"high\", \"needs_clarification\": false, \"question\": null, \"reason\": \"Inferred product from description\"}\n"
        "- Input: 'hi there' → {\"is_valid\": true, \"product\": null, \"company\": null, \"confidence\": \"low\", \"needs_clarification\": true, \"question\": \"Hi! What product and company would you like reviewed?\", \"reason\": \"No product reference; greeting only\"}\n"
        "- Input: 'some random thing from unknown corp' → {\"is_valid\": true, \"product\": null, \"company\": null, \"confidence\": \"low\", \"needs_clarification\": true, \"question\": \"What specific product and company are you referring to?\", \"reason\": \"Vague input without identifiable product/company\"}\n"
    )
    user_prompt = f"""Input: "{product_company}"{context_part}{clarif_part}
        Extract the primary product name and company name if identifiable. Assess confidence (high/low). If low, unclear, or no product/company (e.g., greetings, chit-chat), set needs_clarification: true and provide a helpful, model-generated clarifying question tailored to the input (keep it friendly and specific).
        Respond with JSON (always include all fields as in system prompt):
        {{"is_valid": true, "product": "extracted product name or null", "company": "extracted company name or null", "confidence": "high", "needs_clarification": false, "question": null, "reason": "brief explanation"}}"""
    
    model = "gpt-4o-mini"
    input_str = system_prompt + "\n\n" + user_prompt
    input_tokens = count_tokens(input_str, model)
    output_tokens = 0
    usage_status = "success"
    start = time.time()
    response_format = {"type": "json_object"}
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=300,
            response_format=response_format,
        )
        content = response.choices[0].message.content.strip()
        output_tokens = count_tokens(content, model)
        data = json.loads(content)
        result = {
            "is_valid": data.get("is_valid", True),
            "product": data.get("product"),
            "company": data.get("company"),
            "confidence": data.get("confidence", "low"),
            "needs_clarification": data.get("needs_clarification", True),
            "question": data.get("question"),
            "reason": data.get("reason", "")
        }
        if result["confidence"] == "high":
            result["needs_clarification"] = False
            result["question"] = None
        if clarification and clarification.strip() and result["needs_clarification"]:
            conversation_memory[key].append(clarification.strip())
        if result["confidence"] == "high" and not result["needs_clarification"]:
            conversation_memory.pop(key, None)
        return result
    except json.JSONDecodeError as je:
        usage_status = "failed"
        logger.error(f"JSON decode error in validate_and_extract: {je}")
        return {
            "is_valid": True,
            "product": None,
            "company": None,
            "confidence": "low",
            "needs_clarification": True,
            "question": "I'm having trouble understanding that. Could you specify the product name and company more clearly?",
            "reason": f"JSON parse error: {str(je)}"
        }
    except Exception as e:
        usage_status = "failed"
        logger.error(f"Error in validate_and_extract: {e}")
        return {
            "is_valid": True,
            "product": None,
            "company": None,
            "confidence": "low",
            "needs_clarification": True,
            "question": "I'm having trouble identifying the product. Can you tell me the exact product name and company?",
            "reason": f"Error: {str(e)}"
        }
    finally:
        latency_ms = int((time.time() - start) * 1000)
        total_cost = calculate_llm_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        db.add(LLMUsage(
            feature="product_validation",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=total_cost,
            latency_ms=latency_ms,
            status=usage_status,
        ))
        await db.commit()

async def create_perplexity_review_stream(
    product: str,
    company: str,
    clarification: Optional[str],
    custom_filter: Optional[str],
    is_deepresearch_needed: bool,
    perplexity_client: AsyncOpenAI,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    limiter = get_rate_limiter()
    await limiter.acquire()
    if is_deepresearch_needed:
        additional_params ={"search_results": 10}
    else:
        additional_params = {"search_results": 5}
    system_prompt = (
        "You are an expert product analyst. Provide a comprehensive, deep analysis of the product based on web searches. "
        "Always deliver in-depth insights on features, market position, strengths, weaknesses, and incorporate user reviews where available. "
        "Base your analysis on recent, relevant web data WITHOUT EVER citing, mentioning, marking, or listing any sources, references, URLs, or citations in the output. "
        "Structure your output exactly as:\n"
        "# Product Overview\n"
        "A detailed summary of the product, its purpose, and market context.\n\n"
        "# Key Features\n"
        "- Bullet points of main features with descriptions.\n"
        "...\n\n"
        "# Strengths / Pros\n"
        "- In-depth positive aspects, backed by data or examples.\n"
        "...\n\n"
        "# Weaknesses / Cons\n"
        "- In-depth negative aspects, risks, or limitations.\n"
        "...\n\n"
        "# User Sentiment & Reviews\n"
        "Overall sentiment score (e.g., 4.2/5). Summarize key themes from reviews. Include 2-3 notable user quotes or summaries if available.\n\n"
        "Output ONLY this formatted text—no introductions, extra content, citations, sources, or any markings. Use markdown for structure. Aim for depth: 4-6 bullets per section where possible."
    )
    filter_part = f"Focus on: {custom_filter}." if custom_filter else ""
    clarif_part = f"User clarification: {clarification}." if clarification else ""
    user_prompt = f"{filter_part} {clarif_part} Analyze the product '{product}' from '{company}'. Provide the comprehensive product analysis."
    
    model = "sonar"
    input_str = system_prompt + "\n\n" + user_prompt
    input_tokens = count_tokens(input_str, model)
    output_tokens = 0
    usage_status = "success"
    start = time.time()
    
    async def create_coro():
        return await perplexity_client.chat.completions.create(
            model="sonar",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            stream=True,
            max_tokens=2000,
            extra_body=additional_params
        )
    
    try:
        stream = await retry_on_failure(create_coro)
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                text = chunk.choices[0].delta.content
                yield text
                output_tokens += count_tokens(text, model)
    except Exception as e:
        usage_status = "failed"
        error_msg = json.dumps({"error": "Generation failed", "details": str(e)})
        yield error_msg
        output_tokens += count_tokens(error_msg, model)
    finally:
        latency_ms = int((time.time() - start) * 1000)
        total_cost = calculate_llm_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        db.add(LLMUsage(
            feature="perplexity_review_stream",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=total_cost,
            latency_ms=latency_ms,
            status=usage_status,
        ))
        await db.commit()

class ProductCompanyRequest(BaseModel):
    product_company: str
    is_deepresearch_needed: bool = False
    custom_filter: Optional[str] = None
    clarification: Optional[str] = None # New field

@app.post("/reviews")
async def get_reviews(
    request: ProductCompanyRequest,
    client: Annotated[AsyncOpenAI, Depends(get_openai_client)],
    db: AsyncSession = Depends(get_db)
):
    if not request.product_company.strip():
        return JSONResponse(
            status_code=400,
            content={"detail": "product_company is required"}
        )
    try:
        # Validate and extract
        extract = await validate_and_extract(
            request.product_company,
            request.clarification,
            client,
            db
        )
        print("extract: ", extract)
       
        # Check for needs_clarification first
        if extract.get("needs_clarification"):
            return JSONResponse(
                status_code=200,
                content={
                    "needs_clarification": True,
                    "question": extract.get("question", "Could you provide more details?"),
                    "partial": {
                        "product": extract.get("product"),
                        "company": extract.get("company")
                    }
                }
            )
        # Ensure we have both product and company
        if not extract.get("product") or not extract.get("company"):
            return JSONResponse(
                status_code=200,
                content={
                    "needs_clarification": True,
                    "question": "I couldn't identify the product and company. Can you provide more details?",
                    "partial": {
                        "product": extract.get("product"),
                        "company": extract.get("company")
                    }
                }
            )
        product = extract['product']
        company = extract['company']
       
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in get_reviews extraction: {e}")
        return JSONResponse(
            status_code=200,
            content={
                "needs_clarification": True,
                "question": "I encountered an error processing your request. Could you rephrase your query?",
                "partial": {"product": None, "company": None}
            }
        )
    # Generate streaming response
    try:
        perplexity_stream = create_perplexity_review_stream(
            product, company, request.clarification, request.custom_filter,
            request.is_deepresearch_needed, perplexity_client, db
        )
    except Exception as e:
        logger.error(f"Error creating perplexity stream: {e}")
        raise HTTPException(status_code=503, detail=f"Analysis generation failed: {str(e)}")
    return StreamingResponse(
        perplexity_stream,
        media_type="text/plain",
        headers={"X-Accel-Buffering": "no"}
    )

    
@app.post("/manual-tasks", response_model=dict)
async def create_manual_task(
    title: str = Form(..., description="Task title"),
    caption: str = Form(..., description="Post caption"),
    hashtags: str = Form(..., description="Comma-separated hashtags"),
    notes: Optional[str] = Form(None, description="Optional notes for the task"),
    image: UploadFile = File(..., description="Image file to upload"),
    db: AsyncSession = Depends(get_db)
):

    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image")

    filename = secure_filename(image.filename)
    if not filename or not Path(filename).suffix:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"manual_{timestamp}.jpg"

    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    if Path(filename).suffix.lower() not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported image format")

    try:
        content = await image.read()
    except Exception as e:
        print(f"Failed to read image file: {e}")
        raise HTTPException(status_code=400, detail="Failed to read image file")

    size_bytes = len(content)

    checksum = hashlib.sha256(content).hexdigest()
    filepath = media_dir / filename
    try:
        with open(filepath, "wb") as f:
            f.write(content)
        storage_path = str(filename)  
    except Exception as e:
        print(f"Failed to save image locally: {e}")
        raise HTTPException(status_code=500, detail="Failed to save image")

    try:
        with Image.open(filepath) as img:
            width, height = img.size
    except Exception as e:
        print(f"Failed to extract image dimensions: {e}")
        width, height = None, None

    # Upload to ImgBB if API key available
    imgbb_url = None
    if IMG_BB_API_KEY:
        try:
            files = {"image": (filename, content, image.content_type)}
            data = {"key": IMG_BB_API_KEY}
            response = requests.post("https://api.imgbb.com/1/upload", data=data, files=files, timeout=30)
            if response.status_code == 200:
                res = response.json()
                if res.get("success"):
                    imgbb_url = res["data"]["url"]
                    print(f"Successfully uploaded to ImgBB: {imgbb_url}")
                else:
                    print(f"ImgBB upload failed: {res.get('error', 'Unknown error')}")
            else:
                print(f"ImgBB HTTP error: {response.status_code}")
        except Exception as e:
            print(f"ImgBB upload exception: {e}")
    else:
        print("ImgBB API key not provided; skipping upload")

    # Parse hashtags
    hashtags_list = [h.strip() for h in hashtags.split(",") if h.strip()]

    # Create Task
    task_id = gen_uuid_str()
    task = Task(
        task_id=task_id,
        title=title,
        status=TaskStatus.draft_approved,
        notes=notes
    )
    db.add(task)
    await db.flush()  

    # Create GeneratedContent
    gen_id = gen_uuid_str()
    current_date = datetime.now().date()
    gen_content = GeneratedContent(
        gen_id=gen_id,
        task_id=task_id,
        prompt=f"Manual with {current_date}",
        caption=caption,
        hashtags=hashtags_list,
        image_generated=False,  
    )
    db.add(gen_content)
    await db.flush()

    media_id = gen_uuid_str()
    media = Media(
        media_id=media_id,
        task_id=task_id,
        gen_id=gen_id,
        storage_path=storage_path,
        mime_type=image.content_type,
        img_url=imgbb_url,
        width=width,
        height=height,
        duration_ms=None,  
        checksum=checksum,
        size_bytes=size_bytes,
        is_generated=False,
    )
    db.add(media)

    # Commit all
    try:
        await db.commit()
        print(f"Manual task created: task_id={task_id}, gen_id={gen_id}, media_id={media_id}")
    except Exception as e:
        await db.rollback()
        print(f"Database commit failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to save task to database")

    return {
        "task_id": task_id,
        "gen_id": gen_id,
        "media_id": media_id,
        "storage_path": storage_path,
        "img_url": imgbb_url,
        "message": "Manual task created successfully"
    }