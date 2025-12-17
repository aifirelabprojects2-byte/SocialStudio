import re
import os
import asyncio
import random
import json
import itertools
from urllib.parse import urlparse
from typing import Dict, List, Any, Optional
import instaloader
import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

load_dotenv()

class Config:
    INSTAGRAM_RATE_LIMIT_DELAY_MIN: float = 1.0
    INSTAGRAM_RATE_LIMIT_DELAY_MAX: float = 3.0
    INSTAGRAM_RETRY_ATTEMPTS: int = 3

X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")

HEADERS_CYCLE = itertools.cycle([
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.instagram.com/",
    },
    {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.instagram.com/",
    }
])

def get_headers() -> Dict[str, str]:
    return next(HEADERS_CYCLE)

def detect_platform(url: str) -> str:
    parsed = urlparse(url.lower())
    domain = parsed.netloc
    if "instagram.com" in domain:
        return "instagram"
    elif "x.com" in domain or "twitter.com" in domain:
        return "x"
    return "unknown"

INSTAGRAM_SHORTCODE_PATTERN = re.compile(r'/p/([A-Za-z0-9_-]{11})')

def extract_instagram_shortcode(post_url: str) -> str:
    post_url = post_url.split('?')[0].rstrip('/')
    match = INSTAGRAM_SHORTCODE_PATTERN.search(post_url)
    if not match:
        raise ValueError("Invalid Instagram URL—no shortcode found.")
    return match.group(1)

@retry(
    stop=stop_after_attempt(Config.INSTAGRAM_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(instaloader.exceptions.ConnectionException)
)
async def fetch_instagram_post(shortcode: str) -> Optional[instaloader.Post]:
    loop = asyncio.get_event_loop()

    def _sync_fetch():
        L = instaloader.Instaloader(
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

    try:
        return await loop.run_in_executor(None, _sync_fetch)
    except instaloader.exceptions.LoginRequiredException:
        raise
    except instaloader.exceptions.ConnectionException as e:
        if "429" in str(e) or "rate limit" in str(e).lower():
            await asyncio.sleep(random.uniform(60, 300))
        raise

def extract_instagram_media_urls(post: instaloader.Post) -> List[str]:
    media_urls = []
    if post.typename == 'GraphVideo':
        media_urls.append(post.video_url)
    elif post.typename == 'GraphImage':
        media_urls.append(post.url)
    elif post.typename == 'GraphSidecar':
        for node in post.get_sidecar_nodes():
            media_urls.append(node.video_url if node.is_video else node.display_url)
    else:
        media_urls.append(post.url or post.video_url)
    return [url for url in media_urls if url]

X_TWEET_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/[^/]+/status/(\d+)"
)

def extract_x_tweet_id(url: str) -> Optional[str]:
    match = X_TWEET_PATTERN.search(url.strip())
    return match.group(1) if match else None

def fetch_x_tweet(tweet_id: str) -> Optional[Dict[str, Any]]:
    if not X_BEARER_TOKEN:
        return {"error": "X_BEARER_TOKEN not set in environment."}

    url = f"https://api.twitter.com/2/tweets/{tweet_id}"
    params = {
        "expansions": "attachments.media_keys,author_id",
        "media.fields": "url,type,preview_image_url",
        "tweet.fields": "text",
    }
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "data" not in data:
            return {"error": "No tweet data", "details": data}

        tweet = data["data"]
        text = tweet.get("text", "")

        media_urls = []
        if "includes" in data and "media" in data["includes"]:
            for media in data["includes"]["media"]:
                if media["type"] == "photo" and media.get("url"):
                    # High-res version
                    media_urls.append(media["url"] + "?format=jpg&name=orig")
                elif media["type"] in ["video", "animated_gif"]:
                    # For videos, we usually get preview_image_url
                    media_urls.append(media.get("preview_image_url", ""))

        return {
            "caption": text.strip(),
            "media_urls": [url for url in media_urls if url]
        }

    except requests.exceptions.HTTPError as e:
        error_detail = response.json() if response.content else str(e)
        return {"error": f"HTTP {response.status_code}", "details": error_detail}
    except Exception as e:
        return {"error": str(e)}

async def fetch_social_post(url: str) -> Dict[str, Any]:
    platform = detect_platform(url)

    if platform == "instagram":
        try:
            shortcode = extract_instagram_shortcode(url)
            post = await fetch_instagram_post(shortcode)
            media_urls = extract_instagram_media_urls(post)
            caption = (post.caption or "").strip()

            result = {
                "platform": "instagram",
                "caption": caption,
                "media_urls": media_urls
            }
            # Respectful delay
            await asyncio.sleep(random.uniform(Config.INSTAGRAM_RATE_LIMIT_DELAY_MIN, Config.INSTAGRAM_RATE_LIMIT_DELAY_MAX))
            return result

        except ValueError as e:
            return {"error": str(e)}
        except instaloader.exceptions.LoginRequiredException:
            return {"error": "Instagram post is private or requires login."}
        except Exception as e:
            return {"error": f"Instagram fetch failed: {str(e)}"}

    elif platform == "x":
        tweet_id = extract_x_tweet_id(url)
        if not tweet_id:
            return {"error": "Invalid X/Twitter URL."}
        result = fetch_x_tweet(tweet_id)
        if "error" not in result:
            result["platform"] = "x"
        return result

    else:
        return {"error": "Unsupported platform. Only Instagram and X/Twitter are supported."}

async def main():
    print("Social Media Post Fetcher (Instagram & X)\n")
    while True:
        user_input = input("Enter post URL (or 'quit' to exit): ").strip()
        if user_input.lower() in ["quit", "q", "exit", ""]:
            print("Goodbye!")
            break

        print("Fetching...\n")
        result = await fetch_social_post(user_input)

        if "error" in result:
            print(f"Error: {result['error']}")
            if "details" in result:
                print(f"Details: {json.dumps(result['details'], indent=2)}")
        else:
            print(f"Platform: {result.get('platform', 'Unknown')}")
            print(f"Caption/Text:\n{result['caption']}\n")
            print("Media URLs:")
            if result["media_urls"]:
                for i, url in enumerate(result["media_urls"], 1):
                    print(f"{i}. {url}")
            else:
                print("No media found.")
        print("\n" + "-" * 80 + "\n")

if __name__ == "__main__":
    if os.name == "nt":  
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())