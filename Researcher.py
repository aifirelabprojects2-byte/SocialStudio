import asyncio
from functools import lru_cache
import time
import aiohttp
from dotenv import load_dotenv
from openai import AsyncOpenAI
import Accounts
from CostCalc import calculate_llm_cost, count_tokens
import os
from typing import List, AsyncGenerator, Dict, Any, Annotated, Optional
from fastapi import  Depends, HTTPException, logger
from fastapi.responses import  JSONResponse, StreamingResponse
import json
from Database import  LLMUsage, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import StreamingResponse
import logging
from Configs import OPENAI_API_KEY, SEARCH_API_KEY, perplexity_client
from Schema.Researcher import ProductCompanyRequest

logger = logging.getLogger(__name__)


DEFAULT_CONCURRENT_LIMIT = 5
DEFAULT_RPM = 60
CACHE_TTL_SECONDS = 86400
API_TIMEOUT = 30.0
MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 10.0
SEARCH_IMAGE_LIMIT = 10
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


from functools import lru_cache
@lru_cache(maxsize=1)
def get_rate_limiter() -> AsyncRateLimiter:
    concurrent = int(DEFAULT_CONCURRENT_LIMIT)
    rpm = int(DEFAULT_RPM)
    return AsyncRateLimiter(concurrent, rpm)


def get_openai_client():
    api_key = OPENAI_API_KEY
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    return AsyncOpenAI(api_key=api_key)


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


conversation_memory: Dict[str, List[str]] = {}

def _normalize_key(product_company: str) -> str:
    return "".join(c.lower() for c in product_company if c.isalnum())


async def validate_and_extract(
    product_company: str,
    clarification: Optional[str] = None,
    client: AsyncOpenAI = Depends(get_openai_client),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    key = _normalize_key(product_company)
    print(product_company, clarification)
    if key not in conversation_memory:
        conversation_memory[key] = []
    accumulated_clarifications = " ".join(conversation_memory[key])
    context_part = f"\nPrevious clarifications provided: \"{accumulated_clarifications}\"" if accumulated_clarifications else ""
    clarif_part = f"\nUser clarification: '{clarification}'." if clarification else ""
   
    system_prompt = (
        "You are a precise input validator and extractor for product reviews. Your task is to identify the main product and its company from user input, "
        "handling natural language, variations, models (e.g., 'iPhone 16'), comparisons, and contextual descriptions.\n\n"
        "Key Rules:\n"
        "- Be flexible but decisive: Infer company confidently for well-known products (e.g., iPhone/Galaxy/ChatGPT → Apple/Samsung/OpenAI).\n"
        "- Common inferences (high confidence): iPhone/Mac/Book → Apple; Galaxy/Pixel → Samsung/Google; Maggi → Nestle; Yippee → ITC; ChatGPT/GPT → OpenAI.\n"
        "- For comparisons (e.g., 'compare Maggi and Yippee'), extract the primary/obvious product-company (usually the first mentioned) with high confidence.\n"
        "- Ignore case, fillers ('the', 'from', 'by'), and minor typos.\n"
        "- Always prefer extraction with high confidence if a reasonable product reference exists, even if company is inferred or loosely mentioned.\n"
        "- Only use low confidence + clarification for: greetings/chit-chat ('hi', 'hello'), completely vague inputs ('some gadget'), or truly unknown/niche products without clear context.\n"
        "- Never clarify if a plausible extraction is possible—err strongly toward high confidence for any product-like reference.\n\n"
        "Self-Evaluation Step (think internally first):\n"
        "1. Does the input mention or describe a recognizable product? → If yes, extract + high confidence.\n"
        "2. Can company be reasonably inferred? → If yes, do so.\n"
        "3. Is it purely social/non-product? → If yes, low confidence + clarify.\n"
        "Rate your extraction certainty: high if plausible, low only if impossible.\n\n"
        "Output Format (strict JSON only, no extra text; always include ALL fields):\n"
        "{\n"
        " \"is_valid\": true,\n"
        " \"product\": \"extracted product name (or null)\",\n"
        " \"company\": \"extracted/inferred company (or null)\",\n"
        " \"confidence\": \"high\" or \"low\",\n"
        " \"needs_clarification\": true or false,\n"
        " \"question\": \"helpful clarification question if needs_clarification=true (friendly, specific; else null)\",\n"
        " \"reason\": \"brief explanation of extraction or why clarification needed\"\n"
        "}\n\n"
        "Examples:\n"
        "- Input: 'iPhone' → {\"is_valid\": true, \"product\": \"iPhone\", \"company\": \"Apple\", \"confidence\": \"high\", \"needs_clarification\": false, \"question\": null, \"reason\": \"Direct product reference with inferred company\"}\n"
        "- Input: 'compare maggi and yippee' → {\"is_valid\": true, \"product\": \"Maggi\", \"company\": \"Nestle\", \"confidence\": \"high\", \"needs_clarification\": false, \"question\": null, \"reason\": \"Primary product extracted from comparison\"}\n"
        "- Input: 'latest smartphone from Apple' → {\"is_valid\": true, \"product\": \"iPhone\", \"company\": \"Apple\", \"confidence\": \"high\", \"needs_clarification\": false, \"question\": null, \"reason\": \"Inferred product from description\"}\n"
        "- Input: 'hi there' → {\"is_valid\": true, \"product\": null, \"company\": null, \"confidence\": \"low\", \"needs_clarification\": true, \"question\": \"Hi! What product and company would you like reviewed?\", \"reason\": \"No product reference; greeting only\"}\n"
        "- Input: 'some random thing from unknown corp' → {\"is_valid\": true, \"product\": null, \"company\": null, \"confidence\": \"low\", \"needs_clarification\": true, \"question\": \"What specific product and company are you referring to?\", \"reason\": \"Vague input without identifiable product/company\"}\n"
    )
    user_prompt = f"""Input: "{product_company}"{context_part}{clarif_part}
        Extract the primary product name and company name if identifiable. Assess confidence (high/low). If low, unclear, or no product/company (e.g., greetings, chit-chat), set needs_clarification: true and provide a helpful, model-generated clarifying question tailored to the input (keep it friendly and specific).
        Respond with JSON (always include all fields as in system prompt):
        {{"is_valid": true, "product": "extracted product name or null", "company": "extracted company name or null", "confidence": "high", "needs_clarification": false, "question": null, "reason": "brief explanation"}}"""
    
    model = "gpt-4o-mini"
    input_str = system_prompt + "\n\n" + user_prompt
    input_tokens = count_tokens(input_str, model)
    output_tokens = 0
    usage_status = "success"
    start = time.time()
    response_format = {"type": "json_object"}
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=300,
            response_format=response_format,
        )
        content = response.choices[0].message.content.strip()
        output_tokens = count_tokens(content, model)
        data = json.loads(content)
        result = {
            "is_valid": data.get("is_valid", True),
            "product": data.get("product"),
            "company": data.get("company"),
            "confidence": data.get("confidence", "low"),
            "needs_clarification": data.get("needs_clarification", True),
            "question": data.get("question"),
            "reason": data.get("reason", "")
        }
        if result["confidence"] == "high":
            result["needs_clarification"] = False
            result["question"] = None
        if clarification and clarification.strip() and result["needs_clarification"]:
            conversation_memory[key].append(clarification.strip())
        if result["confidence"] == "high" and not result["needs_clarification"]:
            conversation_memory.pop(key, None)
        return result
    except json.JSONDecodeError as je:
        usage_status = "failed"
        logger.error(f"JSON decode error in validate_and_extract: {je}")
        return {
            "is_valid": True,
            "product": None,
            "company": None,
            "confidence": "low",
            "needs_clarification": True,
            "question": "I'm having trouble understanding that. Could you specify the product name and company more clearly?",
            "reason": f"JSON parse error: {str(je)}"
        }
    except Exception as e:
        usage_status = "failed"
        logger.error(f"Error in validate_and_extract: {e}")
        return {
            "is_valid": True,
            "product": None,
            "company": None,
            "confidence": "low",
            "needs_clarification": True,
            "question": "I'm having trouble identifying the product. Can you tell me the exact product name and company?",
            "reason": f"Error: {str(e)}"
        }
    finally:
        latency_ms = int((time.time() - start) * 1000)
        total_cost = calculate_llm_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        db.add(LLMUsage(
            feature="product_validation",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=total_cost,
            latency_ms=latency_ms,
            status=usage_status,
        ))
        await db.commit()


PRODUCT_ANALYSIS_PROMPT = {
    "product_overview": (
        "You are an expert product analyst. Provide a comprehensive, deep analysis of the product based on web searches. "
        "Always deliver in-depth insights on features, market position, strengths, weaknesses, and incorporate user reviews where available. "
        "Base your analysis on recent, relevant web data WITHOUT EVER citing, mentioning, marking, or listing any sources, references, URLs, or citations in the output. "
        "Structure your output exactly as:\n"
        "# Product Overview\n"
        "A detailed summary of the product, its purpose, and market context.\n\n"
        "# Key Features\n"
        "- Bullet points of main features with descriptions.\n"
        "...\n\n"
        "# Strengths / Pros\n"
        "- In-depth positive aspects, backed by data or examples.\n"
        "...\n\n"
        "# Weaknesses / Cons\n"
        "- In-depth negative aspects, risks, or limitations.\n"
        "...\n\n"
        "# User Sentiment & Reviews\n"
        "Overall sentiment score (e.g., 4.2/5). Summarize key themes from reviews. Include 2-3 notable user quotes or summaries if available.\n\n"
        "Output ONLY this formatted text—no introductions, extra content, citations, sources, or any markings. Use markdown for structure. Aim for depth: 4-6 bullets per section where possible."
    ),

    "technical_specifications": (
        "You are an expert product analyst. Provide a comprehensive, deep analysis of the product's technical specifications based on web searches. "
        "Deliver in-depth details on dimensions, materials, performance metrics, compatibility, and other key specs. "
        "Base your analysis on recent, relevant web data WITHOUT EVER citing, mentioning, marking, or listing any sources, references, URLs, or citations in the output. "
        "Structure your output exactly as:\n"
        "# Technical Specifications\n"
        "A detailed breakdown of the product's core specs, including categories like build, performance, and compatibility.\n\n"
        "# Detailed Specs\n"
        "- Bullet points with in-depth descriptions of key specifications (aim for 6-10 bullets covering major aspects).\n"
        "...\n\n"
        "Output ONLY this formatted text—no introductions, extra content, citations, sources, or any markings. Use markdown for structure, including tables if specs lend themselves to tabular format (e.g., for dimensions or comparisons within the product line). Aim for depth and precision."
    ),

    "product_images": (
        "You are an expert product analyst. Provide a visual showcase of the product based on web searches"
       "You are an expert product analyst. Provide a comprehensive, deep analysis of the product based on web searches. "
        "Always deliver in-depth insights on features, market position, strengths, weaknesses, and incorporate user reviews where available. "
        "Base your analysis on recent, relevant web data WITHOUT EVER citing, mentioning, marking, or listing any sources, references, URLs, or citations in the output. "
        "A detailed summary of the product, its purpose, and market context.\n\n"
        "# User Sentiment & Reviews\n"
        "Overall sentiment score (e.g., 4.2/5). Summarize key themes from reviews. Include 2-3 notable user quotes or summaries if available.\n\n"
        "Output ONLY this formatted text—no introductions, extra content, citations, sources, or any markings. Use markdown for structure. Aim for depth: 4-6 bullets per section where possible."
    ),

    "warranty_and_return_policy": (
        "You are an expert product analyst. Provide a comprehensive, deep analysis of the product's warranty and return policy based on web searches. "
        "Deliver in-depth insights on coverage, duration, claims process, exclusions, and customer protections. "
        "Base your analysis on recent, relevant web data WITHOUT EVER citing, mentioning, marking, or listing any sources, references, URLs, or citations in the output. "
        "Structure your output exactly as:\n"
        "# Warranty and Return Policy\n"
        "A detailed overview of the policies, including what is covered and key terms.\n\n"
        "# Key Coverage Details\n"
        "- Bullet points explaining warranty scope, duration, and protections (aim for 4-6 bullets).\n"
        "...\n\n"
        "# Return Process and Exclusions\n"
        "- Bullet points on how to return, timelines, conditions, and common exclusions (aim for 4-6 bullets).\n"
        "...\n\n"
        "Output ONLY this formatted text—no introductions, extra content, citations, sources, or any markings. Use markdown for structure. Aim for depth to build buyer confidence."
    ),

    "faqs": (
        "You are an expert product analyst. Provide a comprehensive set of frequently asked questions and answers for the product based on web searches. "
        "Focus on common user queries about features, usage, troubleshooting, and policies. "
        "Base your FAQs on recent, relevant web data WITHOUT EVER citing, mentioning, marking, or listing any sources, references, URLs, or citations in the output. "
        "Structure your output exactly as:\n"
        "# Frequently Asked Questions\n"
        "Clear, concise answers to the most common questions about the product.\n\n"
        "# FAQs\n"
        "- **Question 1?** Detailed, helpful answer.\n"
        "- **Question 2?** Detailed, helpful answer.\n"
        "- ... (Aim for 8-12 FAQs covering setup, features, issues, and support).\n\n"
        "Output ONLY this formatted text—no introductions, extra content, citations, sources, or any markings. Use markdown bold for questions. Aim for depth and practicality in answers."
    ),

    "related_products_alternatives": (
        "You are an expert product analyst. Provide a comprehensive analysis of related products and alternatives based on web searches. "
        "Include accessories, bundles, upgrades from the same brand, and competitor options, with comparisons. "
        "Base your suggestions on recent, relevant web data WITHOUT EVER citing, mentioning, marking, or listing any sources, references, URLs, or citations in the output. "
        "Structure your output exactly as:\n"
        "# Related Products & Alternatives\n"
        "Recommendations for complementary items, upgrades, and competing options with reasoning.\n\n"
        "# Related & Complementary Products\n"
        "- Bullet points with descriptions and why they pair well (aim for 4-6 items).\n"
        "...\n\n"
        "# Alternatives\n"
        "- Bullet points comparing similar products from competitors, highlighting differences (aim for 4-6 items).\n"
        "...\n\n"
        "Output ONLY this formatted text—no introductions, extra content, citations, sources, or any markings. Use markdown for structure. Aim for depth in comparisons."
    ),

    "expert_third_party_reviews": (
        "You are an expert product analyst. Provide a comprehensive summary of expert and third-party reviews for the product based on web searches. "
        "Deliver in-depth insights on professional opinions, test results, awards, and consensus views. "
        "Base your analysis on recent, relevant web data WITHOUT EVER citing, mentioning, marking, or listing any sources, references, URLs, or citations in the output. "
        "Structure your output exactly as:\n"
        "# Expert & Third-Party Reviews\n"
        "Overall expert consensus and key highlights from professional evaluations.\n\n"
        "# Strengths Highlighted by Experts\n"
        "- Bullet points of praised aspects with explanations (aim for 4-6 bullets).\n"
        "...\n\n"
        "# Criticisms & Limitations\n"
        "- Bullet points of noted weaknesses (aim for 4-6 bullets).\n"
        "...\n\n"
        "# Notable Quotes or Summaries\n"
        "2-4 paraphrased key takeaways from experts.\n\n"
        "Output ONLY this formatted text—no introductions, extra content, citations, sources, or any markings. Use markdown for structure. Aim for balanced depth."
    ),

    "customer_ratings_reviews_summary": (
        "You are an expert product analyst. Provide a comprehensive summary of customer ratings and reviews for the product based on web searches. "
        "Deliver in-depth insights on overall sentiment, common themes, and aggregated data. "
        "Base your analysis on recent, relevant web data WITHOUT EVER citing, mentioning, marking, or listing any sources, references, URLs, or citations in the output. "
        "Structure your output exactly as:\n"
        "# Customer Ratings & Reviews Summary\n"
        "Overall rating (e.g., 4.3/5) and key sentiment trends.\n\n"
        "# Positive Themes\n"
        "- Bullet points of common praises with examples (aim for 4-6 bullets).\n"
        "...\n\n"
        "# Negative Themes\n"
        "- Bullet points of common complaints with examples (aim for 4-6 bullets).\n"
        "...\n\n"
        "# Notable User Quotes\n"
        "2-3 paraphrased or summarized standout reviews.\n\n"
        "Output ONLY this formatted text—no introductions, extra content, citations, sources, or any markings. Use markdown for structure. Aim for depth and balance."
    )
}

def extract_image_urls(data: Dict[str, Any]) -> List[str]:
    images = data.get('images', [])
    urls = []
    
    for img in images[:SEARCH_IMAGE_LIMIT]:
        if isinstance(img, dict) and 'original' in img:
            original = img['original']
            if isinstance(original, dict) and 'link' in original:
                urls.append(original['link'])
    
    return urls


async def fetch_images(company: str, product: str) -> List[str]:
    if not product:
        return []
    
    
    if not SEARCH_API_KEY:
        print("No SEARCH_API_KEY configured")
        return []
    
    query = f"images of {product} by {company} ".strip().lower()
    params = {
        "engine": "google_images",
        "q": query,
        "api_key": SEARCH_API_KEY,
        "num": SEARCH_IMAGE_LIMIT,
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
                return extract_image_urls(data)
    
    try:
        return await retry_on_failure(fetch_coro, max_retries=MAX_RETRIES)
    except Exception as e:
        print(f"Image fetch error: {str(e)}")
        return []




async def create_perplexity_review_stream(
    product: str,
    company: str,
    clarification: Optional[str],
    custom_filter: Optional[str],
    is_deepresearch_needed: bool,
    sys_promt: Optional[str],
    perplexity_client: AsyncOpenAI,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    limiter = get_rate_limiter()
    await limiter.acquire()

    if sys_promt == "product_images":
        image_urls = await fetch_images(company=company, product=product.replace(" ", "-"))
        if image_urls:
            yield "# Product Images\n\n\n\n"
            yield "<product-images>\n"
            for url in image_urls:
                yield f"{url}\n"
            yield "</product-images>\n\n"
        else:
            yield "No relevant product images found.\n"
        
        # Log usage
        db.add(LLMUsage(
            feature="perplexity_review_stream",
            model="image_search",
            input_tokens=0,
            output_tokens=50,
            total_tokens=50,
            cost_usd=0.0,
            latency_ms=0,
            status="success",
        ))
        await db.commit()
    yield "\n\n\n---\n\n\n"
    if is_deepresearch_needed:
        additional_params = {"search_results": 10}
    else:
        additional_params = {"search_results": 5}

    system_prompt = PRODUCT_ANALYSIS_PROMPT.get(sys_promt, PRODUCT_ANALYSIS_PROMPT["customer_ratings_reviews_summary"])
    filter_part = f"Focus on: {custom_filter}." if custom_filter else ""
    clarif_part = f"User clarification: {clarification}." if clarification else ""
    user_prompt = f"{filter_part} {clarif_part} Analyze the product '{product}' from '{company}'. Provide the comprehensive product analysis."

    model = "sonar"  # This is correct and working!
    input_str = system_prompt + "\n\n" + user_prompt
    input_tokens = count_tokens(input_str, model)
    output_tokens = 0
    usage_status = "success"
    start = time.time()

    async def create_coro():
        return await perplexity_client.chat.completions.create(
            model="sonar",  # Double-check: exactly like this
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            stream=True,
            max_tokens=2000,
            extra_body=additional_params
        )

    try:
        stream = await retry_on_failure(create_coro)
        full_response = None  # To capture final response for sources

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                text = chunk.choices[0].delta.content
                yield text
                output_tokens += count_tokens(text, model)
            full_response = chunk
        sources = []
        if full_response and hasattr(full_response, "model_extra") and full_response.model_extra:
            extra = full_response.model_extra
            if "sources" in extra:
                sources = extra["sources"]
            elif "citations" in extra:
                sources = extra["citations"]
            elif "search_results" in extra:
                sources = [r.get("url") or r.get("link") for r in extra["search_results"] if r.get("url") or r.get("link")]

        if sources:
            yield "\n\n**Sources:**\n"
            for i, src in enumerate(sources[:10], 1):
                if isinstance(src, str):
                    yield f"{i}. {src}\n"
                elif isinstance(src, dict):
                    title = src.get("title", "Source")
                    url = src.get("url") or src.get("link", "")
                    if url:
                        yield f"{i}. [{title}]({url})\n"
                    else:
                        yield f"{i}. {title}\n"

    except Exception as e:
        usage_status = "failed"
        error_msg = json.dumps({"error": "Generation failed", "details": str(e)})
        yield error_msg
        output_tokens += count_tokens(error_msg, model)
    finally:
        latency_ms = int((time.time() - start) * 1000)
        total_cost = calculate_llm_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        db.add(LLMUsage(
            feature="perplexity_review_stream",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=total_cost,
            latency_ms=latency_ms,
            status=usage_status,
        ))
        await db.commit()

def init(app):
    @app.post("/reviews")
    async def get_reviews(
        request: ProductCompanyRequest,
        client: Annotated[AsyncOpenAI, Depends(get_openai_client)],
        db: AsyncSession = Depends(get_db),
        _=Depends(Accounts.get_current_user)
    ):
        if not request.product_company.strip():
            return JSONResponse(
                status_code=400,
                content={"detail": "product_company is required"}
            )
        try:
            # Validate and extract
            extract = await validate_and_extract(
                request.product_company,
                request.clarification,
                client,
                db
            )
            print("extract: ", extract)
        
            # Check for needs_clarification first
            if extract.get("needs_clarification"):
                return JSONResponse(
                    status_code=200,
                    content={
                        "needs_clarification": True,
                        "question": extract.get("question", "Could you provide more details?"),
                        "partial": {
                            "product": extract.get("product"),
                            "company": extract.get("company")
                        }
                    }
                )
            # Ensure we have both product and company
            if not extract.get("product") or not extract.get("company"):
                return JSONResponse(
                    status_code=200,
                    content={
                        "needs_clarification": True,
                        "question": "I couldn't identify the product and company. Can you provide more details?",
                        "partial": {
                            "product": extract.get("product"),
                            "company": extract.get("company")
                        }
                    }
                )
            product = extract['product']
            company = extract['company']
        
        except HTTPException as he:
            raise he
        except Exception as e:
            logger.error(f"Error in get_reviews extraction: {e}")
            return JSONResponse(
                status_code=200,
                content={
                    "needs_clarification": True,
                    "question": "I encountered an error processing your request. Could you rephrase your query?",
                    "partial": {"product": None, "company": None}
                }
            )
        # Generate streaming response
        try:
            perplexity_stream = create_perplexity_review_stream(
                product, company, request.clarification, request.custom_filter,
                request.is_deepresearch_needed,request.sys_promt, perplexity_client ,db
            )
        except Exception as e:
            logger.error(f"Error creating perplexity stream: {e}")
            raise HTTPException(status_code=503, detail=f"Analysis generation failed: {str(e)}")
        return StreamingResponse(
            perplexity_stream,
            media_type="text/plain",
            headers={"X-Accel-Buffering": "no"}
        )