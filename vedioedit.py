from moviepy import VideoFileClip, ImageClip, TextClip, ColorClip, CompositeVideoClip
import re
import os

class VideoCreator:

    COLORS = {
        'fireblue':'#60a5fa',
        'blue': '#0000FF',
        'lightblue': '#87CEEB',
        'skyblue': '#87CEEB',
        'darkblue': '#00008B',
        'navyblue': '#000080',
        'royalblue': '#4169E1',
        'steelblue': '#4682B4',
        'dodgerblue': '#1E90FF',
        'red': '#FF0000',
        'lightred': '#FF6B6B',
        'darkred': '#8B0000',
        'crimson': '#DC143C',
        'tomato': '#FF6347',
        'green': '#00FF00',
        'lightgreen': '#90EE90',
        'darkgreen': '#006400',
        'lime': '#00FF00',
        'forest': '#228B22',
        'mint': '#98FF98',
        'emerald': '#50C878',
        'yellow': '#FFFF00',
        'lightyellow': '#FFFFE0',
        'gold': '#FFD700',
        'orange': '#FFA500',
        'darkorange': '#FF8C00',
        'purple': '#800080',
        'lightpurple': '#DDA0DD',
        'violet': '#EE82EE',
        'magenta': '#FF00FF',
        'lavender': '#E6E6FA',
        'pink': '#FFC0CB',
        'lightpink': '#FFB6C1',
        'hotpink': '#FF69B4',
        'deeppink': '#FF1493',
        'white': '#FFFFFF',
        'black': '#000000',
        'gray': '#808080',
        'lightgray': '#D3D3D3',
        'darkgray': '#A9A9A9',
        'cyan': '#00FFFF',
        'turquoise': '#40E0D0',
        'brown': '#A52A2A',
        'beige': '#F5F5DC',
        'coral': '#FF7F50',
        'salmon': '#FA8072',
    }
    
    def __init__(self, 
                 input_video_path,
                 output_path="output_video.mp4",
                 background_color=(0, 0, 0),
                 width=1080,
                 height=1920):

        self.input_video_path = input_video_path
        self.output_path = output_path
        self.background_color = background_color
        self.width = width
        self.height = height
        self.user_video = None
        self.duration = None
        self.font_path = self._get_default_font()
    
    def _get_default_font(self):
        """Get a working font path for the system"""
        windows_fonts = [
            "C:/Windows/Fonts/Arialbd.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/times.ttf",
        ]
        
        for font_path in windows_fonts:
            if os.path.exists(font_path):
                print(f"Using font: {font_path}")
                return font_path
        
        print("Using default system font")
        return None
    
    def _calculate_brightness(self, rgb_color):
        r, g, b = rgb_color
        return 0.299 * r + 0.587 * g + 0.114 * b
    
    def _choose_logo_path(self, logo_dark_path="logo_dark.png", logo_light_path="logo_light.png"):
        brightness = self._calculate_brightness(self.background_color)
        threshold = 128
        
        if brightness < threshold:
            chosen_logo = logo_dark_path
            print(f"Background is dark (brightness: {brightness:.1f}), using {logo_dark_path}")
        else:
            chosen_logo = logo_light_path
            print(f"Background is light (brightness: {brightness:.1f}), using {logo_light_path}")
        
        if os.path.exists(chosen_logo):
            return chosen_logo
        else:
            print(f"Warning: {chosen_logo} not found")
            alternate = logo_light_path if chosen_logo == logo_dark_path else logo_dark_path
            if os.path.exists(alternate):
                print(f"Using alternate logo: {alternate}")
                return alternate
            return None
    
    def load_video_fullwidth(self, top_margin=200, video_max_height=None):

        self.user_video = VideoFileClip(self.input_video_path)
        self.duration = self.user_video.duration
        
        # Calculate target dimensions for full width coverage
        aspect_ratio = self.user_video.w / self.user_video.h
        
        # Resize to exact template width
        self.user_video = self.user_video.resized(width=self.width)
        
        # If max height specified and exceeded, crop or resize
        if video_max_height and self.user_video.h > video_max_height:
            # Resize to max height instead, then crop width if needed
            self.user_video = self.user_video.resized(height=video_max_height)
            
            # If video is now wider than template, crop to fit
            if self.user_video.w > self.width:
                x_center = self.user_video.w / 2
                self.user_video = self.user_video.cropped(
                    x_center=x_center,
                    width=self.width
                )
            # If video is narrower, resize back to full width
            elif self.user_video.w < self.width:
                self.user_video = self.user_video.resized(width=self.width)
        
        # Position at left edge (x=0) for full width
        x_pos = 0
        y_pos = top_margin
        
        self.user_video = self.user_video.with_position((x_pos, y_pos))
        
        print(f"✓ Video: {self.user_video.w}x{self.user_video.h} at position ({x_pos}, {y_pos})")
        print(f"  Template width: {self.width} | Video fills: {self.user_video.w == self.width}")
        
        return self.user_video.h
    
    def create_background(self):
        background = ColorClip(size=(self.width, self.height), color=self.background_color)
        return background.with_duration(self.duration)
    
    def add_logo(self, logo_path, logo_height=150, position=("center", 40)):
        try:
            logo = ImageClip(logo_path)

            if logo.h > logo_height:
                logo = logo.resized(height=logo_height)

            max_width = self.width - 80
            if logo.w > max_width:
                logo = logo.resized(width=max_width)
                print(f"Logo resized to fit: {logo.w}x{logo.h}")
            
            logo = logo.with_duration(self.duration)
            logo = logo.with_position(position)
            
            return logo
        except Exception as e:
            print(f"Error loading logo: {e}")
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
        
        # Account for stroke in width calculations
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
    
    def create_video(self, 
                 caption_heading="",
                 caption_heading_font_size=80,
                 caption_heading_color='white',
                 caption_heading_stroke_color='black',
                 caption_heading_stroke_width=3,
                 caption_text="Your Caption Here",
                 caption_text_font_size=55,
                 caption_text_color='white',
                 caption_text_stroke_color='black',
                 caption_text_stroke_width=2,
                 logo_dark_path="logo_dark.png",
                 logo_light_path="logo_light.png",
                 auto_select_logo=True,
                 logo_path=None,
                 logo_height=150,
                 logo_top_margin=40,
                 video_to_logo_margin=30,
                 video_max_height=None,
                 heading_to_video_margin=30,
                 text_to_heading_margin=20,
                 caption_heading_font=None,
                 caption_text_font=None,
                 fps=60,
                 bitrate="8000k",
                 preset="ultrafast"):

        current_y = logo_top_margin
        
        # Determine logo height first
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

        # Load video FIRST to set self.duration
        video_height = self.load_video_fullwidth(
            top_margin=current_y,
            video_max_height=video_max_height
        )
        
        # NOW create layers (duration is set)
        layers = []
        layers.append(self.create_background())

        # Add logo
        if final_logo_path:
            logo = self.add_logo(final_logo_path, logo_height, (20, logo_top_margin))
            if logo:
                layers.append(logo)

        # Add video
        layers.append(self.user_video)
        current_y += video_height + heading_to_video_margin


        if caption_heading:
            heading_clips = self.create_multicolor_text(
                caption_heading,
                caption_heading_font_size,
                caption_heading_color,
                ("center", current_y),
                caption_heading_font,
                caption_heading_stroke_color,
                caption_heading_stroke_width
            )
            layers.extend(heading_clips)

            if heading_clips:
                y_positions = set(clip.pos(0)[1] for clip in heading_clips)
                num_lines = len(y_positions)
                heading_height = num_lines * caption_heading_font_size * 1.3
                current_y += int(heading_height) + text_to_heading_margin

        # Add caption text
        text_clips = self.create_multicolor_text(
            caption_text,
            caption_text_font_size,
            caption_text_color,
            ("center", current_y),
            caption_text_font,
            caption_text_stroke_color,
            caption_text_stroke_width
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
            threads=4
        )

if __name__ == "__main__":
    creator = VideoCreator(
        input_video_path="test.mp4",
        output_path="output_final.mp4",
        background_color=(0, 0, 0),
        width=1080,
        height=1920
    )
    
    creator.create_video(
        caption_heading="<fireblue>Future is Here</fireblue>",
        caption_heading_font_size=70,
        caption_heading_color='white',
        caption_heading_stroke_color='black',
        caption_heading_stroke_width=3,
        caption_text="Watching a machine find its voice. It's no longer about whether robots can speak, but how much they sound and feel like us.",
        caption_text_font_size=45,
        caption_text_color='white',
        caption_text_stroke_color='black',
        caption_text_stroke_width=2,
        auto_select_logo=True,
        logo_dark_path="logo_dark.png",
        logo_light_path="logo_light.png",
        logo_height=100,
        logo_top_margin=20,
        video_to_logo_margin=30,  
        video_max_height=800,  
        heading_to_video_margin=30,  
        text_to_heading_margin=20,  
        fps=60,
        bitrate="10000k",
        preset="ultrafast"
    )