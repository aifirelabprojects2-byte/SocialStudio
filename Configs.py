import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

from ImgGen import ImageGenClient

load_dotenv()
GPT_MODEL="gpt-4o-mini"
FERNET_KEY = os.getenv("FERNET_KEY") 
IMG_BB_API_KEY = os.getenv('IMGBB_API')
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Set OPENAI_API_KEY in .env")

# LLM CLIENTS

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
image_client = ImageGenClient(api_key=os.getenv("IMG_API_KEY"))   
perplexity_client = AsyncOpenAI( api_key=os.getenv("PERPLEXITY_API_KEY"),base_url="https://api.perplexity.ai")
