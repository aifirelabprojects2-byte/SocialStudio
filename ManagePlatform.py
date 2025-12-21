from datetime import datetime
from fastapi import Depends, HTTPException
import Accounts
from Database import Platform, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from Encryption import encrypt_token, decrypt_token  
import pytz

KOLKATA_TZ = pytz.timezone("Asia/Kolkata")
UTC_TZ = pytz.UTC


async def get_platform_by_name(db: AsyncSession, name: str) -> Platform:
    result = await db.execute(select(Platform).filter_by(name=name.lower()))
    platform = result.scalar_one_or_none()
    if not platform:
        raise HTTPException(status_code=404, detail="Platform not found")
    return platform


def convert_db_datetime_to_kolkata(db_datetime):
    if db_datetime is None:
        return None
    
    # If datetime is naive (no timezone), treat it as UTC
    if db_datetime.tzinfo is None:
        utc_datetime = UTC_TZ.localize(db_datetime)
    else:
        utc_datetime = db_datetime.astimezone(UTC_TZ)
    
    # Convert to Kolkata
    return utc_datetime.astimezone(KOLKATA_TZ)


def convert_kolkata_to_db_datetime(datetime_str):
    if not datetime_str:
        return None
    naive_datetime = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M")
    kolkata_datetime = KOLKATA_TZ.localize(naive_datetime)
    utc_datetime = kolkata_datetime.astimezone(UTC_TZ)
    return utc_datetime.replace(tzinfo=None)


def init(app):
    @app.get("/api/platforms/list")
    async def list_platforms(db: AsyncSession = Depends(get_db), _=Depends(Accounts.get_current_user)):
        result = await db.execute(select(Platform).order_by(Platform.name))
        platforms = result.scalars().all()

        now_kolkata = datetime.now(KOLKATA_TZ)

        return [
            {
                "platform_id": p.platform_id,
                "name": p.name.capitalize(),
                "api_name": p.api_name,
                "expires_at": convert_db_datetime_to_kolkata(p.expires_at).isoformat() if p.expires_at else None,
                "expires_at_local": convert_db_datetime_to_kolkata(p.expires_at).strftime("%d %b %Y, %I:%M %p") if p.expires_at else "Never",
                "days_remaining": (
                    (convert_db_datetime_to_kolkata(p.expires_at) - now_kolkata).days
                    if p.expires_at else None
                ),
                "is_active": p.is_active or False,
                "has_token": {
                    "facebook": bool(p.page_access_token),
                    "instagram": bool(p.ll_user_access_token),
                    "threads": bool(p.ll_user_access_token),
                    "x": any([
                        p.consumer_key, p.consumer_secret, p.access_token,
                        p.access_token_secret, p.bearer_token
                    ]),
                },
            }
            for p in platforms
        ]
        
    @app.get("/api/active/platforms")
    async def list_active_platforms(db: AsyncSession = Depends(get_db), _=Depends(Accounts.get_current_user)):
        result = await db.execute(
            select(Platform)
            .where(Platform.is_active == True)
            .order_by(Platform.name)
        )
        platforms = result.scalars().all()

        now_kolkata = datetime.now(KOLKATA_TZ)

        active_platforms = []

        for p in platforms:
            platform_name = p.name.lower()
            is_valid = False
            
            if platform_name == "facebook":
                if p.page_access_token:
                    if p.expires_at is None:
                        is_valid = True
                    else:
                        kolkata_expires = convert_db_datetime_to_kolkata(p.expires_at)
                        if kolkata_expires > now_kolkata:
                            is_valid = True

            elif platform_name in ["instagram", "threads"]:
                if p.ll_user_access_token:
                    if p.expires_at is None:
                        is_valid = True
                    else:
                        kolkata_expires = convert_db_datetime_to_kolkata(p.expires_at)
                        if kolkata_expires > now_kolkata:
                            is_valid = True

            elif platform_name == "x" or platform_name == "twitter":
                has_keys = any([
                    p.consumer_key,
                    p.consumer_secret,
                    p.access_token,
                    p.access_token_secret,
                    p.bearer_token
                ])
                if has_keys:
                    is_valid = True

            if is_valid:
                active_platforms.append({
                    "platform_id": p.platform_id,
                    "name": p.name.capitalize(), 
                })

        return active_platforms
    
    @app.get("/api/platforms/{name}")
    async def get_platform(name: str, db: AsyncSession = Depends(get_db), _=Depends(Accounts.get_current_user)):
        platform = await get_platform_by_name(db, name.lower())

        # Convert expires_at from UTC (in database) to Kolkata time for display
        expires_local_str = None
        expires_display = "Never"
        days_remaining = None
        
        if platform.expires_at:
            expires_kolkata = convert_db_datetime_to_kolkata(platform.expires_at)
            # Return in format that datetime-local input expects (YYYY-MM-DDTHH:MM)
            expires_local_str = expires_kolkata.strftime("%Y-%m-%dT%H:%M")
            expires_display = expires_kolkata.strftime("%d %b %Y, %I:%M %p")
            days_remaining = (expires_kolkata - datetime.now(KOLKATA_TZ)).days

        decrypted = {
            "page_access_token": decrypt_token(platform.page_access_token) or "",
            "ll_user_access_token": decrypt_token(platform.ll_user_access_token) or "",
            "threads_long_lived_token": decrypt_token(platform.ll_user_access_token) or "",
            "consumer_key": decrypt_token(platform.consumer_key) or "",
            "consumer_secret": decrypt_token(platform.consumer_secret) or "",
            "access_token": decrypt_token(platform.access_token) or "",
            "access_token_secret": decrypt_token(platform.access_token_secret) or "",
            "bearer_token": decrypt_token(platform.bearer_token) or "",
        }

        return {
            "platform_id": platform.platform_id,
            "name": platform.name,
            "is_active": platform.is_active or False,
            "expires_at": expires_local_str,  # Format for datetime-local input
            "expires_at_display": expires_display,
            "days_remaining": days_remaining,
            "page_id": platform.page_id or "",
            "threads_user_id": platform.threads_user_id or "",
            "threads_username": platform.threads_username or "",
            "decrypted": decrypted,
            "has_token": {
                "facebook": bool(decrypted["page_access_token"]),
                "instagram": bool(decrypted["ll_user_access_token"]),
                "threads": bool(decrypted["threads_long_lived_token"]),
                "x": any([
                    decrypted["consumer_key"], decrypted["consumer_secret"],
                    decrypted["access_token"], decrypted["access_token_secret"],
                    decrypted["bearer_token"]
                ]),
            }
        }

    @app.post("/api/platforms/{name}")
    async def update_platform(name: str, data: dict, db: AsyncSession = Depends(get_db)):
        platform = await get_platform_by_name(db, name.lower())

        if "is_active" in data:
            platform.is_active = data["is_active"]

        if "expires_at" in data:
            if data["expires_at"]:
                # Convert Kolkata time string to naive UTC datetime for storage
                platform.expires_at = convert_kolkata_to_db_datetime(data["expires_at"])
            else:
                platform.expires_at = None

        # Platform-specific token updates
        if name == "facebook":
            if "page_id" in data:
                platform.page_id = data["page_id"] or None
            if "page_access_token" in data and data["page_access_token"]:
                platform.page_access_token = encrypt_token(data["page_access_token"])

        elif name == "instagram":
            if "page_id" in data:
                platform.page_id = data["page_id"] or None
            if "ll_user_access_token" in data and data["ll_user_access_token"]:
                platform.ll_user_access_token = encrypt_token(data["ll_user_access_token"])

        elif name == "threads":
            if "threads_user_id" in data:
                platform.threads_user_id = data["threads_user_id"] or None
            if "threads_username" in data:
                platform.threads_username = data["threads_username"] or None
            if "threads_long_lived_token" in data and data["threads_long_lived_token"]:
                platform.ll_user_access_token = encrypt_token(data["threads_long_lived_token"])

        elif name == "x":
            if "consumer_key" in data and data["consumer_key"]:
                platform.consumer_key = encrypt_token(data["consumer_key"])
            if "consumer_secret" in data and data["consumer_secret"]:
                platform.consumer_secret = encrypt_token(data["consumer_secret"])
            if "access_token" in data and data["access_token"]:
                platform.access_token = encrypt_token(data["access_token"])
            if "access_token_secret" in data and data["access_token_secret"]:
                platform.access_token_secret = encrypt_token(data["access_token_secret"])
            if "bearer_token" in data and data["bearer_token"]:
                platform.bearer_token = encrypt_token(data["bearer_token"])

        await db.commit()
        return {"success": True, "message": "Credentials updated successfully"}