import asyncio
import random
import re
import subprocess
import aiohttp
from pydantic import BaseModel
import yt_dlp
from datetime import datetime
from typing import List, Optional,  Tuple
from pathlib import Path
from enum import Enum
from fastapi import Body, Cookie, FastAPI, Form, Query, Request, Depends, HTTPException, logger, status, UploadFile, File
import unicodedata
from urllib.parse import urlparse
import itertools
from gallery_dl import config, job
import instaloader
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pytubefix import YouTube

import Accounts

DOWNLOADS_DIR = Path("./downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)
INSTALOADER_AVAILABLE = True
FFMPEG_AVAILABLE = False
CONCURRENT_DOWNLOADS = 10  # Limit concurrent heavy downloads for scalability
download_sem = asyncio.Semaphore(CONCURRENT_DOWNLOADS)

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

async def download_x_media(url: str, cookies_file: str = None) -> Tuple[str, List[Path]]:
    """
    Download both images and videos from an X/Twitter post URL.
    
    :param url: The X post URL (e.g., https://x.com/username/status/1234567890)
    :param cookies_file: Optional path to cookies.txt for authentication (Netscape format)
    :return: Tuple of status and list of downloaded file paths
    """
    async with download_sem:
        loop = asyncio.get_event_loop()
        
        def _sync_download():
            old_files = set(str(f) for f in DOWNLOADS_DIR.rglob("*"))
            
            # Base directory for downloads
            config.set((), "base-directory", str(DOWNLOADS_DIR))
            
            # Authentication via cookies (critical for many public posts in 2025)
            if cookies_file:
                config.set(("extractor", "twitter"), "cookies", cookies_file)
            
            # Optional: Better default filename (tweet_id + numbering + extension)
            # This avoids overwrites for multi-media posts
            config.set(("extractor", "twitter"), "filename", "{tweet_id}_{num}.{extension}")
            
            # No need to set "videos": True — it's the default, so both images & videos download
            
            download_job = job.DownloadJob(url)
            download_job.run()
            
            # Detect newly downloaded files
            new_files = [f for f in DOWNLOADS_DIR.rglob("*") if f.is_file() and str(f) not in old_files]
            
            # Rename to avoid conflicts if needed (your original logic)
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
                if dest != f:  # Only rename if needed
                    f.rename(dest)
                moved_files.append(dest)
            
            return moved_files
        
        downloaded_files = await loop.run_in_executor(None, _sync_download)
        
        if downloaded_files:
            return "success", downloaded_files
        else:
            return "no_media_or_error", []

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

def get_pytube_stream(yt: YouTube, quality: str, audio_only: bool):
    if audio_only:
        stream = yt.streams.get_audio_only()
        if not stream:
            raise ValueError("No audio stream available")
        return stream, "m4a"

    res_map = {
        "best": None,
        "720p": 720,
        "1080p": 1080,
        "4k": 2160
    }
    target_height = res_map.get(quality)
    if target_height is None:
        stream = yt.streams.get_highest_resolution()
        if not stream:
            raise ValueError("No video stream available")
        return stream, "mp4"

    # Get best progressive stream <= target height
    streams = yt.streams.filter(progressive=True, file_extension='mp4').order_by('height').desc()
    for stream in streams:
        if stream.height and stream.height <= target_height:
            return stream, "mp4"

    # Fallback to highest resolution
    stream = yt.streams.get_highest_resolution()
    if not stream:
        raise ValueError("No video stream available")
    return stream, "mp4"

def _extract_info(url: str, base_opts: dict):
    with yt_dlp.YoutubeDL(base_opts) as ydl:
        return ydl.extract_info(url, download=False)

def _do_yt_dlp_download(url: str, download_opts: dict):
    with yt_dlp.YoutubeDL(download_opts) as ydl:
        ydl.download([url])

async def download_video(url: str, quality: str, audio_only: bool) -> Tuple[str, list, list]:
    async with download_sem:
        platform = detect_platform(url)
        loop = asyncio.get_event_loop()

        if platform == "YouTube":
            def _pytube_download():
                try:
                    def progress_callback(stream, chunk, bytes_remaining):
                        pass  # Silent progress

                    yt = YouTube(url, on_progress_callback=progress_callback)

                    vid_id = yt.video_id
                    raw_title = yt.title
                    safe_title = slugify_filename(raw_title, max_length=90)
                    final_base = f"{safe_title}_{vid_id}"

                    stream, ext = get_pytube_stream(yt, quality, audio_only)
                    final_filename = f"{final_base}.{ext}"
                    filepath = DOWNLOADS_DIR / final_filename

                    stream.download(output_path=str(DOWNLOADS_DIR), filename=final_filename)

                    downloaded = filepath
                    if not downloaded.exists():
                        matches = list(DOWNLOADS_DIR.glob(f"{final_base}.*"))
                        if matches:
                            matches[0].rename(downloaded)

                    # Handle MP3 conversion for audio_only if FFMPEG available
                    if audio_only and FFMPEG_AVAILABLE and ext == "m4a":
                        mp3_path = downloaded.with_suffix(".mp3")
                        subprocess.run([
                            "ffmpeg", "-i", str(downloaded),
                            "-codec:a", "libmp3lame", "-q:a", "2",
                            str(mp3_path)
                        ], check=True, capture_output=True)
                        downloaded.unlink()
                        final_filename = mp3_path.name
                        downloaded = mp3_path

                    return "success", [str(downloaded)], [final_filename]
                except Exception as e:
                    raise e

            try:
                return await loop.run_in_executor(None, _pytube_download)
            except Exception as e:
                print(f"Pytube failed for YouTube, falling back to yt-dlp: {e}")

        # yt-dlp logic (for non-YouTube or pytube fallback)
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

        info = await loop.run_in_executor(None, _extract_info, url, base_opts)

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
            await loop.run_in_executor(None, _do_yt_dlp_download, url, download_opts)
            
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
    
def init(app):
    @app.post("/download", response_model=dict)
    async def download_endpoint(request: DownloadRequest = Body(...), _=Depends(Accounts.get_current_user)):
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
                    status, files = await download_x_media(request.url)
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