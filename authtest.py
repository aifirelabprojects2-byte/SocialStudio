from dotenv import load_dotenv
load_dotenv()

import os
import uuid
import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import Column, String, Text, DateTime, JSON, Boolean, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

logging.basicConfig(level=logging.INFO)


app = FastAPI(title="Page Automation Connector")

DATABASE_URL = "sqlite+aiosqlite:///social_connections.db"
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


class SocialConnection(Base):
    __tablename__ = "social_connections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    platform = Column(String(32), nullable=False, index=True)
    account_id = Column(String(64))
    account_name = Column(String(128))
    access_token = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True))
    meta = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.on_event("startup")
async def startup():
    await init_db()


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise



GRAPH_VERSION = "v19.0"

REDIRECT_URI_FB = "https://6525110533e0.ngrok-free.app/auth/facebook/callback"
REDIRECT_URI_IG = "https://6525110533e0.ngrok-free.app/auth/instagram/callback"
REDIRECT_URI_THREADS = "https://6525110533e0.ngrok-free.app/auth/threads/callback"


def get_client_creds(platform: str):
    if platform in ("facebook", "instagram"):
        return os.getenv("META_APP_ID_FB"), os.getenv("META_APP_SECRET_FB")
    if platform == "threads":
        return os.getenv("META_APP_ID_THREADS"), os.getenv("META_APP_SECRET_THREADS")
    raise ValueError("Unknown platform")


def build_authorize_url(platform: str, redirect_uri: str, scopes: str):
    client_id, _ = get_client_creds(platform)
    state = f"{platform}:{uuid.uuid4()}"

    if platform in ("facebook", "instagram"):
        base = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
        scope = scopes
    else:
        base = "https://threads.net/oauth/authorize"
        scope = scopes.replace(" ", ",")

    return (
        f"{base}?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope={scope}"
        f"&state={state}"
    )


async def exchange_code(code: str, redirect_uri: str, platform: str):
    client_id, client_secret = get_client_creds(platform)

    async with httpx.AsyncClient(timeout=15) as c:
        if platform == "threads":
            r = await c.post(
                "https://graph.threads.net/oauth/access_token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
        else:
            r = await c.get(
                f"https://graph.facebook.com/{GRAPH_VERSION}/oauth/access_token",
                params={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )

        r.raise_for_status()
        return r.json()


async def exchange_long_lived(short_token: str):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            f"https://graph.facebook.com/{GRAPH_VERSION}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": os.getenv("META_APP_ID_FB"),
                "client_secret": os.getenv("META_APP_SECRET_FB"),
                "fb_exchange_token": short_token,
            },
        )
        r.raise_for_status()
        return r.json()


@app.get("/", response_class=HTMLResponse)
async def dashboard(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(SocialConnection))
    items = res.scalars().all()

    html = "<h1>Page Automation Connector</h1>"
    html += '<a href="/auth/instagram/start"><button>Instagram</button></a><br><br>'
    html += '<a href="/auth/facebook/start"><button>Facebook</button></a><br><br>'
    html += '<a href="/auth/threads/start"><button>Threads</button></a><br><br>'
    html += "<h2>Connected</h2><ul>"

    for c in items:
        photo = c.meta.get("PROFILE_PHOTO_URL") if c.meta else None
        html += "<li>"
        if photo:
            html += f'<img src="{photo}" width="32" height="32" style="vertical-align:middle;border-radius:50%"> '
        html += f"{c.platform} — {c.account_name}</li>"

    html += "</ul>"
    return html

@app.get("/auth/facebook/start")
async def start_fb():
    return RedirectResponse(
        build_authorize_url(
            "facebook",
            REDIRECT_URI_FB,
            "pages_show_list pages_read_engagement pages_manage_posts",
        )
    )


@app.get("/auth/instagram/start")
async def start_ig():
    return RedirectResponse(
        build_authorize_url(
            "instagram",
            REDIRECT_URI_IG,
            "instagram_basic instagram_content_publish pages_show_list",
        )
    )


@app.get("/auth/threads/start")
async def start_threads():
    return RedirectResponse(
        build_authorize_url(
            "threads",
            REDIRECT_URI_THREADS,
            "threads_basic threads_content_publish",
        )
    )


@app.get("/auth/facebook/callback")
async def cb_fb(req: Request, db: AsyncSession = Depends(get_db)):
    return await handle_callback(req, db, "facebook", REDIRECT_URI_FB)


@app.get("/auth/instagram/callback")
async def cb_ig(req: Request, db: AsyncSession = Depends(get_db)):
    return await handle_callback(req, db, "instagram", REDIRECT_URI_IG)


@app.get("/auth/threads/callback")
async def cb_threads(req: Request, db: AsyncSession = Depends(get_db)):
    return await handle_callback(req, db, "threads", REDIRECT_URI_THREADS)


async def handle_callback(req: Request, db: AsyncSession, platform: str, redirect_uri: str):
    code = req.query_params.get("code")
    if not code:
        raise HTTPException(400, "Missing code")

    token = await exchange_code(code, redirect_uri, platform)

    async with httpx.AsyncClient(timeout=15) as client:

        # ---------------- FACEBOOK PAGES ----------------
        if platform == "facebook":
            long_token = await exchange_long_lived(token["access_token"])

            pages = await client.get(
                f"https://graph.facebook.com/{GRAPH_VERSION}/me/accounts",
                params={"access_token": long_token["access_token"]},
            )
            pages.raise_for_status()

            page = pages.json()["data"][0]

            conn = SocialConnection(
                platform="facebook",
                account_id=page["id"],
                account_name=page["name"],
                access_token=page["access_token"],
                expires_at=datetime.now(timezone.utc) + timedelta(days=60),
                meta={
                    "PAGE_ID": page["id"],
                    "PAGE_ACCESS_TOKEN": page["access_token"],
                    "PROFILE_PHOTO_URL": None,
                },
            )
            db.add(conn)

        # ---------------- INSTAGRAM BUSINESS ----------------
        elif platform == "instagram":
            long_token = await exchange_long_lived(token["access_token"])

            pages = await client.get(
                f"https://graph.facebook.com/{GRAPH_VERSION}/me/accounts",
                params={"access_token": long_token["access_token"]},
            )
            pages.raise_for_status()

            for page in pages.json()["data"]:
                ig = await client.get(
                    f"https://graph.facebook.com/{GRAPH_VERSION}/{page['id']}",
                    params={
                        "fields": "instagram_business_account{id,username,profile_picture_url}",
                        "access_token": page["access_token"],
                    },
                )
                ig.raise_for_status()
                ig_data = ig.json().get("instagram_business_account")

                if ig_data:
                    conn = SocialConnection(
                        platform="instagram",
                        account_id=ig_data["id"],
                        account_name=ig_data["username"],
                        access_token=long_token["access_token"],
                        expires_at=datetime.now(timezone.utc) + timedelta(days=60),
                        meta={
                            "PAGE_ID": page["id"],
                            "FB_LONG_LIVED_USER_ACCESS_TOKEN": long_token["access_token"],
                            "PROFILE_PHOTO_URL": ig_data.get("profile_picture_url"),
                        },
                    )
                    db.add(conn)
                    break

        # ---------------- THREADS USER ----------------
        else:
            me = await client.get(
                "https://graph.threads.net/me",
                params={
                    "access_token": token["access_token"],
                    "fields": "id,username,threads_profile_picture_url",
                },
            )

            profile = me.json() if me.status_code == 200 else {}

            conn = SocialConnection(
                platform="threads",
                account_id=profile.get("id"),
                account_name=profile.get("username"),
                access_token=token["access_token"],
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                meta={
                    "THREADS_USER_ID": profile.get("id"),
                    "THREAD_USERNAME": profile.get("username"),
                    "THREADS_LONG_LIVE_TOKEN": token["access_token"],
                    "PROFILE_PHOTO_URL": profile.get("threads_profile_picture_url"),
                },
            )
            db.add(conn)

    return RedirectResponse("/", status_code=303)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
