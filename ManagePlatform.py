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
from Database import OAuthToken, Platform, TaskStatus, get_db, Task, GeneratedContent, Media
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, update, delete
from sqlalchemy.orm import selectinload




ENCRYPTION_KEY = os.getenv("FERNET_KEY") or Fernet.generate_key()
fernet = Fernet(ENCRYPTION_KEY)


class PlatformCreate(BaseModel):
    name: str
    api_name: Optional[str] = None
    meta: Optional[dict] = None
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    token_meta: Optional[dict] = None


def encrypt_token(token: str) -> str:
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    return fernet.decrypt(encrypted.encode()).decode()




def init(app):
    @app.get("/api/platforms")
    async def get_platforms(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(Platform).order_by(Platform.created_at.desc()))
        platforms = result.scalars().all()

        output = []
        for p in platforms:
            token_result = await db.execute(
                select(OAuthToken)
                .filter(OAuthToken.platform_id == p.platform_id)
                .order_by(OAuthToken.created_at.desc())
                .limit(1)
            )
            token = token_result.scalars().first()

            masked = None
            valid = False
            if token and token.access_token:
                try:
                    full = decrypt_token(token.access_token)
                    masked = "••••" + full[-8:]
                    valid = True
                except:
                    masked = "Decryption failed"
                    valid = False

            output.append({
                "platform_id": p.platform_id,
                "name": p.name,
                "api_name": p.api_name or "",
                "created_at": p.created_at.isoformat(),
                "has_token": bool(token),
                "token_valid": valid,
                "masked_token": masked,
            })

        return output


    # endpoint
    @app.post("/api/platforms/create")
    async def create_platform(
        payload: PlatformCreate,                     # ← MUST be the model, not dict!
        db: AsyncSession = Depends(get_db)
    ):
        exists = await db.execute(select(Platform).where(Platform.name == payload.name))
        if exists.scalars().first():
            raise HTTPException(400, "Platform name already exists")
        
        

        platform = Platform(name=payload.name, api_name=payload.api_name, meta=payload.meta or {})
        db.add(platform)
        await db.commit()
        await db.refresh(platform)

        # This will ALWAYS run because access_token is required
        oauth = OAuthToken(
            platform_id=platform.platform_id,
            access_token=encrypt_token(payload.access_token),
            refresh_token=encrypt_token(payload.refresh_token) if payload.refresh_token else None,
            expires_at=payload.expires_at,
            meta=payload.token_meta or {}
        )
        db.add(oauth)
        await db.commit()

        return {"message": "Platform and token created", "platform_id": platform.platform_id}


    # DELETE: Fixed — now works!
    @app.delete("/api/platforms/{platform_id}")
    async def delete_platform(platform_id: str, db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(Platform).filter(Platform.platform_id == platform_id))
        platform = result.scalars().first()
        if not platform:
            raise HTTPException(status_code=404, detail="Platform not found")

        # This deletes Platform → cascades to OAuthToken (thanks to your cascade="all, delete-orphan")
        await db.execute(delete(Platform).where(Platform.platform_id == platform_id))
        await db.commit()

        return JSONResponse(status_code=200, content={"message": "Deleted successfully"})
