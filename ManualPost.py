import hashlib
import subprocess
import requests
import json
from Configs import IMG_BB_API_KEY
import Accounts
from datetime import datetime
from typing import Optional
from pathlib import Path
from fastapi import Depends, Form, HTTPException, UploadFile, File
from Database import TaskStatus, gen_uuid_str, get_db, Task, GeneratedContent, Media
from sqlalchemy.ext.asyncio import AsyncSession
from werkzeug.utils import secure_filename
from PIL import Image

media_dir = Path("static/media")

def upload_to_catbox(file_path):
    url = "https://catbox.moe/user/api.php"
    try:
        with open(file_path, "rb") as f:
            files = {"fileToUpload": f}
            data = {"reqtype": "fileupload", "json": "1"}
            
            response = requests.post(url, files=files, data=data, timeout=60)
            
            if response.status_code == 200:
                result = response.text.strip()
                if "files.catbox.moe" in result:
                    return result
                else:
                    print(f"Catbox Error Response: {result}")
            else:
                print(f"Catbox HTTP Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Catbox Upload Exception: {e}")
    
    return None

def init(app):
    @app.post("/manual-tasks", response_model=dict)
    async def create_manual_task(
        title: str = Form(..., description="Task title"),
        caption: str = Form(..., description="Post caption"),
        hashtags: str = Form(..., description="Comma-separated hashtags"),
        notes: Optional[str] = Form(None, description="Optional notes for the task"),
        file: UploadFile = File(..., description="Image or Video file to upload"),
        db: AsyncSession = Depends(get_db),
        _=Depends(Accounts.get_current_user)
    ):
        if not file.content_type or not (file.content_type.startswith("image/") or file.content_type.startswith("video/")):
            raise HTTPException(status_code=400, detail="Uploaded file must be an image or video")
        filename = secure_filename(file.filename)
        if not filename or not Path(filename).suffix:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Default extension based on type if missing
            ext = ".jpg" if file.content_type.startswith("image/") else ".mp4"
            filename = f"manual_{timestamp}{ext}"
        allowed_img_ext = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        allowed_vid_ext = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
        file_ext = Path(filename).suffix.lower()

        if file.content_type.startswith("image/") and file_ext not in allowed_img_ext:
            raise HTTPException(status_code=400, detail="Unsupported image format")
        if file.content_type.startswith("video/") and file_ext not in allowed_vid_ext:
             raise HTTPException(status_code=400, detail="Unsupported video format")
        try:
            content = await file.read()
        except Exception as e:
            print(f"Failed to read file: {e}")
            raise HTTPException(status_code=400, detail="Failed to read file")

        size_bytes = len(content)
        checksum = hashlib.sha256(content).hexdigest()
        filepath = media_dir / filename
        try:
            with open(filepath, "wb") as f:
                f.write(content)
            storage_path = str(filename)
        except Exception as e:
            print(f"Failed to save media locally: {e}")
            raise HTTPException(status_code=500, detail="Failed to save media")
        width, height = None, None
        duration_ms = None
        imgbb_url = None 
        if file.content_type.startswith("image/"):
            try:
                with Image.open(filepath) as img:
                    width, height = img.size
            except Exception as e:
                print(f"Failed to extract image dimensions: {e}")

            if IMG_BB_API_KEY:
                try:
                    files = {"image": (filename, content, file.content_type)}
                    data = {"key": IMG_BB_API_KEY}
                    response = requests.post("https://api.imgbb.com/1/upload", data=data, files=files, timeout=30)
                    if response.status_code == 200:
                        res = response.json()
                        if res.get("success"):
                            imgbb_url = res["data"]["url"]
                            print(f"Successfully uploaded to ImgBB: {imgbb_url}")
                        else:
                            print(f"ImgBB upload failed: {res.get('error', 'Unknown error')}")
                    else:
                        print(f"ImgBB HTTP error: {response.status_code}")
                except Exception as e:
                    print(f"ImgBB upload exception: {e}")
            else:
                print("ImgBB API key not provided; skipping upload")

        elif file.content_type.startswith("video/"):
            try:
                cmd = [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width,height,duration",
                    "-of", "json", str(filepath)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    info = json.loads(result.stdout)
                    if "streams" in info and len(info["streams"]) > 0:
                        stream = info["streams"][0]
                        width = int(stream.get("width", 0)) or None
                        height = int(stream.get("height", 0)) or None
                        duration_sec = float(stream.get("duration", 0))
                        duration_ms = int(duration_sec * 1000) if duration_sec else None
            except Exception as e:
                print(f"Could not extract video metadata (ffmpeg might be missing): {e}")
            print("Uploading video to Catbox...")
            catbox_result = upload_to_catbox(filepath)
            
            if catbox_result:
                imgbb_url = catbox_result
                print(f"Successfully uploaded to Catbox: {imgbb_url}")
            else:
                print("Failed to upload video to Catbox.")

        hashtags_list = [h.strip() for h in hashtags.split(",") if h.strip()]

        task_id = gen_uuid_str()
        task = Task(
            task_id=task_id,
            title=title,
            status=TaskStatus.draft_approved,
            notes=notes
        )
        db.add(task)
        await db.flush()
        
        gen_id = gen_uuid_str()
        current_date = datetime.now().date()
        gen_content = GeneratedContent(
            gen_id=gen_id,
            task_id=task_id,
            prompt=f"Manual upload ({file.content_type}) on {current_date}",
            caption=caption,
            hashtags=hashtags_list,
            image_generated=False,
        )
        db.add(gen_content)
        await db.flush()
        
        media_id = gen_uuid_str()
        media = Media(
            media_id=media_id,
            task_id=task_id,
            gen_id=gen_id,
            storage_path=storage_path,
            mime_type=file.content_type,
            img_url=imgbb_url,      
            width=width,
            height=height,
            duration_ms=duration_ms, 
            checksum=checksum,
            size_bytes=size_bytes,
            is_generated=True,
        )
        db.add(media)
        
        try:
            await db.commit()
            print(f"Manual task created: task_id={task_id}, gen_id={gen_id}, media_id={media_id}")
        except Exception as e:
            await db.rollback()
            print(f"Database commit failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to save task to database")

        return {
            "task_id": task_id,
            "gen_id": gen_id,
            "media_id": media_id,
            "storage_path": storage_path,
            "img_url": imgbb_url,
            "message": "Manual task created successfully"
        }