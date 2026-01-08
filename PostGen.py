import asyncio
import hashlib
import io
import os
import time
import json
from datetime import datetime
from typing import List, Optional, Literal, Tuple, Any
from pathlib import Path
from functools import partial

from fastapi import Form, Query, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import requests
from PIL import Image, UnidentifiedImageError, ImageEnhance, ImageStat
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, update, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError
from google import genai
from google.genai import types

# Local Imports
import Accounts
from CostCalc import calculate_image_cost, calculate_llm_cost
from Database import LLMUsage, TaskStatus, gen_uuid_str, get_db, Task, GeneratedContent, Media
from Configs import IMG_BB_API_KEY, client

# Constants
media_dir = Path("static/media")
GenaiClient = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
DEFAULT_LIMIT = 4

# --- Helper Functions ---

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

class GeneratedContentResponse(BaseModel):
    caption: str = Field(..., max_length=2000)
    hashtags: List[str] = Field(default_factory=list, max_items=10)
    image_prompt: Optional[str] = Field(None, max_length=1000)
    suggested_posting_time: str 

# --- Routes ---

def init(app):
    @app.get("/api/tasks")
    async def api_list_tasks(
        db: AsyncSession = Depends(get_db),
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
        _=Depends(Accounts.get_current_user)
    ):
        limit = min(limit, DEFAULT_LIMIT)
        
        stmt = (
            select(Task)
            .where(Task.status == TaskStatus.draft)
            .options(
                selectinload(Task.generated_contents),
                selectinload(Task.media)
            )
            .order_by(Task.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        tasks = result.scalars().all()
        
        count_stmt = select(func.count()).select_from(Task).where(Task.status == TaskStatus.draft)
        total_count_result = await db.execute(count_stmt)
        total_drafts = total_count_result.scalar_one()

        task_list = []
        for task in tasks:
            content = None
            if task.generated_contents:
                content = max(task.generated_contents, key=lambda x: x.created_at)

            media_url = None
            if task.media:
                generated = [m for m in task.media if m.is_generated]
                media = generated[0] if generated else task.media[0]
                media_url = f"/media/{media.storage_path}" 

            task_list.append({
                "task_id": task.task_id,
                "title": task.title or "Untitled Draft",
                "created_at": task.created_at.isoformat(),
                "caption_preview": (
                            (content.caption[:120] + "...")
                            if content and content.caption and len(content.caption) > 120
                            else (content.caption if content and content.caption else "")
                        ),
                "has_image": bool(media_url),
                "media_url": media_url,
            })

        return {
            "tasks": task_list,
            "total_count": total_drafts,
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if (offset + limit) < total_drafts else None,
            "prev_offset": offset - limit if offset > 0 else None,
        }
        
    @app.post("/generate-preview")
    async def generate_preview(
        prompt: str = Form(...),
        num_drafts: int = Form(1),
        generate_image: Literal["yes", "no"] = Form("no"),
        image_style: Optional[str] = Form("realistic"),  
        db: AsyncSession = Depends(get_db),
        _=Depends(Accounts.get_current_user)
    ):
        if num_drafts < 1 or num_drafts > 10:
            raise HTTPException(status_code=400, detail="Number of drafts must be between 1 and 10")
        
        want_image = generate_image == "yes"
        style_mapping = {
            "realistic": "realistic photo",
            "cinematic": "cinematic scene with dramatic lighting",
            "cartoon": "cartoon style",
            "illustration": "beautiful digital illustration",
            "digital_art": "stunning digital art",
            "anime": "anime style",
            "minimalist": "clean minimalist design",
            "vintage": "vintage retro style",
        }
        style_prompt = style_mapping.get(image_style, "realistic photo")

        # 1. PURE LOGIC FUNCTION (NO DB ACCESS)
        # This function runs in parallel without touching the shared session
        async def generate_content_data(i: int):
            start = time.time()
            user_content = f"""Topic: {prompt} - Generate variation {i + 1}
Include image prompt: {want_image}
Image style: {style_prompt if want_image else "N/A"}
Generate the JSON now."""
            
            try:
                completion = await client.beta.chat.completions.parse(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": """You are a professional social media manager. 
Generate engaging social media content for the given topic. 
Output ONLY valid JSON matching this exact structure:
{
"caption": "The full post caption text (1-3 sentences, engaging, with emojis if appropriate). Max 2000 chars.",
"hashtags": ["tag1", "tag2", "tag3"],
"image_prompt": "Detailed description for AI image generation (if requested). Max 1000 chars.",
"suggested_posting_time": "Best time to post: e.g., 'Weekdays 8-10 AM EST'."
}
Rules:
- For image_prompt: Start with the chosen style and make it highly detailed.
- Only include image_prompt if requested.
- Hashtags: 3-10 relevant, lowercase, no # symbol."""
                        },
                        {"role": "user", "content": user_content},
                    ],
                    temperature=0.8,
                    response_format=GeneratedContentResponse,
                )

                latency_ms = int((time.time() - start) * 1000)
                usage = completion.usage
                
                # Usage Data (Dict)
                usage_data = {
                    "feature": "generate_post",
                    "model": "gpt-4o-mini",
                    "input_tokens": usage.prompt_tokens,
                    "output_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost_usd": calculate_llm_cost("gpt-4o-mini", usage.prompt_tokens, usage.completion_tokens),
                    "latency_ms": latency_ms,
                    "status": "success"
                }

                # Result Data (Dict)
                result = completion.choices[0].message.parsed.model_dump()
                
                # Post-process tags
                result["hashtags"] = [
                    tag.strip().lstrip("#").lower() for tag in result["hashtags"] 
                    if tag.strip() and not tag.strip().startswith("#")
                ]
                result["hashtags"] = list(dict.fromkeys(result["hashtags"]))[:10]
                
                if not result["suggested_posting_time"]:
                    result["suggested_posting_time"] = "Weekdays 9-11 AM local time"

                return {
                    "success": True,
                    "usage": usage_data,
                    "result": result
                }

            except Exception as e:
                latency_ms = int((time.time() - start) * 1000)
                # Failure Usage Data
                usage_data = {
                    "feature": "generate_post",
                    "model": "gpt-4o-mini",
                    "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
                    "cost_usd": 0, "latency_ms": latency_ms,
                    "status": "error"
                }
                return {
                    "success": False,
                    "usage": usage_data,
                    "error": str(e)
                }

        # 2. RUN PARALLEL GENERATION
        coros = [generate_content_data(i) for i in range(num_drafts)]
        results_data = await asyncio.gather(*coros)

        # 3. SEQUENTIAL DB WRITES (High Scale Optimization)
        # We process all DB operations in one go to avoid race conditions.
        
        successful_drafts = []
        db_objects_to_add = []

        try:
            for data in results_data:
                # Add Usage Log (Success or Fail)
                usage_row = LLMUsage(**data["usage"])
                db.add(usage_row) # Add to session, but don't commit yet
                
                if data["success"]:
                    res = data["result"]
                    
                    # Create Task
                    new_task = Task(
                        title=prompt[:40] + "..." if len(prompt) > 40 else prompt,
                        status=TaskStatus.draft,
                        time_zone="UTC",
                    )
                    db.add(new_task)
                    
                    # Create GeneratedContent (Linked via object reference)
                    gen_content = GeneratedContent(
                        task=new_task, # SQLAlchemy handles the ID assignment automatically upon flush
                        prompt=prompt,
                        caption=res["caption"],
                        hashtags=res["hashtags"],
                        image_prompt=res["image_prompt"] if want_image else None,
                        suggested_posting_time=res["suggested_posting_time"],
                        image_generated=False,
                        meta={
                            "model": "gpt-4o-mini",
                            "structured": True,
                            "image_style": image_style if want_image else None  
                        },
                    )
                    db.add(gen_content)
                    
                    # For response
                    successful_drafts.append({
                        "task_id": "pending", # We don't have ID yet, but front-end usually reloads list
                        "result": res,
                        "prompt": prompt,
                        "generate_image": want_image
                    })

            if not successful_drafts:
                # Commit usages even if all failed
                await db.commit()
                raise ValueError("All generations failed.")

            # Single atomic commit for everything
            await db.commit()
            
            # Note: IDs are populated in the objects after commit if you need to return them, 
            # but usually for 'preview' just returning success is enough or reloading the list.
            
            return JSONResponse({
                "success": True,
                "drafts": successful_drafts, # Contains the data to show immediately
                "message": f"Generated {len(successful_drafts)} drafts successfully."
            })

        except ValueError as ve:
             # Already committed usages, just raise
            raise HTTPException(status_code=500, detail=str(ve))
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Database commit failed: {str(e)}")


    @app.get("/tasks/{task_id}")
    async def get_task(task_id: str, db: AsyncSession = Depends(get_db),_=Depends(Accounts.get_current_user)):
        stmt = select(Task).options(
            selectinload(Task.generated_contents),
            selectinload(Task.media)
        ).where(Task.task_id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

        gen_content = task.generated_contents[0] if task.generated_contents else None
        media = task.media[0] if task.media else None

        return JSONResponse({
            "task": {
                "id": task.task_id,
                "title": task.title,
                "status": task.status.value if task.status else None,
                "created_at": task.created_at.isoformat() if task.created_at else None,
            },
            "content": {
                "caption": gen_content.caption if gen_content else "",
                "hashtags": gen_content.hashtags if gen_content else [],
                "image_prompt": gen_content.image_prompt if gen_content else None,
                "image_generated": gen_content.image_generated if gen_content else False,
            },
            "media_url": f"/media/{media.storage_path}" if media and media.storage_path else None,
        })
        
    @app.post("/tasks/{task_id}/approve")
    async def approve_task(task_id: str, db: AsyncSession = Depends(get_db),_=Depends(Accounts.get_current_user)):
        try:
            async with db.begin():
                stmt = select(Task).where(Task.task_id == task_id)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()

                if not task:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

                if task.status != TaskStatus.draft:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Task cannot be approved from status '{task.status.value}'."
                    )

                task.status = TaskStatus.draft_approved
                db.add(task)
            await db.refresh(task)

        except HTTPException:
            raise
        except SQLAlchemyError as e:
            try:
                await db.rollback()
            except Exception:
                pass
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Failed to approve task due to a database error")

        return JSONResponse({
            "task": {
                "id": task.task_id,
                "status": task.status.value,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None
            }
        })

    @app.put("/tasks/{task_id}")
    async def update_task(
        task_id: str,
        caption: str = Form(None),
        hashtags: str = Form(None),
        image_prompt: str = Form(None),
        db: AsyncSession = Depends(get_db),
        _=Depends(Accounts.get_current_user)
    ):
        try:
            hashtags_list = json.loads(hashtags) if hashtags else []
            
            stmt = update(GeneratedContent).where(GeneratedContent.task_id == task_id).values(
                caption=caption,
                hashtags=hashtags_list,
                image_prompt=image_prompt,
            )
            await db.execute(stmt)
            await db.commit()
            return JSONResponse({"success": True, "message": "Updated successfully"})
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/tasks/{task_id}")
    async def delete_task(task_id: str, db: AsyncSession = Depends(get_db),_=Depends(Accounts.get_current_user)):
        stmt = delete(Task).where(Task.task_id == task_id)
        await db.execute(stmt)
        await db.commit()
        return JSONResponse({"success": True, "message": "Deleted successfully"})

    @app.post("/tasks/{task_id}/generate-image")
    async def generate_image_for_task(
        task_id: str,
        model: str = Form("gemini-2.5-flash-image", description="Gemini model"),
        watermark_position: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db),
        _=Depends(Accounts.get_current_user)
    ):
        # 1. PRE-CHECK & DATA FETCHING
        allowed_models = ["gemini-2.5-flash-image", "gemini-3-pro-image-preview"]
        if model not in allowed_models:
            raise HTTPException(status_code=400, detail=f"Invalid model.")

        stmt = select(GeneratedContent).join(Task).where(Task.task_id == task_id)
        result = await db.execute(stmt)
        gen_content = result.scalar_one_or_none()
        
        if not gen_content or not gen_content.image_prompt:
            raise HTTPException(status_code=400, detail="No image prompt available")

        # Capture values into local variables to avoid DetachedInstanceErrors
        target_gen_id = gen_content.gen_id
        image_prompt = gen_content.image_prompt

        media_stmt = select(Media).where(Media.task_id == task_id)
        media_result = await db.execute(media_stmt)
        existing_media = media_result.scalar_one_or_none()
        
        # Load existing image in thread pool to avoid blocking
        loop = asyncio.get_running_loop()
        input_image = None
        
        if existing_media and existing_media.storage_path:
            input_image_path = media_dir / existing_media.storage_path
            if input_image_path.is_file():
                try:
                    # Run IO/Image processing in executor
                    input_image = await loop.run_in_executor(
                        None, 
                        lambda: Image.open(input_image_path).convert("RGB")
                    )
                except Exception as e:
                    print(f"Failed to load existing image: {e}")

        # 2. GENERATE (Heavy Lifting)
        start = time.time()
        try:
            contents = [image_prompt]
            if input_image:
                contents.append(input_image)
            
            # Call Gemini API
            response = await loop.run_in_executor(
                None,
                partial(
                    GenaiClient.models.generate_content,
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(response_modalities=["IMAGE"])
                )
            )
            
            image_data = None
            if response.candidates:
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if part.inline_data:
                                image_data = part.inline_data.data
                                break
                    if image_data: break
            
            if not image_data:
                raise ValueError("No image generated by Gemini")

            # Process Image Saving in Executor (CPU Bound)
            def save_and_process_image(data_bytes):
                generated_img = Image.open(io.BytesIO(data_bytes))
                f_name = f"{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                f_path = media_dir / f_name
                generated_img.save(f_path, "PNG")
                
                final_img = generated_img
                m_type = "image/png"
                
                if watermark_position:
                    try:
                        watermarked = add_watermark(str(f_path), position=watermark_position)
                        final_img = watermarked.convert("RGB")
                        f_name = f"{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_watermarked.jpg"
                        f_path = media_dir / f_name
                        final_img.save(f_path, "JPEG", quality=95)
                        m_type = "image/jpeg"
                    except Exception as wm_error:
                        print(f"Watermark failed: {wm_error}")

                return f_name, f_path, final_img.width, final_img.height, m_type

            filename, filepath, width, height, mime_type = await loop.run_in_executor(
                None, save_and_process_image, image_data
            )

            # Get File Stats
            stat = await loop.run_in_executor(None, filepath.stat)
            size_bytes = stat.st_size
            
            # Checksum (CPU Bound)
            def calculate_checksum():
                return hashlib.sha256(filepath.read_bytes()).hexdigest()
            checksum = await loop.run_in_executor(None, calculate_checksum)
            
            # Upload to ImgBB (Network I/O - wrap in executor just in case)
            img_url = await loop.run_in_executor(
                None, upload_to_imgbb, str(filepath), mime_type
            )
            
            latency_ms = int((time.time() - start) * 1000)

            # 3. DB PERSISTENCE
            # Re-check for media inside this final block for update vs insert
            existing_gen_stmt = select(Media).where(Media.task_id == task_id, Media.is_generated == True)
            existing_gen_res = await db.execute(existing_gen_stmt)
            existing_gen_media = existing_gen_res.scalar_one_or_none()

            if existing_gen_media:
                existing_gen_media.storage_path = filename
                existing_gen_media.size_bytes = size_bytes
                existing_gen_media.img_url = img_url
                existing_gen_media.mime_type = mime_type
                existing_gen_media.width = width
                existing_gen_media.height = height
                existing_gen_media.checksum = checksum
            else:
                new_media = Media(
                    media_id=gen_uuid_str(),
                    task_id=task_id,
                    gen_id=target_gen_id,
                    storage_path=filename,
                    mime_type=mime_type,
                    size_bytes=size_bytes,
                    img_url=img_url,
                    width=width,
                    height=height,
                    checksum=checksum,
                    is_generated=True,
                )
                db.add(new_media)

            await db.execute(
                update(GeneratedContent)
                .where(GeneratedContent.gen_id == target_gen_id)
                .values(image_generated=True)
            )

            cost_usd = float(calculate_image_cost(model=model, images_generated=1))
            db.add(LLMUsage(
                feature="generate_image_regen",
                model=model,
                input_tokens=0, output_tokens=0, total_tokens=0,
                cost_usd=cost_usd, latency_ms=latency_ms, status="success"
            ))
            
            await db.commit()

            return JSONResponse({
                "success": True,
                "media_url": f"/media/{filename}",
                "message": "Image regenerated successfully"
            })

        except Exception as e:
            await db.rollback()
            latency_ms = int((time.time() - start) * 1000)
            
            error_usage = LLMUsage(
                feature="generate_image_regen",
                model=model,
                input_tokens=0, output_tokens=0, total_tokens=0,
                cost_usd=0, latency_ms=latency_ms, status="error"
            )
            try:
                # New transaction for logging error
                db.add(error_usage)
                await db.commit()
            except:
                pass
            
            print(f"Error in generate_image_for_task: {e}")
            raise HTTPException(status_code=500, detail=str(e))


    @app.get("/api/tasks/approved", status_code=200)
    async def list_approved_drafts(
        db: AsyncSession = Depends(get_db),
        limit: int = Query(DEFAULT_LIMIT, ge=1),
        offset: int = 0,
        _=Depends(Accounts.get_current_user)
    ):
        limit = min(limit, DEFAULT_LIMIT)

        stmt = (
            select(Task)
            .where(Task.status == TaskStatus.draft_approved)
            .options(selectinload(Task.generated_contents), selectinload(Task.media))
            .order_by(Task.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        tasks = result.scalars().all()

        count_stmt = select(func.count()).select_from(Task).where(Task.status == TaskStatus.draft_approved)
        total_count_result = await db.execute(count_stmt)
        total = total_count_result.scalar_one()

        task_list = []
        for task in tasks:
            content = None
            if task.generated_contents:
                content = max(task.generated_contents, key=lambda x: x.created_at)

            media_url = None
            if task.media:
                generated = [m for m in task.media if m.is_generated]
                media = generated[0] if generated else task.media[0]
                media_url = f"/media/{media.storage_path}"

            caption_preview = ""
            if content and content.caption:
                caption_preview = (content.caption[:120] + "...") if len(content.caption) > 120 else content.caption
            elif content and content.prompt:
                caption_preview = (content.prompt[:120] + "...") if len(content.prompt) > 120 else content.prompt

            task_list.append({
                "task_id": task.task_id,
                "title": task.title or "Untitled Draft",
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "caption_preview": caption_preview,
                "has_image": bool(media_url),
                "media_url": media_url,
            })

        return {
            "tasks": task_list,
            "total_count": total,
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if (offset + limit) < total else None,
            "prev_offset": offset - limit if offset > 0 else None,
        }

    @app.get("/api/tasks/approved/{task_id}", status_code=200)
    async def get_approved_draft_detail(task_id: str, db: AsyncSession = Depends(get_db),_=Depends(Accounts.get_current_user)):
        stmt = (
            select(Task)
            .where(Task.task_id == task_id, Task.status == TaskStatus.draft_approved)
            .options(selectinload(Task.generated_contents), selectinload(Task.media))
        )
        result = await db.execute(stmt)
        task = result.scalars().first()
        if not task:
            raise HTTPException(status_code=404, detail="Approved draft not found")

        content = None
        if task.generated_contents:
            content = max(task.generated_contents, key=lambda x: x.created_at)

        media_url = None
        media_items = []
        for m in task.media or []:
            url = f"/media/{m.storage_path}"
            media_items.append({"media_id": m.media_id, "url": url, "mime_type": m.mime_type})
            if m.is_generated and not media_url:
                media_url = url
        if not media_url and media_items:
            media_url = media_items[0]["url"]

        return {
            "task_id": task.task_id,
            "title": task.title,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "status": task.status.value,
            "generated_content": {
                "gen_id": content.gen_id,
                "prompt": content.prompt,
                "caption": content.caption,
                "hashtags": content.hashtags,
                "suggested_posting_time": content.suggested_posting_time,
                "created_at": content.created_at.isoformat() if content.created_at else None,
            } if content else None,
            "media": media_items,
            "preview_image": media_url,
        }