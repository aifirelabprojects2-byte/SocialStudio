from datetime import datetime
from typing import Optional
from fastapi import Depends, Query
from sqlalchemy import desc, func, select
import Accounts
from Database import ErrorLog, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from Schema.ErrorLog import ErrorLogListResponse


def init(app):
    @app.get("/error-logs", response_model=ErrorLogListResponse)
    async def list_error_logs(
        from_date: Optional[datetime] = Query(None),
        to_date: Optional[datetime] = Query(None),
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
        db: AsyncSession = Depends(get_db),
        _=Depends(Accounts.get_current_user)
    ):
        query = select(ErrorLog).order_by(desc(ErrorLog.created_at))

        if from_date:
            query = query.where(ErrorLog.created_at >= from_date)
        if to_date:
            query = query.where(ErrorLog.created_at <= to_date)

        subq = query.subquery()
        count_query = select(func.count()).select_from(subq)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.limit(limit).offset(offset)
        result = await db.execute(query)
        error_logs = result.scalars().all()

        return ErrorLogListResponse(
            error_logs=error_logs,
            total=total,
            limit=limit,
            offset=offset
        )

