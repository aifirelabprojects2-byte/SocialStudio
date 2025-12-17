import os
import json
import time
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

from Database import init_db

load_dotenv()

perplexity_client = AsyncOpenAI(
    api_key=os.getenv("PERPLEXITY_API_KEY"),
    base_url="https://api.perplexity.ai"
)

class SimpleRateLimiter:
    def __init__(self, max_concurrent=5, rpm=60):
        self.sem = asyncio.Semaphore(max_concurrent)
        self.rpm = rpm
        self.tokens = rpm
        self.last = time.time()
        self.lock = asyncio.Lock()

    async def wait(self):
        async with self.sem:
            async with self.lock:
                now = time.time()
                elapsed = now - self.last
                self.tokens = min(self.rpm, self.tokens + elapsed * (self.rpm / 60))
                self.last = now
                if self.tokens < 1:
                    await asyncio.sleep((1 - self.tokens) * (60 / self.rpm))
                    self.tokens = 1
                self.tokens -= 1

limiter = SimpleRateLimiter(
    max_concurrent=int(os.getenv("MAX_CONCURRENT", "5")),
    rpm=int(os.getenv("RPM_LIMIT", "60"))
)

async def enrich_company(question: str) -> dict:
    ques = question.strip()
    if not ques:
        return {"summary": "", "details": {}, "sources": []}

    if not os.getenv("PERPLEXITY_API_KEY"):
        return {
            "summary": "Perplexity API key missing.",
            "details": {},
            "sources": []
        }

    await limiter.wait()

    system_prompt = (
        "fetch details about this company product"
    )

    try:
        response = await perplexity_client.chat.completions.create(
            model="sonar",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{ques}"}
            ],
            temperature=0.1,
            max_tokens=800,
            extra_body={
        "search_results": 5
    }
            
        )

        content = response.choices[0].message.content.strip()
        return content

    except Exception as e:
        return {
           f"error occured {e}"
        }

# print(asyncio.run(enrich_company("whtai developed by aifirelab")))

# asyncio.run(init_db())