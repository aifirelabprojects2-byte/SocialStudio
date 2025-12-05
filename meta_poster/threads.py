# meta_poster/threads.py
import time
import logging
import requests
from typing import Optional, List
from urllib.parse import quote
from .utils import build_caption  


logger = logging.getLogger("meta_poster.threads")

class ThreadsPoster:
    BASE_URL = "https://graph.threads.net/v1.0"
    TIMEOUT = 60
    MAX_RETRIES = 3
    RATE_LIMIT_BACKOFF = 65  # seconds

    def __init__(
        self,
        threads_user_id: str,
        access_token: str,
        username: str = "_pablo_dev_"  # for generating final URL
    ):
        self.threads_user_id = str(threads_user_id).strip()
        self.access_token = access_token.strip()
        self.username = username.strip().lstrip("@")

        if not self.threads_user_id or not self.access_token:
            raise ValueError("threads_user_id and access_token are required")

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SocialStudio-Threads/2.0 (+https://yoursite.com)"
        })

    def _request(self, method: str, url: str, **kwargs) -> dict:
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.request(method, url, timeout=self.TIMEOUT, **kwargs)
                data = response.json()

                if response.status_code in (200, 201):
                    return data

                error = data.get("error", {})
                code = error.get("code")
                msg = error.get("message", "")

                # Rate limit → smart backoff
                if code == 80001 or "rate limit" in msg.lower():
                    logger.warning(f"Threads rate limit hit. Sleeping {self.RATE_LIMIT_BACKOFF}s...")
                    time.sleep(self.RATE_LIMIT_BACKOFF)
                    continue

                # Token issue
                if code in (190, 368):
                    raise ValueError(f"Invalid/expired token: {msg}")

                logger.error(f"Threads API error {code}: {msg}")
                raise RuntimeError(f"Threads API error: {data}")

            except requests.exceptions.RequestException as e:
                if attempt == self.MAX_RETRIES - 1:
                    logger.exception("Network failure after retries")
                    raise
                time.sleep(2 ** attempt)

        raise RuntimeError("Max retries exceeded")

    def post(
        self,
        text: str,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
        hashtags: Optional[List[str]] = None,
        topic_tag: Optional[str] = None,
        spoiler: bool = False,
    ) -> str:

        

        if not text and not (image_url or video_url):
            raise ValueError("text or media is required")

        final_text = build_caption(text, hashtags or [])

        # Step 1: Create container
        media_type = "TEXT"
        payload = {
            "text": final_text,
            "access_token": self.access_token,
        }

        if image_url:
            media_type = "IMAGE"
            payload["image_url"] = image_url
        elif video_url:
            media_type = "VIDEO"
            payload["video_url"] = video_url

        payload["media_type"] = media_type

        if topic_tag:
            payload["topic_tag"] = topic_tag.lower()
        if spoiler:
            payload["spoiler"] = "true"

        logger.info(f"Creating Threads container (type={media_type}) for @{self.username}")
        container = self._request("POST", f"{self.BASE_URL}/{self.threads_user_id}/threads", data=payload)
        container_id = container["id"]

        # Step 2: Publish
        logger.info(f"Publishing container {container_id}")
        publish = self._request(
            "POST",
            f"{self.BASE_URL}/{self.threads_user_id}/threads_publish",
            data={"creation_id": container_id, "access_token": self.access_token}
        )

        post_id = publish["id"]
        post_url = f"https://www.threads.net/@{self.username}/post/{post_id}"

        logger.info(f"Threads post successful: {post_url}")
        return post_url