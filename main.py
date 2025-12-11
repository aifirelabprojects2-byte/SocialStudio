import asyncio
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
from ImgGen import ImageGenClient
import PostGen,ManagePlatform
from celery_app import Capp
import os
import base64
import io
from datetime import datetime
from typing import List, AsyncGenerator, Dict, Any, Annotated, Optional, Literal
from pathlib import Path
from enum import Enum
from fastapi import Body, FastAPI, Form, Query, Request, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import json
from Database import AttemptStatus, ErrorLog, OAuthToken, Platform, PostAttempt, PublishStatus, TaskStatus, gen_uuid_str, get_db, init_db, Task, GeneratedContent, Media, PlatformSelection
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, update, delete,desc
from sqlalchemy.orm import selectinload,joinedload
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from werkzeug.utils import secure_filename
from PIL import Image
import unicodedata
import pytz
from tasks import execute_posting 

load_dotenv()

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
    await db.refresh(task) 

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



DOWNLOADS_DIR = Path("./downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)


FFMPEG_AVAILABLE = False
try:
    subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    FFMPEG_AVAILABLE = True
except (subprocess.CalledProcessError, FileNotFoundError):
    print("error")

class DownloadRequest(BaseModel):
    url: str
    quality: Optional[str] = "best"
    audio_only: Optional[bool] = False

def sanitize_filename(name: str, max_length: int = 80) -> str:
    if not name:
        name = "video"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = name.replace(' ', '_')
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')
    if len(name) > max_length:
        name = name[:max_length]
    return name

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
        return "Unknown (yt-dlp will handle if supported)"

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

def slugify_filename(text: str, max_length: int = 100) -> str:
    text = unicodedata.normalize('NFKC', text)

    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', text)      
    text = re.sub(r'[\[\](){}]', '', text)                
    text = re.sub(r'[^\w\s\-.£€$!&+]', '', text)           
    text = re.sub(r'\s+', '_', text)                      
    text = re.sub(r'_+', '_', text)                        
    text = text.strip('_.- ')
    
    if not text:
        text = "video"
    
    if len(text) > max_length:
        text = text[:max_length]
    
    return text


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


async def download_video(url: str, quality: str, audio_only: bool) -> tuple[str, str, str]:
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

    "cookiefile": "cookies.txt" if Path("cookies.txt").exists() else None,
}

    cookies_path = Path("cookies.txt")
    if cookies_path.exists():
        print("bruh cookie exist..")
        base_opts["cookiefile"] = str(cookies_path)
    else:
        try:
            base_opts["cookiefile"] = yt_dlp.utils.browser_cookie_file()
        except:
            pass  # no cookies = okay for public videos

    # Step 1: Extract info
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

    # Final download options
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
        # Keep fresh random headers for the actual download too
        "http_headers": get_random_headers(),
    })

    try:
        with yt_dlp.YoutubeDL(download_opts) as ydl:
            await loop.run_in_executor(None, lambda: ydl.download([url]))
        if not filepath.exists():
            matches = list(DOWNLOADS_DIR.glob(f"{final_base}.*"))
            if matches:
                matches[0].rename(filepath)

        return "success", str(filepath), final_filename

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Sign in to confirm you’re not a bot" in error_msg:
            raise HTTPException(status_code=429, detail="Bot detection triggered. Update your cookies.txt")
        if "Private video" in error_msg or "unavailable" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Video is private or region-locked")
        raise HTTPException(status_code=500, detail=f"Download failed: {error_msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/download", response_model=dict)
async def download_endpoint(request: DownloadRequest = Body(...)):
    platform = detect_platform(request.url)

    
    if platform == "Unknown":
        raise HTTPException(status_code=400, detail="Unsupported platform. yt-dlp supports 1000+ sites—try anyway!")
    
    try:
        status, filepath, filename = await download_video(request.url, request.quality, request.audio_only)

        base_url = "http://127.0.0.1:8000"  
        download_url = f"{base_url}/downloads/{filename}"
        
        return {
            "status": status,
            "platform": platform,
            "download_url": download_url,  
            "file_path": filepath,
            "message": f"Downloaded to {filepath} ({'MP3' if request.audio_only and FFMPEG_AVAILABLE else 'M4A/MP4'})"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
    


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


def get_search_api_key():
    key = os.getenv("SEARCH_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="SEARCH_API_KEY not configured")
    return key


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


async def search_web(query: str, num: int, search_key: str) -> List[Dict[str, str]]:
    params = {
        "engine": "google",
        "q": query,
        "api_key": search_key,
        "num": num,
    }

    limiter = get_rate_limiter()
    await limiter.acquire()

    async def fetch_coro():
        connector = aiohttp.TCPConnector(limit=10)
        timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get("https://www.searchapi.io/api/v1/search", params=params) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
                return data.get("organic_results", [])

    try:
        results = await retry_on_failure(fetch_coro, max_retries=MAX_RETRIES)
        return [
            {
                "title": result.get("title", ""),
                "url": result.get("link", ""),
                "snippet": result.get("snippet", ""),
            }
            for result in results
        ]
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Search failed for query '{query}'")


async def validate_and_extract(product_company: str, client: Annotated[AsyncOpenAI, Depends(get_openai_client)]) -> Optional[Dict[str, str]]:
    system_prompt = (
        "You are an input validator and extractor. Analyze the input to determine if it refers to a product and its company, "
        "handling natural language variations, casual phrasing, and comparisons. Always be flexible and recognize common products. "
        "Key guidelines:\n"
        "- Product names can include numbers/models (e.g., 'iPhone 15', 'iPhone 14', 'Maggi 2 Minute').\n"
        "- Ignore case, extra words like 'from', 'by', 'of', 'the', 'a'.\n"
        "- For comparisons (e.g., 'compare maggi and yippee'), extract the primary product-company pair (e.g., Maggi-Nestle), and note it's for single review focus.\n"
        "- Common products: iPhone (Apple), Maggi (Nestle), Yippee (ITC), Galaxy (Samsung), etc.\n"
        "Examples of valid inputs:\n"
        "- 'iPhone Apple' -> product: 'iPhone', company: 'Apple'\n"
        "- 'iphone 15 apple' -> product: 'iPhone 15', company: 'Apple'\n"
        "- 'iPhone 14 from apple' -> product: 'iPhone 14', company: 'Apple'\n"
        "- 'Maggi Nestle' -> product: 'Maggi', company: 'Nestle'\n"
        "- 'Nestle Maggi' -> product: 'Maggi', company: 'Nestle'\n"
        "- 'compare maggi and yippee' -> product: 'Maggi', company: 'Nestle' (primary focus)\n"
        "- 'can you compare maggi and yippee noodles' -> product: 'Maggi', company: 'Nestle'\n"
        "If it clearly references a product and company (even loosely), validate as true. Only invalid if no product/company identifiable."
    )
    user_prompt = f"""Input: "{product_company}".
Extract the primary product name and company name if valid. Respond with JSON:
{{"is_valid": true, "product": "extracted product name", "company": "extracted company name", "reason": "brief explanation"}}
If invalid, respond with JSON:
{{"is_valid": false, "reason": "brief explanation"}}"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
            max_tokens=150,
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        if data.get("is_valid"):
            return {
                "product": data["product"].strip(),
                "company": data["company"].strip(),
                "reason": data.get("reason", "")
            }
        else:
            return None
    except json.JSONDecodeError as e:
        return None
    except Exception as e:
        raise HTTPException(status_code=503, detail="Validation service unavailable")


async def generate_search_queries(product_company: str, custom_filter: Optional[str], client: Annotated[AsyncOpenAI, Depends(get_openai_client)]) -> List[str]:
    system_prompt = "You are a search query expert. Generate diverse, effective Google search queries focused on finding customer reviews (good and bad) for the given product-company pair."
    filter_part = f" Include focus on: {custom_filter}" if custom_filter else ""
    user_prompt = f'Product-Company: "{product_company}".{filter_part} Generate exactly 5 queries. Respond with JSON: {{"queries": ["query1", "query2", "query3", "query4", "query5"]}}'

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            response_format={"type": "json_object"},
            max_tokens=300,
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        queries = data.get("queries", [])
        if custom_filter:
            queries = [q + " " + custom_filter for q in queries]
        return queries
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=503, detail="Query generation failed")
    except Exception as e:
        raise HTTPException(status_code=503, detail="Query generation failed")


async def validate_and_prepare(
    product_company: str,
    is_deepresearch_needed: bool,
    custom_filter: Optional[str],
    client: Annotated[AsyncOpenAI, Depends(get_openai_client)],
    search_key: Annotated[str, Depends(get_search_api_key)]
) -> tuple[str, str, List[Dict[str, Any]]]:
    # Step 1: Validate and extract
    extract = await validate_and_extract(product_company, client)
    if extract is None:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid input: '{product_company}'. Please provide a product and company reference (e.g., 'iPhone 15 Apple', 'iPhone 14 from Apple', 'compare Maggi and Yippee')."
        )

    product = extract['product']
    company = extract['company']
    normalized_product_company = f"{product} {company}"

    # Step 2: Generate queries
    queries = await generate_search_queries(normalized_product_company, custom_filter, client)
    if not queries:
        raise HTTPException(status_code=503, detail="Failed to generate search queries.")

    # Step 3: Search
    num_results = DEEP_RESEARCH_NUM_RESULTS if is_deepresearch_needed else SEARCH_NUM_RESULTS
    all_sources: List[Dict[str, Any]] = []
    source_counter = 1
    for query in queries:
        results = await search_web(query, num_results, search_key)
        for result in results:
            all_sources.append(
                {
                    "id": source_counter,
                    "title": result["title"],
                    "url": result["url"],
                    "content": result["snippet"],
                }
            )
            source_counter += 1

    if not all_sources:
        raise HTTPException(status_code=404, detail="No search results found for the product.")

    # Step 4: Format context
    formatted_context = "\n\n".join(
        [
            f"Source [{s['id']}]: {s['title']}\nURL: {s['url']}\nContent: {s['content']}"
            for s in all_sources
        ]
    )

    return formatted_context, product, all_sources


async def generate_review_stream(
    context: str, product: str, client: Annotated[AsyncOpenAI, Depends(get_openai_client)]
) -> AsyncGenerator[str, None]:
    system_prompt = (
        "You are an expert reviewer analyzer. Extract and summarize key good and bad customer "
        "reviews from the sources. Use inline citations like [1] after relevant points. "
        "Structure your output exactly as:\n"
        "# Good Reviews for {product}\n"
        "- Bullet point summarizing a positive aspect [citation]\n"
        "...\n\n"
        "# Bad Reviews for {product}\n"
        "- Bullet point summarizing a negative aspect [citation]\n"
        "...\n\n"
        "## Sources\n"
        "1. Title - URL\n"
        "2. Title - URL\n"
        "...\n"
        "Output ONLY this formatted text—no introductions, explanations, markdown beyond bullets, "
        "or extra content. Aim for 3-5 bullets per section. Ensure citations are used."
    ).format(product=product)

    user_prompt = f"Context from searches:\n{context}\n\nProvide the review analysis."

    try:
        stream = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,  
            stream=True,
            max_tokens=1500,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                yield content
    except Exception as e:
        raise HTTPException(status_code=503, detail="Review generation failed")

class ProductCompanyRequest(BaseModel):
    product_company: str
    is_deepresearch_needed: bool = False
    custom_filter: Optional[str] = None

@app.post("/reviews", response_class=StreamingResponse)
async def get_reviews(
    request: ProductCompanyRequest, 
    client: Annotated[AsyncOpenAI, Depends(get_openai_client)], 
    search_key: Annotated[str, Depends(get_search_api_key)]
):
    if not request.product_company.strip():
        raise HTTPException(status_code=400, detail="product_company is required")

    try:
        formatted_context, product, _ = await validate_and_prepare(
            request.product_company,
            request.is_deepresearch_needed,
            request.custom_filter,
            client,
            search_key
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

    async def event_generator():
        try:
            async for chunk in generate_review_stream(formatted_context, product, client):
                yield chunk
        except Exception as e:
            raise HTTPException(status_code=500, detail="Internal server error")

    return StreamingResponse(
        event_generator(),
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