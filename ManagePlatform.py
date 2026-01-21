from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status
import Accounts
from Database import ErrorLog, GeneratedContent, Media, Platform, PlatformSelection, PostAttempt, Task, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, distinct, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional, Any
from pydantic import BaseModel

# 1. Define Pydantic Schema for the Response
class PlatformResponse(BaseModel):
    platform_id: str
    api_name: str
    account_name: Optional[str] = None
    profile_photo_url: Optional[str] = None
    expiry_days_left: Optional[int] = None

    class Config:
        from_attributes = True # Use 'orm_mode = True' if using Pydantic v1



def init(app):
    @app.get("/api/active/platforms", response_model=List[PlatformResponse])
    async def get_active_platforms(db: AsyncSession = Depends(get_db)):
        stmt = select(Platform).where(Platform.is_active == True)
        result = await db.execute(stmt)
        platforms = result.scalars().all()

        # Use NAIVE UTC time to match DB values
        now = datetime.utcnow()

        results = []

        for p in platforms:
            # -----------------------------
            # Profile photo
            # -----------------------------
            photo_url = None
            if p.meta and isinstance(p.meta, dict):
                photo_url = p.meta.get("PROFILE_PHOTO_URL")

            # -----------------------------
            # Expiry calculation
            # NULL = never expire
            # -----------------------------
            expiry_days_left: Optional[int] = None

            if p.expires_at:
                expires_at = p.expires_at  # naive datetime

                delta = expires_at - now
                expiry_days_left = max(delta.days, 0)

            results.append({
                "platform_id": p.platform_id,
                "api_name": p.api_name,
                "account_name": p.account_name,
                "profile_photo_url": photo_url,
                "expiry_days_left": expiry_days_left  # None = never expires
            })

        return results
    
    @app.delete("/api/platforms/{platform_id}/revoke", status_code=200)
    async def revoke_platform(platform_id: str, db: AsyncSession = Depends(get_db)):
        try:
            platform = await db.get(Platform, platform_id)
            if platform is None:
                raise HTTPException(status_code=404, detail="Platform not found")

            # 1. Tasks connected to this platform
            res = await db.execute(
                select(distinct(PlatformSelection.task_id))
                .where(PlatformSelection.platform_id == platform_id)
            )
            affected_task_ids = [r[0] for r in res.fetchall() if r[0]]

            # 2. Platform-scoped cleanup
            await db.execute(delete(PostAttempt).where(PostAttempt.platform_id == platform_id))
            await db.execute(delete(ErrorLog).where(ErrorLog.platform_id == platform_id))
            await db.execute(delete(PlatformSelection).where(PlatformSelection.platform_id == platform_id))

            if affected_task_ids:
                # 3. Find tasks that still have other platforms
                res = await db.execute(
                    select(distinct(PlatformSelection.task_id))
                    .where(PlatformSelection.task_id.in_(affected_task_ids))
                )
                remaining_task_ids = {r[0] for r in res.fetchall() if r[0]}
                tasks_to_delete = set(affected_task_ids) - remaining_task_ids

                if tasks_to_delete:
                    tasks_to_delete = list(tasks_to_delete)

                    await db.execute(delete(GeneratedContent).where(GeneratedContent.task_id.in_(tasks_to_delete)))
                    await db.execute(delete(Media).where(Media.task_id.in_(tasks_to_delete)))
                    await db.execute(delete(PostAttempt).where(PostAttempt.task_id.in_(tasks_to_delete)))
                    await db.execute(delete(ErrorLog).where(ErrorLog.task_id.in_(tasks_to_delete)))
                    await db.execute(delete(PlatformSelection).where(PlatformSelection.task_id.in_(tasks_to_delete)))
                    await db.execute(delete(Task).where(Task.task_id.in_(tasks_to_delete)))

            # 4. Delete platform
            await db.execute(delete(Platform).where(Platform.platform_id == platform_id))

            # ✅ single commit
            await db.commit()

            return {"success": True}

        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail="Database error")
