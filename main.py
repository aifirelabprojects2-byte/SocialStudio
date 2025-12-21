from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator, ValidationError
import ManageTheme
import MediaSnag
import Researcher
import ManualPost
import TextFormatter
import UsageTracker
import PostGen
# import TaskScheduler
import ManagePlatform
import ErrorLogs
import Accounts
import ScheduledTasks
import os
from starlette.status import HTTP_303_SEE_OTHER
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
import pytz

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

media_dir = Path("static/media")
media_dir.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory="static/media"), name="media")

templates = Jinja2Templates(directory="templates")


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok"}

@app.on_event("startup")
async def startup():
    await init_db()

@app.exception_handler(HTTPException)
async def unauthorized_handler(request: Request, exc: HTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    raise exc

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, _=Depends(Accounts.get_current_user)):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/setting", response_class=HTMLResponse)
async def settings(request: Request, _=Depends(Accounts.get_current_user)):
    return templates.TemplateResponse("settings.html", {"request": request})

@app.get("/session", response_class=HTMLResponse)
async def settings(request: Request, _=Depends(Accounts.get_current_user)):
    return templates.TemplateResponse("session.html", {"request": request})


PostGen.init(app)    
ManagePlatform.init(app)
ManageTheme.init(app)
UsageTracker.init(app)
Accounts.init(app)
Researcher.init(app)
MediaSnag.init(app)
TextFormatter.init(app)
ErrorLogs.init(app)
ManualPost.init(app)
ScheduledTasks.init(app)
# TaskScheduler.init(app)
