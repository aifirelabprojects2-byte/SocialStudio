# Database.py 

import os
import enum
import uuid
from typing import AsyncGenerator
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
    UniqueConstraint,
    JSON,
    Enum as SAEnum,
    func,
    create_engine,
    select,
    event
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker,relationship
from sqlalchemy.types import TypeDecorator
from sqlalchemy.exc import SQLAlchemyError
import pytz
import json
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)


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
    connect_args={"timeout": 30} 
)

# 2. Update Sync Engine
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"timeout": 30}
)
@event.listens_for(async_engine.sync_engine, "connect")
@event.listens_for(sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

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

class TemplateDB(Base):
    __tablename__ = "templates"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    type = Column(String)     
    category = Column(String)  
    style = Column(String)     
    width = Column(Integer)
    height = Column(Integer)
    preview_url = Column(String) 
    json_data = Column(Text)     

class DesignRecord(Base):
    __tablename__ = "generated_designs"
    id = Column(String, primary_key=True, index=True) 
    batch_id = Column(String, index=True) 
    json_data = Column(JSON)
    caption = Column(Text)

    
class Platform(Base):
    __tablename__ = "platform"
    platform_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    api_name = Column(String(32), nullable=False, index=True)
    account_id = Column(String(64))
    account_name = Column(String(128))
    access_token = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True))
    meta = Column(JSON) # platform.meta.get("REFRESH_TOKEN") for accessing
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())    
    
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
    storage_path = Column(Text, nullable=False)  
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

class JSONText(TypeDecorator):
    impl = Text
    def process_bind_param(self, value, dialect):
        if value is None: return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None: return None
        return json.loads(value)


class Company(Base, SyncBase):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True, index=True)
    website_url = Column(String, nullable=False) 
    company_name = Column(String, nullable=True)
    company_details = Column(Text, nullable=True)
    company_location = Column(String, nullable=True)
    company_products = Column(JSONText, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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


def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

async def seed_admin_user_if_missing() -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(User).where(User.username == "admin")
            )
            admin = result.scalar_one_or_none()

            if admin is None:
                admin_user = User(
                    username="admin",
                    password_hash=hash_password("qwerty2k26"),
                    is_active=True,
                )
                session.add(admin_user)


async def init_db() -> None:
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, checkfirst=True)
    except Exception as e:
        print(f"Note: Base metadata creation encountered: {e}")
        pass

    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(SyncBase.metadata.create_all, checkfirst=True)
    except Exception as e:
        print(f"Note: SyncBase metadata creation encountered: {e}")
        pass
    await seed_admin_user_if_missing()

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