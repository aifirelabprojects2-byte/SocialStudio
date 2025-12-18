from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from datetime import datetime, timedelta
from typing import List, AsyncGenerator, Dict, Any, Annotated, Optional, Literal, Tuple
from pathlib import Path
from enum import Enum
from fastapi import Body, FastAPI, Form, Query, Request, Depends, HTTPException, logger, status, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import json
from Database import AttemptStatus, ErrorLog, LLMUsage, OAuthToken, Platform, PostAttempt, PublishStatus, TaskStatus, gen_uuid_str, get_db, init_db, Task, GeneratedContent, Media, PlatformSelection
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, update, delete,desc
from sqlalchemy.orm import selectinload,joinedload
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from werkzeug.utils import secure_filename
from PIL import Image
import unicodedata
import pytz
from urllib.parse import urlparse
import itertools
from gallery_dl import config, job
import instaloader
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class UsageItem(BaseModel):
    id: str
    feature: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: Decimal
    latency_ms: Optional[int] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)  # Critical line

class PaginatedUsage(BaseModel):
    items: List[UsageItem]
    total: int
    page: int
    limit: int

class GraphData(BaseModel):
    label: str
    total_tokens: int
    total_cost: Decimal
    count: int

class UsageStat(BaseModel):
    period: str
    total_tokens: int
    total_cost: Decimal
    avg_latency: Optional[float]
    request_count: int

def init(app):
    @app.get("/llm-usage/", response_model=PaginatedUsage)
    async def get_llm_usage(
        page: int = Query(1, ge=1),
        limit: int = Query(10, ge=1, le=100),
        feature: Optional[str] = Query(None),
        model: Optional[str] = Query(None),
        start_date: Optional[datetime] = Query(None),
        end_date: Optional[datetime] = Query(None),
        db: AsyncSession = Depends(get_db)
    ):
        stmt = select(LLMUsage)
        
        if feature:
            stmt = stmt.where(LLMUsage.feature == feature)
        if model:
            stmt = stmt.where(LLMUsage.model == model)
        if start_date:
            stmt = stmt.where(LLMUsage.created_at >= start_date)
        if end_date:
            stmt = stmt.where(LLMUsage.created_at <= end_date)
        
        # Total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()
        
        # Paginated items with order
        stmt = stmt.order_by(LLMUsage.created_at.desc()).offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        items = result.scalars().all()
        
        return PaginatedUsage(
            items = [
                    UsageItem.model_validate({
                        "id": item.id,
                        "feature": item.feature,
                        "model": item.model,
                        "input_tokens": item.input_tokens,
                        "output_tokens": item.output_tokens,
                        "total_tokens": item.total_tokens,
                        "cost_usd": item.cost_usd,
                        "latency_ms": item.latency_ms,
                        "status": item.status,
                        "created_at": item.created_at,
                    })
                    for item in items
                ],
            total=total,
            page=page,
            limit=limit
        )


    @app.get("/api/usage/stats", response_model=List[UsageStat])
    async def get_usage_stats(
        interval: str = Query("day", regex="^(hour|day|month)$"),
        days_back: int = Query(30, ge=1, le=365),
        feature: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db)
    ):
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        # Dynamic grouping based on interval
        if interval == "hour":
            group_by = func.strftime("%Y-%m-%d %H:00", LLMUsage.created_at).label("period")
        elif interval == "day":
            group_by = func.strftime("%Y-%m-%d", LLMUsage.created_at).label("period")
        else:  # month
            group_by = func.strftime("%Y-%m", LLMUsage.created_at).label("period")
        
        stmt = select(
            group_by,
            func.sum(LLMUsage.total_tokens).label("total_tokens"),
            func.sum(LLMUsage.cost_usd).label("total_cost"),
            func.avg(LLMUsage.latency_ms).label("avg_latency"),
            func.count(LLMUsage.id).label("request_count")
        ).where(
            LLMUsage.created_at >= start_date,
            LLMUsage.created_at < end_date
        ).group_by(group_by)
        
        if feature:
            stmt = stmt.where(LLMUsage.feature == feature)
        
        result = await db.execute(stmt.order_by("period"))
        rows = result.fetchall()
        
        return [UsageStat(
            period=row.period,
            total_tokens=int(row.total_tokens or 0),
            total_cost=row.total_cost or Decimal("0.00"),
            avg_latency=float(row.avg_latency) if row.avg_latency is not None else None,
            request_count=int(row.request_count)
        ) for row in rows]

