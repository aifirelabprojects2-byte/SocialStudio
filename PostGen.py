from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from ImgGen import ImageGenClient
import os
import base64
import io
from datetime import datetime
from typing import List, Optional, Literal
from pathlib import Path
from fastapi import Form, Query, Request, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
import json
from Database import TaskStatus, get_db, Task, GeneratedContent, Media
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, update, delete
from sqlalchemy.orm import selectinload

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Set OPENAI_API_KEY in .env")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
image_client = ImageGenClient(api_key=os.getenv("IMG_API_KEY"))   


media_dir = Path("static/media")


class GeneratedContentResponse(BaseModel):
    caption: str = Field(..., max_length=2000)
    hashtags: List[str] = Field(default_factory=list, max_items=10)
    image_prompt: Optional[str] = Field(None, max_length=1000)
    suggested_posting_time: str 

# Constants for Pagination
DEFAULT_LIMIT = 4

def init(app):
    @app.get("/api/tasks")
    async def api_list_tasks(
        db: AsyncSession = Depends(get_db),
        # Add query parameters for pagination
        limit: int = DEFAULT_LIMIT,
        offset: int = 0
    ):
        # Ensure limit is reasonable (e.g., max 5 drafts)
        limit = min(limit, DEFAULT_LIMIT)
        
        # 1. Fetch the Paginated Tasks
        stmt = (
            select(Task)
            .where(Task.status == TaskStatus.draft)
            .options(
                selectinload(Task.generated_contents),
                selectinload(Task.media)
            )
            .order_by(Task.created_at.desc())
            .limit(limit)  # Apply the limit
            .offset(offset)  # Apply the offset
        )
        result = await db.execute(stmt)
        tasks = result.scalars().all()
        
        # 2. Count Total Drafts (for pagination logic)
        count_stmt = select(func.count()).select_from(Task).where(Task.status == TaskStatus.draft)
        total_count_result = await db.execute(count_stmt)
        total_drafts = total_count_result.scalar_one()

        # 3. Process Tasks (your existing logic)
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
                "caption_preview": (content.caption[:120] + "...") if content and content.caption and len(content.caption) > 120 else (content.caption or ""),
                "has_image": bool(media_url),
                "media_url": media_url,
            })

        # Return the tasks along with total count and current pagination info
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
        generate_image: Literal["yes", "no"] = Form("no"),
        db: AsyncSession = Depends(get_db),
    ):
        want_image = generate_image == "yes"

        try:
            completion = await client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": """You are a professional social media manager. 

    Generate engaging social media content for the given topic. 

    Output ONLY valid JSON matching this exact structure - no explanations, no markdown, no extra text:

    {
    "caption": "The full post caption text (1-3 sentences, engaging, with emojis if appropriate). Max 2000 chars.",
    "hashtags": ["tag1", "tag2", "tag3"],  // 3-10 relevant hashtags WITHOUT the # symbol, lowercase, no duplicates.
    "image_prompt": "Detailed description for AI image generation (if requested). Max 1000 chars."  // Only include if image is requested, else omit or null.
    "suggested_posting_time": "Best time to post: e.g., 'Weekdays 8-10 AM EST' or 'Weekends 6-8 PM PST' based on typical engagement for this content type."
    }

    For hashtags: Always exclude the # symbol. Use relevant, concise terms (e.g., "aiart" not "#AIArt").
    For suggested_posting_time: Always provide a specific, actionable suggestion with timezone if relevant."""
                    },
                    {
                        "role": "user", 
                        "content": f"Topic: {prompt}\n\nInclude image prompt: {want_image}\n\nGenerate the JSON now."
                    },
                ],
                temperature=0.8,
                response_format=GeneratedContentResponse,
            )

            result = completion.choices[0].message.parsed.dict()

            # Post-process hashtags to ensure no # and normalize
            result["hashtags"] = [
                tag.strip().lstrip("#").lower() for tag in result["hashtags"] 
                if tag.strip() and not tag.strip().startswith("#")
            ]
            result["hashtags"] = list(dict.fromkeys(result["hashtags"]))[:10]  # Remove dups, limit

            # Ensure suggested_posting_time is formatted consistently
            if not result["suggested_posting_time"]:
                result["suggested_posting_time"] = "Weekdays 9-11 AM local time (high engagement for most audiences)"

            # ───── Save draft task ─────
            task = Task(
                title=prompt[:40] + "..." if len(prompt) > 40 else prompt,
                status="draft",
                time_zone="UTC",
            )
            db.add(task)
            await db.flush()  # gets task.task_id

            gen = GeneratedContent(
                task_id=task.task_id,
                prompt=prompt,
                caption=result["caption"],
                hashtags=result["hashtags"],
                image_prompt=result["image_prompt"] if want_image else None,
                suggested_posting_time=result["suggested_posting_time"],
                image_generated=False,
                meta={"model": "gpt-4o-mini", "structured": True},
            )
            db.add(gen)
            await db.commit()

            # Return JSON with task_id and result
            return JSONResponse({
                "success": True,
                "task_id": task.task_id,
                "gen_id": gen.gen_id,
                "result": result,
                "prompt": prompt,
                "generate_image": want_image,
            })

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Generation failed: {str(e)}"
            )


    @app.get("/tasks/{task_id}")
    async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
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
        
        
    from sqlalchemy.exc import SQLAlchemyError

    @app.post("/tasks/{task_id}/approve")
    async def approve_task(task_id: str, db: AsyncSession = Depends(get_db)):
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
            # print("Database error approving task %s: %s", task_id, e)
            try:
                await db.rollback()
            except Exception:
                print("Rollback failed")
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
        hashtags: str = Form(None),  # JSON string
        image_prompt: str = Form(None),
        db: AsyncSession = Depends(get_db),
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
    async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
        stmt = delete(Task).where(Task.task_id == task_id)
        await db.execute(stmt)
        await db.commit()
        return JSONResponse({"success": True, "message": "Deleted successfully"})


    @app.post("/tasks/{task_id}/generate-image")
    async def generate_image_for_task(
        task_id: str,
        db: AsyncSession = Depends(get_db),
    ):

        stmt = select(GeneratedContent).join(Task).where(Task.task_id == task_id)
        result = await db.execute(stmt)
        gen_content = result.scalar_one_or_none()
        if not gen_content or not gen_content.image_prompt:
            raise HTTPException(status_code=400, detail="No image prompt available")

        try:
            image_bytes,imgUrl = image_client.generate(
                prompt=gen_content.image_prompt,
                width=1024,
                height=1024,
                num_steps=4,   
            )


            # Save to media directory
            filename = f"{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = media_dir / filename

            with open(filepath, "wb") as f:
                f.write(image_bytes)

            # Update or create Media entry
            media_stmt = select(Media).where(Media.task_id == task_id, Media.is_generated == True)
            media_result = await db.execute(media_stmt)
            existing_media = media_result.scalar_one_or_none()

            if existing_media:
                update_media = (
                    update(Media)
                    .where(Media.media_id == existing_media.media_id)
                    .values(
                        storage_path=str(filename),
                        size_bytes=len(image_bytes),
                        img_url=imgUrl,
                        is_generated=True,
                    )
                )
                await db.execute(update_media)
            else:
                media = Media(
                    task_id=task_id,
                    gen_id=gen_content.gen_id,
                    storage_path=str(filename),
                    mime_type="image/png",
                    size_bytes=len(image_bytes),
                    img_url=imgUrl,
                    is_generated=True,
                )
                db.add(media)

            # Update generated content record
            update_gen = (
                update(GeneratedContent)
                .where(GeneratedContent.gen_id == gen_content.gen_id)
                .values(image_generated=True)
            )
            await db.execute(update_gen)

            await db.commit()

            return JSONResponse({
                "success": True,
                "media_url": f"/media/{filename}",
                "message": "Image generated successfully"
            })

        except Exception as e:
            print(e)
            raise HTTPException(status_code=500, detail=str(e))


    @app.get("/api/tasks/approved", status_code=200)
    async def list_approved_drafts(
        db: AsyncSession = Depends(get_db),
        limit: int = Query(DEFAULT_LIMIT, ge=1),
        offset: int = 0
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
                # pick the latest generated content for preview
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
    async def get_approved_draft_detail(task_id: str, db: AsyncSession = Depends(get_db)):
        stmt = (
            select(Task)
            .where(Task.task_id == task_id, Task.status == TaskStatus.draft_approved)
            .options(selectinload(Task.generated_contents), selectinload(Task.media))
        )
        result = await db.execute(stmt)
        task = result.scalars().first()
        if not task:
            raise HTTPException(status_code=404, detail="Approved draft not found")

        # Latest generated content (if any)
        content = None
        if task.generated_contents:
            content = max(task.generated_contents, key=lambda x: x.created_at)

        # pick an image/media URL if available
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