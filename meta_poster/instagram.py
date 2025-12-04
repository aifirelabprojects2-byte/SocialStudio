# meta_poster/instagram.py
import time
from typing import Optional, List
from .base import BaseMetaPoster
from .utils import build_caption
from .exceptions import MetaAPIError

class InstagramPoster(BaseMetaPoster):
    def __init__(self, page_id: str = None, access_token: str = None):
        super().__init__(page_id, access_token)
        self.ig_user_id = self._get_ig_business_id()

    def _get_ig_business_id(self) -> str:
        url = f"{self.BASE_URL}/{self.page_id}"
        params = {"fields": "instagram_business_account", "access_token": self.access_token}
        data = self._request("GET", url, params=params)
        ig_account = data.get("instagram_business_account")
        if not ig_account:
            raise MetaAPIError("No Instagram Business Account linked to this Page")
        return ig_account["id"]

    def _create_container(
        self,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
        caption: str = "",
        is_reel: bool = False
    ) -> str:
        url = f"{self.BASE_URL}/{self.ig_user_id}/media"
        payload = {
            "caption": caption,
            "access_token": self.access_token,
        }

        if image_url:
            payload.update({"image_url": image_url, "media_type": "IMAGE"})
        elif video_url:
            payload.update({
                "video_url": video_url,
                "media_type": "REELS" if is_reel else "VIDEO"
            })
        else:
            payload.update({"media_type": "TEXT", "text": caption})

        data = self._request("POST", url, data=payload)
        return data["id"]

    def _publish(self, creation_id: str) -> str:
        url = f"{self.BASE_URL}/{self.ig_user_id}/media_publish"
        data = self._request("POST", url, data={
            "creation_id": creation_id,
            "access_token": self.access_token
        })
        return data["id"]

    def post(
        self,
        caption: str,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
        hashtags: Optional[List[str]] = None,
        is_reel: bool = False
    ) -> str:
        """Post to Instagram (image, video, reel, or text)"""
        final_caption = build_caption(caption, hashtags)

        container_id = self._create_container(
            image_url=image_url,
            video_url=video_url,
            caption=final_caption,
            is_reel=is_reel
        )

        # Wait a bit for processing (especially videos)
        if video_url:
            time.sleep(5)

        post_id = self._publish(container_id)
        print(f"Instagram post successful: {post_id}")
        return post_id