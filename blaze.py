import json
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from Database import get_db, Platform, Task, PlatformSelection

app = FastAPI()
templates = Jinja2Templates(directory="templates")

SUPPORTED_PLATFORMS = [
    {
        "id": "instagram", 
        "name": "Instagram", 
        "auth_url": "/auth/instagram/start",
        # SVG Path for Instagram logo
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



@app.get("/social-dashboard", response_class=HTMLResponse)
async def social_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    # 1. Fetch connected platforms
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
            
            # Identify first connection for default load
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
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)