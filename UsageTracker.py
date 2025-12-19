from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from datetime import datetime, timedelta
from typing import List, AsyncGenerator, Dict, Any, Annotated, Optional, Literal, Tuple
from pathlib import Path
from enum import Enum
from fastapi import Body, FastAPI, Form, Query, Request, Depends, HTTPException, logger, status, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import json
from Database import AttemptStatus, ErrorLog, LLMUsage, Platform, PostAttempt, PublishStatus, TaskStatus, gen_uuid_str, get_db, init_db, Task, GeneratedContent, Media, PlatformSelection
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, update, delete,desc, case
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
import numpy as np  # Add this import for percentile calculation

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

class SummaryStat(BaseModel):
    total_cost: Decimal
    total_tokens: int
    input_tokens: int
    output_tokens: int
    request_count: int
    success_count: int
    success_rate: float
    avg_latency: Optional[float]
    p95_latency: Optional[int]
    cost_change_pct: Optional[float]  # % change from previous period
    token_change_pct: Optional[float]  # % change from previous period

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

    @app.get("/api/usage/summary", response_model=SummaryStat)
    async def get_usage_summary(
        days_back: int = Query(30, ge=1, le=365),
        feature: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db)
    ):
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        prev_end_date = start_date
        prev_start_date = prev_end_date - timedelta(days=days_back)

        # Current period aggregates
        current_stmt = select(
            func.sum(LLMUsage.input_tokens).label("input_tokens"),
            func.sum(LLMUsage.output_tokens).label("output_tokens"),
            func.sum(LLMUsage.total_tokens).label("total_tokens"),
            func.sum(LLMUsage.cost_usd).label("total_cost"),
            func.count(LLMUsage.id).label("request_count"),
            func.sum(case((LLMUsage.status == "success", 1), else_=0)).label("success_count"),
            func.avg(LLMUsage.latency_ms).label("avg_latency")
        ).where(
            LLMUsage.created_at >= start_date,
            LLMUsage.created_at < end_date
        )
        if feature:
            current_stmt = current_stmt.where(LLMUsage.feature == feature)
        current_result = await db.execute(current_stmt)
        current_row = current_result.fetchone()

        # Fetch latencies for P95 (assuming manageable size; for large datasets, consider approximation)
        latency_stmt = select(LLMUsage.latency_ms).where(
            LLMUsage.created_at >= start_date,
            LLMUsage.created_at < end_date,
            LLMUsage.latency_ms.isnot(None)
        )
        if feature:
            latency_stmt = latency_stmt.where(LLMUsage.feature == feature)
        latency_result = await db.execute(latency_stmt)
        latencies = [row[0] for row in latency_result.fetchall() if row[0] is not None]
        p95_latency = int(np.percentile(latencies, 95)) if latencies else None

        # Previous period aggregates for % change
        prev_stmt = select(
            func.sum(LLMUsage.total_tokens).label("prev_total_tokens"),
            func.sum(LLMUsage.cost_usd).label("prev_total_cost")
        ).where(
            LLMUsage.created_at >= prev_start_date,
            LLMUsage.created_at < prev_end_date
        )
        if feature:
            prev_stmt = prev_stmt.where(LLMUsage.feature == feature)
        prev_result = await db.execute(prev_stmt)
        prev_row = prev_result.fetchone()

        current_input = int(current_row.input_tokens or 0)
        current_output = int(current_row.output_tokens or 0)
        current_total_tokens = int(current_row.total_tokens or 0)
        current_total_cost = current_row.total_cost or Decimal("0.00")
        current_request_count = int(current_row.request_count or 0)
        current_success_count = int(current_row.success_count or 0)
        current_avg_latency = float(current_row.avg_latency) if current_row.avg_latency is not None else None

        success_rate = (current_success_count / current_request_count * 100) if current_request_count > 0 else 0.0

        prev_total_tokens = int(prev_row.prev_total_tokens or 0)
        prev_total_cost = prev_row.prev_total_cost or Decimal("0.00")

        cost_change_pct = ((current_total_cost - prev_total_cost) / prev_total_cost * 100) if prev_total_cost > 0 else None
        token_change_pct = ((current_total_tokens - prev_total_tokens) / prev_total_tokens * 100) if prev_total_tokens > 0 else None

        return SummaryStat(
            total_cost=current_total_cost,
            total_tokens=current_total_tokens,
            input_tokens=current_input,
            output_tokens=current_output,
            request_count=current_request_count,
            success_count=current_success_count,
            success_rate=round(success_rate, 1),
            avg_latency=current_avg_latency,
            p95_latency=p95_latency,
            cost_change_pct=round(cost_change_pct, 1) if cost_change_pct is not None else None,
            token_change_pct=round(token_change_pct, 1) if token_change_pct is not None else None
        )