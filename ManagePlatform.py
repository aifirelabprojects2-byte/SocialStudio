from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from ImgGen import ImageGenClient

load_dotenv()

import os
import base64
import io
from datetime import datetime
from typing import List, Optional, Literal
from pathlib import Path

from fastapi import Form, Query, Request, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
import json
from Database import TaskStatus, get_db, Task, GeneratedContent, Media
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, update, delete
from sqlalchemy.orm import selectinload



OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Set OPENAI_API_KEY in .env")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
image_client = ImageGenClient(api_key=os.getenv("IMG_API_KEY"))   


media_dir = Path("static/media")



class GeneratedContentResponse(BaseModel):
    caption: str = Field(..., max_length=2000)
    hashtags: List[str] = Field(default_factory=list, max_items=10)
    image_prompt: Optional[str] = Field(None, max_length=1000)
    suggested_posting_time: str

class GeneratedContentResponse(BaseModel):
    caption: str = Field(..., max_length=2000)
    hashtags: List[str] = Field(default_factory=list, max_items=10)
    image_prompt: Optional[str] = Field(None, max_length=1000)
    suggested_posting_time: str 

# Constants for Pagination
DEFAULT_LIMIT = 4

def init(app):
    pass
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())  # Run once, save it!