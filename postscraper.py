import re
import os
import asyncio
import random
import json
import sys
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, List, Optional, Any
import instaloader  
from dotenv import load_dotenv
import itertools

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()


class Config:
    INSTAGRAM_RATE_LIMIT_DELAY_MIN: float = float('1.0')
    INSTAGRAM_RATE_LIMIT_DELAY_MAX: float = float('3.0')
    INSTAGRAM_RETRY_ATTEMPTS: int = int('3')


HEADERS_CYCLE = itertools.cycle([
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.instagram.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.instagram.com/",
    }
])

def get_headers() -> Dict[str, str]:
    return next(HEADERS_CYCLE)

@retry(
    stop=stop_after_attempt(Config.INSTAGRAM_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(instaloader.exceptions.ConnectionException)
)
async def fetch_instagram_post(shortcode: str) -> Optional[instaloader.Post]:
    loop = asyncio.get_event_loop()
    
    def _sync_fetch():
        L = instaloader.Instaloader(
            dirname_pattern="",
            filename_pattern="{shortcode}_{date_utc}",
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            post_metadata_txt_pattern="",
            request_timeout=30,
            max_connection_attempts=3,
        )
        session = L.context._session
        session.headers.update(get_headers())
        return instaloader.Post.from_shortcode(L.context, shortcode)
    
    try:
        post = await loop.run_in_executor(None, _sync_fetch)
        return post
    except instaloader.exceptions.LoginRequiredException as e:
        raise
    except instaloader.exceptions.ConnectionException as e:
        if "429" in str(e) or "rate limit" in str(e).lower():
            await asyncio.sleep(random.uniform(60, 300)) 
        raise
    except Exception as e:
        raise

def extract_shortcode(post_url: str) -> str:
    post_url = post_url.split('?')[0].rstrip('/')
    match = re.search(r'/p/([A-Za-z0-9_-]{11})', post_url)
    if match:
        return match.group(1)
    raise ValueError("Invalid Instagram URL—no shortcode found.")

def fetch_media_urls(post: instaloader.Post) -> List[str]:
    media_urls = []
    if post.typename == 'GraphVideo':
        media_urls.append(post.video_url)
    elif post.typename == 'GraphImage':
        media_urls.append(post.url)
    elif post.typename == 'GraphSidecar':
        for node in post.get_sidecar_nodes():
            if node.is_video:
                media_urls.append(node.video_url)
            else:
                media_urls.append(node.display_url)
    else:
        media_urls.append(post.url)  
    return media_urls

async def fetch_post_data(post_url: str) -> Dict[str, Any]:
    caption = ""
    media_urls = []
   
    domain = urlparse(post_url).netloc.lower()
    if "instagram.com" not in domain:
        return {"error": "Unsupported platform—only Instagram supported."}
   
    try:
        shortcode = extract_shortcode(post_url)
        post = await fetch_instagram_post(shortcode)
       
        caption = post.caption or ""
        media_urls = fetch_media_urls(post)

    except ValueError as e:
        return {"error": str(e)}
    except instaloader.exceptions.LoginRequiredException:
        return {"error": "Post requires login. Try logging in via instaloader or use cookies."}
    except Exception as e:
        return {"error": f"Fetch failed: {str(e)}"}
    
    result = {
        "caption": caption.strip(),
        "media_urls": media_urls,
    }
    
    await asyncio.sleep(random.uniform(Config.INSTAGRAM_RATE_LIMIT_DELAY_MIN, Config.INSTAGRAM_RATE_LIMIT_DELAY_MAX))
   
    return result

async def main():
    url = input("Enter post URL: ").strip()
    result = await fetch_post_data(url)
    print("\nFinal Result:")
    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())