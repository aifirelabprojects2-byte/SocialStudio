"""
Platform Specifications for Social Media Posts
Defines format requirements, size limits, and media specifications for each platform
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class MediaSpec:
    """Specifications for media files"""
    max_file_size_mb: float
    min_width: Optional[int] = None
    min_height: Optional[int] = None
    max_width: Optional[int] = None
    max_height: Optional[int] = None
    aspect_ratios: Optional[List[str]] = None
    supported_formats: Optional[List[str]] = None
    max_duration_sec: Optional[int] = None
    min_duration_sec: Optional[int] = None


@dataclass
class PlatformSpec:
    """Complete specifications for a social media platform"""
    platform_name: str
    max_caption_length: int
    max_hashtags: int
    image_specs: MediaSpec
    video_specs: MediaSpec
    supports_carousel: bool = False
    max_carousel_items: int = 1
    supports_video: bool = True
    supports_image: bool = True


# Instagram Specifications
INSTAGRAM_SPEC = PlatformSpec(
    platform_name="Instagram",
    max_caption_length=2200,
    max_hashtags=30,
    image_specs=MediaSpec(
        max_file_size_mb=8,
        min_width=320,
        min_height=320,
        max_width=1440,
        max_height=1440,
        aspect_ratios=["1:1", "4:5", "16:9", "9:16"],
        supported_formats=["jpg", "jpeg", "png"]
    ),
    video_specs=MediaSpec(
        max_file_size_mb=100,
        min_width=320,
        min_height=320,
        max_width=1920,
        max_height=1920,
        aspect_ratios=["1:1", "4:5", "16:9", "9:16"],
        supported_formats=["mp4", "mov"],
        max_duration_sec=60,
        min_duration_sec=3
    ),
    supports_carousel=True,
    max_carousel_items=10
)

# Facebook Specifications
FACEBOOK_SPEC = PlatformSpec(
    platform_name="Facebook",
    max_caption_length=63206,
    max_hashtags=30,
    image_specs=MediaSpec(
        max_file_size_mb=10,
        min_width=600,
        min_height=315,
        max_width=8192,
        max_height=8192,
        aspect_ratios=["16:9", "1:1", "4:5", "9:16"],
        supported_formats=["jpg", "jpeg", "png", "gif", "bmp"]
    ),
    video_specs=MediaSpec(
        max_file_size_mb=4096,
        min_width=120,
        min_height=120,
        max_width=1920,
        max_height=1920,
        aspect_ratios=["16:9", "1:1", "4:5", "9:16"],
        supported_formats=["mp4", "mov"],
        max_duration_sec=240 * 60,  # 240 minutes
        min_duration_sec=1
    ),
    supports_carousel=True,
    max_carousel_items=10
)

# Twitter/X Specifications
TWITTER_SPEC = PlatformSpec(
    platform_name="Twitter",
    max_caption_length=280,
    max_hashtags=None,  # No specific limit but counts toward character limit
    image_specs=MediaSpec(
        max_file_size_mb=5,
        min_width=600,
        min_height=335,
        max_width=8192,
        max_height=8192,
        aspect_ratios=["16:9", "1:1", "4:5", "2:1"],
        supported_formats=["jpg", "jpeg", "png", "gif", "webp"]
    ),
    video_specs=MediaSpec(
        max_file_size_mb=512,
        min_width=32,
        min_height=32,
        max_width=1920,
        max_height=1920,
        aspect_ratios=["16:9", "1:1", "9:16"],
        supported_formats=["mp4", "mov"],
        max_duration_sec=140,
        min_duration_sec=0.5
    ),
    supports_carousel=True,
    max_carousel_items=4
)

# LinkedIn Specifications
LINKEDIN_SPEC = PlatformSpec(
    platform_name="LinkedIn",
    max_caption_length=3000,
    max_hashtags=None,  # No specific limit
    image_specs=MediaSpec(
        max_file_size_mb=10,
        min_width=552,
        min_height=276,
        max_width=7680,
        max_height=4320,
        aspect_ratios=["1.91:1", "1:1", "4:5"],
        supported_formats=["jpg", "jpeg", "png", "gif"]
    ),
    video_specs=MediaSpec(
        max_file_size_mb=5120,
        min_width=256,
        min_height=144,
        max_width=1920,
        max_height=1920,
        aspect_ratios=["16:9", "1:1", "9:16", "4:5", "2:3"],
        supported_formats=["mp4", "mov", "avi"],
        max_duration_sec=600,  # 10 minutes
        min_duration_sec=3
    ),
    supports_carousel=True,
    max_carousel_items=9
)

# Threads Specifications
THREADS_SPEC = PlatformSpec(
    platform_name="Threads",
    max_caption_length=500,
    max_hashtags=None,  # No specific limit
    image_specs=MediaSpec(
        max_file_size_mb=8,
        min_width=320,
        min_height=320,
        max_width=1440,
        max_height=1440,
        aspect_ratios=["1:1", "4:5", "16:9", "9:16"],
        supported_formats=["jpg", "jpeg", "png"]
    ),
    video_specs=MediaSpec(
        max_file_size_mb=100,
        min_width=320,
        min_height=320,
        max_width=1920,
        max_height=1920,
        aspect_ratios=["1:1", "4:5", "16:9", "9:16"],
        supported_formats=["mp4", "mov"],
        max_duration_sec=60,
        min_duration_sec=3
    ),
    supports_carousel=True,
    max_carousel_items=10
)

# TikTok Specifications
TIKTOK_SPEC = PlatformSpec(
    platform_name="TikTok",
    max_caption_length=2200,
    max_hashtags=None,  # No specific limit
    image_specs=MediaSpec(
        max_file_size_mb=10,
        min_width=720,
        min_height=720,
        max_width=1920,
        max_height=1920,
        aspect_ratios=["9:16", "1:1"],  # Vertical preferred
        supported_formats=["jpg", "jpeg", "png", "webp"]
    ),
    video_specs=MediaSpec(
        max_file_size_mb=287,  # ~4GB max
        min_width=720,
        min_height=720,
        max_width=1920,
        max_height=1920,
        aspect_ratios=["9:16", "1:1", "16:9"],  # 9:16 vertical is most common
        supported_formats=["mp4", "mov", "webm"],
        max_duration_sec=600,  # 10 minutes max (3 min for regular, 10 for longer videos)
        min_duration_sec=3
    ),
    supports_carousel=False,  # TikTok doesn't support traditional carousels
    max_carousel_items=1,
    supports_video=True,
    supports_image=True  # Photo mode/slideshow
)

# Snapchat Specifications
SNAPCHAT_SPEC = PlatformSpec(
    platform_name="Snapchat",
    max_caption_length=250,
    max_hashtags=None,  # No specific limit
    image_specs=MediaSpec(
        max_file_size_mb=5,
        min_width=1080,
        min_height=1920,  # 9:16 vertical recommended
        max_width=1080,
        max_height=1920,
        aspect_ratios=["9:16", "16:9"],  # Vertical preferred for Stories
        supported_formats=["jpg", "jpeg", "png"]
    ),
    video_specs=MediaSpec(
        max_file_size_mb=1024,  # 1GB
        min_width=640,
        min_height=640,
        max_width=1080,
        max_height=1920,
        aspect_ratios=["9:16", "16:9", "1:1"],  # 9:16 vertical is standard
        supported_formats=["mp4", "mov"],
        max_duration_sec=180,  # 3 minutes for Snap Ads, 60 seconds for Stories
        min_duration_sec=3
    ),
    supports_carousel=True,  # Snap Ads support carousel
    max_carousel_items=10,
    supports_video=True,
    supports_image=True
)


# Platform specifications dictionary
PLATFORM_SPECS: Dict[str, PlatformSpec] = {
    "instagram": INSTAGRAM_SPEC,
    "facebook": FACEBOOK_SPEC,
    "twitter": TWITTER_SPEC,
    "linkedin": LINKEDIN_SPEC,
    "threads": THREADS_SPEC,
    "tiktok": TIKTOK_SPEC,
    "snapchat": SNAPCHAT_SPEC,
}


def get_platform_spec(platform_name: str) -> Optional[PlatformSpec]:
    """
    Get platform specifications by platform name

    Args:
        platform_name: Name of the platform (case-insensitive)

    Returns:
        PlatformSpec object or None if platform not found
    """
    return PLATFORM_SPECS.get(platform_name.lower())


def validate_media(platform_name: str, media_type: str, file_size_mb: float,
                   width: int, height: int, duration_sec: Optional[int] = None,
                   file_format: Optional[str] = None) -> tuple[bool, Optional[str]]:
    """
    Validate media against platform specifications

    Args:
        platform_name: Name of the platform
        media_type: 'image' or 'video'
        file_size_mb: File size in megabytes
        width: Media width in pixels
        height: Media height in pixels
        duration_sec: Video duration in seconds (for videos only)
        file_format: File format extension (e.g., 'mp4', 'jpg')

    Returns:
        Tuple of (is_valid, error_message)
    """
    spec = get_platform_spec(platform_name)
    if not spec:
        return False, f"Unknown platform: {platform_name}"

    media_spec = spec.video_specs if media_type == "video" else spec.image_specs

    # Check file size
    if file_size_mb > media_spec.max_file_size_mb:
        return False, f"File size {file_size_mb}MB exceeds maximum {media_spec.max_file_size_mb}MB for {platform_name}"

    # Check dimensions
    if media_spec.min_width and width < media_spec.min_width:
        return False, f"Width {width}px is below minimum {media_spec.min_width}px for {platform_name}"

    if media_spec.min_height and height < media_spec.min_height:
        return False, f"Height {height}px is below minimum {media_spec.min_height}px for {platform_name}"

    if media_spec.max_width and width > media_spec.max_width:
        return False, f"Width {width}px exceeds maximum {media_spec.max_width}px for {platform_name}"

    if media_spec.max_height and height > media_spec.max_height:
        return False, f"Height {height}px exceeds maximum {media_spec.max_height}px for {platform_name}"

    # Check format
    if file_format and media_spec.supported_formats:
        if file_format.lower().lstrip('.') not in media_spec.supported_formats:
            return False, f"Format {file_format} not supported for {platform_name}. Supported: {', '.join(media_spec.supported_formats)}"

    # Check video duration
    if media_type == "video" and duration_sec is not None:
        if media_spec.min_duration_sec and duration_sec < media_spec.min_duration_sec:
            return False, f"Duration {duration_sec}s is below minimum {media_spec.min_duration_sec}s for {platform_name}"

        if media_spec.max_duration_sec and duration_sec > media_spec.max_duration_sec:
            return False, f"Duration {duration_sec}s exceeds maximum {media_spec.max_duration_sec}s for {platform_name}"

    return True, None


def get_recommended_specs(platform_name: str, media_type: str = "image") -> Optional[str]:
    """
    Get human-readable recommended specifications for a platform

    Args:
        platform_name: Name of the platform
        media_type: 'image' or 'video'

    Returns:
        Formatted string with recommendations or None if platform not found
    """
    spec = get_platform_spec(platform_name)
    if not spec:
        return None

    media_spec = spec.video_specs if media_type == "video" else spec.image_specs

    recommendations = [
        f"{spec.platform_name} {media_type.capitalize()} Specifications:",
        f"  Max file size: {media_spec.max_file_size_mb}MB",
    ]

    if media_spec.min_width or media_spec.min_height:
        recommendations.append(f"  Min dimensions: {media_spec.min_width}x{media_spec.min_height}px")

    if media_spec.max_width or media_spec.max_height:
        recommendations.append(f"  Max dimensions: {media_spec.max_width}x{media_spec.max_height}px")

    if media_spec.aspect_ratios:
        recommendations.append(f"  Recommended aspect ratios: {', '.join(media_spec.aspect_ratios)}")

    if media_spec.supported_formats:
        recommendations.append(f"  Supported formats: {', '.join(media_spec.supported_formats)}")

    if media_type == "video":
        if media_spec.min_duration_sec:
            recommendations.append(f"  Min duration: {media_spec.min_duration_sec}s")
        if media_spec.max_duration_sec:
            recommendations.append(f"  Max duration: {media_spec.max_duration_sec}s")

    return "\n".join(recommendations)
