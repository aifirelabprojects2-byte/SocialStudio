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
from cryptography.fernet import Fernet
from fastapi import Form, Query, Request, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
import json
from Database import Platform, TaskStatus, get_db, Task, GeneratedContent, Media
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from Encryption import encrypt_token, decrypt_token  
import pytz
from datetime import datetime

KOLKATA_TZ = pytz.timezone("Asia/Kolkata")


async def get_platform_by_name(db: AsyncSession, name: str) -> Platform:
    result = await db.execute(select(Platform).filter_by(name=name.lower()))
    platform = result.scalar_one_or_none()
    if not platform:
        raise HTTPException(status_code=404, detail="Platform not found")
    return platform



def init(app):
    @app.get("/api/platforms/list")
    async def list_platforms(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(Platform).order_by(Platform.name))
        platforms = result.scalars().all()

        now_kolkata = datetime.now(KOLKATA_TZ)

        return [
            {
                "platform_id": p.platform_id,
                "name": p.name.capitalize(),
                "api_name": p.api_name,
                "expires_at": p.expires_at.astimezone(KOLKATA_TZ).isoformat() if p.expires_at else None,
                "expires_at_local": p.expires_at.astimezone(KOLKATA_TZ).strftime("%d %b %Y, %I:%M %p") if p.expires_at else "Never",
                "days_remaining": (
                    (p.expires_at.astimezone(KOLKATA_TZ) - now_kolkata).days
                    if p.expires_at else None
                ),
                "is_active": p.is_active or False,
                "has_token": {
                    "facebook": bool(p.page_access_token),
                    "instagram": bool(p.ll_user_access_token),
                    "threads": bool(p.ll_user_access_token),
                    "x": any([
                        p.consumer_key, p.consumer_secret, p.access_token,
                        p.access_token_secret, p.bearer_token
                    ]),
                },
            }
            for p in platforms
        ]
    @app.get("/api/platforms/{name}")
    async def get_platform(name: str, db: AsyncSession = Depends(get_db)):
        platform = await get_platform_by_name(db, name.lower())

        # Convert expires_at to Kolkata time for display
        expires_local = None
        if platform.expires_at:
            expires_local = platform.expires_at.astimezone(KOLKATA_TZ)

        decrypted = {
            "page_access_token": decrypt_token(platform.page_access_token) or "",
            "ll_user_access_token": decrypt_token(platform.ll_user_access_token) or "",
            "threads_long_lived_token": decrypt_token(platform.ll_user_access_token) or "",  # shared with IG
            "consumer_key": decrypt_token(platform.consumer_key) or "",
            "consumer_secret": decrypt_token(platform.consumer_secret) or "",
            "access_token": decrypt_token(platform.access_token) or "",
            "access_token_secret": decrypt_token(platform.access_token_secret) or "",
            "bearer_token": decrypt_token(platform.bearer_token) or "",
        }

        return {
            "platform_id": platform.platform_id,
            "name": platform.name,
            "is_active": platform.is_active or False,
            "expires_at": expires_local.isoformat() if expires_local else None,
            "expires_at_display": expires_local.strftime("%d %b %Y, %I:%M %p") if expires_local else "Never",
            "days_remaining": (
                (expires_local - datetime.now(KOLKATA_TZ)).days
                if expires_local else None
            ),
            "page_id": platform.page_id or "",
            "threads_user_id": platform.threads_user_id or "",
            "threads_username": platform.threads_username or "",
            "decrypted": decrypted,
            "has_token": {
                "facebook": bool(decrypted["page_access_token"]),
                "instagram": bool(decrypted["ll_user_access_token"]),
                "threads": bool(decrypted["threads_long_lived_token"]),
                "x": any([
                    decrypted["consumer_key"], decrypted["consumer_secret"],
                    decrypted["access_token"], decrypted["access_token_secret"],
                    decrypted["bearer_token"]
                ]),
            }
        }

    @app.post("/api/platforms/{name}")
    async def update_platform(name: str, data: dict, db: AsyncSession = Depends(get_db)):
        platform = await get_platform_by_name(db, name.lower())

        if "is_active" in data:
            platform.is_active = data["is_active"]

        if "expires_at" in data and data["expires_at"]:
            # Frontend sends Kolkata time → convert to UTC for storage
            local_dt = datetime.fromisoformat(data["expires_at"])
            utc_dt = KOLKATA_TZ.localize(local_dt).astimezone(pytz.UTC)
            platform.expires_at = utc_dt
        elif "expires_at" in data and data["expires_at"] is None:
            platform.expires_at = None

        # Platform-specific
        if name == "facebook":
            if "page_id" in data:
                platform.page_id = data["page_id"] or None
            if "page_access_token" in data and data["page_access_token"]:
                platform.page_access_token = encrypt_token(data["page_access_token"])

        elif name == "instagram":
            if "page_id" in data:
                platform.page_id = data["page_id"] or None
            if "ll_user_access_token" in data and data["ll_user_access_token"]:
                platform.ll_user_access_token = encrypt_token(data["ll_user_access_token"])

        elif name == "threads":
            if "threads_user_id" in data:
                platform.threads_user_id = data["threads_user_id"] or None
            if "threads_username" in data:
                platform.threads_username = data["threads_username"] or None
            if "threads_long_lived_token" in data and data["threads_long_lived_token"]:
                platform.ll_user_access_token = encrypt_token(data["threads_long_lived_token"])

        elif name == "x":
            if "consumer_key" in data and data["consumer_key"]:
                platform.consumer_key = encrypt_token(data["consumer_key"])
            if "consumer_secret" in data and data["consumer_secret"]:
                platform.consumer_secret = encrypt_token(data["consumer_secret"])
            if "access_token" in data and data["access_token"]:
                platform.access_token = encrypt_token(data["access_token"])
            if "access_token_secret" in data and data["access_token_secret"]:
                platform.access_token_secret = encrypt_token(data["access_token_secret"])
            if "bearer_token" in data and data["bearer_token"]:
                platform.bearer_token = encrypt_token(data["bearer_token"])

        await db.commit()
        return {"success": True, "message": "Credentials updated successfully"}