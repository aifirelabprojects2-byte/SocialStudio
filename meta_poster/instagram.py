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

    def _get_container_status(self, container_id: str) -> dict:
        """Poll the container status to check if media processing is complete."""
        url = f"{self.BASE_URL}/{container_id}"
        params = {
            "fields": "status_code",  # Only request status_code (status_message does not exist)
            "access_token": self.access_token
        }
        return self._request("GET", url, params=params)

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
                "media_type": "REELS"
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
        media_url: Optional[str] = None,
        hashtags: Optional[List[str]] = None,
        is_reel: bool = False
    ) -> str:
        final_caption = build_caption(caption, hashtags)
        
        image_url = None
        video_url = None

        if media_url:
            video_extensions = ('.mp4', '.mov', '.avi', '.wmv', '.flv', '.mkv')
            
            if is_reel or media_url.lower().endswith(video_extensions):
                video_url = media_url
            else:
                image_url = media_url

        container_id = self._create_container(
            image_url=image_url,
            video_url=video_url,
            caption=final_caption,
            is_reel=is_reel
        )

        if video_url:
            # --- Polling for processing completion ---
            max_wait_seconds = 600  # 10 minutes max
            poll_interval = 10
            elapsed = 0

            print(f"Polling container {container_id} for FINISHED status...")  # Debug help

            while elapsed < max_wait_seconds:
                status_data = self._get_container_status(container_id)
                status_code = status_data.get("status_code")

                print(f"Current status_code: {status_code}")  # Debug: see what Meta returns

                if status_code == "FINISHED":
                    print("Video processing finished!")
                    break
                elif status_code == "ERROR":
                    raise MetaAPIError("Video processing failed (status_code: ERROR)")
                elif status_code == "EXPIRED":
                    raise MetaAPIError("Media container expired before processing completed")

                # Continue polling for IN_PROGRESS or other transient states
                time.sleep(poll_interval)
                elapsed += poll_interval
                poll_interval = min(poll_interval * 2, 60)

            else:
                raise MetaAPIError("Timeout: Video processing took too long (>10 minutes)")

            # --- Retry logic for publish (handles transient "not ready" even after FINISHED) ---
            max_publish_retries = 8
            publish_delay = 5

            for attempt in range(1, max_publish_retries + 1):
                try:
                    post_id = self._publish(container_id)
                    print(f"Instagram post successful (publish attempt {attempt}): {post_id}")
                    return post_id
                except MetaAPIError as e:
                    error_str = str(e).lower()
                    if ("media is not ready" in error_str or 
                        "2207027" in error_str or 
                        "9007" in error_str or
                        "media id is not available" in error_str):
                        if attempt < max_publish_retries:
                            print(f"Transient 'not ready' error – retrying publish in {publish_delay}s (attempt {attempt + 1}/{max_publish_retries})")
                            time.sleep(publish_delay)
                            publish_delay = min(publish_delay * 2, 60)
                            continue
                    raise

            raise MetaAPIError("Failed to publish media after maximum retries")

        else:
            # Images are synchronous
            post_id = self._publish(container_id)
            print(f"Instagram post successful: {post_id}")
            return post_id