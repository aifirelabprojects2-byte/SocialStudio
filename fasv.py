from fastapi import FastAPI, File, UploadFile, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from moviepy import VideoFileClip, ImageClip, TextClip, ColorClip, CompositeVideoClip
import re
import os
import uuid
import asyncio
from pathlib import Path
from typing import Optional
import shutil
from datetime import datetime
from proglog import ProgressBarLogger

app = FastAPI(title="Video Creator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
FONTS_DIR = Path("Fonts") 

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
FONTS_DIR.mkdir(exist_ok=True) 

app.mount("/static", StaticFiles(directory="static"), name="static")

active_connections = {}

FONT_MAP = {
    "Arial": "ARIAL.TTF",
    "Arial Bold": "ARIALBD.TTF",
    "Calibri": "CALIBRI.TTF",
}

def get_font_path(font_name: str) -> Optional[str]:

    if not font_name:
        return None
        
    # 1. Check mapped names in Fonts folder
    filename = FONT_MAP.get(font_name, font_name) 
    if not filename.endswith(".ttf") and not filename.endswith(".otf"):
        potential_filename = f"{filename}.ttf"
    else:
        potential_filename = filename

    local_font_path = FONTS_DIR / potential_filename

    if local_font_path.exists():
        return str(local_font_path)

    return None

class WebSocketLogger(ProgressBarLogger):
    def __init__(self, ws_id, loop):
        super().__init__(init_state=None, bars=None, ignored_bars=None,
                 logged_bars='all', min_time_interval=0, ignore_bars_under=0)
        self.ws_id = ws_id
        self.loop = loop
    
    def callback(self, **changes):
        for (parameter, value) in changes.items():
            if parameter == 'message':
                self.send_to_ws({"type": "log", "message": value})

    def bars_callback(self, bar, attr, value, old_value=None):
        if bar in self.bars:
            total = self.bars[bar]['total']
            if total > 0:
                percentage = int((value / total) * 100)
                self.send_to_ws({
                    "type": "progress", 
                    "progress": percentage, 
                    "message": f"Processing: {percentage}%"
                })

    def send_to_ws(self, data):
        if self.ws_id in active_connections:
            websocket = active_connections[self.ws_id]
            asyncio.run_coroutine_threadsafe(websocket.send_json(data), self.loop)

class VideoCreator:
    COLORS = {
        'fireblue':'#60a5fa', 'blue': '#0000FF', 'lightblue': '#87CEEB',
        'skyblue': '#87CEEB', 'darkblue': '#00008B', 'navyblue': '#000080',
        'royalblue': '#4169E1', 'steelblue': '#4682B4', 'dodgerblue': '#1E90FF',
        'red': '#FF0000', 'lightred': '#FF6B6B', 'darkred': '#8B0000',
        'crimson': '#DC143C', 'tomato': '#FF6347', 'green': '#00FF00',
        'lightgreen': '#90EE90', 'darkgreen': '#006400', 'lime': '#00FF00',
        'forest': '#228B22', 'mint': '#98FF98', 'emerald': '#50C878',
        'yellow': '#FFFF00', 'lightyellow': '#FFFFE0', 'gold': '#FFD700',
        'orange': '#FFA500', 'darkorange': '#FF8C00', 'purple': '#800080',
        'lightpurple': '#DDA0DD', 'violet': '#EE82EE', 'magenta': '#FF00FF',
        'lavender': '#E6E6FA', 'pink': '#FFC0CB', 'lightpink': '#FFB6C1',
        'hotpink': '#FF69B4', 'deeppink': '#FF1493', 'white': '#FFFFFF',
        'black': '#000000', 'gray': '#808080', 'lightgray': '#D3D3D3',
        'darkgray': '#A9A9A9', 'cyan': '#00FFFF', 'turquoise': '#40E0D0',
        'brown': '#A52A2A', 'beige': '#F5F5DC', 'coral': '#FF7F50',
        'salmon': '#FA8072',
    }
    
    def __init__(self, input_video_path, output_path="output_video.mp4",
                 background_color=(0, 0, 0), width=1080, height=1920):
        self.input_video_path = input_video_path
        self.output_path = output_path
        self.background_color = background_color
        self.width = width
        self.height = height
        self.user_video = None
        self.duration = None
        self.font_path = self._get_default_font()
    
    def _get_default_font(self):
        local_default = Path("Fonts/Arial.ttf")
        if local_default.exists():
            return str(local_default)

        windows_fonts = [
            "C:/Windows/Fonts/Arial.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/times.ttf",
        ]
        for font_path in windows_fonts:
            if os.path.exists(font_path):
                return font_path
        return None
    
    def _calculate_brightness(self, rgb_color):
        r, g, b = rgb_color
        return 0.299 * r + 0.587 * g + 0.114 * b
    
    def _choose_logo_path(self, logo_dark_path="logo_dark.png", logo_light_path="logo_light.png"):
        brightness = self._calculate_brightness(self.background_color)
        threshold = 128
        
        if brightness < threshold:
            chosen_logo = logo_dark_path
        else:
            chosen_logo = logo_light_path
        
        if os.path.exists(chosen_logo):
            return chosen_logo
        else:
            alternate = logo_light_path if chosen_logo == logo_dark_path else logo_dark_path
            if os.path.exists(alternate):
                return alternate
            return None
    
    def load_video_fullwidth(self, top_margin=200, video_max_height=None):
        self.user_video = VideoFileClip(self.input_video_path)
        self.duration = self.user_video.duration
        
        self.user_video = self.user_video.resized(width=self.width)
        
        if video_max_height and self.user_video.h > video_max_height:
            self.user_video = self.user_video.resized(height=video_max_height)
            
            if self.user_video.w > self.width:
                x_center = self.user_video.w / 2
                self.user_video = self.user_video.cropped(
                    x_center=x_center,
                    width=self.width
                )
            elif self.user_video.w < self.width:
                self.user_video = self.user_video.resized(width=self.width)
        
        x_pos = 0
        y_pos = top_margin
        self.user_video = self.user_video.with_position((x_pos, y_pos))
        
        return self.user_video.h
    
    def create_background(self):
        background = ColorClip(size=(self.width, self.height), color=self.background_color)
        return background.with_duration(self.duration)
    
    def add_logo(self, logo_path, logo_height=100, position=("center", 40)):
        try:
            logo = ImageClip(logo_path)
            if logo.h > logo_height:
                logo = logo.resized(height=logo_height)
            max_width = self.width - 80
            if logo.w > max_width:
                logo = logo.resized(width=max_width)
            logo = logo.with_duration(self.duration)
            logo = logo.with_position(position)
            return logo
        except Exception as e:
            return None
    
    def _resolve_color(self, color_name):
        if color_name.lower() in self.COLORS:
            return self.COLORS[color_name.lower()]
        return color_name
    
    def parse_colored_text(self, text):
        pattern = r'<(\w+)>(.*?)</\1>|([^<]+)'
        segments = []
        for match in re.finditer(pattern, text):
            if match.group(1):
                color = match.group(1)
                text_content = match.group(2)
                segments.append((text_content, color))
            elif match.group(3):
                segments.append((match.group(3), None))
        return segments
    
    def _wrap_text_segments(self, segments, max_width, font_size, font, stroke_width=0):
        lines = []
        current_line = []
        current_width = 0

        stroke_adjustment = stroke_width * 2
        
        for text_content, color in segments:
            parts = text_content.split('\n')
            
            for part_idx, part in enumerate(parts):
                words = part.split(' ')
                
                for i, word in enumerate(words):
                    if not word:
                        continue
                    
                    test_word = word if not current_line or current_width == 0 else ' ' + word
                    temp_clip = TextClip(
                        text=test_word,
                        font_size=font_size,
                        color='white',
                        font=font,
                        method='label'
                    )
                    word_width = temp_clip.w + stroke_adjustment  # Add stroke adjustment
                    temp_clip.close()
                    
                    if current_width + word_width <= max_width:
                        current_line.append((test_word, color))
                        current_width += word_width
                    else:
                        if current_line:
                            lines.append(current_line)
                            current_line = []
                            current_width = 0
                        
                        current_line.append((word, color))
                        temp_clip = TextClip(text=word, font_size=font_size, color='white', font=font, method='label')
                        current_width = temp_clip.w + stroke_adjustment  # Add stroke adjustment
                        temp_clip.close()
                
                if part_idx < len(parts) - 1:
                    if current_line:
                        lines.append(current_line)
                    current_line = []
                    current_width = 0
        
        if current_line:
            lines.append(current_line)
        
        return lines

    def create_multicolor_text(self, text, font_size=60, default_color='white', position=("center", 500), 
                        font=None, stroke_color='black', stroke_width=2):
        segments = self.parse_colored_text(text)
        font_to_use = font if font else self.font_path
        default_color = self._resolve_color(default_color)

        safe_margin = 100  
        max_text_width = self.width - (safe_margin * 2)
        
        if len(segments) == 1 and segments[0][1] is None:
            caption = TextClip(
                text=text,
                font_size=font_size,
                color=default_color,
                font=font_to_use,
                stroke_color=stroke_color if stroke_width > 0 else None,
                stroke_width=stroke_width,
                method='caption',
                size=(max_text_width, None)
            )
            caption = caption.with_position(("center", position[1]))
            caption = caption.with_duration(self.duration)
            return [caption]
        
        lines = self._wrap_text_segments(segments, max_text_width, font_size, font_to_use, stroke_width)
        text_clips = []
        y_start = position[1] if isinstance(position[1], int) else 500
        line_spacing = int(font_size * 1.3)
        
        for line_idx, line_segments in enumerate(lines):
            line_clips = []
            
            for text_content, color in line_segments:
                clip_color = self._resolve_color(color) if color else default_color
                
                clip = TextClip(
                    text=text_content,
                    font_size=font_size,
                    color=clip_color,
                    font=font_to_use,
                    stroke_color=stroke_color if stroke_width > 0 else None,
                    stroke_width=stroke_width,
                    method='label'
                )
                line_clips.append(clip)
            
            line_width = sum(clip.w for clip in line_clips)

            start_x = (self.width - line_width) // 2
            
            y_pos = y_start + (line_idx * line_spacing)
            
            current_x = start_x
            for clip in line_clips:
                positioned_clip = clip.with_position((current_x, y_pos))
                positioned_clip = positioned_clip.with_duration(self.duration)
                text_clips.append(positioned_clip)
                current_x += clip.w
                                
        return text_clips
    
    def create_video(self, caption_heading="", caption_heading_font_size=80,
                 caption_heading_color='white', caption_heading_stroke_color='black',
                 caption_heading_stroke_width=3, caption_text="Your Caption Here",
                 caption_text_font_size=55, caption_text_color='white',
                 caption_text_stroke_color='black', caption_text_stroke_width=2,
                 logo_dark_path="logo_dark.png", logo_light_path="logo_light.png",
                 auto_select_logo=True, logo_path=None, logo_height=100,
                 logo_top_margin=20, video_to_logo_margin=30, video_max_height=None,
                 heading_to_video_margin=30, text_to_heading_margin=20,
                 caption_heading_font=None, caption_text_font=None,
                 fps=60, bitrate="8000k", preset="ultrafast", logger=None):

        current_y = logo_top_margin
        
        if logo_path:
            final_logo_path = logo_path
        elif auto_select_logo:
            final_logo_path = self._choose_logo_path(logo_dark_path, logo_light_path)
        else:
            final_logo_path = logo_dark_path if os.path.exists(logo_dark_path) else None

        logo_actual_height = 0
        if final_logo_path and os.path.exists(final_logo_path):
            temp_logo = ImageClip(final_logo_path)
            if temp_logo.h > logo_height:
                logo_actual_height = logo_height
            else:
                logo_actual_height = temp_logo.h
            temp_logo.close()
            current_y += logo_actual_height + video_to_logo_margin

        video_height = self.load_video_fullwidth(
            top_margin=current_y,
            video_max_height=video_max_height
        )
        
        layers = []
        layers.append(self.create_background())

        if final_logo_path:
            logo = self.add_logo(final_logo_path, logo_height, (20, logo_top_margin))
            if logo:
                layers.append(logo)

        layers.append(self.user_video)
        current_y += video_height + heading_to_video_margin

        if caption_heading:
            heading_clips = self.create_multicolor_text(
                caption_heading, caption_heading_font_size, caption_heading_color,
                ("center", current_y), caption_heading_font,
                caption_heading_stroke_color, caption_heading_stroke_width
            )
            layers.extend(heading_clips)

            if heading_clips:
                y_positions = set(clip.pos(0)[1] for clip in heading_clips)
                num_lines = len(y_positions)
                heading_height = num_lines * caption_heading_font_size * 1.3
                current_y += int(heading_height) + text_to_heading_margin

        text_clips = self.create_multicolor_text(
            caption_text, caption_text_font_size, caption_text_color,
            ("center", current_y), caption_text_font,
            caption_text_stroke_color, caption_text_stroke_width
        )
        layers.extend(text_clips)

        final_video = CompositeVideoClip(layers)

        final_video.write_videofile(
            self.output_path,
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            bitrate=bitrate,
            preset=preset,
            threads=4,
            logger=logger
        )

def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

@app.get("/", response_class=HTMLResponse)
async def get_html():
    return FileResponse("index.html")

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    active_connections[client_id] = websocket
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        del active_connections[client_id]

@app.post("/process-video")
async def process_video(
    video: UploadFile = File(...),
    caption_heading: str = Form(""),
    caption_heading_font_size: int = Form(70),
    caption_heading_color: str = Form("white"),
    caption_heading_font: str = Form("Arial"), # New field for heading font
    caption_text: str = Form("Your Caption Here"),
    caption_text_font_size: int = Form(45),
    caption_text_color: str = Form("white"),
    caption_text_font: str = Form("Arial"), # New field for text font
    background_color: str = Form("#000000"),
    fps: int = Form(60),
    bitrate: str = Form("8000k"),
    client_id: str = Form(...)
):

    video_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    input_path = UPLOAD_DIR / f"{video_id}_{video.filename}"
    output_filename = f"video_{timestamp}_{video_id}.mp4"
    output_path = OUTPUT_DIR / output_filename
    
    # Save uploaded video
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)
    
    try:
        loop = asyncio.get_event_loop()

        if client_id in active_connections:
            await active_connections[client_id].send_json({
                "type": "status",
                "message": "Initializing video engine..."
            })

        ws_logger = WebSocketLogger(client_id, loop)
        
        bg_color = hex_to_rgb(background_color)
        
        # Resolve Font Paths
        heading_font_path = get_font_path(caption_heading_font)
        text_font_path = get_font_path(caption_text_font)

        creator = VideoCreator(
            input_video_path=str(input_path),
            output_path=str(output_path),
            background_color=bg_color,
            width=1080,
            height=1920
        )
        
        await loop.run_in_executor(
            None, 
            lambda: creator.create_video(
                caption_heading=caption_heading,
                caption_heading_font_size=caption_heading_font_size,
                caption_heading_color=caption_heading_color,
                caption_heading_font=heading_font_path, 
                caption_text=caption_text,
                caption_text_font_size=caption_text_font_size,
                caption_text_color=caption_text_color,
                caption_text_font=text_font_path, 
                fps=fps,
                bitrate=bitrate,
                preset="ultrafast",
                logger=ws_logger  
            )
        )

        if client_id in active_connections:
            await active_connections[client_id].send_json({
                "type": "complete",
                "message": "Video processing complete!",
                "download_url": f"/download/video/{output_filename}"
            })

        if os.path.exists(input_path):
            os.remove(input_path)
        
        return {
            "status": "success",
            "video_id": video_id,
            "download_url": f"/download/video/{output_filename}"
        }
        
    except Exception as e:
        if client_id in active_connections:
            await active_connections[client_id].send_json({
                "type": "error",
                "message": f"Error: {str(e)}"
            })
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/video/{filename}")
async def download_video(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="video/mp4", filename=filename)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)