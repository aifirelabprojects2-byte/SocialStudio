import io
import json
import os
import uuid
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import Body, FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from PIL import ImageFont, Image, ImageDraw
from rembg import remove
from fastapi.responses import JSONResponse
from google import genai
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
FONTS_DIR = BASE_DIR / "Fonts" 

class Layer(BaseModel):
    type: str   
    shape_type: Optional[str] = None
    source: Optional[str] = "" 
    x: float    
    y: float    
    width: float
    height: float
    angle: float = 0.0
    opacity: float = 1.0
    
    # Text/Shape Specifics
    color: Optional[str] = None
    font_family: Optional[str] = None
    font_size: Optional[float] = None
    font_weight: Optional[str] = None
    font_style: Optional[str] = None
    underline: bool = False
    linethrough: bool = False
    
    line_height: Optional[float] = None
    char_spacing: Optional[float] = None
    
    border_color: Optional[str] = None
    border_width: Optional[int] = None
    background_color: Optional[str] = None
    shadow_color: Optional[str] = None
    shadow_blur: Optional[int] = None

class RenderReq(BaseModel):
    layers: List[Layer]
    background: str
    width: int = 1080
    height: int = 1080


FONT_FILES = {
    "Arial": {
        "regular": "ARIAL.TTF",
        "bold": "ARIALBD.TTF",
        "italic": "ARIALI.TTF",
        "bold_italic": "ARIALBI.TTF",
    },
    "Times New Roman": {
        "regular": "TIMES.TTF",
        "bold": "TIMESBD.TTF",
        "italic": "TIMESI.TTF",
        "bold_italic": "TIMESBI.TTF",
    },
    "Courier New": {
        "regular": "COUR.TTF",
        "bold": "COURBD.TTF",
        "italic": "COURI.TTF",
        "bold_italic": "COURBI.TTF",
    },
    "Verdana": {
        "regular": "VERDANA.TTF",
        "bold": "VERDANAB.TTF",
        "italic": "VERDANAI.TTF",
        "bold_italic": "VERDANAZ.TTF",
    },
    "Calibri": {
        "regular": "CALIBRI.TTF",
        "bold": "CALIBRIB.TTF",
        "italic": "CALIBRII.TTF",
        "bold_italic": "CALIBRIZ.TTF",
    },
}


def get_font_path(font_name: str, weight: str = "normal", style: str = "normal") -> Optional[str]:
    if not font_name:
        return None
        
    # 1. Normalize Inputs
    is_bold = False
    if weight:
        w_str = str(weight).lower()
        if "bold" in w_str or (w_str.isdigit() and int(w_str) >= 600):
            is_bold = True
            
    is_italic = "italic" in str(style).lower()

    # 2. Find Family Key
    family_key = font_name
    if font_name not in FONT_FILES:
        # Try to find partial match or default
        family_key = "Arial" 
        
    font_group = FONT_FILES.get(family_key, FONT_FILES["Arial"])
    
    # 3. Select Variant
    if is_bold and is_italic:
        filename = font_group.get("bold_italic", font_group.get("bold"))
    elif is_bold:
        filename = font_group.get("bold", font_group.get("regular"))
    elif is_italic:
        filename = font_group.get("italic", font_group.get("regular"))
    else:
        filename = font_group.get("regular")

    # 4. Resolve Path
    local_font_path = FONTS_DIR / filename
    
    # If specific variant missing, fallback to regular in the same group, then generic
    if not local_font_path.exists():
        fallback = font_group.get("regular", "arial.ttf")
        local_font_path = FONTS_DIR / fallback
        
    if local_font_path.exists():
        return local_font_path.as_posix()
        
    return None

def create_shape_image(layer: Layer) -> str:
    w, h = int(layer.width), int(layer.height)
    w = max(1, w)
    h = max(1, h)
    
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = layer.color or "#000000"

    shape = layer.shape_type

    if shape == 'rect':
        draw.rectangle([0, 0, w, h], fill=color)
    
    elif shape == 'circle':
        draw.ellipse([0, 0, w, h], fill=color)
        
    elif shape == 'triangle':
        points = [(w/2, 0), (0, h), (w, h)]
        draw.polygon(points, fill=color)

    elif shape == 'star':
        cx, cy = w/2, h/2
        rx, ry = w/2, h/2
        points = []
        import math
        for i in range(10):
            angle = i * 36 * math.pi / 180 - math.pi / 2
            r = rx if i % 2 == 0 else rx * 0.4
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        draw.polygon(points, fill=color)

    elif shape == 'heart':
        draw.polygon([
            (w/2, h*0.25), (w, 0), (w, h*0.5), (w/2, h), (0, h*0.5), (0, 0)
        ], fill=color)

    else: 
         draw.rectangle([0, 0, w, h], fill=color)

    filename = f"shape_{uuid.uuid4()}.png"
    path = UPLOAD_DIR / filename
    img.save(path)
    return filename

def process_frame_image(layer: Layer) -> str:
    # 1. FIX: Check if source is empty
    if not layer.source or layer.source.strip() == "":
        print("Frame skipped: No source image ID found.")
        return "" 

    src_path = UPLOAD_DIR / layer.source

    # 2. FIX: Check if path is a directory (Prevents PermissionError)
    if not src_path.exists() or src_path.is_dir():
        print(f"Frame skipped: Source '{src_path}' is not a valid file.")
        return layer.source 
    
    try:
        # 3. Open and convert to RGBA (handles existing transparency)
        img = Image.open(src_path).convert("RGBA")
        w, h = img.size
        
        # 4. Create a blank grayscale mask (Black = Transparent)
        mask = Image.new('L', (w, h), 0)
        draw = ImageDraw.Draw(mask)
        
        # 5. Draw the shape in White (Opaque) on the mask
        if layer.shape_type == 'circle':
            draw.ellipse((0, 0, w, h), fill=255)
            
        elif layer.shape_type == 'diamond':
            # Diamond coordinates: Top, Right, Bottom, Left
            points = [(w/2, 0), (w, h/2), (w/2, h), (0, h/2)]
            draw.polygon(points, fill=255)
            
        else:
            # Default to full rectangle
            draw.rectangle((0, 0, w, h), fill=255)
            
        # 6. Apply the mask to the image's alpha channel
        img.putalpha(mask)
        
        # 7. Save as temporary PNG
        new_filename = f"frame_render_{uuid.uuid4()}.png"
        img.save(UPLOAD_DIR / new_filename, format="PNG")
        
        return new_filename
        
    except Exception as e:
        print(f"Frame processing error: {e}")
        return layer.source # Fallback to unmasked image on error



def measure_text_size(text: str, font_path: Optional[str], font_size: int, line_height: Optional[float]):
    try:
        if font_path and Path(font_path).exists():
            font = ImageFont.truetype(font_path, max(6, int(font_size)))
        else:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    lines = text.split("\n")

    widths = []
    heights = []

    for line in lines:
        if not line:
            line = " "  # avoid zero-width bbox
        bbox = font.getbbox(line)  # (x0, y0, x1, y1)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        widths.append(w)
        heights.append(h)

    text_w = int(max(widths)) if widths else 0
    text_h = int(sum(heights)) if heights else int(font_size)

    # Apply line-height multiplier
    if line_height and line_height > 0:
        text_h = int(text_h * line_height)

    return text_w, text_h


def init(app):
    @app.post("/render")
    def render_video(data: RenderReq):
        out_path = OUTPUT_DIR / f"{uuid.uuid4()}.mp4"
        
        bg_color = data.background if data.background.startswith('#') else 'black'
        cmd_inputs = ["-f", "lavfi", "-i", f"color=c={bg_color}:s={data.width}x{data.height}"]
        
        filter_chain = []
        processed_layers = []
        
        # Add Video/Images
        for l in data.layers:
            if l.type == 'frame': 
                # NEW: Handle Frame
                # Convert the rectangular image into a shaped transparent PNG
                new_source = process_frame_image(l)
                l.source = new_source
                l.type = 'image' # Now treated as a standard image by FFmpeg
                processed_layers.append(l)

            elif l.type == 'shape':
                # Existing Shape Logic
                temp_filename = create_shape_image(l)
                l.source = temp_filename
                processed_layers.append(l)

            elif l.type in ['video', 'image']:
                processed_layers.append(l)

        # Text is separate
        text_layers = [l for l in data.layers if l.type == 'text']

        # 2. Add Media Inputs
        valid_media_inputs = [] 
        current_input_idx = 1
        
        for layer in processed_layers:
            if not layer.source: continue
            
            p = UPLOAD_DIR / layer.source
            if not p.exists(): continue
                
            cmd_inputs.extend(["-i", str(p)])
            valid_media_inputs.append((layer, current_input_idx))
            current_input_idx += 1

        has_video = any(l.type == 'video' for l, idx in valid_media_inputs)

        # 3. Build Filter Chain (Standard Overlay Logic)
        last_label = "0:v"
        duration_capped = False

        for i, (layer, input_idx) in enumerate(valid_media_inputs):
            scale_lbl = f"s{i}"
            rot_lbl = f"r{i}"
            opac_lbl = f"o{i}"
            overlay_lbl = f"v{i}"
            
            # Scale
            w = int(layer.width // 2 * 2)
            h = int(layer.height // 2 * 2)
            filter_chain.append(f"[{input_idx}:v]scale={w}:{h}[{scale_lbl}]")
            
            # Rotate
            angle_rad = layer.angle * 3.14159 / 180
            filter_chain.append(
                f"[{scale_lbl}]rotate={angle_rad}:c=none:ow=rotw(iw):oh=roth(ih)[{rot_lbl}]"
            )
            
            # Opacity
            filter_chain.append(
                f"[{rot_lbl}]format=rgba,colorchannelmixer=aa={layer.opacity}[{opac_lbl}]"
            )
            
            # Overlay
            x_expr = f"{layer.x}-(w/2)"
            y_expr = f"{layer.y}-(h/2)"
            overlay_opts = f"x={x_expr}:y={y_expr}"
            
            if layer.type == 'video' and not duration_capped:
                overlay_opts += ":shortest=1"
                duration_capped = True
                
            filter_chain.append(f"[{last_label}][{opac_lbl}]overlay={overlay_opts}[{overlay_lbl}]")
            last_label = overlay_lbl


        if text_layers:
            txt_filters = []
            for t in text_layers:
                font_path = get_font_path(t.font_family, t.font_weight, t.font_style)

                if font_path:
                    font_path_esc = font_path.replace("\\", "/").replace(":", "\\:")
                    font_arg = f"fontfile='{font_path_esc}'"
                else:
                    font_arg = "font=Sans"

                content = t.source.replace("'", "").replace(":", "\\:") if t.source else ""
                
                fontcolor = t.color or "#ffffff"
                fontcolor_arg = f"fontcolor={fontcolor}"

                # Drawtext construction
                dt_parts = [
                    f"text='{content}'",
                    f"x={t.x}-text_w/2",
                    f"y={t.y}-text_h/2",
                    f"fontsize={int(t.font_size or 40)}",
                    fontcolor_arg,
                    font_arg
                ]

                if t.line_height:
                    spacing_px = max(0, int((t.line_height - 1.0) * (t.font_size or 40)))
                    dt_parts.append(f"line_spacing={spacing_px}")

                if t.background_color:
                    dt_parts.append(f"box=1:boxcolor={t.background_color}@0.5:boxborderw=10")

                if t.border_width and t.border_width > 0:
                    dt_parts.append(f"borderw={int(t.border_width)}")
                    if t.border_color:
                        dt_parts.append(f"bordercolor={t.border_color}")

                if t.shadow_color:
                    dt_parts.append(f"shadowx=5:shadowy=5")
                    dt_parts.append(f"shadowcolor={t.shadow_color}")

                txt_filters.append(f"drawtext={':'.join(dt_parts)}")
                
                # Simple Underline/Strikethrough rendering (unchanged)
                text_w_px = int(t.width) # Approximate
                text_h_px = int(t.font_size or 40)
                thickness = max(1, int(text_h_px * 0.05))
                line_color = t.border_color or (t.color or "#000000")

                if t.linethrough:
                    txt_filters.append(f"drawbox=x={int(t.x-text_w_px/2)}:y={int(t.y)}:w={text_w_px}:h={thickness}:color={line_color}:t=fill")
                if t.underline:
                    txt_filters.append(f"drawbox=x={int(t.x-text_w_px/2)}:y={int(t.y+text_h_px/2)}:w={text_w_px}:h={thickness}:color={line_color}:t=fill")

            if txt_filters:
                full_txt_filter = ",".join(txt_filters)
                filter_chain.append(f"[{last_label}]{full_txt_filter}[final_out]")
                last_label = "final_out"

        if not filter_chain:
            filter_chain.append(f"[0:v]null[final_out]")
            last_label = "final_out"

        # 5. Execute FFmpeg
        cmd = ["ffmpeg", "-y"]
        if not has_video:
            cmd.extend(["-t", "5"])
            
        cmd.extend(cmd_inputs)
        cmd.extend(["-filter_complex", ";".join(filter_chain)])
        cmd.extend(["-map", f"[{last_label}]"])
        
        first_vid_idx = -1
        for layer, idx in valid_media_inputs:
            if layer.type == 'video':
                first_vid_idx = idx
                break
                
        if first_vid_idx > 0:
            cmd.extend(["-map", f"{first_vid_idx}:a?"])
            cmd.extend(["-c:a", "aac"])
            
        cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)])
        
        print(f"Running FFmpeg render...")
        try:
            subprocess.run(cmd, check=True, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode()
            print("FFmpeg Error:", error_msg)
            raise HTTPException(status_code=500, detail=f"Rendering failed: {error_msg}")

        return FileResponse(out_path, media_type="video/mp4")

    @app.post("/canva/upload")
    async def upload(file: UploadFile = File(...)):
        # Simple extension detection
        ct = file.content_type or ""
        if "video" in ct:
            ext = ".mp4"
        elif "image" in ct:
            ext = ".png"
        else:
            ext = ".dat"
        
        file_id = f"{uuid.uuid4()}{ext}"
        path = UPLOAD_DIR / file_id
        with open(path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        return {"file_id": file_id, "type": "video" if ext == ".mp4" else "image"}