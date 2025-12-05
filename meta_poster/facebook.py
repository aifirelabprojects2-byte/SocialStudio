from pathlib import Path
import tempfile
from typing import Optional, List
from urllib.parse import urlparse
import requests
from .utils import build_caption
import os


class FacebookPoster:
    BASE_URL = "https://graph.facebook.com/v20.0"  
    def __init__(self, page_id: str, page_access_token: str):
        self.page_id = str(page_id)
        self.page_access_token = page_access_token
        self.session = requests.Session()

    def _request(self, method: str, url: str, **kwargs):
        params = kwargs.pop("params", {})
        params["access_token"] = self.page_access_token

        response = self.session.request(method, url, params=params, **kwargs)

        if response.status_code >= 400:
            try:
                error_detail = response.json()
            except ValueError:
                error_detail = response.text
            raise RuntimeError(f"Facebook API error {response.status_code}: {error_detail}")

        return response.json()

    def post_text(
        self,
        message: str,
        link: Optional[str] = None,
        hashtags: Optional[List[str]] = None,
    ):
        final_msg = build_caption(message, hashtags)

        url = f"{self.BASE_URL}/{self.page_id}/feed"
        payload = {"message": final_msg}

        if link:
            payload["link"] = link

        return self._request("POST", url, data=payload)

    def post_photo(
        self,
        message: str,
        image: str,  
        hashtags: Optional[List[str]] = None,
        published: bool = True,
    ) -> dict:

        final_caption = build_caption(message, hashtags)
        url = f"{self.BASE_URL}/{self.page_id}/photos"

        data = {
            "caption": final_caption,
            "published": str(published).lower(),
        }

        # Case 1: Local file path
        if os.path.isfile(image):
            with open(image, "rb") as f:
                files = {"source": f}
                return self._request("POST", url, data=data, files=files)

        # Case 2: Remote URL
        elif isinstance(image, str) and image.startswith(("http://", "https://")):
            try:
                # Stream download with timeout and proper headers
                response = requests.get(
                    image,
                    stream=True,
                    timeout=30,
                    headers={"User-Agent": "FacebookPoster/1.0"},
                    allow_redirects=True
                )
                response.raise_for_status()

                # Basic content-type check
                content_type = response.headers.get("content-type", "")
                if not content_type.startswith("image/"):
                    raise ValueError(f"URL does not point to an image: {content_type}")

                # Create secure temp file with proper extension
                suffix = Path(urlparse(image).path).suffix or ".jpg"
                if suffix.lower() not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
                    suffix = ".jpg"

                temp_file = tempfile.NamedTemporaryFile(
                    delete=False, suffix=suffix, prefix="fb_upload_"
                )
                temp_path = temp_file.name
                temp_file.close()

                try:
                    # Stream write to avoid loading full image in memory
                    with open(temp_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                    # Now upload from temp file
                    with open(temp_path, "rb") as f:
                        files = {"source": ("image" + suffix, f, content_type)}
                        result = self._request("POST", url, data=data, files=files)

                    return result

                finally:
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass

            except requests.RequestException as e:
                raise ConnectionError(f"Failed to download image from URL: {image} | {e}")
            except Exception as e:
                raise RuntimeError(f"Error processing image URL {image}: {e}")

        else:
            raise ValueError("image must be a valid local file path or http(s) URL")