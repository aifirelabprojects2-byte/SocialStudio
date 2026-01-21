import os
os.environ.pop("SSLKEYLOGFILE", None)

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import ManageTheme
import MediaSnag
import Referencer
import Researcher
import ManualPost
import TextFormatter
import UsageTracker
import PostGen
import TaskScheduler
import SocialConnect
import ManagePlatform
import ErrorLogs
import Accounts  # Force reload 2025-12-30
import ScheduledTasks
from pathlib import Path
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from Database import init_db
from fastapi.middleware.cors import CORSMiddleware
import CanvaTools, VideoRender ,DesignBuilder,CompanyFetch
app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

media_dir = Path("static/media")
media_dir.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory="static/media"), name="media")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/downloads", StaticFiles(directory="static/downloads"), name="downloads")
app.mount("/uploads", StaticFiles(directory="static/uploads"), name="uploads")
templates = Jinja2Templates(directory="templates")


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok"}

@app.on_event("startup")
async def startup():
    await init_db()

@app.exception_handler(HTTPException)
async def unauthorized_handler(request: Request, exc: HTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=401,
                content={"detail": exc.detail}
            )
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    raise exc

# @app.get("/", response_class=HTMLResponse)
# async def home(request: Request, _=Depends(Accounts.get_current_user)):
#     return templates.TemplateResponse("social_dashboard.html", {"request": request})

@app.get("/setting", response_class=HTMLResponse)
async def settings(request: Request, _=Depends(Accounts.get_current_user)):
    return templates.TemplateResponse("settings.html", {"request": request})

@app.get("/canvas", response_class=HTMLResponse)
async def settings(request: Request, _=Depends(Accounts.get_current_user)):
    return templates.TemplateResponse("designstudio.html", {"request": request})



CanvaTools.init(app)
VideoRender.init(app)
DesignBuilder.init(app)
PostGen.init(app)    
ManagePlatform.init(app)
ManageTheme.init(app)
UsageTracker.init(app)
Accounts.init(app)
Researcher.init(app)
Referencer.init(app)
MediaSnag.init(app)
TextFormatter.init(app)
ErrorLogs.init(app)
ManualPost.init(app)
ScheduledTasks.init(app)
SocialConnect.init(app)
TaskScheduler.init(app)
CompanyFetch.init(app)
