import os
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
_session = requests.Session()

class ImageGenClient:
    def __init__(self, api_key: str):
        self.api_url = "https://gateway.pixazo.ai/flux-1-schnell/v1/getData"
        self.headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Ocp-Apim-Subscription-Key": api_key
        }

    def generate(self,
                 prompt: str,
                 width: int = 512,
                 height: int = 512,
                 num_steps: int = 4,
                 seed: Optional[int] = None) -> bytes:
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "num_steps": num_steps,
            "seed": seed if seed is not None else -1
        }

        resp = _session.post(self.api_url, headers=self.headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        image_url = data["output"]
        img_resp = _session.get(image_url, timeout=30)
        img_resp.raise_for_status()

        return img_resp.content,image_url





