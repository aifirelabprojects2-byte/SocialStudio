from datetime import datetime
from fastapi import Depends, HTTPException
import Accounts
from Database import Platform, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from pydantic import BaseModel

# 1. Define Pydantic Schema for the Response
class PlatformResponse(BaseModel):
    platform_id: str
    api_name: str
    account_name: Optional[str] = None
    profile_photo_url: Optional[str] = None

    class Config:
        from_attributes = True # Use 'orm_mode = True' if using Pydantic v1



def init(app):
    @app.get("/api/active/platforms", response_model=List[PlatformResponse])
    async def get_active_platforms(db: AsyncSession = Depends(get_db)):
        stmt = select(Platform).where(Platform.is_active == True)

        result = await db.execute(stmt)
        
        # 3. Get the objects from the result
        platforms = result.scalars().all()
        
        results = []
        for p in platforms:
            photo_url = None
            if p.meta and isinstance(p.meta, dict):
                photo_url = p.meta.get("PROFILE_PHOTO_URL")

            results.append({
                "platform_id": p.platform_id,
                "api_name": p.api_name,
                "account_name": p.account_name,
                "profile_photo_url": photo_url
            })
            
        return results