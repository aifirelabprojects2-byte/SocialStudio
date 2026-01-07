from datetime import datetime, timedelta
from fastapi import HTTPException, status
import pytz
from sqlalchemy import select, delete
from Database import User, LoginSession, get_db, AsyncSession
import secrets
from sqlalchemy.orm import joinedload  
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

async def create_session(db: AsyncSession, user_id: str, ip: str, ua: str, days: int = 30) -> str:
    token = secrets.token_urlsafe(48)
    now = datetime.now(pytz.UTC)
    expires_at = now + timedelta(days=days)
    session = LoginSession(
        user_id=user_id,
        token=token,
        ip_address=ip,
        user_agent=ua,
        expires_at=expires_at,
    )
    db.add(session)
    await db.commit()
    return token



async def get_current_user_from_token(db: AsyncSession, token: str):
    now = datetime.now(pytz.UTC)
    result = await db.execute(
        select(LoginSession)
        .options(joinedload(LoginSession.user))
        .where(
            LoginSession.token == token,
            LoginSession.expires_at > now
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    if not session.user.is_active:
        return None
    # Update last_seen
    session.last_seen_at = now
    await db.commit()
    return session.user

async def invalidate_all_sessions(db: AsyncSession, user_id: str):
    await db.execute(delete(LoginSession).where(LoginSession.user_id == user_id))
    await db.commit()