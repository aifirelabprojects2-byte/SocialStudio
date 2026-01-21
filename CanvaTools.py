import io
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional, List
from fastapi import Body, Depends, FastAPI, UploadFile, File, HTTPException,Form
from pydantic import BaseModel, Field
from PIL import ImageFont, Image
from rembg import remove,new_session
from fastapi.responses import JSONResponse
from google import genai
from google.genai import types
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import  Session
from sqlalchemy.ext.asyncio import AsyncSession 


# Use "u2netp" (portable) instead of "u2net" for 4GB VMs—it's much lighter.
SESSION = new_session("u2netp")

STYLE_PRESETS = {
    "Bold": "Make a bold, high-contrast YouTube-style thumbnail. Use vibrant, saturated colors, big readable text area, dramatic lighting and deep shadows. Prioritize legibility at small sizes and place the subject in the foreground with strong rim light.",
    "Dark": "Dark cinematic thumbnail with moody tones. Emphasize dramatic low-key lighting, deep blacks, and a desaturated color palette. Use light falloff to highlight the subject's face and expression.",
    "Minimal": "Minimalistic, clean thumbnail with lots of negative space. Use a simple background, one bold subject, and limited text. Favor geometric composition and subtle drop shadows for depth.",
    "Pop Art": "Pop-art inspired thumbnail with halftone textures, vivid complementary colors, and bold outlines. Add stylized speech-bubble text and exaggerated facial expressions for a playful, retro feel.",
    "Neon": "Neon glow aesthetic — vivid electric colors on a dark background, soft glows and reflections. Use neon rim light on the subject and stylized typography with glow effects.",
    "Vintage": "Vintage film look: warm film grain, subtle vignetting, faded colors and soft contrast. Add chromatic aberration and film scratches sparingly for authenticity.",
    "Tech": "High-tech, UI-inspired thumbnail. Use glassmorphism, grid overlays, neon accents, and thin futuristic fonts. Place the subject slightly off-center with data/graphic overlays.",
    "Cartoon": "Cartoon/comic-book style with bold outlines, simplified shapes and flat shading. Use expressive poses and amplified facial features for readability at thumbnail sizes.",
    "Retro": "Retro 80s/90s aesthetic with saturated gradients, 'analog' textures, large blocky type and chrome accents. Use bold color blocks and simple geometric backgrounds.",
    "Clean": "Clean, modern thumbnail: neutral background, soft shadows, balanced composition, and sans-serif typography. Prioritize clarity and a polished, professional look.",
    "MrBeast": "Create a viral YouTube thumbnail inspired by high-performing creators. One subject only, extreme facial expression, face close-up, dramatic lighting, bright background, high contrast, big bold text area, and exaggerated reaction cues.",
    "None": "" 
}

THUMBNAIL_RATIOS = {
    "YouTube": "16:9",
    "Instagram": "1:1",
    "TikTok": "9:16",
    "Facebook": "1.91:1",
    "Pinterest": "2:3",
}

STYLE_PRESETS = {
    "None": "",
    "Cinematic": "A cinematic film still, dramatic lighting, high detail, 4k: ",
    "Anime": "Anime style illustration, vibrant colors, studio ghibli vibes: ",
    "Pixel Art": "Pixel art style, 8-bit retro game graphics: ",
    "Cyberpunk": "Cyberpunk sci-fi style, neon lights, futuristic, rain: ",
    "Watercolor": "A soft watercolor painting, textured paper, gentle strokes: "
}

from Database import TemplateDB, get_db

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI()


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static/uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
class TemplateSchema(BaseModel):
    name: str
    type: str
    category: str
    style: str
    width: int
    height: int
    json_data: str

    @classmethod
    def as_form(
        cls,
        name: str = Form(...),
        type: str = Form(...),
        category: str = Form(...),
        style: str = Form(...),
        width: int = Form(...),
        height: int = Form(...),
        json_data: str = Form(...)
    ):
        return cls(
            name=name,
            type=type,
            category=category,
            style=style,
            width=width,
            height=height,
            json_data=json_data
        )
def init(app):
    
    @app.post("/save-template")
    async def save_template(
        name: str = Form(...),
        type: str = Form(...),
        category: str = Form(...),
        style: str = Form(...),
        width: int = Form(...),
        height: int = Form(...),
        json_data: str = Form(...),
        preview: UploadFile = File(...),
        db: AsyncSession = Depends(get_db) # Updated to AsyncSession
    ):
        # 1. Save Preview Image
        preview_filename = f"tpl_preview_{uuid.uuid4()}.png"
        preview_path = os.path.join(UPLOAD_DIR, preview_filename)
        
        # Using await read() is cleaner in async contexts, though shutil works too
        with open(preview_path, "wb") as f:
            shutil.copyfileobj(preview.file, f)

        # 2. Save to DB
        new_template = TemplateDB(
            name=name,
            type=type,
            category=category,
            style=style,
            width=width,
            height=height,
            json_data=json_data,
            preview_url=preview_filename
        )
        
        db.add(new_template)
        await db.commit() # Must await commit
        await db.refresh(new_template) # Must await refresh
        
        return {"status": "success", "id": new_template.id}

    @app.get("/templates")
    async def get_templates( # Changed to async def
        type: Optional[str] = None, 
        category: Optional[str] = None, 
        style: Optional[str] = None,
        db: AsyncSession = Depends(get_db)
    ):
        # Async SQLAlchemy uses 'select', not 'db.query'
        stmt = select(TemplateDB)
        
        if type and type != "All":
            stmt = stmt.where(TemplateDB.type == type)
        if category and category != "All":
            stmt = stmt.where(TemplateDB.category == category)
        if style and style != "All":
            stmt = stmt.where(TemplateDB.style == style)
            
        result = await db.execute(stmt)
        templates = result.scalars().all() # Return pure ORM objects
        
        return templates

    @app.post("/remove-bg")
    async def remove_background(file: UploadFile = File(...)):
        try:
            contents = await file.read()
            input_img = Image.open(io.BytesIO(contents))

            # 2. Pass the pre-loaded SESSION here
            output_img = remove(
                input_img,
                session=SESSION,  # CRITICAL: Reuses the model already in RAM
                alpha_matting=True,
                alpha_matting_foreground_threshold=240,
                alpha_matting_background_threshold=10,
                alpha_matting_erode_size=10
            )

            filename = f"bg_removed_{uuid.uuid4()}.png"
            filepath = os.path.join(UPLOAD_DIR, filename)
            output_img.save(filepath, format="PNG")

            return JSONResponse({
                "status": "success",
                "file_id": filename, 
                "url": f"/uploads/{filename}" 
            })

        except Exception as e:
            # If it's a library error (like missing libglib), it will show up here
            print(f"CRITICAL ERROR: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        

    @app.post("/generate-image")
    async def generate_image_endpoint(
        prompt: str = Body(..., embed=True),
        model: str = Body(..., embed=True),
        style: str = Body("None", embed=True) 
    ):
        try:

            styled_prompt = STYLE_PRESETS.get(style, "") + prompt

            response = client.models.generate_content(
                model=model,
                contents=[styled_prompt],
            )

            generated_part = None
            for part in response.parts:
                if part.inline_data is not None:
                    generated_part = part
                    break

            if not generated_part:
                raise HTTPException(status_code=500, detail="No image data in response")

            filename = f"gen_ai_{uuid.uuid4()}.png"
            filepath = os.path.join(UPLOAD_DIR, filename)
            img = generated_part.as_image()
            img.save(filepath)

            return JSONResponse({
                "status": "success",
                "url": f"/uploads/{filename}",
                "file_id": filename
            })
        except Exception as e:
            print(f"GenAI Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))


    @app.post("/edit-image-ai")
    async def edit_image_ai_endpoint(
        file: UploadFile = File(...),
        prompt: str = Form(...),
        model: str = Form(...),
        style: str = Form("None")
    ):
        try:
            image_bytes = await file.read()
            input_image = Image.open(io.BytesIO(image_bytes))
            styled_prompt = STYLE_PRESETS.get(style, "") + prompt
            
            response = client.models.generate_content(
                model=model, 
                contents=[input_image, styled_prompt]
            )
            
            generated_part = None
            if response.parts:
                for part in response.parts:
                    if part.inline_data is not None:
                        generated_part = part
                        break
            
            if not generated_part:
                error_text = response.text if response.text else "Failed to generate image modification."
                raise HTTPException(status_code=400, detail=error_text)

            filename = f"ai_edit_{uuid.uuid4()}.png"
            filepath = os.path.join(UPLOAD_DIR, filename)

            out_img = generated_part.as_image()
            out_img.save(filepath)

            return JSONResponse({
                "status": "success",
                "url": f"/uploads/{filename}",
                "file_id": filename
            })

        except Exception as e:
            print(f"AI Edit Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    @app.post("/create-thumbnail")
    async def create_thumbnail(
        file: List[UploadFile] = File(...),
        prompt: str = Form(...),
        ratio: str = Form(...),
        style: str = Form(...),
        model: str = Form(...)
    ):
        try:
            # Load images
            pil_images = []
            for f in file:
                content = await f.read()
                # Basic validation to ensure we have data
                if len(content) > 0:
                    img = Image.open(io.BytesIO(content)).convert("RGBA")
                    pil_images.append(img)
            
            if not pil_images:
                raise HTTPException(status_code=400, detail="No valid image data received.")

            # Construct Prompt
            style_instruction = STYLE_PRESETS.get(style, "")
            full_prompt = f"{style_instruction} {prompt}".strip()
            
            aspect = THUMBNAIL_RATIOS.get(ratio, "16:9")

            # Prepare payload
            contents = []
            contents.extend(pil_images)
            contents.append(full_prompt)
            SYSTEM_PROMPT = """You are a professional graphic designer. 
                                Your goal is to create high-quality social media thumbnails. 
                                ALWAYS return an image response. Do not provide text descriptions 
                                unless specifically asked."""
            # Generate
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    image_config=types.ImageConfig(aspect_ratio=aspect)
                )
                
            )

            # Process Response
            out_filenames = []

            if response.parts:
                for part in response.parts:
                    if hasattr(part, "inline_data") and part.inline_data:
                        image_data = part.inline_data.data
                        out_img = Image.open(io.BytesIO(image_data))
                        
                        filename = f"thumb_{uuid.uuid4()}.png"
                        filepath = UPLOAD_DIR / filename
                        out_img.save(filepath)
                        out_filenames.append(filename)

                    elif hasattr(part, "executable_code"):
                        pass 
            if not out_filenames:
                try:
                    for part in response.parts:
                        img = part.as_image()
                        filename = f"thumb_{uuid.uuid4()}.png"
                        img.save(UPLOAD_DIR / filename)
                        out_filenames.append(filename)
                except:
                    pass 
            if not out_filenames:
                print(response) 
                raise HTTPException(status_code=500, detail="Model generated a response but no image was found.")

            return {"status": "success", "filenames": out_filenames}

        except Exception as e:
            print(f"Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))