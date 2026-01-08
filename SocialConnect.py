
import json
import os
from typing import List, Optional
import uuid
import logging
from datetime import datetime, timedelta, timezone
import secrets
import hashlib
import base64
from asyncio import Lock
from fastapi.templating import Jinja2Templates
import httpx
from fastapi import Query, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import and_, func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
from pydantic import BaseModel
from sqlalchemy.orm import Session
import Accounts
from Database import GeneratedContent, Media, Platform, PlatformSelection, Task, TaskStatus, get_db, get_sync_db
load_dotenv()
templates = Jinja2Templates(directory="templates")

GRAPH_VERSION = "v19.0"
REDIRECT_URI_FB = "https://aisocialstudio.onrender.com/auth/facebook/callback"
REDIRECT_URI_IG = "https://aisocialstudio.onrender.com/auth/instagram/callback"
REDIRECT_URI_THREADS = "https://aisocialstudio.onrender.com/auth/threads/callback"
REDIRECT_URI_TWITTER = "https://aisocialstudio.onrender.com/auth/twitter/callback"
REDIRECT_URI_LINKEDIN = "https://aisocialstudio.onrender.com/auth/linkedin/callback"

SUPPORTED_PLATFORMS = [
    {
        "id": "instagram", 
        "name": "Instagram", 
        "auth_url": "/auth/instagram/start",
        "svg": "M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"
    },
    {
        "id": "facebook", 
        "name": "Facebook", 
        "auth_url": "/auth/facebook/start",
        "svg": "M9.101 23.691v-7.98H6.627v-3.667h2.474v-1.58c0-4.085 1.848-5.978 5.858-5.978.401 0 .955.042 1.468.103a8.68 8.68 0 0 1 1.141.195v3.325a8.623 8.623 0 0 0-.653-.036c-2.148 0-2.797 1.66-2.797 3.54v1.237h3.362l-.294 3.667h-3.068v7.98H9.101z"
    },
    {
        "id": "linkedin", 
        "name": "LinkedIn", 
        "auth_url": "/auth/linkedin/start",
        "svg": "M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.202 24 24 23.227 24 22.271V1.729C24 .774 23.202 0 22.222 0h.003z"
    },
    {
        "id": "twitter", 
        "name": "Twitter (X)", 
        "auth_url": "/auth/twitter-oauth1/start",
        "svg": "M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z"
    },
    {
        "id": "threads", 
        "name": "Threads", 
        "auth_url": "/auth/threads/start",
        "svg": "M9.4815 9.024c-.405-.27-1.749-1.203-1.749-1.203 1.134-1.6215 2.6295-2.253 4.698-2.253 1.4625 0 2.7045.4905 3.591 1.422.8865.9315 1.392 2.2635 1.5075 3.966q.738.3105 1.3575.726c1.6635 1.1175 2.5785 2.79 2.5785 4.7055 0 4.074-3.339 7.6125-9.384 7.6125C6.891 24 1.5 20.9805 1.5 11.991 1.5 3.051 6.723 0 12.066 0c2.469 0 8.259.3645 10.434 7.554l-2.04.5295C18.774 2.961 15.2445 2.145 12.009 2.145c-5.3475 0-8.373 3.2565-8.373 10.185 0 6.2145 3.381 9.5145 8.445 9.5145 4.1655 0 7.2705-2.1645 7.2705-5.334 0-2.157-1.812-3.1905-1.905-3.1905-.354 1.851-1.302 4.965-5.466 4.965-2.427 0-4.5195-1.677-4.5195-3.873 0-3.135 2.976-4.2705 5.325-4.2705.879 0 1.941.06 2.4945.171 0-.9555-.81-2.592-2.85-2.592-1.875 0-2.349.6075-2.9505 1.302ZM13.074 12.285c-3.06 0-3.456 1.305-3.456 2.124 0 1.317 1.5645 1.752 2.4 1.752 1.53 0 3.1005-.423 3.348-3.6345a9.3 9.3 0 0 0-2.292-.2415"
    },
]



pending_auth: dict[str, str] = {}
auth_lock = Lock()


def get_client_creds(platform: str):
    if platform in ("facebook", "instagram"):
        return os.getenv("META_APP_ID_FB"), os.getenv("META_APP_SECRET_FB")
    if platform == "threads":
        return os.getenv("META_APP_ID_THREADS"), os.getenv("META_APP_SECRET_THREADS")
    if platform == "twitter":
        return os.getenv("TWITTER_CLIENT_ID"), os.getenv("TWITTER_CLIENT_SECRET")
    if platform == "linkedin":
        return os.getenv("LINKEDIN_CLIENT_ID"), os.getenv("LINKEDIN_CLIENT_SECRET")
    raise ValueError("Unknown platform")

def build_authorize_url(platform: str, redirect_uri: str, scopes: str):
    client_id, _ = get_client_creds(platform)
    state = f"{platform}:{uuid.uuid4()}"

    if platform in ("facebook", "instagram"):
        base = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
        scope = scopes
    elif platform == "threads":
        base = "https://threads.net/oauth/authorize"
        scope = scopes.replace(" ", ",")
    elif platform == "linkedin":
        base = "https://www.linkedin.com/oauth/v2/authorization"
        scope = scopes  
    else:
        raise ValueError("Unknown platform")

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
        elif platform == "linkedin":
            r = await c.post(
                "https://www.linkedin.com/oauth/v2/accessToken",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": client_id,
                    "client_secret": client_secret,
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

async def get_threads_long_lived_token(short_lived_token: str, platform: str):
    client_id, client_secret = get_client_creds(platform)
    
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(
            "https://graph.threads.net/access_token",
            params={
                "grant_type": "th_exchange_token",
                "client_secret": client_secret,
                "access_token": short_lived_token,
            },
        )
        if r.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get long-lived token")
        
        return r.json()

async def handle_callback(req: Request, db: AsyncSession, platform: str, redirect_uri: str):
    code = req.query_params.get("code")
    error = req.query_params.get("error")
    if error:
        raise HTTPException(400, f"OAuth error from platform: {error}")
    if not code:
        raise HTTPException(400, "Missing code")

    async with httpx.AsyncClient(timeout=15) as client:
        if platform == "facebook":
            token = await exchange_code(code, redirect_uri, platform)
            long_token = await exchange_long_lived(token["access_token"])

            # Updated to include 'picture' in fields to get the DP
            pages = await client.get(
                f"https://graph.facebook.com/{GRAPH_VERSION}/me/accounts",
                params={
                    "access_token": long_token["access_token"],
                    "fields": "id,name,access_token,picture.type(large)" # 'large' gets a high-res DP
                },
            )
            pages.raise_for_status()

            # Get the first page from the list
            page_data = pages.json().get("data", [])
            if not page_data:
                raise HTTPException(status_code=404, detail="No Facebook pages found for this account")
            
            page = page_data[0]
            profile_pic_url = page.get("picture", {}).get("data", {}).get("url")

            conn = Platform(
                api_name="facebook",
                account_id=page["id"],
                account_name=page["name"],
                access_token=page["access_token"],
                expires_at=datetime.now(timezone.utc) + timedelta(days=60),
                meta={
                    "PAGE_ID": page["id"],
                    "PAGE_ACCESS_TOKEN": page["access_token"],
                    "PROFILE_PHOTO_URL": profile_pic_url,
                },
            )
            db.add(conn)
            await db.commit()

        elif platform == "instagram":
            token = await exchange_code(code, redirect_uri, platform)
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
                    conn = Platform(
                        api_name="instagram",
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
                    await db.commit()
                    break

        elif platform == "threads":
            short_token_data = await exchange_code(code, redirect_uri, platform)
            short_token = short_token_data["access_token"]
            long_token_data = await get_threads_long_lived_token(short_token, platform)
            long_access_token = long_token_data["access_token"]
            expires_in = long_token_data.get("expires_in", 5184000) 

            me = await client.get(
                "https://graph.threads.net/me",
                params={
                    "access_token": long_access_token,
                    "fields": "id,username,threads_profile_picture_url",
                },
            )

            profile = me.json() if me.status_code == 200 else {}

            conn = Platform(
                api_name="threads",
                account_id=profile.get("id"),
                account_name=profile.get("username"),
                access_token=long_access_token,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
                meta={
                    "THREADS_USER_ID": profile.get("id"),
                    "THREAD_USERNAME": profile.get("username"),
                    "THREADS_LONG_LIVE_TOKEN": long_access_token,
                    "PROFILE_PHOTO_URL": profile.get("threads_profile_picture_url"),
                },
            )
            db.add(conn)
            await db.commit()

        elif platform == "twitter":
            state = req.query_params.get("state")
            if not state:
                raise HTTPException(400, "Missing state")

            async with auth_lock:
                if state not in pending_auth:
                    raise HTTPException(400, "Invalid or expired state")
                code_verifier = pending_auth.pop(state)

            client_id, client_secret = get_client_creds("twitter")
            basic_auth = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")

            # Exchange code for tokens
            token_resp = await client.post(
                "https://api.x.com/2/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": client_id,
                    "redirect_uri": redirect_uri,
                    "code_verifier": code_verifier,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {basic_auth}",
                },
            )
            if token_resp.status_code != 200:
                error_detail = token_resp.text
                logging.error(f"Twitter token exchange failed: {token_resp.status_code} {error_detail}")
                raise HTTPException(500, f"Twitter OAuth token exchange failed: {error_detail}")

            token_data = token_resp.json()

            access_token = token_data["access_token"]
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 7200)  # Default 2 hours

            # Get user profile
            user_resp = await client.get(
                "https://api.x.com/2/users/me",
                params={"user.fields": "profile_image_url"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_resp.status_code != 200:
                error_detail = user_resp.text
                logging.error(f"Twitter user lookup failed: {error_detail}")
                raise HTTPException(500, f"Twitter user lookup failed: {error_detail}")

            user_data = user_resp.json()["data"]

            profile_pic = user_data.get("profile_image_url", "")
            if profile_pic:
                profile_pic = profile_pic.replace("_normal.jpg", ".jpg")  # Larger version

            conn = Platform(
                api_name="twitter",
                account_id=user_data["id"],
                account_name=user_data["username"],
                access_token=access_token,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
                meta={
                    "REFRESH_TOKEN": refresh_token,
                    "PROFILE_PHOTO_URL": profile_pic,
                },
            )
            db.add(conn)
            await db.commit()
        elif platform == "linkedin":
            token = await exchange_code(code, redirect_uri, platform)

            access_token = token["access_token"]
            expires_in = token.get("expires_in", 5184000)  # ~60 days default

            async with httpx.AsyncClient(timeout=15) as client:
                me = await client.get(
                    "https://api.linkedin.com/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                me.raise_for_status()
                profile = me.json()
            conn = Platform(
                api_name="linkedin",
                account_id=profile.get("sub"),
                account_name=profile.get("name"),
                access_token=access_token,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
                meta={
                    "USERNAME": profile.get("preferred_username") or profile.get("email"),
                    "PROFILE_PHOTO_URL": profile.get("picture"),
                },
            )
            db.add(conn)
            await db.commit()
        else:
            raise ValueError("Unknown platform")
    return RedirectResponse("/", status_code=303)

# Pydantic models for response
class PlatformInfo(BaseModel):
    platform_id: str
    api_name: str
    account_name: Optional[str]
    publish_status: str

class TaskListItem(BaseModel):
    task_id: str
    title: Optional[str]
    status: str
    scheduled_at: Optional[datetime]
    caption: Optional[str]
    thumbnail_url: Optional[str]
    platforms: List[PlatformInfo]
    created_at: datetime
    
    class Config:
        from_attributes = True

class TaskListResponse(BaseModel):
    tasks: List[TaskListItem]
    total: int
    filters_applied: dict

    
def init(app):
    @app.get("/social", response_class=HTMLResponse)
    async def dashboard(db: AsyncSession = Depends(get_db)):
        res = await db.execute(select(Platform))
        items = res.scalars().all()

        html = "<h1>Page Automation Connector</h1>"
        html += '<a href="/auth/instagram/start"><button>Instagram</button></a><br><br>'
        html += '<a href="/auth/facebook/start"><button>Facebook</button></a><br><br>'
        html += '<a href="/auth/threads/start"><button>Threads</button></a><br><br>'
        html += '<a href="/auth/linkedin/start"><button>LinkedIn</button></a><br><br>'
        html += '<a href="/auth/twitter-oauth1/start"><button>Twitter (Media Upload)</button></a><br><br>'

        
        html += "<h2>Connected Accounts</h2><ul>"

        for c in items:
            photo = c.meta.get("PROFILE_PHOTO_URL") if c.meta else None
            html += "<li>"
            if photo:
                html += f'<img src="{photo}" width="32" height="32" style="vertical-align:middle;border-radius:50%"> '
            html += f"{c.api_name.capitalize()} — {c.account_name}</li>"

        html += "</ul>"
        return html

    from tweepy import OAuth1UserHandler,API

    @app.get("/auth/twitter-oauth1/start")
    async def start_twitter_oauth1():
        auth = OAuth1UserHandler(
            consumer_key=os.getenv("X_API_KEY"),
            consumer_secret=os.getenv("X_API_KEY_SECRET"),
            callback=REDIRECT_URI_TWITTER + "?flow=oauth1"
        )

        try:
            redirect_url = auth.get_authorization_url()
        except Exception as e:
            raise HTTPException(500, f"Twitter OAuth1 init failed: {e}")

        # store request token temporarily
        pending_auth[auth.request_token["oauth_token"]] = auth.request_token

        return RedirectResponse(redirect_url)

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

    @app.get("/auth/twitter/start")
    async def start_twitter():
        client_id, _ = get_client_creds("twitter")
        code_verifier_bytes = secrets.token_bytes(32)
        code_verifier = base64.urlsafe_b64encode(code_verifier_bytes).decode("utf-8").rstrip("=")
        code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("utf-8")).digest()).decode("utf-8").rstrip("=")

        state = str(uuid.uuid4())

        scopes = "tweet.read tweet.write users.read offline.access"
        scope_str = scopes.replace(" ", "%20")

        authorize_url = (
            f"https://x.com/i/oauth2/authorize"
            f"?response_type=code"
            f"&client_id={client_id}"
            f"&redirect_uri={REDIRECT_URI_TWITTER}"
            f"&scope={scope_str}"
            f"&state={state}"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
        )

        async with auth_lock:
            pending_auth[state] = code_verifier

        return RedirectResponse(authorize_url)

    @app.get("/auth/facebook/callback")
    async def cb_fb(req: Request, db: AsyncSession = Depends(get_db)):
        return await handle_callback(req, db, "facebook", REDIRECT_URI_FB)

    @app.get("/auth/instagram/callback")
    async def cb_ig(req: Request, db: AsyncSession = Depends(get_db)):
        return await handle_callback(req, db, "instagram", REDIRECT_URI_IG)

    @app.get("/auth/threads/callback")
    async def cb_threads(req: Request, db: AsyncSession = Depends(get_db)):
        return await handle_callback(req, db, "threads", REDIRECT_URI_THREADS)


    @app.get("/auth/twitter/callback")
    async def cb_twitter(req: Request, db: AsyncSession = Depends(get_db)):
        flow = req.query_params.get("flow")

        if flow == "oauth1":
            oauth_token = req.query_params.get("oauth_token")
            oauth_verifier = req.query_params.get("oauth_verifier")

            if not oauth_token or not oauth_verifier:
                raise HTTPException(400, "Missing OAuth1 parameters")

            request_token = pending_auth.pop(oauth_token, None)
            if not request_token:
                raise HTTPException(400, "Invalid or expired OAuth1 token")

            auth = OAuth1UserHandler(
                consumer_key=os.getenv("X_API_KEY"),
                consumer_secret=os.getenv("X_API_KEY_SECRET")
            )
            auth.request_token = request_token

            try:
                access_token, access_token_secret = auth.get_access_token(oauth_verifier)
            except Exception as e:
                raise HTTPException(500, f"OAuth1 token exchange failed: {e}")

            # Fetch username
            api = API(auth)
            me = api.verify_credentials()

            conn = Platform(
                api_name="twitter",
                account_id=str(me.id),
                account_name=me.screen_name,
                access_token=access_token,  
                expires_at=None,             
                meta={
                    "ACCESS_TOKEN_SECRET": access_token_secret,
                    "PROFILE_PHOTO_URL": me.profile_image_url_https.replace("_normal", "")
                }
            )

            db.add(conn)
            await db.commit()
            return RedirectResponse("/", status_code=303)

        return await handle_callback(req, db, "twitter", REDIRECT_URI_TWITTER)


    @app.get("/auth/linkedin/start")
    async def start_linkedin():
        return RedirectResponse(
            build_authorize_url(
                "linkedin",
                REDIRECT_URI_LINKEDIN,
                "openid profile email w_member_social", 
            )
        )

    @app.get("/auth/linkedin/callback")
    async def cb_linkedin(req: Request, db: AsyncSession = Depends(get_db)):
        return await handle_callback(req, db, "linkedin", REDIRECT_URI_LINKEDIN)

    
    @app.get("/", response_class=HTMLResponse)
    async def social_dashboard(request: Request, db: AsyncSession = Depends(get_db), _=Depends(Accounts.get_current_user)):
        result = await db.execute(select(Platform).where(Platform.is_active == True))
        connected_platforms_db = result.scalars().all()
        
        # 2. Map for lookup
        connected_map = {p.api_name: p for p in connected_platforms_db}

        nav_items = []
        first_connected_id = None
        first_connected_db_id = None

        for sp in SUPPORTED_PLATFORMS:
            db_obj = connected_map.get(sp["id"])
            
            item = {
                "id": sp["id"],
                "name": sp["name"],
                "svg": sp["svg"],
                "is_connected": False,
                "action_url": sp["auth_url"],
                "profile_url": None
            }

            if db_obj:
                item["is_connected"] = True
                item["action_url"] = "#" # Handled by JS
                item["db_id"] = db_obj.platform_id
                
                # Profile logic
                meta_data = db_obj.meta if db_obj.meta else {}
                if isinstance(meta_data, str):
                    try: meta_data = json.loads(meta_data)
                    except: meta_data = {}
                item["profile_url"] = meta_data.get("PROFILE_PHOTO_URL")
                if not first_connected_id:
                    first_connected_id = sp["id"]
                    first_connected_db_id = db_obj.platform_id

            nav_items.append(item)

        return templates.TemplateResponse("social_dashboard.html", {
            "request": request,
            "nav_items": nav_items,
            # We pass the ID of the *supported platform* list to find the button
            "default_platform_pill_id": first_connected_id, 
            # We pass the actual DB ID to fetch data
            "default_platform_db_id": first_connected_db_id
        })

    @app.get("/api/platform/{platform_id}/tasks", response_class=JSONResponse)
    async def get_platform_tasks(platform_id: str, db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(Platform).where(Platform.platform_id == platform_id))
        platform = result.scalar_one_or_none()
        
        if not platform:
            raise HTTPException(status_code=404, detail="Platform not found")

        stmt = (
            select(Task)
            .join(PlatformSelection, Task.task_id == PlatformSelection.task_id)
            .where(PlatformSelection.platform_id == platform.platform_id)
            .options(
                selectinload(Task.generated_contents),
                selectinload(Task.media)
            )
            .order_by(Task.created_at.desc())
        )
        
        tasks_result = await db.execute(stmt)
        tasks = tasks_result.scalars().all()

        data = []
        posted_count = 0
        scheduled_count = 0

        for t in tasks:
            content = t.generated_contents[0] if t.generated_contents else None
            media_item = t.media[0] if t.media else None
            
            if t.status.value == 'posted':
                posted_count += 1
            elif t.status.value == 'scheduled':
                scheduled_count += 1
            
            data.append({
                "task_id": t.task_id,
                "title": t.title or "Untitled Post",
                "status": t.status.value,
                "created_at": t.created_at.strftime("%b %d, %I:%M %p") if t.created_at else "",
                "caption": content.caption if content else None,
                "image_url": media_item.img_url if media_item else None
            })

        stats = {
            "scheduled_count": scheduled_count,
            "total_posted": posted_count
        }

        return {
            "platform_name": platform.api_name,
            "account_name": platform.account_name,
            "stats": stats,
            "tasks": data
        }



    @app.get("/api/scheduled_posts", response_model=dict)
    def get_scheduled_posts(
        db: Session = Depends(get_sync_db),
        statuses: Optional[List[str]] = Query(None, description="Filter by post statuses (e.g., scheduled, queued)"),
        channels: Optional[List[str]] = Query(None, description="Filter by channels (e.g., instagram, facebook)"),
        page: int = Query(1, ge=1, description="Page number"),
        limit: int = Query(10, ge=1, le=100, description="Items per page")
    ):

        query = select(Task).where(Task.status != TaskStatus.draft)  # Exclude drafts, focus on scheduled/posted/etc.

        if statuses:
            query = query.where(Task.status.in_([TaskStatus[s] for s in statuses if s in TaskStatus.__members__]))

        if channels:
            query = query.join(PlatformSelection).join(Platform).where(Platform.api_name.in_(channels)).distinct()
        total = db.execute(select(func.count()).select_from(query.subquery())).scalar()
        query = query.order_by(Task.scheduled_at.desc()).offset((page - 1) * limit).limit(limit)
        tasks = db.scalars(query).all()

        posts = []
        for task in tasks:
            platforms = db.scalars(
                select(Platform.api_name)
                .join(PlatformSelection)
                .where(PlatformSelection.task_id == task.task_id)
            ).all()
            content = db.scalars(
                select(GeneratedContent)
                .where(GeneratedContent.task_id == task.task_id)
                .limit(1)
            ).first()
            cont_gn = (content.caption[:500] + "..." if content and content.caption else "Untitled Post")
            head_gn = (content.prompt[:100] + "..." if content and content.caption else "New Post")

            media = db.scalars(
                select(Media)
                .where(Media.task_id == task.task_id)
                .limit(1)
            ).first()
            preview = media.storage_path if media else None

            posts.append({
                "id": task.task_id,
                "heading": head_gn,
                "content": cont_gn,
                "post_date": task.scheduled_at.isoformat() if task.scheduled_at else None,
                "status": task.status.value,
                "platforms": platforms,
                "preview": preview
            })

        return {
            "posts": posts,
            "total": total,
            "page": page,
            "limit": limit
        }