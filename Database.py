# Database.py 

import os
import enum
import uuid
from typing import AsyncGenerator, Optional
from datetime import datetime
from sqlalchemy import (
    DECIMAL,
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
    select,
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker,relationship
from sqlalchemy.exc import SQLAlchemyError
import pytz

IST = pytz.timezone('Asia/Kolkata')

def ist_now() -> datetime:
    return datetime.now(IST)

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

class SyncBase(DeclarativeBase):
    pass

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
    is_active = Column(Boolean, default=False)

    # Generic
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Meta specific
    page_id = Column(String(64), nullable=True)  # For IG & FB
    # Facebook specific 
    page_access_token = Column(String(128), nullable=True)  
    
    # Instagram specific 
    ll_user_access_token = Column(String(128), nullable=True)  # long live user access token
    
    # Threads specific
    threads_user_id = Column(String(64), nullable=True)
    threads_username = Column(String(64), nullable=True)

    # X/Twitter specific
    consumer_key = Column(String(128), nullable=True)
    consumer_secret = Column(String(128), nullable=True)
    access_token = Column(String(128), nullable=True)
    access_token_secret = Column(String(128), nullable=True)
    bearer_token = Column(Text, nullable=True)

    meta = Column(JSON, nullable=True) 
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=ist_now)
    
class ImageTheme(Base, SyncBase):
    __tablename__ = "image_theme"

    theme_id = Column(String(36), primary_key=True, default=gen_uuid_str)
    name = Column(String(64), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True) 
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=ist_now)

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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=ist_now)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=ist_now)
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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=ist_now)

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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=ist_now)

    task = relationship("Task", back_populates="media")
    generated_content = relationship("GeneratedContent", back_populates="media")

class PlatformSelection(Base, SyncBase):
    __tablename__ = "platform_selection"

    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    task_id = Column(String(36), ForeignKey("task.task_id", ondelete="CASCADE"), nullable=False, index=True)
    platform_id = Column(String(36), ForeignKey("platform.platform_id", ondelete="RESTRICT"), nullable=False, index=True)
    publish_status = Column(SAEnum(PublishStatus, name="publish_status"), nullable=False, default=PublishStatus.pending, index=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=ist_now)

    task = relationship("Task", back_populates="platform_selections")
    platform = relationship("Platform")

    __table_args__ = (UniqueConstraint("task_id", "platform_id", name="uq_task_platform"),)

class LLMUsage(Base, SyncBase):
    __tablename__ = "llm_usage"
    id = Column(String(36), primary_key=True, default=gen_uuid_str)
    feature = Column(String(50), nullable=False, index=True)
    model = Column(String(50), nullable=False, index=True)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    cost_usd = Column(DECIMAL(10, 6), nullable=False)
    latency_ms = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="success")
    created_at = Column( DateTime(timezone=True),server_default=func.now(), default=ist_now,nullable=False)

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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=ist_now)

class User(Base, SyncBase):
    __tablename__ = "user"

    user_id = Column(String(36), primary_key=True, default=gen_uuid_str)
    username = Column(String(64), nullable=False, unique=True, default="admin")  # fixed username
    password_hash = Column(String(128), nullable=False)   # bcrypt hash
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=ist_now)


class LoginSession(Base, SyncBase):
    __tablename__ = "login_session"

    session_id = Column(String(36), primary_key=True, default=gen_uuid_str)
    user_id = Column(String(36), ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(64), nullable=False, unique=True, index=True)  # random token stored in cookie
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=ist_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)  # e.g. 30 days

    user = relationship("User")

# Index("ix_task_scheduled_at_status", Task.scheduled_at, Task.status)
# Index("ix_generated_content_created_at", GeneratedContent.created_at)
# Index("ix_post_attempt_status_attempted_at", PostAttempt.status, PostAttempt.attempted_at)
# Index("ix_login_session_token", LoginSession.token)
# Index("ix_login_session_expires_at", LoginSession.expires_at)

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

async def seed_platforms_if_missing() -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            required_platforms = [
                {
                    "name": "facebook",
                    "api_name": "facebook",
                },
                {
                    "name": "instagram",
                    "api_name": "instagram",
                },
                {
                    "name": "threads",
                    "api_name": "threads",
                },
                {
                    "name": "x",
                    "api_name": "twitter",
                },
            ]

            for plat in required_platforms:
                exists = await session.execute(
                    select(Platform).filter_by(name=plat["name"])
                )
                if exists.scalar_one_or_none() is None:
                    new_platform = Platform(
                        name=plat["name"],
                        api_name=plat["api_name"],
                        expires_at=None,
                        page_id=None,
                        page_access_token=None,
                        ll_user_access_token=None,
                        threads_user_id=None,
                        threads_username=None,
                        consumer_key=None,
                        consumer_secret=None,
                        access_token=None,
                        access_token_secret=None,
                        bearer_token=None,
                        meta=None,  
                    )
                    session.add(new_platform)
        await session.commit()

async def init_db() -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)

    async with async_engine.begin() as conn:
        await conn.run_sync(SyncBase.metadata.create_all, checkfirst=True)

    await seed_platforms_if_missing()

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