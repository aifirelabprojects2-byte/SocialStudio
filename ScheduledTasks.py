from typing import  Optional
from enum import Enum
from fastapi import Query ,Depends, HTTPException
import Accounts
from Database import ErrorLog,  PostAttempt, TaskStatus, get_db, Task, GeneratedContent, PlatformSelection
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, desc
from sqlalchemy.orm import selectinload

from Schema.Scheduled import *



def init(app):
    @app.get("/api/tasks-scheduled", response_model=TaskListResponse,)
    async def list_tasks(
        status: Optional[TaskStatusFilter] = Query(None, description="Filter by specific status (scheduled, posted, failed, cancelled)"),
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
        db: AsyncSession = Depends(get_db),
        _=Depends(Accounts.get_current_user)
    ):
        query = select(Task).order_by(desc(Task.created_at))

        if status is None:
            query = query.where(Task.status.in_([TaskStatus.scheduled, TaskStatus.posted, TaskStatus.failed, TaskStatus.cancelled]))
        else:
            query = query.where(Task.status == TaskStatus[status])

        count_query = select(func.count(Task.task_id)).where(query.whereclause)
        total_result = await db.execute(count_query)
        total = total_result.scalar_one_or_none() or 0

        query = query.limit(limit).offset(offset)
        result = await db.execute(query)
        tasks = result.scalars().all()


        task_dicts = []
        for task in tasks:
            task_dict = {column.name: getattr(task, column.name) for column in Task.__table__.columns}
            task_dicts.append(task_dict)
        
        return TaskListResponse(tasks=task_dicts, total=total, limit=limit, offset=offset)

    @app.get("/view/tasks-scheduled/{task_id}", response_model=TaskDetailOut)
    async def get_task_detail(task_id: str, db: AsyncSession = Depends(get_db)):
        stmt = (
            select(Task)
            .options(
                selectinload(Task.generated_contents).selectinload(GeneratedContent.media),
                selectinload(Task.media),
                selectinload(Task.platform_selections).selectinload(PlatformSelection.platform),
                selectinload(Task.post_attempts).selectinload(PostAttempt.platform),
            )
            .where(Task.task_id == task_id)
        )
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # Error logs
        error_result = await db.execute(
            select(ErrorLog)
            .where(ErrorLog.task_id == task_id)
            .order_by(desc(ErrorLog.created_at))
        )
        error_logs = error_result.scalars().all()

        image_url: str | None = None

        for m in task.media:
            if m.img_url:
                image_url = m.img_url
                break

        if not image_url:
            for gc in task.generated_contents:
                for m in gc.media:
                    if m.img_url:
                        image_url = m.img_url
                        break
                if image_url:
                    break

        print(image_url)
        caption: str | None = None
        caption_with_hashtags: str | None = None

        if task.generated_contents:
            latest = max(task.generated_contents, key=lambda x: x.created_at)
            caption = latest.caption
            hashtags = latest.hashtags or []

            if caption:
                if hashtags:
                    tags_str = " ".join(f"#{tag.strip('# ')}" for tag in hashtags if tag)
                    caption_with_hashtags = f"{caption.strip()} {tags_str}".strip()
                else:
                    caption_with_hashtags = caption.strip()

        return TaskDetailOut(
            task=TaskOut.model_validate(task),
            post_attempts=[PostAttemptOut.model_validate(pa) for pa in task.post_attempts],
            error_logs=[ErrorLogOut.model_validate(el) for el in error_logs],
            image_url=image_url,                   
            caption=caption,
            caption_with_hashtags=caption_with_hashtags,
        )