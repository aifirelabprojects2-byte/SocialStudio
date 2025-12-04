# meta_poster/facebook.py
from typing import Optional, List
from .base import BaseMetaPoster
from .utils import build_caption
import os

class FacebookPoster(BaseMetaPoster):
    def post_text(self, message: str, link: Optional[str] = None, hashtags: Optional[List[str]] = None):
        final_msg = build_caption(message, hashtags)
        url = f"{self.BASE_URL}/{self.page_id}/feed"
        payload = {"message": final_msg, "access_token": self.access_token}
        if link:
            payload["link"] = link
        return self._request("POST", url, data=payload)

    def post_photo(self, message: str, image_path: str, hashtags: Optional[List[str]] = None):
        if not os.path.isfile(image_path):
            raise FileNotFoundError(image_path)
        final_msg = build_caption(message, hashtags)
        url = f"{self.BASE_URL}/{self.page_id}/photos"
        with open(image_path, "rb") as f:
            files = {"source": f}
            data = {"caption": final_msg, "access_token": self.access_token}
            return self._request("POST", url, data=data, files=files)