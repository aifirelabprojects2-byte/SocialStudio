# meta_poster/threads.py
from typing import Optional, List
from .base import BaseMetaPoster
from .utils import build_caption

class ThreadsPoster(BaseMetaPoster):
    def __init__(self, page_id: str = None, access_token: str = None):
        super().__init__(page_id, access_token)
        self.ig_user_id = self._get_ig_business_id()  # Threads uses same ID

    def _get_ig_business_id(self) -> str:
        url = f"{self.BASE_URL}/{self.page_id}"
        params = {"fields": "instagram_business_account", "access_token": self.access_token}
        data = self._request("GET", url, params=params)
        ig_account = data.get("instagram_business_account")
        if not ig_account:
            raise ValueError("No Instagram account linked (required for Threads)")
        return ig_account["id"]

    def post(
        self,
        text: str,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
        hashtags: Optional[List[str]] = None
    ) -> str:
        """Post to Threads"""
        final_text = build_caption(text, hashtags)

        url = f"{self.BASE_URL}/{self.ig_user_id}/threads"

        payload = {
            "media_type": "TEXT" if not (image_url or video_url) else "IMAGE" if image_url else "VIDEO",
            "text": final_text,
            "access_token": self.access_token,
        }

        if image_url:
            payload["image_url"] = image_url
        if video_url:
            payload["video_url"] = video_url

        data = self._request("POST", url, data=payload)
        thread_id = data["id"]
        print(f"Threads post successful: {thread_id}")
        return thread_id