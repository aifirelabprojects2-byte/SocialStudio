import os
import time
import asyncio
from typing import Dict, Any
from openai import AsyncOpenAI
from dotenv import load_dotenv 
load_dotenv()
perplexity_client = AsyncOpenAI(
    api_key=os.getenv("PERPLEXITY_API_KEY"),
    base_url="https://api.perplexity.ai"
)

async def fetch_company_profile(company_url: str) -> Dict[str, Any]:
    company_url = company_url.strip()
    if not company_url:
        return {"error": "Company URL is required"}

    system_prompt = (
        "You are an expert company intelligence analyst.\n"
        "You MUST use live web search.\n find out company founders and co founder.. company latest product"
        "Only use information from the official website or very recent web sources.\n"
        "If information is missing or unclear, say so explicitly.\n"
        "Do NOT guess."
    )

    user_prompt = f"details {company_url} "

    try:
        response = await perplexity_client.chat.completions.create(
            model="sonar-pro",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=900,
            extra_body={
                "search_recency_days": 7,
                "search_domain_filter": [company_url.replace("https://", "").replace("http://", "")]
            }
        )

        content = response.choices[0].message.content.strip()

        sources = []
        extra = response.model_extra or {}
        if "sources" in extra:
            sources = extra["sources"]
        elif "citations" in extra:
            sources = extra["citations"]
        elif "search_results" in extra:
            sources = [r.get("url") for r in extra["search_results"] if r.get("url")]

        return {
            "data": content,   # JSON string from model
            "sources": sources
        }

    except Exception as e:
        return {
            "error": str(e),
            "sources": []
        }


# result = asyncio.run(fetch_company_profile("https://aifirelab.com"))

