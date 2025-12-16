import os
import re
import asyncio
import random
import sys
from urllib.parse import urlparse
from typing import Optional
import itertools
import aiohttp
from gallery_dl import config, job
import instaloader
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

class Config:
    INSTAGRAM_RATE_LIMIT_DELAY_MIN = 1.0
    INSTAGRAM_RATE_LIMIT_DELAY_MAX = 3.0
    INSTAGRAM_RETRY_ATTEMPTS = 5
    AIOHTTP_TIMEOUT = 60
    CHUNK_SIZE = 1024 * 1024

HEADERS_CYCLE = itertools.cycle([
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.instagram.com/"},
    {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.instagram.com/"},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"},
])

def get_headers() -> dict:
    return next(HEADERS_CYCLE)

def is_x_url(url: str) -> bool:
    domain = urlparse(url).netloc.lower()
    return "x.com" in domain or "twitter.com" in domain

def is_instagram_url(url: str) -> bool:
    domain = urlparse(url).netloc.lower()
    return "instagram.com" in domain

async def download_x_images(url: str):
    # Run gallery-dl synchronously in a thread pool
    loop = asyncio.get_event_loop()
    def _sync_download():
        # Set config to download images only (skip videos)
        config.set(("extractor", "twitter"), "videos", False)
        # Optional: better filename and directory
        config.set((), "base-directory", "x_downloads")
        # Download the post/tweet
        download_job = job.DownloadJob(url)
        download_job.run()
    await loop.run_in_executor(None, _sync_download)

def extract_instagram_shortcode(url: str) -> str:
    url = url.split('?')[0].rstrip('/')
    match = re.search(r'/p/([A-Za-z0-9_-]{11})', url) or re.search(r'/reel/([A-Za-z0-9_-]{11})', url)
    if match:
        return match.group(1)
    raise ValueError("Invalid Instagram URL")

@retry(stop=stop_after_attempt(Config.INSTAGRAM_RETRY_ATTEMPTS), wait=wait_exponential(multiplier=1, min=4, max=10), retry=retry_if_exception_type((instaloader.exceptions.ConnectionException, instaloader.exceptions.QueryReturnedNotFoundException)))
async def fetch_instagram_post(shortcode: str) -> Optional[instaloader.Post]:
    loop = asyncio.get_event_loop()
    def _sync_fetch():
        L = instaloader.Instaloader(
            dirname_pattern="instagram_downloads",
            filename_pattern="{shortcode}_{date_utc}",
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            post_metadata_txt_pattern="",
            request_timeout=30,
        )
        session = L.context._session
        session.headers.update(get_headers())
        return instaloader.Post.from_shortcode(L.context, shortcode)
    return await loop.run_in_executor(None, _sync_fetch)

async def download_single_image(image_url: str, filename: str):
    timeout = aiohttp.ClientTimeout(total=Config.AIOHTTP_TIMEOUT)
    async with aiohttp.ClientSession(headers=get_headers(), timeout=timeout) as session:
        async with session.get(image_url) as resp:
            if resp.status == 200:
                ext = image_url.split('?')[0].split('.')[-1]
                if len(ext) > 4:
                    ext = "jpg"
                filepath = f"{filename}.{ext}"
                with open(filepath, "wb") as f:
                    async for chunk in resp.content.iter_chunked(Config.CHUNK_SIZE):
                        f.write(chunk)

async def download_instagram_images(url: str):
    try:
        shortcode = extract_instagram_shortcode(url)
        post = await fetch_instagram_post(shortcode)
        if not post:
            return
        os.makedirs("instagram_downloads", exist_ok=True)
        tasks = []
        if post.typename == 'GraphSidecar':
            for idx, node in enumerate(post.get_sidecar_nodes()):
                if not node.is_video:
                    tasks.append(download_single_image(node.display_url, f"instagram_downloads/{shortcode}_{idx}"))
        elif post.typename == 'GraphImage':
            tasks.append(download_single_image(post.url, f"instagram_downloads/{shortcode}_0"))
        if tasks:
            await asyncio.gather(*tasks)
    except Exception as e:
        print(f"Error downloading Instagram post: {e}")
    finally:
        await asyncio.sleep(random.uniform(Config.INSTAGRAM_RATE_LIMIT_DELAY_MIN, Config.INSTAGRAM_RATE_LIMIT_DELAY_MAX))

async def process_url(url: str):
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        print("Invalid URL")
        return
    if is_x_url(url):
        await download_x_images(url)
    elif is_instagram_url(url):
        await download_instagram_images(url)
    else:
        print("Unsupported platform")

if __name__ == "__main__":
    user_url = input("Enter post URL (X/Twitter or Instagram): ").strip()
    if user_url:
        if user_url.startswith(("http://", "https://")):
            asyncio.run(process_url(user_url))
        else:
            print("Please enter a valid URL starting with http:// or https://")
    else:
        print("No URL provided.")