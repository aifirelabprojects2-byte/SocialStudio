import asyncio
import random
import re
import subprocess
import aiohttp
import os
import itertools
from pydantic import BaseModel
import yt_dlp
from typing import List, Optional, Tuple
from pathlib import Path
from fastapi import Body, FastAPI, Depends, HTTPException
import unicodedata
from urllib.parse import urlparse
from tenacity import retry, stop_after_attempt, wait_exponential
from pytubefix import YouTube
from dotenv import load_dotenv
from apify_client import ApifyClient

import Accounts
from Configs import PROXY_URL

load_dotenv()
APIFY_KEY = os.getenv("APIFY_KEY")

DOWNLOADS_DIR = Path("./static/downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)

FFMPEG_AVAILABLE = False
CONCURRENT_DOWNLOADS = 10
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

HEADERS_CYCLE = itertools.cycle([
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36", "Accept": "*/*"},
    {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1", "Accept": "*/*"},
])

def get_headers() -> dict:
    return next(HEADERS_CYCLE)

def detect_platform(url: str) -> str:
    domain = urlparse(url).netloc.lower()
    if "youtube.com" in domain or "youtu.be" in domain:
        return "YouTube"
    elif "instagram.com" in domain:
        return "Instagram"
    elif "facebook.com" in domain or "fb.watch" in domain:
        return "Facebook"
    elif "tiktok.com" in domain:
        return "TikTok"
    elif "twitter.com" in domain or "x.com" in domain:
        return "Twitter/X"
    elif "reddit.com" in domain:
        return "Reddit"
    elif "twitch.tv" in domain:
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
    text = re.sub(r'\s+', '_', text)
    text = text.strip('_.- ')
    if not text:
        text = "media"
    return text[:max_length]

def get_insta_data_sync(post_url):
    if not APIFY_KEY:
        raise ValueError("APIFY_KEY not set in environment variables.")
        
    client = ApifyClient(APIFY_KEY)
    run_input = {
        "directUrls": [post_url],
        "resultsType": "posts",
        "resultsLimit": 1,
        "searchLimit": 1,
    }

    # Run the actor
    run = client.actor("shu8hvrXbJbY3Eb9W").call(run_input=run_input)
    
    # Iterate results
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        media_url = item.get("videoUrl") if item.get("videoUrl") else item.get("displayUrl")
        caption = item.get("caption", "No caption available")
        
        # Determine basic type
        media_type = "video" if item.get("videoUrl") else "image"
        
        return {
            "caption": caption,
            "media_url": media_url,
            "type": media_type,
            "status": "Success"
        }
    
    return {"status": "No Data Found", "media_url": None}

def get_x_media_v2_sync(tweet_url: str):
    if not APIFY_KEY:
        raise ValueError("APIFY_KEY not set in environment variables.")

    client = ApifyClient(APIFY_KEY)
    # Extract tweet ID
    try:
        tweet_id = tweet_url.split("/")[-1].split("?")[0]
    except Exception:
         # Fallback for simple ID extraction
        match = re.search(r'status/(\d+)', tweet_url)
        tweet_id = match.group(1) if match else None

    if not tweet_id:
        return {"status": "Invalid URL format"}

    run = client.actor(
        "kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest"
    ).call(run_input={
        "tweetIDs": [tweet_id],
        "maxItems": 1
    })

    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    if not items:
        return {"status": "No items in dataset"}

    item = items[0]  # Take first item

    caption = item.get("text") or "No text found"

    # -------- media --------
    media_url = None
    media_type = "text"
    
    media_entities = item.get("extendedEntities", {}).get("media", []) or []

    if media_entities:
        media = media_entities[0]  # First media item

        type_str = media.get("type", "")
        if type_str == "photo":
            media_url = media.get("media_url_https") or media.get("url") or media.get("media_url")
            media_type = "image"
        elif type_str in ("video", "animated_gif"):
            media_type = "video"
            # For videos/GIFs, variants are nested under "video_info"
            video_info = media.get("video_info", {})
            variants = video_info.get("variants", [])
            mp4s = [
                v for v in variants
                if isinstance(v, dict) and v.get("content_type") == "video/mp4" and "bitrate" in v
            ]
            if mp4s:
                # Highest quality (bitrate)
                media_url = max(mp4s, key=lambda x: x.get("bitrate", 0)).get("url")
            else:
                # Fallback to any video URL
                for v in variants:
                    if isinstance(v, dict) and "url" in v:
                        media_url = v["url"]
                        break
                # Or direct fallback
                if not media_url:
                    media_url = media.get("videoUrl") or media.get("url")

    return {
        "caption": caption,
        "media_url": media_url,
        "type": media_type,
        "status": "Success" if media_url else ("Text Only" if caption != "No text found" else "No Data Found")
    }

async def download_media_from_url(url: str, filename_base: str, forced_ext: str = None) -> str:
    timeout = aiohttp.ClientTimeout(total=300) # 5 min timeout for large videos
    
    # Determine extension
    if forced_ext:
        ext = forced_ext
    else:
        path = urlparse(url).path
        ext = path.split('.')[-1]
        # Basic cleanup of extension if it contains extra params or is too long
        if len(ext) > 4 or "/" in ext:
            if "mp4" in url: ext = "mp4"
            elif "jpg" in url or "jpeg" in url: ext = "jpg"
            elif "png" in url: ext = "png"
            elif "webp" in url: ext = "webp"
            else: ext = "mp4" # Default fallback
            
    final_filename = f"{filename_base}.{ext}"
    filepath = DOWNLOADS_DIR / final_filename
    
    # Avoid Overwrites
    counter = 1
    while filepath.exists():
        filepath = DOWNLOADS_DIR / f"{filename_base}_{counter}.{ext}"
        counter += 1

    try:
        async with aiohttp.ClientSession(headers=get_headers(), timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    with open(filepath, "wb") as f:
                        async for chunk in resp.content.iter_chunked(1024 * 1024):
                            f.write(chunk)
                    return str(filepath)
                else:
                    raise HTTPException(status_code=resp.status, detail=f"Failed to download media content: HTTP {resp.status}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download IO error: {str(e)}")

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

    res_map = {"best": None, "720p": 720, "1080p": 1080, "4k": 2160}
    target_height = res_map.get(quality)
    if target_height is None:
        stream = yt.streams.get_highest_resolution()
        return stream, "mp4"

    streams = yt.streams.filter(progressive=True, file_extension='mp4').order_by('height').desc()
    for stream in streams:
        if stream.height and stream.height <= target_height:
            return stream, "mp4"

    stream = yt.streams.get_highest_resolution()
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

        # Try PyTube for YouTube first
        if platform == "YouTube":
            def _pytube_download():
                try:
                    yt = YouTube(url, on_progress_callback=lambda s,c,b: None)
                    vid_id = yt.video_id
                    safe_title = slugify_filename(yt.title, max_length=90)
                    final_base = f"{safe_title}_{vid_id}"

                    stream, ext = get_pytube_stream(yt, quality, audio_only)
                    final_filename = f"{final_base}.{ext}"
                    filepath = DOWNLOADS_DIR / final_filename

                    stream.download(output_path=str(DOWNLOADS_DIR), filename=final_filename)

                    downloaded = filepath
                    if not downloaded.exists():
                        matches = list(DOWNLOADS_DIR.glob(f"{final_base}.*"))
                        if matches: matches[0].rename(downloaded)

                    if audio_only and FFMPEG_AVAILABLE and ext == "m4a":
                        mp3_path = downloaded.with_suffix(".mp3")
                        subprocess.run(["ffmpeg", "-i", str(downloaded), "-codec:a", "libmp3lame", "-q:a", "2", str(mp3_path)], check=True, capture_output=True)
                        downloaded.unlink()
                        final_filename = mp3_path.name
                        downloaded = mp3_path

                    return "success", [str(downloaded)], [final_filename]
                except Exception as e:
                    raise e

            try:
                return await loop.run_in_executor(None, _pytube_download)
            except Exception as e:
                print(f"Pytube failed, falling back to yt-dlp: {e}")

        # yt-dlp fallback
        base_opts = {
            "quiet": True, "no_warnings": True, "noplaylist": True, "retries": 10,
            "http_headers": get_headers(), "proxy": PROXY_URL,
             "extractor_args": {"youtube": {"player_client": "android", "player_skip": ["webpage", "configs"], "skip": ["dash"]}}
        }
        
        try:
            base_opts["cookiefile"] = yt_dlp.utils.browser_cookie_file()
        except: pass

        info = await loop.run_in_executor(None, _extract_info, url, base_opts)
        if not info: raise HTTPException(status_code=400, detail="Failed to extract video info")

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
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}] if audio_only and FFMPEG_AVAILABLE else [],
        })

        try:
            await loop.run_in_executor(None, _do_yt_dlp_download, url, download_opts)
            file_paths = [str(filepath)]
            file_names = [final_filename]
            return "success", file_paths, file_names
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# --- Main Initialization ---

def init(app):
    @app.get("/api/downloads/list")
    async def list_downloads(_=Depends(Accounts.get_current_user)):
        files = []
        try:
            for file_path in DOWNLOADS_DIR.iterdir():
                if file_path.is_file():
                    stat = file_path.stat()
                    # Determine file type based on extension
                    ext = file_path.suffix.lower()
                    if ext in ['.mp4', '.webm', '.mkv', '.avi', '.mov']:
                        file_type = 'video'
                    elif ext in ['.mp3', '.m4a', '.wav', '.flac', '.aac']:
                        file_type = 'audio'
                    elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                        file_type = 'image'
                    else:
                        file_type = 'file'
                    
                    files.append({
                        "name": file_path.name,
                        "size": stat.st_size,
                        "size_formatted": _format_size(stat.st_size),
                        "extension": ext[1:] if ext else "",
                        "type": file_type,
                        "modified": stat.st_mtime,
                        "download_url": f"/downloads/{file_path.name}"
                    })
            
            # Sort by modified time, newest first - O(n log n)
            files.sort(key=lambda x: x["modified"], reverse=True)
            
            return {"status": "success", "files": files, "count": len(files)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing downloads: {str(e)}")

    def _format_size(size_bytes: int) -> str:
        """Format bytes to human readable size - O(1)"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    @app.delete("/api/downloads/{filename}")
    async def delete_download(filename: str, _=Depends(Accounts.get_current_user)):
        """Delete a file from downloads folder - O(1)"""
        file_path = DOWNLOADS_DIR / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Not a file")
        try:
            file_path.unlink()
            return {"status": "success", "message": f"Deleted {filename}"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")

    @app.post("/download", response_model=dict)
    async def download_endpoint(request: DownloadRequest = Body(...), _=Depends(Accounts.get_current_user)):
        loop = asyncio.get_event_loop()
        platform = detect_platform(request.url)

        if is_x_url(request.url):
            try:
                # 1. Fetch Metadata via Apify (Async wrapper)
                apify_data = await loop.run_in_executor(None, get_x_media_v2_sync, request.url)
                
                if apify_data.get("status") != "Success":
                    raise HTTPException(status_code=404, detail=f"Apify Error: {apify_data.get('status')}")
                
                media_url = apify_data.get("media_url")
                if not media_url:
                    raise HTTPException(status_code=404, detail="No media found in tweet")

                # 2. Try to download the actual file, fallback to direct URL on failure
                safe_name = slugify_filename(apify_data.get("caption", "twitter_media"), max_length=50)
                
                try:
                    file_path_str = await download_media_from_url(media_url, f"x_{safe_name}")
                    file_name = Path(file_path_str).name
                    download_urls = [f"/downloads/{file_name}"]
                    
                    return {
                        "status": "success",
                        "platform": "Twitter/X",
                        "download_method": "Apify+Aiohttp",
                        "download_url": download_urls,
                        "file_paths": [file_path_str],
                        "files": [file_name],
                        "file_count": 1,
                        "message": f"Downloaded: {apify_data.get('caption')[:30]}..."
                    }
                except Exception as download_err:
                    # Server-side download failed, return direct media URL to user
                    print(f"Server-side X download failed, returning direct URL: {download_err}")
                    return {
                        "status": "success",
                        "platform": "Twitter/X",
                        "download_method": "DirectURL",
                        "download_url": [media_url],
                        "direct_url": media_url,
                        "media_type": apify_data.get("type", "media"),
                        "file_count": 1,
                        "is_external": True,
                        "message": f"Direct link: {apify_data.get('caption', '')[:30]}..."
                    }

            except HTTPException:
                raise
            except Exception as e:
                # Metadata fetch failed completely
                raise HTTPException(status_code=500, detail=f"X Download Failed: {str(e)}")


        if is_instagram_url(request.url):
            try:
                apify_data = await loop.run_in_executor(None, get_insta_data_sync, request.url)
                
                if not apify_data.get("media_url"):
                    raise HTTPException(status_code=404, detail=f"Apify Error: {apify_data.get('status', 'Unknown error')}")

                media_url = apify_data.get("media_url")
                safe_name = slugify_filename(apify_data.get("caption", "insta_media"), max_length=50)

                try:
                    file_path_str = await download_media_from_url(media_url, f"insta_{safe_name}")
                    file_name = Path(file_path_str).name
                    download_urls = [f"/downloads/{file_name}"]

                    return {
                        "status": "success",
                        "platform": "Instagram",
                        "download_method": "Apify+Aiohttp",
                        "download_url": download_urls,
                        "file_paths": [file_path_str],
                        "files": [file_name],
                        "file_count": 1,
                        "message": f"Downloaded {apify_data.get('type')}: {apify_data.get('caption')[:30]}..."
                    }
                except Exception as download_err:
                    # Server-side download failed, return direct media URL to user
                    print(f"Server-side Instagram download failed, returning direct URL: {download_err}")
                    return {
                        "status": "success",
                        "platform": "Instagram",
                        "download_method": "DirectURL",
                        "download_url": [media_url],
                        "direct_url": media_url,
                        "media_type": apify_data.get("type", "media"),
                        "file_count": 1,
                        "is_external": True,
                        "message": f"Direct link ({apify_data.get('type')}): {apify_data.get('caption', '')[:30]}..."
                    }

            except HTTPException:
                raise
            except Exception as e:
                # Metadata fetch failed completely
                raise HTTPException(status_code=500, detail=f"Instagram Download Failed: {str(e)}")


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
                "message": f"Downloaded to {file_paths[0]}"
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")