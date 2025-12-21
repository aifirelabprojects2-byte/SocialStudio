import os
import time
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

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

    system_prompt = ("You are an expert product analyst")

    try:
        response = await perplexity_client.chat.completions.create(
            model="sonar",  # Recommended: sonar-pro for better search and citations; fallback to "sonar" if needed
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": ques}
            ],
            temperature=0.1,
            max_tokens=800,
            extra_body={
                "search_recency_days": 365,  # Optional: adjust for recency if needed
            }
        )

        content = response.choices[0].message.content.strip()

        # Extract sources if the model includes them at the end
        sources = []
        if "sources" in response.model_extra:
            sources = response.model_extra["sources"]  # List of URLs or detailed sources
        elif "citations" in response.model_extra:
            sources = response.model_extra["citations"]
        elif "search_results" in response.model_extra:
            sources = [result.get("url", "") for result in response.model_extra["search_results"] if "url" in result]

        return {
            "summary": content,
            "details": {},  # Can be extended if needed
            "sources": sources
        }

    except Exception as e:
        return {
            "error": f"Error occurred: {str(e)}",
            "sources": []
        }

# Example usage
result = asyncio.run(enrich_company("laban product images from nadec saudi arabia"))
print(result["summary"])
if result.get("sources"):
    print("\nSources:")
    for i, src in enumerate(result["sources"], 1):
        print(f"[{i}] {src}")
      
        
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
        "You are an expert product analyst. Provide a visual showcase of the product based on web searches for high-quality images. "
        "Select and describe the most representative images, focusing on different angles, features in use, and key details. "
        "Base your selection on recent, relevant web data WITHOUT EVER citing, mentioning, marking, or listing any sources, references, URLs, or citations in the output. "
        "Structure your output exactly as:\n"
        "# Product Images\n"
        "A curated gallery of the product's visuals, with descriptive captions highlighting what each image shows.\n\n"
        "# Image Gallery\n"
        "- ![Caption describing the image, e.g., Front view showing design and ports](image_url_1)\n"
        "- ![Caption describing the image, e.g., Side angle with dimensions highlighted](image_url_2)\n"
        "- ... (Aim for 5-8 images covering multiple views, close-ups, and real-world use).\n\n"
        "Output ONLY this formatted text—no introductions, extra content, citations, sources, or any markings. Use markdown image syntax exclusively for embedding. Ensure captions are detailed and insightful."
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

instruction = PRODUCT_ANALYSIS_PROMPT.get("expert_third_party_reviews", PRODUCT_ANALYSIS_PROMPT["customer_ratings_reviews_summary"])

print(instruction)