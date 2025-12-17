import itertools
import os
import json
import uuid
import hashlib
import asyncio
import random
import re
import io
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
from PIL import Image, UnidentifiedImageError
import aiohttp
import requests
import instaloader
from dotenv import load_dotenv
from sqlalchemy import select
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI
from google import genai
from google.genai import types

from Database import GeneratedContent, ImageTheme, Media, Task, TaskStatus, get_db

load_dotenv()


def gen_uuid_str() -> str:
    return str(uuid.uuid4())

media_dir = Path("static/media")

class Config:
    INSTAGRAM_RATE_LIMIT_DELAY_MIN: float = 1.0
    INSTAGRAM_RATE_LIMIT_DELAY_MAX: float = 3.0
    INSTAGRAM_RETRY_ATTEMPTS: int = 3

X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
IMG_BB_API_KEY = os.getenv("IMGBB_API")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GenaiClient = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


HEADERS_CYCLE = itertools.cycle([  # Assuming import itertools
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.instagram.com/",
    },
    {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.instagram.com/",
    }
])

def get_headers() -> Dict[str, str]:
    return next(HEADERS_CYCLE)

def detect_platform(url: str) -> str:
    parsed = urlparse(url.lower())
    domain = parsed.netloc
    if "instagram.com" in domain:
        return "instagram"
    elif "x.com" in domain or "twitter.com" in domain:
        return "x"
    return "unknown"

INSTAGRAM_SHORTCODE_PATTERN = re.compile(r'/p/([A-Za-z0-9_-]{11})')

def extract_instagram_shortcode(post_url: str) -> str:
    post_url = post_url.split('?')[0].rstrip('/')
    match = INSTAGRAM_SHORTCODE_PATTERN.search(post_url)
    if not match:
        raise ValueError("Invalid Instagram URL—no shortcode found.")
    return match.group(1)

@retry(
    stop=stop_after_attempt(Config.INSTAGRAM_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(instaloader.exceptions.ConnectionException)
)
async def fetch_instagram_post(shortcode: str) -> Optional[instaloader.Post]:
    loop = asyncio.get_event_loop()

    def _sync_fetch():
        L = instaloader.Instaloader(
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

    try:
        return await loop.run_in_executor(None, _sync_fetch)
    except instaloader.exceptions.LoginRequiredException:
        raise
    except instaloader.exceptions.ConnectionException as e:
        if "429" in str(e) or "rate limit" in str(e).lower():
            await asyncio.sleep(random.uniform(60, 300))
        raise

def extract_instagram_media_urls(post: instaloader.Post) -> List[str]:
    media_urls = []
    if post.typename == 'GraphVideo':
        media_urls.append(post.video_url)
    elif post.typename == 'GraphImage':
        media_urls.append(post.url)
    elif post.typename == 'GraphSidecar':
        for node in post.get_sidecar_nodes():
            media_urls.append(node.video_url if node.is_video else node.display_url)
    else:
        media_urls.append(post.url or post.video_url)
    return [url for url in media_urls if url]

X_TWEET_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/[^/]+/status/(\d+)"
)

def extract_x_tweet_id(url: str) -> Optional[str]:
    match = X_TWEET_PATTERN.search(url.strip())
    return match.group(1) if match else None

def fetch_x_tweet(tweet_id: str) -> Optional[Dict[str, Any]]:
    if not X_BEARER_TOKEN:
        return {"error": "X_BEARER_TOKEN not set in environment."}

    url = f"https://api.twitter.com/2/tweets/{tweet_id}"
    params = {
        "expansions": "attachments.media_keys,author_id",
        "media.fields": "url,type,preview_image_url",
        "tweet.fields": "text",
    }
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "data" not in data:
            return {"error": "No tweet data", "details": data}

        tweet = data["data"]
        text = tweet.get("text", "")

        media_urls = []
        if "includes" in data and "media" in data["includes"]:
            for media in data["includes"]["media"]:
                if media["type"] == "photo" and media.get("url"):
                    media_urls.append(media["url"] + "?format=jpg&name=orig")
                elif media["type"] in ["video", "animated_gif"]:
                    media_urls.append(media.get("preview_image_url", ""))

        return {
            "caption": text.strip(),
            "media_urls": [url for url in media_urls if url]
        }

    except requests.exceptions.HTTPError as e:
        response = e.response  # Assuming e.response available
        error_detail = response.json() if response.content else str(e)
        return {"error": f"HTTP {response.status_code}", "details": error_detail}
    except Exception as e:
        return {"error": str(e)}

async def download_file(session: aiohttp.ClientSession, url: str, filepath: Path) -> bool:
    try:
        async with session.get(url, timeout=30) as resp:
            if resp.status == 200:
                # Ensure parent directory exists (though it should)
                filepath.parent.mkdir(parents=True, exist_ok=True)
                with open(filepath, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        if chunk:
                            f.write(chunk)
                return True
            else:
                print(f"Download failed: HTTP {resp.status} for {url}")
                return False
    except Exception as e:
        print(f"Failed to download {url}: {str(e)}")
        return False

async def fetch_social_post(url: str) -> Dict[str, Any]:
    platform = detect_platform(url)

    async with aiohttp.ClientSession() as session:
        saved_media_paths: List[str] = []

        if platform == "instagram":
            try:
                shortcode = extract_instagram_shortcode(url)
                post = await fetch_instagram_post(shortcode)
                media_urls = extract_instagram_media_urls(post)
                caption = (post.caption or "").strip()

                # Download each media, only add if successful
                for media_url in media_urls:
                    # Determine extension
                    ext = media_url.split("?")[0].split(".")[-1].lower()
                    if ext not in ["jpg", "jpeg", "png", "mp4"]:
                        ext = "mp4" if "video" in media_url.lower() or media_url.endswith("/mp4") else "jpg"

                    filename = f"{gen_uuid_str()}.{ext}"
                    filepath = media_dir / filename
                    local_url = f"/media/{filename}"

                    if await download_file(session, media_url, filepath):
                        saved_media_paths.append(local_url)

                result = {
                    "platform": "instagram",
                    "caption": caption,
                    "media_urls": saved_media_paths  # Only successful local downloads
                }

                await asyncio.sleep(random.uniform(Config.INSTAGRAM_RATE_LIMIT_DELAY_MIN, Config.INSTAGRAM_RATE_LIMIT_DELAY_MAX))
                return result

            except ValueError as e:
                return {"error": str(e)}
            except instaloader.exceptions.LoginRequiredException:
                return {"error": "Instagram post is private or requires login."}
            except Exception as e:
                return {"error": f"Instagram fetch failed: {str(e)}"}

        elif platform == "x":
            tweet_id = extract_x_tweet_id(url)
            if not tweet_id:
                return {"error": "Invalid X/Twitter URL."}
            
            tweet_data = fetch_x_tweet(tweet_id)  # Assuming this returns dict with 'text' and 'media_urls'
            
            if "error" in tweet_data:
                return tweet_data

            caption = tweet_data.get("text", "").strip()
            original_media_urls = tweet_data.get("media_urls", [])

            # Process each media URL from X (try to get highest quality)
            for media_url in original_media_urls:
                # Upgrade to original quality if possible
                if ":large" in media_url:
                    media_url = media_url.replace(":large", ":orig")
                elif "?format=" in media_url and "&name=large" in media_url:
                    media_url = media_url.replace("&name=large", "&name=orig")

                # Guess extension
                ext = media_url.split(".")[-1].split("?")[0].lower()
                if ext not in ["jpg", "jpeg", "png", "mp4", "gif"]:
                    ext = "jpg"  # default fallback

                filename = f"{gen_uuid_str()}.{ext}"
                filepath = media_dir / filename
                local_url = f"/media/{filename}"

                if await download_file(session, media_url, filepath):
                    saved_media_paths.append(local_url)

            result = {
                "platform": "x",
                "caption": caption,
                "media_urls": saved_media_paths  
            }
            return result

        else:
            return {"error": "Unsupported platform. Only Instagram and X/Twitter are supported."}
        
        
def upload_to_imgbb(file_path: str, mime_type: str = "image/jpeg") -> Optional[str]:
    if not IMG_BB_API_KEY:
        return None
    filename = Path(file_path).name
    try:
        with open(file_path, 'rb') as f:
            files = {"image": (filename, f, mime_type)}
            data = {"key": IMG_BB_API_KEY}
            response = requests.post("https://api.imgbb.com/1/upload", data=data, files=files, timeout=30)
            response.raise_for_status()
            res = response.json()
            if res.get("success"):
                return res["data"]["url"]
    except Exception as e:
        print(f"ImgBB upload failed: {e}")
    return None





class FetchRequest(BaseModel):
    url: str

class CreateRequest(BaseModel):
    rephrase_prompt: str
    image_suggestion: str
    theme_id: str
    model: str = "gemini-2.5-flash-image"
    imgpath:str
    caption:str
    
def init(app):
    @app.post("/api/fetch-post-details")
    async def fetch_post_details(request: FetchRequest):
        result = await fetch_social_post(request.url)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result


    @app.post("/api/create-draft-task")
    async def create_draft_task(request: CreateRequest, db: AsyncSession = Depends(get_db)):
        original_caption = request.caption

        clean_path = Path(request.imgpath).name  
        image_path = media_dir / clean_path

        if not image_path.is_file():
            raise HTTPException(status_code=404, detail=f"Image not found: {clean_path}")

        pil_img = Image.open(image_path)
        result = await db.execute(select(ImageTheme).where(ImageTheme.theme_id == request.theme_id))
        theme = result.scalar_one_or_none()
        if not theme:
            raise HTTPException(status_code=404, detail="Image theme not found.")

        theme_name = theme.name
        theme_desc = theme.description or ""

        # Create task
        task_id = gen_uuid_str()
        task = Task(
            task_id=task_id,
            title=f"Rephrased post",
            status=TaskStatus.draft,
        )
        db.add(task)
        await db.flush()

        original_path = media_dir / f"{task_id}_original.jpg"
        pil_img.save(original_path, "JPEG", quality=95)

        if not OPENAI_API_KEY:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set.")
        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        image_prompt = f"{request.image_suggestion}. Apply the theme: {theme_name} - {theme_desc}"
        rephrase_full = f"{request.rephrase_prompt}. Original caption: '{original_caption}'. Incorporate the image theme."

        try:
            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a social media caption rephraser for a shoe company. Output only valid JSON."},
                    {"role": "user", "content": f"{rephrase_full}\n\nRespond with JSON: {{\"caption\": \"rephrased caption\", \"hashtags\": [\"#tag1\", \"#tag2\"], \"suggested_posting_time\": \"time suggestion\"}}"}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            gen_data = json.loads(response.choices[0].message.content)
            caption = gen_data.get("caption", original_caption)
            hashtags = gen_data.get("hashtags", [])
            suggested_time = gen_data.get("suggested_posting_time", "Weekdays 8-10 AM EST")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Caption rephrasing failed: {str(e)}")


        try:
            # Step 1: Check if file exists
            if not os.path.exists(original_path):
                raise HTTPException(status_code=400, detail="Image file not found.")

            if not os.path.isfile(original_path):
                raise HTTPException(status_code=400, detail="Path is not a file.")

            # Step 2: Try to open and verify it's a valid image
            try:
                with Image.open(original_path) as img:  # 'with' ensures file closes properly
                    img.verify()  # Forces Pillow to fully validate the image data
                    # Re-open after verify() since it invalidates the image object
                    input_image = Image.open(original_path)
                    input_image = input_image.convert("RGB")  # Optional: Normalize format
                print(f"Valid image loaded: {original_path} ({input_image.size}, {input_image.format})")
            except (UnidentifiedImageError, OSError, IOError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid or corrupted image file: {str(e)}")

            # Proceed with Gemini call
            gen_response = GenaiClient.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=[image_prompt, input_image],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"]
                ),
            )

            # Extract image (NOTE: Big fix here!)
            image_data = None
            mime_type_edited = "image/png"
            edited_path = media_dir / f"{task_id}_edited.png"
            for candidate in gen_response.candidates:
                for part in candidate.content.parts:
                    if part.inline_data is not None:
                        image_data = part.inline_data.data
                        edited_image = Image.open(io.BytesIO(image_data))
                        edited_image.save(edited_path)
                        print(f"New edited image saved as {edited_path}")
                        image_saved = True
                        break
                else:
                    continue
                break

            if not image_data:
                raise ValueError("No image generated by Gemini.")

        except Exception as e:
            if isinstance(e, HTTPException):
                raise e 
            raise HTTPException(status_code=500, detail=f"Image editing failed: {str(e)}")


        edited_image.save(edited_path, "PNG")
        storage_path_edited = str(edited_path)
        size_bytes_edited = edited_path.stat().st_size
        with open(storage_path_edited, 'rb') as f:
            checksum_edited = hashlib.sha256(f.read()).hexdigest()

        # Upload edited
        img_url_edited = upload_to_imgbb(storage_path_edited, mime_type_edited)


        gen_id = gen_uuid_str()
        generated_content = GeneratedContent(
            gen_id=gen_id,
            task_id=task_id,
            prompt=request.rephrase_prompt,
            caption=caption,
            hashtags=hashtags,
            image_prompt=image_prompt,
            image_generated=True,
            suggested_posting_time=suggested_time,
            meta={
                "text_model": "gpt-4o-mini",
                "image_model": request.model
            }
        )
        db.add(generated_content)
        await db.flush()  # Flush to get gen_id set

        media_edited = Media(
            media_id=gen_uuid_str(),
            task_id=task_id,
            gen_id=gen_id,
            storage_path=Path(storage_path_edited).name,
            mime_type=mime_type_edited,
            img_url=img_url_edited,
            width=edited_image.width,
            height=edited_image.height,
            size_bytes=size_bytes_edited,
            checksum=checksum_edited,
            is_generated=True
        )
        db.add(media_edited)

        await db.commit()

        return {
            "success": True,
            "task_id": task_id,
            "message": "Draft task created successfully with rephrased content and edited image."
        }
