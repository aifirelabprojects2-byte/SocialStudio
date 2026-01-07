import os
import json
import asyncio
import sys
import aiohttp
from typing import List, Optional
from pydantic import BaseModel, Field
from openai import AsyncOpenAI

from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-openai-key-here")
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY2", "your-search-api-key-here")

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- Pydantic Models ---
class MemeList(BaseModel):
    names: List[str] = Field(
        ..., 
        description="A list of exactly 10 popular meme template names.", 
        min_items=10, 
        max_items=10
    )

# --- Utilities ---
class RateLimiter:
    """A simple async rate limiter using a Semaphore."""
    def __init__(self, limit: int):
        self.semaphore = asyncio.Semaphore(limit)

    async def acquire(self):
        await self.semaphore.acquire()
        
    def release(self):
        self.semaphore.release()

global_rate_limiter = RateLimiter(limit=5)

def get_openai_client():
    return AsyncOpenAI(api_key=OPENAI_API_KEY)

# --- Core Logic ---

async def fetch_single_meme_image(
    session: aiohttp.ClientSession, 
    meme_name: str
) -> Optional[str]:
    if not SEARCH_API_KEY:
        return None

    query = f"{meme_name} meme template".strip()
    
    params = {
        "engine": "google_images",
        "q": query,
        "api_key": SEARCH_API_KEY,
        "num": 1, 
    }

    await global_rate_limiter.acquire()
    
    try:
        async with session.get("https://www.searchapi.io/api/v1/search", params=params) as resp:
            global_rate_limiter.release() 
            
            if resp.status != 200:
                print(f"Search API Error {resp.status} for '{meme_name}'")
                return None
                
            data = await resp.json()
            
            if "images" in data and len(data["images"]) > 0:
                image_obj = data["images"][0]
                
                # --- FIXED EXTRACTION LOGIC ---
                # Sometimes 'original' is a string, sometimes it's a dict with 'link'
                original = image_obj.get("original")
                
                if isinstance(original, dict):
                    # Extract link from dictionary (Fix for your specific error)
                    return original.get("link") or original.get("url")
                elif isinstance(original, str):
                    return original
                else:
                    # Fallback to thumbnail if original is weird/missing
                    return image_obj.get("thumbnail")
            
            return None

    except Exception as e:
        global_rate_limiter.release()
        # Return the exception so we can see it in the gather results if needed
        return e 


async def generate_meme_templates(user_context: str) -> List[str]:
    client = get_openai_client()

    # 1. Generate Meme Names
    system_prompt = (
        "You are a meme expert. Analyze the user's situation and suggest exactly 10 "
        "classic or trending meme template names. "
        "Return the result as a strict JSON object with a 'names' key."
    )

    print(f"Generating meme concepts for: '{user_context}'...")

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context: {user_context}"},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        
        content = response.choices[0].message.content
        meme_data = MemeList.model_validate_json(content)
        meme_names = meme_data.names
        print(f"AI Suggested: {meme_names}")

    except Exception as e:
        print(f"OpenAI Generation Failed: {e}")
        return []

    # 2. Concurrent Image Fetching
    valid_urls = []
    
    connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
    timeout = aiohttp.ClientTimeout(total=15)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [fetch_single_meme_image(session, name) for name in meme_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, str):
                valid_urls.append(result)
            elif isinstance(result, Exception):
                print(f"Request failed for '{meme_names[i]}': {result}")
            elif result is None:
                print(f"No image found for '{meme_names[i]}'")
            else:
                # If it's not a string, exception, or None, it's an unexpected type
                print(f"Unexpected data type for '{meme_names[i]}': {type(result)}")

        # Windows Clean Exit: Give a tiny moment for the underlying socket to close
        await asyncio.sleep(0.25)

    return valid_urls

# --- Execution Entry Point ---

if __name__ == "__main__":
    context = "When the code works on my machine but fails in production"
    
    try:
        # Run the async loop
        final_images = asyncio.run(generate_meme_templates(context))
        
        print("\n--- Final Image List ---")
        print(json.dumps(final_images, indent=2))
        print(f"Total images retrieved: {len(final_images)}")
        
    except KeyboardInterrupt:
        print("Process interrupted.")