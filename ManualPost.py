
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
from Configs import IMG_BB_API_KEY
from CostCalc import calculate_llm_cost, count_tokens
from ImgGen import ImageGenClient
import PostGen,ManagePlatform,Referencer,ManageTheme,UsageTracker,Accounts
import os
from datetime import datetime
from typing import List, AsyncGenerator, Dict, Any, Annotated, Optional, Literal, Tuple
from pathlib import Path
from enum import Enum
from fastapi import Body, Cookie, FastAPI, Form, Query, Request, Depends, HTTPException, logger, status, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
import json
from Database import AsyncSessionLocal, AttemptStatus, ErrorLog, LLMUsage, LoginSession, Platform, PostAttempt, PublishStatus, TaskStatus, User, gen_uuid_str, get_db, init_db, Task, GeneratedContent, Media, PlatformSelection
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, update, delete,desc
from sqlalchemy.orm import selectinload,joinedload
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from werkzeug.utils import secure_filename
from PIL import Image
media_dir = Path("static/media")

def init(app):
    @app.post("/manual-tasks", response_model=dict)
    async def create_manual_task(
        title: str = Form(..., description="Task title"),
        caption: str = Form(..., description="Post caption"),
        hashtags: str = Form(..., description="Comma-separated hashtags"),
        notes: Optional[str] = Form(None, description="Optional notes for the task"),
        image: UploadFile = File(..., description="Image file to upload"),
        db: AsyncSession = Depends(get_db),
        _=Depends(Accounts.get_current_user)
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