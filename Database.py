# Database.py 

import os
import enum
import uuid
from typing import AsyncGenerator, Optional
from datetime import datetime

import pytz
from sqlalchemy import (
    Boolean,
    Column,
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    JSON,
    Enum as SAEnum,
    func,
    create_engine,
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker,relationship
from sqlalchemy.exc import SQLAlchemyError

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")

# Sync URL for Celery (remove aiosqlite)
SYNC_DATABASE_URL = DATABASE_URL.replace("+aiosqlite", "").replace("aiosqlite://", "sqlite://")

async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=False,
    future=True,
)

class Base(AsyncAttrs, DeclarativeBase):
    pass

# Sync Base (without AsyncAttrs for Celery compatibility)
class SyncBase(DeclarativeBase):
    pass

# Note: In production, consider separate sync models if issues arise, but models are shared here.

class TaskStatus(enum.Enum):
    draft = "draft"
    draft_approved = "draft_approved"
    scheduled = "scheduled"
    queued = "queued"
    posted = "posted"
    failed = "failed"
    cancelled = "cancelled"

class PublishStatus(enum.Enum):
    pending = "pending"
    scheduled = "scheduled"
    posted = "posted"
    failed = "failed"

class AttemptStatus(enum.Enum):
    success = "success"
    transient_failure = "transient_failure"
    permanent_failure = "permanent_failure"

def gen_uuid_str() -> str:
    return str(uuid.uuid4())

class Platform(Base, SyncBase):
    __tablename__ = "platform"

    platform_id = Column(String(36), primary_key=True, default=gen_uuid_str)
    name = Column(String(64), nullable=False, unique=True, index=True) 
    api_name = Column(String(128), nullable=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ImageTheme(Base, SyncBase):
    __tablename__ = "image_theme"

    theme_id = Column(String(36), primary_key=True, default=gen_uuid_str)
    name = Column(String(64), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TaskStatus(enum.Enum):
    draft = "draft"
    draft_approved = "draft_approved"
    scheduled = "scheduled"
    queued = "queued"
    posted = "posted"
    failed = "failed"
    cancelled = "cancelled"


class Task(Base, SyncBase):
    __tablename__ = "task"

    task_id = Column(String(36), primary_key=True, default=gen_uuid_str)
    organization_id = Column(String(36), nullable=True, index=True)
    title = Column(String(255), nullable=True)
    status = Column(SAEnum(TaskStatus, name="task_status"), nullable=False, default=TaskStatus.draft, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    scheduled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    time_zone = Column(String(64), nullable=True)
    notes = Column(Text, nullable=True)

    generated_contents = relationship("GeneratedContent", back_populates="task", cascade="all, delete-orphan")
    media = relationship("Media", back_populates="task", cascade="all, delete-orphan")
    platform_selections = relationship("PlatformSelection", back_populates="task", cascade="all, delete-orphan")
    post_attempts = relationship("PostAttempt", back_populates="task", cascade="all, delete-orphan")

class GeneratedContent(Base, SyncBase):
    __tablename__ = "generated_content"

    gen_id = Column(String(36), primary_key=True, default=gen_uuid_str)
    task_id = Column(String(36), ForeignKey("task.task_id", ondelete="CASCADE"), nullable=False, index=True)
    prompt = Column(Text, nullable=True)
    caption = Column(Text, nullable=True)
    hashtags = Column(JSON, nullable=True)  # list of strings
    image_prompt = Column(Text, nullable=True)
    image_generated = Column(Boolean, default=False)
    suggested_posting_time = Column(String(255), nullable=True)  # e.g., "Weekdays 8-10 AM EST"
    meta = Column(JSON, nullable=True)  # model name, tokens, scores etc
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    task = relationship("Task", back_populates="generated_contents")
    media = relationship("Media", back_populates="generated_content", cascade="all, delete-orphan")

class Media(Base, SyncBase):
    __tablename__ = "media"

    media_id = Column(String(36), primary_key=True, default=gen_uuid_str)
    task_id = Column(String(36), ForeignKey("task.task_id", ondelete="CASCADE"), nullable=False, index=True)
    gen_id = Column(String(36), ForeignKey("generated_content.gen_id", ondelete="SET NULL"), nullable=True, index=True)
    storage_path = Column(Text, nullable=False)  # S3/MinIO/CNAME path or local path during testing
    mime_type = Column(String(64), nullable=True)
    img_url = Column(String(128), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    checksum = Column(String(128), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    is_generated = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    task = relationship("Task", back_populates="media")
    generated_content = relationship("GeneratedContent", back_populates="media")

class PlatformSelection(Base, SyncBase):
    __tablename__ = "platform_selection"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    task_id = Column(String(36), ForeignKey("task.task_id", ondelete="CASCADE"), nullable=False, index=True)
    platform_id = Column(String(36), ForeignKey("platform.platform_id", ondelete="RESTRICT"), nullable=False, index=True)
    publish_status = Column(SAEnum(PublishStatus, name="publish_status"), nullable=False, default=PublishStatus.pending, index=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    task = relationship("Task", back_populates="platform_selections")
    platform = relationship("Platform")

    __table_args__ = (UniqueConstraint("task_id", "platform_id", name="uq_task_platform"),)

class OAuthToken(Base, SyncBase):
    __tablename__ = "oauth_token"

    token_id = Column(String(36), primary_key=True, default=gen_uuid_str)
    platform_id = Column(String(36), ForeignKey("platform.platform_id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(36), nullable=True)
    access_token = Column(Text, nullable=False) 
    refresh_token = Column(Text, nullable=True) 
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PostAttempt(Base, SyncBase):
    __tablename__ = "post_attempt"

    attempt_id = Column(String(36), primary_key=True, default=gen_uuid_str)
    task_id = Column(String(36), ForeignKey("task.task_id", ondelete="SET NULL"), nullable=True, index=True)
    platform_id = Column(String(36), ForeignKey("platform.platform_id", ondelete="SET NULL"), nullable=True, index=True)
    attempted_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    status = Column(SAEnum(AttemptStatus, name="attempt_status"), nullable=False, default=AttemptStatus.transient_failure, index=True)
    response = Column(JSON, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    error_log_id = Column(String(36), ForeignKey("error_log.error_id", ondelete="SET NULL"), nullable=True)

    task = relationship("Task", back_populates="post_attempts")
    platform = relationship("Platform")

class ErrorLog(Base, SyncBase):
    __tablename__ = "error_log"

    error_id = Column(String(36), primary_key=True, default=gen_uuid_str)
    task_id = Column(String(36), ForeignKey("task.task_id", ondelete="SET NULL"), nullable=True)
    platform_id = Column(String(36), ForeignKey("platform.platform_id", ondelete="SET NULL"), nullable=True)
    attempt_id = Column(String(36), nullable=True)
    error_type = Column(String(128), nullable=True)
    error_code = Column(String(64), nullable=True)
    message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

Index("ix_task_scheduled_at_status", Task.scheduled_at, Task.status)
Index("ix_generated_content_created_at", GeneratedContent.created_at)
Index("ix_post_attempt_status_attempted_at", PostAttempt.status, PostAttempt.attempted_at)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=AsyncSession,
    future=True,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)

async def init_db() -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    with sync_engine.begin() as conn:
        SyncBase.metadata.create_all(bind=conn)

def get_sync_db():
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session