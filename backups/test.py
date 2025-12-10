import os
import asyncio
import shutil  # For cleanup if needed
from pathlib import Path
from typing import Optional
import re
from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # Add for serving files
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import yt_dlp
import logging
import subprocess  # To check FFmpeg

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Social Media Video Downloader", version="1.0.0")

# CORS (already there)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files from /downloads (fixes 404!)
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")

app.mount("/static", StaticFiles(directory="static"), name="static")

media_dir = Path("static/media")


DOWNLOADS_DIR = Path("./downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)

# Check if FFmpeg is available (run once)
FFMPEG_AVAILABLE = False
try:
    subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    FFMPEG_AVAILABLE = True
    logger.info("✅ FFmpeg detected – Full merging & MP3 conversion enabled!")
except (subprocess.CalledProcessError, FileNotFoundError):
    logger.warning("⚠️ No FFmpeg – Using single-stream fallback (still good quality!)")

class DownloadRequest(BaseModel):
    url: str
    quality: Optional[str] = "best"
    audio_only: Optional[bool] = False

def sanitize_filename(name: str, max_length: int = 80) -> str:
    """Sanitize and truncate filename to avoid length/path issues."""
    if not name:
        name = "video"
    # Replace invalid filename characters
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    # Replace spaces with underscores for URL safety
    name = name.replace(' ', '_')
    # Collapse multiple underscores
    name = re.sub(r'_+', '_', name)
    # Trim leading/trailing underscores
    name = name.strip('_')
    # Truncate to max_length
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
    """Dynamic format based on FFmpeg availability."""
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

import unicodedata

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

async def download_video(url: str, quality: str, audio_only: bool) -> tuple[str, str, str]:
    loop = asyncio.get_event_loop()

    # Step 1: Extract info first
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True}) as ydl:
        info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))

    raw_title = info.get("title", "video")
    vid_id = info.get("id", "unknown")[:11]  # YouTube IDs are 11 chars max

    # This is the safe name we will actually use
    safe_title = slugify_filename(raw_title, max_length=90)
    final_base = f"{safe_title}_{vid_id}"        # e.g. A_6_Meal_Turned_Into_His_Worst_Day_Ever_up5x3qDdAtQ

    # Determine final extension
    if audio_only:
        ext = "mp3" if FFMPEG_AVAILABLE else "m4a"
    else:
        ext = "mp4"

    final_filename = f"{final_base}.{ext}"
    filepath = DOWNLOADS_DIR / final_filename

    # Only now do the real download with exact known filename
    opts = {
        "format": get_ydl_format(quality, audio_only)["format"],
        "outtmpl": str(filepath.as_posix().replace(f".{ext}", ".%(ext)s")),  # forces exact name
        "merge_output_format": "mp4" if not audio_only and FFMPEG_AVAILABLE else None,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }] if audio_only and FFMPEG_AVAILABLE else [],
        "retries": 10,
        "fragment_retries": 10,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            await loop.run_in_executor(None, lambda: ydl.download([url]))

        if not filepath.exists():
            raise FileNotFoundError(f"File was not created: {filepath}")

        logger.info(f"Downloaded: {final_filename}")
        return "success", str(filepath), final_filename

    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("yt.html", {"request": request})

@app.post("/download", response_model=dict)
async def download_endpoint(request: DownloadRequest = Body(...)):
    platform = detect_platform(request.url)
    logger.info(f"Request for {platform}: {request.url} (Audio-only: {request.audio_only})")
    
    if platform == "Unknown":
        raise HTTPException(status_code=400, detail="Unsupported platform. yt-dlp supports 1000+ sites—try anyway!")
    
    try:
        status, filepath, filename = await download_video(request.url, request.quality, request.audio_only)
        
        # Build download URL (fixes 404!)
        base_url = "http://127.0.0.1:8000"  # Change to your domain in prod
        download_url = f"{base_url}/downloads/{filename}"
        
        return {
            "status": status,
            "platform": platform,
            "download_url": download_url,  # Frontend uses this!
            "file_path": filepath,
            "message": f"Downloaded to {filepath} ({'MP3' if request.audio_only and FFMPEG_AVAILABLE else 'M4A/MP4'})"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "ffmpeg_available": FFMPEG_AVAILABLE}