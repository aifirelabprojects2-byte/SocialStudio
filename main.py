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
import ImageEditor
# import TaskScheduler
import SocialConnect
import ManagePlatform
import ErrorLogs
import Accounts  # Force reload 2025-12-30
import ScheduledTasks
import VideoTempBuilder
from pathlib import Path
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from Database import init_db
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")

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

templates = Jinja2Templates(directory="templates")

app.mount("/designs", StaticFiles(directory="designs"), name="designs")


LOGO_DB = [
    {"name": "FireLab Logo Light", "filename": "logo_dark.png"},
    {"name": "FireLab Logo Dark", "filename": "logo_light.png"}
]

@app.get("/api/logos")
async def get_logos():
    return LOGO_DB

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok"}

@app.on_event("startup")
async def startup():
    await init_db()

@app.exception_handler(HTTPException)
async def unauthorized_handler(request: Request, exc: HTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    raise exc

# @app.get("/", response_class=HTMLResponse)
# async def home(request: Request, _=Depends(Accounts.get_current_user)):
#     return templates.TemplateResponse("social_dashboard.html", {"request": request})

@app.get("/setting", response_class=HTMLResponse)
async def settings(request: Request, _=Depends(Accounts.get_current_user)):
    return templates.TemplateResponse("settings.html", {"request": request})

@app.get("/design", response_class=HTMLResponse)
async def settings(request: Request, _=Depends(Accounts.get_current_user)):
    return templates.TemplateResponse("designstudio.html", {"request": request})


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
VideoTempBuilder.init(app)
ImageEditor.init(app)
SocialConnect.init(app)
# TaskScheduler.init(app)
