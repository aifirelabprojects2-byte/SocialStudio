import asyncio
import os
import json
from pathlib import Path
import time
import aiohttp
from typing import List, AsyncGenerator, Dict, Any, Annotated, Optional
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openai import AsyncOpenAI
from functools import lru_cache
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

DEFAULT_CONCURRENT_LIMIT = 5
DEFAULT_RPM = 60
CACHE_TTL_SECONDS = 86400
API_TIMEOUT = 30.0
MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 10.0
SEARCH_IMAGE_LIMIT = 3
SEARCH_NUM_RESULTS = 5
DEEP_RESEARCH_NUM_RESULTS = 10

class AsyncRateLimiter:
    def __init__(self, concurrent_limit: int = DEFAULT_CONCURRENT_LIMIT, rpm: int = DEFAULT_RPM):
        self.semaphore = asyncio.Semaphore(concurrent_limit)
        self.rpm = rpm
        self.tokens = rpm
        self.last_refill = time.time()
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def acquire(self):
        async with self.semaphore:
            async with self.lock:
                now = time.time()
                elapsed = now - self.last_refill
                self.tokens = min(self.rpm, self.tokens + (elapsed / 60) * self.rpm)
                self.last_refill = now
                
                while self.tokens < 1:
                    await asyncio.sleep(60 / self.rpm)
                    now = time.time()
                    elapsed = now - self.last_refill
                    self.tokens = min(self.rpm, self.tokens + (elapsed / 60) * self.rpm)
                    self.last_refill = now
                
                self.tokens -= 1


@lru_cache(maxsize=1)
def get_rate_limiter() -> AsyncRateLimiter:
    """Lazy initialization with caching."""
    concurrent = int(os.getenv("RATE_LIMIT_CONCURRENT", DEFAULT_CONCURRENT_LIMIT))
    rpm = int(os.getenv("RATE_LIMIT_RPM", DEFAULT_RPM))
    return AsyncRateLimiter(concurrent, rpm)


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    return AsyncOpenAI(api_key=api_key)


def get_search_api_key():
    key = os.getenv("SEARCH_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="SEARCH_API_KEY not configured")
    return key


async def retry_on_failure(coro_func, max_retries: int = MAX_RETRIES, base_delay: float = BASE_DELAY, max_delay: float = MAX_DELAY):
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await coro_func()
        except Exception as e:
            last_exception = e
            if attempt == max_retries:
                raise
            
            delay = min(base_delay * (2 ** attempt) + (time.time() % 1.0), max_delay)
            await asyncio.sleep(delay)
    
    raise last_exception


async def search_web(query: str, num: int, search_key: str) -> List[Dict[str, str]]:
    """Perform a Google search using SearchAPI and return top results with titles, URLs, and snippets."""
    params = {
        "engine": "google",
        "q": query,
        "api_key": search_key,
        "num": num,
    }

    limiter = get_rate_limiter()
    await limiter.acquire()

    async def fetch_coro():
        connector = aiohttp.TCPConnector(limit=10)
        timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get("https://www.searchapi.io/api/v1/search", params=params) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
                return data.get("organic_results", [])

    try:
        results = await retry_on_failure(fetch_coro, max_retries=MAX_RETRIES)
        return [
            {
                "title": result.get("title", ""),
                "url": result.get("link", ""),
                "snippet": result.get("snippet", ""),
            }
            for result in results
        ]
    except Exception as e:
        logger.error(f"Search error for query '{query}': {str(e)}")
        raise HTTPException(status_code=503, detail=f"Search failed for query '{query}'")


async def validate_and_extract(product_company: str, client: Annotated[AsyncOpenAI, Depends(get_openai_client)]) -> Optional[Dict[str, str]]:
    """Validate if the input refers to a product-company pair (flexible formats) using GPT and extract normalized names."""
    system_prompt = (
        "You are an input validator and extractor. Analyze the input to determine if it refers to a product and its company, "
        "handling natural language variations, casual phrasing, and comparisons. Always be flexible and recognize common products. "
        "Key guidelines:\n"
        "- Product names can include numbers/models (e.g., 'iPhone 15', 'iPhone 14', 'Maggi 2 Minute').\n"
        "- Ignore case, extra words like 'from', 'by', 'of', 'the', 'a'.\n"
        "- For comparisons (e.g., 'compare maggi and yippee'), extract the primary product-company pair (e.g., Maggi-Nestle), and note it's for single review focus.\n"
        "- Common products: iPhone (Apple), Maggi (Nestle), Yippee (ITC), Galaxy (Samsung), etc.\n"
        "Examples of valid inputs:\n"
        "- 'iPhone Apple' -> product: 'iPhone', company: 'Apple'\n"
        "- 'iphone 15 apple' -> product: 'iPhone 15', company: 'Apple'\n"
        "- 'iPhone 14 from apple' -> product: 'iPhone 14', company: 'Apple'\n"
        "- 'Maggi Nestle' -> product: 'Maggi', company: 'Nestle'\n"
        "- 'Nestle Maggi' -> product: 'Maggi', company: 'Nestle'\n"
        "- 'compare maggi and yippee' -> product: 'Maggi', company: 'Nestle' (primary focus)\n"
        "- 'can you compare maggi and yippee noodles' -> product: 'Maggi', company: 'Nestle'\n"
        "If it clearly references a product and company (even loosely), validate as true. Only invalid if no product/company identifiable."
    )
    user_prompt = f"""Input: "{product_company}".
Extract the primary product name and company name if valid. Respond with JSON:
{{"is_valid": true, "product": "extracted product name", "company": "extracted company name", "reason": "brief explanation"}}
If invalid, respond with JSON:
{{"is_valid": false, "reason": "brief explanation"}}"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
            max_tokens=150,
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        if data.get("is_valid"):
            return {
                "product": data["product"].strip(),
                "company": data["company"].strip(),
                "reason": data.get("reason", "")
            }
        else:
            logger.warning(f"Invalid input '{product_company}': {data.get('reason', 'Unknown reason')}")
            return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from validation for '{product_company}': {content}. Error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Validation error for '{product_company}': {str(e)}")
        raise HTTPException(status_code=503, detail="Validation service unavailable")


async def generate_search_queries(product_company: str, custom_filter: Optional[str], client: Annotated[AsyncOpenAI, Depends(get_openai_client)]) -> List[str]:
    """Generate 5 diverse search queries for reviews using GPT, incorporating custom filter if provided."""
    system_prompt = "You are a search query expert. Generate diverse, effective Google search queries focused on finding customer reviews (good and bad) for the given product-company pair."
    filter_part = f" Include focus on: {custom_filter}" if custom_filter else ""
    user_prompt = f'Product-Company: "{product_company}".{filter_part} Generate exactly 5 queries. Respond with JSON: {{"queries": ["query1", "query2", "query3", "query4", "query5"]}}'

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            response_format={"type": "json_object"},
            max_tokens=300,
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        queries = data.get("queries", [])
        # Append custom_filter to each query if provided
        if custom_filter:
            queries = [q + " " + custom_filter for q in queries]
        return queries
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from query generation: {content}. Error: {str(e)}")
        raise HTTPException(status_code=503, detail="Query generation failed")
    except Exception as e:
        logger.error(f"Query generation error: {str(e)}")
        raise HTTPException(status_code=503, detail="Query generation failed")


async def validate_and_prepare(
    product_company: str,
    is_deepresearch_needed: bool,
    custom_filter: Optional[str],
    client: Annotated[AsyncOpenAI, Depends(get_openai_client)],
    search_key: Annotated[str, Depends(get_search_api_key)]
) -> tuple[str, str, List[Dict[str, Any]]]:
    """Validate, generate queries, search, and prepare formatted context. Raises on error."""
    # Step 1: Validate and extract
    extract = await validate_and_extract(product_company, client)
    if extract is None:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid input: '{product_company}'. Please provide a product and company reference (e.g., 'iPhone 15 Apple', 'iPhone 14 from Apple', 'compare Maggi and Yippee')."
        )

    product = extract['product']
    company = extract['company']
    normalized_product_company = f"{product} {company}"

    # Step 2: Generate queries
    queries = await generate_search_queries(normalized_product_company, custom_filter, client)
    if not queries:
        raise HTTPException(status_code=503, detail="Failed to generate search queries.")

    # Step 3: Search
    num_results = DEEP_RESEARCH_NUM_RESULTS if is_deepresearch_needed else SEARCH_NUM_RESULTS
    all_sources: List[Dict[str, Any]] = []
    source_counter = 1
    for query in queries:
        results = await search_web(query, num_results, search_key)
        for result in results:
            all_sources.append(
                {
                    "id": source_counter,
                    "title": result["title"],
                    "url": result["url"],
                    "content": result["snippet"],
                }
            )
            source_counter += 1

    if not all_sources:
        raise HTTPException(status_code=404, detail="No search results found for the product.")

    # Step 4: Format context
    formatted_context = "\n\n".join(
        [
            f"Source [{s['id']}]: {s['title']}\nURL: {s['url']}\nContent: {s['content']}"
            for s in all_sources
        ]
    )

    return formatted_context, product, all_sources


async def generate_review_stream(
    context: str, product: str, client: Annotated[AsyncOpenAI, Depends(get_openai_client)]
) -> AsyncGenerator[str, None]:
    """Generate a formatted stream of good and bad reviews from search context using GPT."""
    system_prompt = (
        "You are an expert reviewer analyzer. Extract and summarize key good and bad customer "
        "reviews from the sources. Use inline citations like [1] after relevant points. "
        "Structure your output exactly as:\n"
        "# Good Reviews for {product}\n"
        "- Bullet point summarizing a positive aspect [citation]\n"
        "...\n\n"
        "# Bad Reviews for {product}\n"
        "- Bullet point summarizing a negative aspect [citation]\n"
        "...\n\n"
        "## Sources\n"
        "1. Title - URL\n"
        "2. Title - URL\n"
        "...\n"
        "Output ONLY this formatted text—no introductions, explanations, markdown beyond bullets, "
        "or extra content. Aim for 3-5 bullets per section. Ensure citations are used."
    ).format(product=product)

    user_prompt = f"Context from searches:\n{context}\n\nProvide the review analysis."

    try:
        stream = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,  
            stream=True,
            max_tokens=1500,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                yield content
    except Exception as e:
        logger.error(f"Review generation error: {str(e)}")
        raise HTTPException(status_code=503, detail="Review generation failed")



class ProductCompanyRequest(BaseModel):
    product_company: str
    is_deepresearch_needed: bool = False
    custom_filter: Optional[str] = None

@app.post("/reviews", response_class=StreamingResponse)
async def get_reviews(
    request: ProductCompanyRequest, 
    client: Annotated[AsyncOpenAI, Depends(get_openai_client)], 
    search_key: Annotated[str, Depends(get_search_api_key)]
):
    if not request.product_company.strip():
        raise HTTPException(status_code=400, detail="product_company is required")

    # Pre-validate and prepare to avoid errors during streaming
    try:
        formatted_context, product, _ = await validate_and_prepare(
            request.product_company,
            request.is_deepresearch_needed,
            request.custom_filter,
            client,
            search_key
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected preparation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

    async def event_generator():
        try:
            async for chunk in generate_review_stream(formatted_context, product, client):
                yield chunk
        except Exception as e:
            logger.error(f"Unexpected streaming error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    return StreamingResponse(
        event_generator(),
        media_type="text/plain",
        headers={"X-Accel-Buffering": "no"}  
    )