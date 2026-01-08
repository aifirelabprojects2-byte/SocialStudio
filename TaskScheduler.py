from pydantic import BaseModel
from datetime import datetime
from typing import List,Optional
from fastapi import  Depends, HTTPException
import Accounts
from Database import Platform, PublishStatus, TaskStatus, get_db, Task, PlatformSelection, get_sync_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import pytz
from tasks import execute_posting 
from celery_app import celery_app
from sqlalchemy.orm import Session

ist = pytz.timezone("Asia/Kolkata")

class ScheduleTaskRequest(BaseModel):
    task_id: str
    platform_ids: List[str]
    scheduled_at: datetime  
    notes: Optional[str] = None



def init(app):
    @app.post("/task/post-now-scheduled/{task_id}")
    async def post_now_scheduled(
        task_id: str,
        db: AsyncSession = Depends(get_db),
        _=Depends(Accounts.get_current_user)
    ):
        stmt = (
            select(Task)
            .where(Task.task_id == task_id)
            .with_for_update()
            .options(selectinload(Task.platform_selections))
        )

        result = await db.execute(stmt)
        task = result.scalar_one_or_none()

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.status != TaskStatus.scheduled:
            raise HTTPException(
                status_code=400,
                detail="Only scheduled tasks can be posted immediately"
            )

        now = datetime.now(ist)

        task.status = TaskStatus.queued
        task.scheduled_at = now
        task.updated_at = now

        for sel in task.platform_selections:
            if sel.publish_status == PublishStatus.scheduled:
                sel.scheduled_at = now

        await db.commit()

        execute_posting.delay(task.task_id)

        return {
            "status": "success",
            "message": "Scheduled task posted",
            "task_id": task.task_id,
            "executed_at": now.isoformat(),
        }

    @app.post("/task/post-now")
    async def post_now(
        request: ScheduleTaskRequest, 
        db: AsyncSession = Depends(get_db),
        _ = Depends(Accounts.get_current_user)
    ):
        stmt = select(Task).options(selectinload(Task.generated_contents)).where(Task.task_id == request.task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        current_time_ist = datetime.now(ist)
        task.status = TaskStatus.queued
        task.scheduled_at = current_time_ist
        task.notes = request.notes
        task.updated_at = current_time_ist
        
        seen_platforms = set()
        platform_selections_to_add = []
        
        for platform_id in request.platform_ids:
            if platform_id in seen_platforms:
                raise HTTPException(status_code=400, detail="Duplicate platform selected")
            seen_platforms.add(platform_id)

            platform = await db.get(Platform, platform_id)
            if not platform:
                raise HTTPException(status_code=404, detail=f"Platform {platform_id} not found")

            existing = await db.scalar(
                select(PlatformSelection).where(
                    PlatformSelection.task_id == task.task_id,
                    PlatformSelection.platform_id == platform_id
                )
            )
            
            if existing:
                existing.publish_status = PublishStatus.scheduled
                existing.scheduled_at = current_time_ist
            else:
                platform_selections_to_add.append(
                    PlatformSelection(
                        task_id=task.task_id,
                        platform_id=platform_id,
                        publish_status=PublishStatus.scheduled,
                        scheduled_at=current_time_ist,
                    )
                )

        db.add_all(platform_selections_to_add)
        await db.commit()

        execute_posting.delay(task.task_id)

        return {
            "status": "success",
            "message": "Immediate posting initiated",
            "task_id": request.task_id,
            "platforms_count": len(request.platform_ids)
        }
            
    @app.post("/schedule-task", response_model=dict)
    async def schedule_task(
        request: ScheduleTaskRequest,
        db: AsyncSession = Depends(get_db),
        _=Depends(Accounts.get_current_user)
    ) -> dict:
        if request.scheduled_at.tzinfo is None:
            request.scheduled_at = ist.localize(request.scheduled_at)
        else:
            request.scheduled_at = request.scheduled_at.astimezone(ist)

        stmt = select(Task).options(selectinload(Task.generated_contents)).where(Task.task_id == request.task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.status not in (TaskStatus.draft, TaskStatus.draft_approved):
            raise HTTPException(status_code=400, detail="Task must be in draft or draft_approved status")
        
        if not task.generated_contents:
            raise HTTPException(status_code=400, detail="Task must have generated content")

        task.status = TaskStatus.scheduled
        task.scheduled_at = request.scheduled_at
        task.time_zone = "Asia/Kolkata"
        task.notes = request.notes
        task.updated_at = datetime.now(ist)

        seen_platforms = set()
        platform_selections_to_add = []
        
        for platform_id in request.platform_ids:
            if platform_id in seen_platforms:
                raise HTTPException(status_code=400, detail="Duplicate platform selected")
            seen_platforms.add(platform_id)

            platform = await db.get(Platform, platform_id)
            if not platform:
                raise HTTPException(status_code=404, detail=f"Platform {platform_id} not found")
            existing = await db.scalar(
                select(PlatformSelection).where(
                    PlatformSelection.task_id == task.task_id,
                    PlatformSelection.platform_id == platform_id
                )
            )
            if existing:
                raise HTTPException(status_code=400, detail=f"Platform {platform_id} already selected for task")

            platform_selections_to_add.append(
                PlatformSelection(
                    task_id=task.task_id,
                    platform_id=platform_id,
                    publish_status=PublishStatus.scheduled,
                    scheduled_at=request.scheduled_at,
                )
            )
        db.add_all(platform_selections_to_add)

        await db.commit()
        await db.refresh(task)
        execute_posting.apply_async(args=(task.task_id,), eta=request.scheduled_at)

        return {
            "message": "Task scheduled successfully",
            "task_id": task.task_id,
            "scheduled_at": request.scheduled_at.isoformat(),
            "platforms": len(request.platform_ids),
        }

