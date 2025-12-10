import re
import os
import asyncio
import random
import json
import time
import sys
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, List, Optional, Any
from openai import AsyncOpenAI
import instaloader  # Only this import—no internals!
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import itertools

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()


class Config:
    OPENAI_API_KEY: str = os.getenv('OPENAI_API_KEY')
    INSTAGRAM_RATE_LIMIT_DELAY_MIN: float = float('1.0')
    INSTAGRAM_RATE_LIMIT_DELAY_MAX: float = float('3.0')
    INSTAGRAM_RETRY_ATTEMPTS: int = int('3')
    OPENAI_MODEL: str = 'gpt-4o-mini'
    OPENAI_TEMPERATURE: float = float('0.7')
    OPENAI_MAX_TOKENS: int = int('500')
    
client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)

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

async def rephrase_with_gpt4o_mini(plain_caption: str, company_name: str = "TechFlow", tone: str = "professional yet friendly") -> Dict[str, Any]:
    if not plain_caption:
        return {
            "rephrased_caption": "Exciting content ahead! 🚀",
            "suggested_hashtags": [f"#{company_name.replace(' ', '')}", "#Innovation"]
        }
   
    system_prompt = f"""You are a social media expert for {company_name}.
    Rephrase the following plain caption (hashtags already removed) in a {tone} tone: engaging, branded, and optimized for shares.
    Preserve length and excitement. Do not include any hashtags in the rephrased caption.
   
    Then, suggest exactly 1-2 relevant hashtags for {company_name}, including the branded one (e.g., #{company_name.replace(' ', '')}).
   
    Respond ONLY with a valid JSON object in this exact format, no other text:
    {{
        "rephrased_caption": "your rephrased caption here",
        "suggested_hashtags": ["#hashtag1", "#hashtag2"]
    }}"""
   
    try:
        stream = await client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": plain_caption},
            ],
            temperature=Config.OPENAI_TEMPERATURE,
            stream=True,
            max_tokens=Config.OPENAI_MAX_TOKENS,
        )
       
        new_response = ""
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                new_response += chunk.choices[0].delta.content
        parsed = json.loads(new_response.strip())
        return parsed
    except json.JSONDecodeError as e:
        return {
            "rephrased_caption": plain_caption or "Great share",
            "suggested_hashtags": [f"#{company_name.replace(' ', '')}", "#Innovation"]
        }
    except Exception as e:
        return {
            "rephrased_caption": plain_caption or "Great share",
            "suggested_hashtags": [f"#{company_name.replace(' ', '')}", "#Innovation"]
        }

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
        media_urls.append(post.url)  # Fallback
    return media_urls

async def fetch_and_rephrase_post(post_url: str, company_name: str = "TechFlow", tone: str = "professional yet friendly") -> Dict[str, Any]:
    caption = ""
    original_hashtags = []
    media_urls = []
   
    domain = urlparse(post_url).netloc.lower()
    if "instagram.com" not in domain:
        return {"error": "Unsupported platform—only Instagram supported."}
   
    try:
        shortcode = extract_shortcode(post_url)
        post = await fetch_instagram_post(shortcode)
       
        caption = post.caption or ""
        original_hashtags = list(post.caption_hashtags) if hasattr(post, 'caption_hashtags') and post.caption_hashtags else []

        plain_caption = re.sub(r'#\w+', '', caption).strip()
       
        media_urls = fetch_media_urls(post)

    except ValueError as e:
        return {"error": str(e)}
    except instaloader.exceptions.LoginRequiredException:
        return {"error": "Post requires login. Set login_username or use --load-cookies chrome in CLI."}
    except Exception as e:
        return {"error": f"Fetch failed: {str(e)}"}
    
    try:
        gpt_response = await rephrase_with_gpt4o_mini(plain_caption, company_name, tone)
        rephrased_caption = gpt_response.get("rephrased_caption", plain_caption or "Exciting content ahead! 🚀")
        suggested_hashtags = gpt_response.get("suggested_hashtags", [])
       
        # Combine original + suggested (dedupe)
        all_hashtags = list(set(original_hashtags + suggested_hashtags))
       
    except Exception as e:
        rephrased_caption = plain_caption or "Great share"
        all_hashtags = original_hashtags + [f"#{company_name.replace(' ', '')}", "#Innovation"]
    
    result = {
        "caption": rephrased_caption,
        "hashtags": all_hashtags,
        "media_urls": media_urls,
        "source_url": post_url
    }
    await asyncio.sleep(random.uniform(Config.INSTAGRAM_RATE_LIMIT_DELAY_MIN, Config.INSTAGRAM_RATE_LIMIT_DELAY_MAX))
   
    return result

async def main():
    url = input("Enter post URL: ").strip()
    company = input("Enter company name [default: TechFlow]: ").strip() or "TechFlow"
    tone = input("Enter rephrase tone [default: professional yet friendly]: ").strip() or "professional yet friendly"
   
    result = await fetch_and_rephrase_post(url, company, tone)
    print("\nFinal Result:")
    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())