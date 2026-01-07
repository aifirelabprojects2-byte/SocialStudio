
import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
import secrets
import hashlib
import base64
from asyncio import Lock
import httpx
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import Column, String, Text, DateTime, JSON, Boolean, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv

from Database import Platform, get_db, init_db
load_dotenv()

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Page Automation Connector")

GRAPH_VERSION = "v19.0"
REDIRECT_URI_FB = "https://716a167452c2.ngrok-free.app/auth/facebook/callback"
REDIRECT_URI_IG = "https://716a167452c2.ngrok-free.app/auth/instagram/callback"
REDIRECT_URI_THREADS = "https://716a167452c2.ngrok-free.app/auth/threads/callback"
REDIRECT_URI_TWITTER = "https://716a167452c2.ngrok-free.app/auth/twitter/callback"
REDIRECT_URI_LINKEDIN = "https://716a167452c2.ngrok-free.app/auth/linkedin/callback"


pending_auth: dict[str, str] = {}
auth_lock = Lock()


@app.on_event("startup")
async def startup():
    await init_db()




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

@app.get("/", response_class=HTMLResponse)
async def dashboard(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Platform))
    items = res.scalars().all()

    html = "<h1>Page Automation Connector</h1>"
    html += '<a href="/auth/instagram/start"><button>Instagram</button></a><br><br>'
    html += '<a href="/auth/facebook/start"><button>Facebook</button></a><br><br>'
    html += '<a href="/auth/threads/start"><button>Threads</button></a><br><br>'
    html += '<a href="/auth/twitter/start"><button>Twitter (X)</button></a><br><br>'
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
            access_token=access_token,  # OAuth1 access token
            expires_at=None,             # OAuth1 tokens do NOT expire
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

            pages = await client.get(
                f"https://graph.facebook.com/{GRAPH_VERSION}/me/accounts",
                params={"access_token": long_token["access_token"]},
            )
            pages.raise_for_status()

            page = pages.json()["data"][0]

            conn = Platform(
                api_name="facebook",
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
            token = await exchange_code(code, redirect_uri, platform)

            me = await client.get(
                "https://graph.threads.net/me",
                params={
                    "access_token": token["access_token"],
                    "fields": "id,username,threads_profile_picture_url",
                },
            )

            profile = me.json() if me.status_code == 200 else {}

            conn = Platform(
                api_name="threads",
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)