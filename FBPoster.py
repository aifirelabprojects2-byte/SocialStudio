import os
import logging
import requests
from typing import Optional
from dotenv import load_dotenv
from urllib.parse import urljoin

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FacebookPagePoster:
    BASE_URL = "https://graph.facebook.com/v24.0"

    def __init__(self, page_id: str = None, access_token: str = None):
        self.page_id = page_id or os.getenv("PAGE_ID")
        self.access_token = access_token or os.getenv("FB_LONG_LIVED_PAGE_TOKEN")  
        
        if not self.page_id or not self.access_token:
            raise ValueError("PAGE_ID and FB_LONG_LIVED_PAGE_TOKEN must be set in .env or passed explicitly")

    def post_to_feed(
        self,
        message: str,
        image_path: Optional[str] = None,
        hashtags: Optional[list[str]] = None,
        link: Optional[str] = None
    ) -> dict:

        final_message = self._build_message(message, hashtags)

        if image_path:
            return self._post_photo(message=final_message, image_path=image_path)
        else:
            return self._post_text(message=final_message, link=link)

    def _build_message(self, message: str, hashtags: Optional[list[str]]) -> str:
        """Append hashtags to message if provided"""
        if not hashtags:
            return message.strip()
        
        hashtag_str = " " + " ".join([f"#{tag.replace(' ', '').strip()}" for tag in hashtags if tag])
        return f"{message.strip()}{hashtag_str}"

    def _post_text(self, message: str, link: Optional[str] = None) -> dict:
        """Post text-only or text + link"""
        url = f"{self.BASE_URL}/{self.page_id}/feed"
        
        payload = {
            "message": message,
            "access_token": self.access_token
        }
        if link:
            payload["link"] = link

        logger.info("Posting text to Facebook Page...")
        return self._make_request("POST", url, data=payload)

    def _post_photo(self, message: str, image_path: str) -> dict:
        """Upload photo with caption"""
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Step 1: Upload photo
        upload_url = f"{self.BASE_URL}/{self.page_id}/photos"
        
        with open(image_path, "rb") as image_file:
            files = {"source": image_file}
            data = {
                "caption": message,
                "access_token": self.access_token,
                "published": "true"  # Set to "false" for draft
            }
            
            logger.info(f"Uploading photo post: {image_path}")
            response = requests.post(upload_url, data=data, files=files)
        
        return self._handle_response(response, "Photo")

    def _make_request(self, method: str, url: str, **kwargs) -> dict:
        """Centralized request handler with error logging"""
        try:
            response = requests.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            result = response.json()
            logger.info("Post successful!")
            return result
        except requests.exceptions.HTTPError as e:
            error_detail = response.json() if response.content else str(e)
            logger.error(f"HTTP Error: {error_detail}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def _handle_response(self, response: requests.Response, post_type: str) -> dict:
        """Handle and log API response"""
        try:
            data = response.json()
            if response.status_code == 200:
                post_id = data.get("id") or data.get("post_id")
                logger.info(f"{post_type} post successful! Post ID: {post_id}")
                return data
            else:
                error = data.get("error", {})
                logger.error(f"{post_type} post failed: {error.get('message')} (Code: {error.get('code')})")
                return data
        except ValueError:
            logger.error(f"Invalid JSON response: {response.text}")
            return {"error": "Invalid response from Facebook"}


# ============= USAGE EXAMPLE =============
if __name__ == "__main__":
    poster = FacebookPagePoster()

    poster.post_to_feed(
        message="Beautiful sunset from our office terrace today!",
        image_path="./static/media/0038f17f-e3d5-44dd-b212-34d9a6005025_20251203_002821.png",
        hashtags=["OfficeVibes", "Sunset", "TeamLife"]
    )

