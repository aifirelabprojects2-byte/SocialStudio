from fastapi.templating import Jinja2Templates
import ipinfo
from Auth import create_session, get_current_user_from_token, hash_password, invalidate_all_sessions, verify_password
from datetime import datetime
from typing import Optional
from fastapi import  Cookie, Form, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from Database import AsyncSessionLocal, LoginSession, User, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import  select, delete
import pytz
templates = Jinja2Templates(directory="templates")

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    session_token: Optional[str] = Cookie(None, alias="session_token")
):
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = await get_current_user_from_token(db, session_token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    return user
handler = ipinfo.getHandler("")  

def init(app):
    @app.get("/login", response_class=HTMLResponse)
    async def login_page(
        request: Request,
        message: Optional[str] = None,
        session_token: Optional[str] = Cookie(None, alias="session_token")
    ):
        if session_token:
            async with AsyncSessionLocal() as db:
                user = await get_current_user_from_token(db, session_token)
                if user:
                    return RedirectResponse(url="/", status_code=303)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "message": message}
        )
    @app.get("/debug-bcrypt/{test_password}")
    async def debug_bcrypt(test_password: str, db: AsyncSession = Depends(get_db)):
        import bcrypt as bcrypt_module
        result = await db.execute(select(User).where(User.is_active == True))
        user = result.scalar_one_or_none()
        if not user:
            return {"error": "No active user found"}

        # Test the current hash
        test_result = verify_password(test_password, user.password_hash)

        # Create a fresh hash for comparison
        fresh_hash = hash_password(test_password)
        fresh_verify = verify_password(test_password, fresh_hash)

        return {
            "test_password": test_password,
            "stored_hash": user.password_hash,
            "verify_with_stored": test_result,
            "fresh_hash": fresh_hash,
            "verify_with_fresh": fresh_verify,
            "bcrypt_version": bcrypt_module.__version__,
            "username": user.username
        }

    @app.get("/reset-pw/{new_password}")
    async def temp_reset_password(new_password: str, db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(User).where(User.is_active == True))
        user = result.scalar_one_or_none()
        if user:
            user.password_hash = hash_password(new_password)
            await db.commit()
            return {"status": "ok", "new_password": new_password, "new_hash": user.password_hash}
        return {"status": "error"}

    @app.post("/login")
    async def login_post(
        request: Request,
        password: str = Form(...),
        db: AsyncSession = Depends(get_db)
    ):
        result = await db.execute(select(User).where(User.is_active == True))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid password"}, status_code=400)

        # Get IP from X-Forwarded-For header (Azure App Service uses this)
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.headers.get("X-Client-IP", "")
        if not client_ip and request.client:
            client_ip = request.client.host
        if not client_ip:
            client_ip = "unknown"

        token = await create_session(
            db=db,
            user_id=user.user_id,
            ip=client_ip,
            ua=str(request.headers.get("user-agent", "")),
            days=30
        )
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            secure=request.url.scheme == "https",  # Only secure if request is HTTPS
            samesite="lax",
            max_age=30*24*60*60   # 30 days
        )
        return response

    @app.post("/logout")
    async def logout(
        db: AsyncSession = Depends(get_db),
        session_token: Optional[str] = Cookie(None, alias="session_token")
    ):
        if session_token:
            await db.execute(delete(LoginSession).where(LoginSession.token == session_token))
            await db.commit()
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie("session_token")
        return response

    @app.post("/logout-all")
    async def logout_all_devices(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        await invalidate_all_sessions(db, user.user_id)
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie("session_token")
        return response

    @app.post("/sessions/{session_id}/logout")
    async def logout_specific_session(
        session_id: str,
        user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        request: Request = None
    ):

        result = await db.execute(
            select(LoginSession).where(
                LoginSession.session_id == session_id,
                LoginSession.user_id == user.user_id
            )
        )
        session = result.scalar_one_or_none()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found or not yours")

        response = RedirectResponse(url="/sessions", status_code=303)
        current_token = request.cookies.get("session_token") if request else None
        if session.token == current_token:
            response.delete_cookie("session_token")

        await db.delete(session)
        await db.commit()

        return response

    @app.get("/api/sessions")
    async def api_list_sessions(
        user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        result = await db.execute(
            select(LoginSession)
            .where(
                LoginSession.user_id == user.user_id,
                LoginSession.expires_at > datetime.now(pytz.UTC)
            )
            .order_by(LoginSession.last_seen_at.desc())
        )
        sessions = result.scalars().all()

        response = []
        for s in sessions:
            try:
                loc = handler.getDetails(s.ip_address)
                location = (
                    f"{loc.city}, {loc.country_name}"
                    if loc.city and loc.country_name
                    else loc.country_name or "Unknown Location"
                )
            except Exception:
                location = "Unknown Location"

            response.append({
                "session_id": s.session_id,
                "ip_address": s.ip_address,
                "user_agent": s.user_agent,
                "created_at": s.created_at.isoformat(),
                "last_seen_at": s.last_seen_at.isoformat(),
                "expires_at": s.expires_at.isoformat(),
                "location": location,
            })

        return response

    @app.post("/change-password")
    async def change_password(
        old_password: str = Form(...),
        new_password: str = Form(...),
        new_password_confirm: str = Form(...),
        user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        if not verify_password(old_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Old password incorrect")
        if new_password != new_password_confirm:
            raise HTTPException(status_code=400, detail="New passwords do not match")
        if len(new_password) < 8:
            raise HTTPException(status_code=400, detail="New password too short")

        user.password_hash = hash_password(new_password)
        await invalidate_all_sessions(db, user.user_id)
        await db.commit()

        # Force re-login
        response = JSONResponse({"detail": "Password changed successfully. Please log in again."})
        response.delete_cookie("session_token")
        return response
