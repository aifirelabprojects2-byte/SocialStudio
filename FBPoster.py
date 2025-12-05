import os
import logging
import requests
import json
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FacebookPagePoster:
    BASE_URL = "https://graph.facebook.com/v24.0"

    def __init__(self, page_id: str = None, access_token: str = None):
        self.page_id = page_id or os.getenv("PAGE_ID")
        self.access_token = access_token or os.getenv("FB_LONG_LIVED_USER_ACCESS_TOKEN")
        
        if not self.page_id or not self.access_token:
            raise ValueError("PAGE_ID and FB_LONG_LIVED_USER_ACCESS_TOKEN must be set in .env")

    def post_to_feed(
        self,
        message: str,
        image_path: Optional[str] = None,
        hashtags: Optional[list[str]] = None,
        link: Optional[str] = None
    ) -> dict:

        final_message = self._build_message(message, hashtags)

        if image_path:
            return self._post_photo_with_feed(message=final_message, image_path=image_path)
        else:
            return self._post_text_only(message=final_message, link=link)

    def _build_message(self, message: str, hashtags: Optional[list[str]]) -> str:
        if not hashtags:
            return message.strip()
        hashtag_str = " " + " ".join([f"#{tag.replace(' ', '').strip('#')}" for tag in hashtags if tag])
        return f"{message.strip()}{hashtag_str}"

    def _post_text_only(self, message: str, link: Optional[str] = None) -> dict:
        url = f"{self.BASE_URL}/{self.page_id}/feed"
        payload = {
            "message": message,
            "access_token": self.access_token
        }
        if link:
            payload["link"] = link

        logger.info("Posting text/link to Facebook Page...")
        return self._make_request("POST", url, data=payload)

    def _post_photo_with_feed(self, message: str, image_path: str) -> dict:
        """Upload photo using temporary=true, then attach to feed post"""
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Step 1: Upload photo with temporary=true to get media ID (no unpublished issues)
        upload_url = f"{self.BASE_URL}/{self.page_id}/photos"
        
        with open(image_path, "rb") as f:
            files = {"source": f}
            data = {
                "caption": message,  # Optional: sets caption if no feed post
                "access_token": self.access_token,
                "temporary": "true",  # Key: Creates usable temp object without publishing
                "published": "false"  # Required with temporary=true
            }
            logger.info(f"Uploading temporary photo: {image_path}")
            response = requests.post(upload_url, data=data, files=files)
        
        response_data = self._handle_response(response, "Temporary photo upload")
        photo_id = response_data.get("id")
        if not photo_id:
            raise Exception(f"Failed to get photo ID: {response_data}")

        # Step 2: Publish to feed using attached_media (JSON-encoded)
        feed_url = f"{self.BASE_URL}/{self.page_id}/feed"
        attached_media = json.dumps([{"media_fbid": photo_id, "type": "photo"}])
        payload = {
            "message": message,
            "attached_media": attached_media,
            "access_token": self.access_token,
            "published": "true"  # Ensures final post is published
        }

        logger.info("Publishing photo post to feed...")
        return self._make_request("POST", feed_url, data=payload)

    def _make_request(self, method: str, url: str, **kwargs) -> dict:
        try:
            response = requests.request(method, url, timeout=60, **kwargs)
            response.raise_for_status()
            result = response.json()
            return result
        except requests.exceptions.HTTPError as e:
            try:
                error_detail = response.json()
                error = error_detail.get("error", {})
                logger.error(f"API Error {error.get('code')}: {error.get('message')} ({error.get('type')})")
            except:
                logger.error(f"HTTP Error: {response.text}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise

    def _handle_response(self, response: requests.Response, action: str) -> dict:
        try:
            data = response.json()
            if 200 <= response.status_code < 300:
                post_id = data.get("id") or data.get("post_id")
                if post_id:
                    logger.info(f"{action} successful! ID: {post_id}")
                return data
            else:
                error = data.get("error", {})
                logger.error(f"{action} failed: {error.get('message')} (Code: {error.get('code')})")
                return data
        except ValueError:
            logger.error(f"Invalid JSON: {response.text}")
            return {"error": "Invalid JSON response"}


