import bcrypt
from datetime import datetime, timedelta
from fastapi import HTTPException, status
import pytz
from sqlalchemy import select, delete
from Database import User, LoginSession, get_db, AsyncSession
import secrets
from sqlalchemy.orm import joinedload  

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

async def create_session(db: AsyncSession, user_id: str, ip: str, ua: str, days: int = 30) -> str:
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(pytz.timezone("Asia/Kolkata")) + timedelta(days=days)
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
    now = datetime.now(pytz.timezone("Asia/Kolkata"))
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