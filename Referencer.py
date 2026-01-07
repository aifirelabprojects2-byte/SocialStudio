import itertools
import os
import json
import time
import uuid
import hashlib
import asyncio
import random
import re
import io
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
import aiohttp
import requests
from apify_client import ApifyClient  
from dotenv import load_dotenv
from sqlalchemy import select
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI
from PIL import Image, UnidentifiedImageError, ImageEnhance, ImageStat
from google import genai
from google.genai import types

import Accounts
from CostCalc import calculate_image_cost, calculate_llm_cost
from Database import GeneratedContent, ImageTheme, LLMUsage, Media, Task, TaskStatus, get_db

load_dotenv()

# --- Config & Environment ---

def gen_uuid_str() -> str:
    return str(uuid.uuid4())

media_dir = Path("static/media")

class Config:
    # Kept for general usage, though Instaloader specific retries are removed
    RETRY_ATTEMPTS: int = 3

# Updated API Keys
APIFY_KEY = os.getenv("APIFY_KEY")
IMG_BB_API_KEY = os.getenv("IMGBB_API")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GenaiClient = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- Helper Functions ---

def detect_platform(url: str) -> str:
    parsed = urlparse(url.lower())
    domain = parsed.netloc
    if "instagram.com" in domain:
        return "instagram"
    elif "x.com" in domain or "twitter.com" in domain:
        return "x"
    return "unknown"

async def download_file(session: aiohttp.ClientSession, url: str, filepath: Path) -> bool:
    try:
        async with session.get(url, timeout=30) as resp:
            if resp.status == 200:
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

# --- Apify Fetching Logic (Synchronous) ---

def fetch_instagram_apify(post_url: str) -> Dict[str, Any]:
    """
    Fetches Instagram post data using Apify actor shu8hvrXbJbY3Eb9W.
    """
    if not APIFY_KEY:
        return {"error": "APIFY_KEY not set."}

    try:
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
        dataset_items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        
        if not dataset_items:
            return {"error": "No data found for this Instagram URL."}

        item = dataset_items[0]
        media_url = item.get("videoUrl") if item.get("videoUrl") else item.get("displayUrl")
        caption = item.get("caption", "")

        return {
            "caption": caption,
            "media_url": media_url, # Single URL
            "type": "video" if item.get("videoUrl") else "image"
        }
    except Exception as e:
        return {"error": f"Apify Instagram Error: {str(e)}"}

def fetch_x_apify(tweet_url: str) -> Dict[str, Any]:
    """
    Fetches X/Twitter data using Apify actor kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest.
    """
    if not APIFY_KEY:
        return {"error": "APIFY_KEY not set."}

    try:
        client = ApifyClient(APIFY_KEY)
        
        # Clean URL to get ID
        try:
            tweet_id = tweet_url.split("/")[-1].split("?")[0]
        except Exception:
            return {"error": "Could not parse Tweet ID from URL"}

        run_input = {
            "tweetIDs": [tweet_id],
            "maxItems": 1
        }

        run = client.actor(
            "kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest"
        ).call(run_input=run_input)

        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        
        if not items:
            return {"error": "Tweet not found or private."}

        item = items[0]
        caption = item.get("text") or ""

        # Process media
        media_url = None
        media_entities = item.get("extendedEntities", {}).get("media", []) or []

        if media_entities:
            media = media_entities[0]  # Grab first media item
            media_type = media.get("type", "")

            if media_type == "photo":
                media_url = media.get("media_url_https") or media.get("url") or media.get("media_url")
            
            elif media_type in ("video", "animated_gif"):
                video_info = media.get("video_info", {})
                variants = video_info.get("variants", [])
                
                # Filter for MP4s and sort by bitrate to get best quality
                mp4s = [
                    v for v in variants
                    if isinstance(v, dict) and v.get("content_type") == "video/mp4" and "bitrate" in v
                ]
                
                if mp4s:
                    media_url = max(mp4s, key=lambda x: x.get("bitrate", 0)).get("url")
                else:
                    # Fallback
                    for v in variants:
                        if isinstance(v, dict) and "url" in v:
                            media_url = v["url"]
                            break
                    media_url = media_url or media.get("videoUrl") or media.get("url")

        if not media_url and caption == "":
             return {"error": "No content found in tweet."}

        return {
            "caption": caption,
            "media_url": media_url,
            "type": "video" if media_url and ".mp4" in media_url else "image"
        }

    except Exception as e:
        return {"error": f"Apify X Error: {str(e)}"}


# --- Main Async Fetcher ---

async def fetch_social_post(url: str) -> Dict[str, Any]:
    platform = detect_platform(url)
    loop = asyncio.get_event_loop()
    
    # 1. Fetch metadata using Apify (Offload sync calls to thread)
    fetched_data = {}
    
    if platform == "instagram":
        fetched_data = await loop.run_in_executor(None, fetch_instagram_apify, url)
    elif platform == "x":
        fetched_data = await loop.run_in_executor(None, fetch_x_apify, url)
    else:
        return {"error": "Unsupported platform. Only Instagram and X/Twitter are supported."}

    if "error" in fetched_data:
        return fetched_data

    # 2. Extract Data
    caption = fetched_data.get("caption", "").strip()
    remote_media_url = fetched_data.get("media_url")
    
    # 3. Download Media Locally (Maintain compatibility with rest of app)
    saved_media_paths: List[str] = []
    
    if remote_media_url:
        async with aiohttp.ClientSession() as session:
            # Determine extension
            ext = remote_media_url.split("?")[0].split(".")[-1].lower()
            if len(ext) > 4 or ext not in ["jpg", "jpeg", "png", "mp4", "gif"]:
                # Basic fallback based on type hint if extension parsing fails
                ext = "mp4" if fetched_data.get("type") == "video" else "jpg"

            filename = f"{gen_uuid_str()}.{ext}"
            filepath = media_dir / filename
            local_url = f"/media/{filename}"

            if await download_file(session, remote_media_url, filepath):
                saved_media_paths.append(local_url)
    
    # Return structure matching what your frontend expects
    return {
        "platform": platform,
        "caption": caption,
        "media_urls": saved_media_paths  # List of local paths
    }


# --- Image Processing & Utils ---

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

def add_watermark(
    image_path: str,
    position: str = "bottom-right",         
    light_logo_path: str = "logo_light.png",
    dark_logo_path: str = "logo_dark.png",
    margin: int = 13,                      
    opacity: float = 1.0,                  
    scale_factor: float = 0.16,            
    min_logo_size: int = 120                
) -> Image.Image:

    img = Image.open(image_path).convert("RGBA")
    width, height = img.size

    logo_width = max(min_logo_size, int(width * scale_factor))
    gray = img.convert("L")
    stat = ImageStat.Stat(gray)
    brightness = stat.mean[0] 
    logo_path = light_logo_path if brightness > 115 else dark_logo_path

    if not os.path.exists(logo_path):
        raise FileNotFoundError(f"Logo not found: {logo_path}")
    logo = Image.open(logo_path).convert("RGBA")
    logo_w, logo_h = logo.size
    ratio = logo_w / logo_h
    
    new_logo_w = logo_width
    new_logo_h = int(new_logo_w / ratio)
    logo = logo.resize((new_logo_w, new_logo_h), Image.Resampling.LANCZOS)

    if opacity < 1.0:
        alpha = logo.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
        logo.putalpha(alpha)

    pos = position.lower()

    if pos in ["br", "bottom-right", "bottom_right"]:
        paste_x = width - new_logo_w - margin
        paste_y = height - new_logo_h - margin

    elif pos in ["tl", "top-left", "top_left"]:
        paste_x = margin
        paste_y = margin

    elif pos in ["bl", "bottom-left", "bottom_left"]:
        paste_x = margin
        paste_y = height - new_logo_h - margin

    elif pos in ["tr", "top-right", "top_right"]:
        paste_x = width - new_logo_w - margin
        paste_y = margin
    else:
        raise ValueError("Position must be one of: 'top-left', 'bottom-right', 'top-right', 'bottom-left'")

    paste_x = max(0, min(paste_x, width - new_logo_w))
    paste_y = max(0, min(paste_y, height - new_logo_h))

    img.paste(logo, (paste_x, paste_y), logo)

    return img


class FetchRequest(BaseModel):
    url: str

class CreateRequest(BaseModel):
    rephrase_prompt: str
    image_suggestion: str
    theme_id: Optional[str] = None
    model: str = "gemini-2.5-flash-image"
    imgpath: str
    caption: str
    watermark_position: Optional[str] = None  # None, top-left, bottom-right, top-right, bottom-left
    
def init(app):
    @app.post("/api/fetch-post-details")
    async def fetch_post_details(request: FetchRequest,_=Depends(Accounts.get_current_user)):
        result = await fetch_social_post(request.url)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result


    @app.post("/api/create-draft-task")
    async def create_draft_task(request: CreateRequest, db: AsyncSession = Depends(get_db),_=Depends(Accounts.get_current_user)):
        original_caption = request.caption

        clean_path = Path(request.imgpath).name  
        image_path = media_dir / clean_path

        if not image_path.is_file():
            raise HTTPException(status_code=404, detail=f"Image not found: {clean_path}")

        pil_img = Image.open(image_path)
        theme_name = ""
        theme_desc = ""
        if request.theme_id:
            result = await db.execute(select(ImageTheme).where(ImageTheme.theme_id == request.theme_id))
            theme = result.scalar_one_or_none()
            if theme:
                theme_name = theme.name
                theme_desc = theme.description or ""
            else:
                # Optional, so log warning but proceed without theme
                print(f"Warning: Image theme not found for theme_id: {request.theme_id}")

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

        image_prompt = request.image_suggestion
        if theme_name:
            image_prompt += f". Apply the theme: {theme_name} - {theme_desc}"
        rephrase_full = f"{request.rephrase_prompt}. Original caption: '{original_caption}'. Incorporate the image theme." if theme_name else f"{request.rephrase_prompt}. Original caption: '{original_caption}'."

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
            if not os.path.exists(original_path):
                raise HTTPException(status_code=400, detail="Image file not found.")

            if not os.path.isfile(original_path):
                raise HTTPException(status_code=400, detail="Path is not a file.")

            try:
                with Image.open(original_path) as img: 
                    img.verify()  
                    input_image = Image.open(original_path)
                    input_image = input_image.convert("RGB")  # Optional: Normalize format
                print(f"Valid image loaded: {original_path} ({input_image.size}, {input_image.format})")
            except (UnidentifiedImageError, OSError, IOError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid or corrupted image file: {str(e)}")

            start = time.time()
            
            gen_response = GenaiClient.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=[image_prompt, input_image],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"]
                ),
            )
            latency_ms = int((time.time() - start) * 1000)
            
            cost_usd = float(calculate_image_cost(model="gemini-2.5-flash-image", images_generated=1))
            usage_row = LLMUsage(
                    feature="rephrased_post",
                    model="gemini-2.5-flash-image",
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    status="success"
                )
            db.add(usage_row)

            image_data = None
            mime_type_edited = "image/png"
            edited_path = media_dir / f"{task_id}_edited.png"
            edited_image = None
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
                raise ValueError("No image generated by Gemini")

            # Apply watermark if requested
            if request.watermark_position and edited_image:
                try:
                    watermarked_image = add_watermark(
                        str(edited_path),
                        position=request.watermark_position
                    )
                    watermarked_image = watermarked_image.convert("RGB")
                    edited_path = media_dir / f"{task_id}_edited_watermarked.jpg"
                    watermarked_image.save(edited_path, "JPEG", quality=95)
                    mime_type_edited = "image/jpeg"
                    edited_image = watermarked_image  # Update for metadata
                    print(f"Watermark applied and saved as {edited_path}")
                except Exception as wm_error:
                    print(f"Watermark application failed: {wm_error}")
                    # Proceed without watermark

        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            db.add(LLMUsage(
                feature="rephrased_post",
                model="gemini-2.5-flash-image",
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost_usd=0,
                latency_ms=latency_ms,
                status="error",
            ))
            await db.commit()
            if isinstance(e, HTTPException):
                raise e 
            raise HTTPException(status_code=500, detail=f"Image editing failed: {str(e)}")

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
        await db.flush()  

        media_edited = Media(
            media_id=gen_uuid_str(),
            task_id=task_id,
            gen_id=gen_id,
            storage_path=Path(storage_path_edited).name,
            mime_type=mime_type_edited,
            img_url=img_url_edited,
            width=edited_image.width if edited_image else 0,
            height=edited_image.height if edited_image else 0,
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