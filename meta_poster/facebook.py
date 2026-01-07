import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Optional, List
from urllib.parse import urlparse
import requests
from .utils import build_caption

class FacebookPoster:
    BASE_URL = "https://graph.facebook.com/v20.0"

    def __init__(self, page_id: str, page_access_token: str):
        self.page_id = str(page_id)
        self.page_access_token = page_access_token
        self.session = requests.Session()

        mimetypes.init()

    def _request(self, method: str, url: str, **kwargs):
        # Ensure we have a data dict to work with
        data = kwargs.get("data", {})
        if not isinstance(data, dict):
            data = {}
        # Add access_token to the form body (works for both urlencoded and multipart)
        data["access_token"] = self.page_access_token
        kwargs["data"] = data

        response = self.session.request(method, url, **kwargs)

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

    def post_media(
        self,
        message: str,
        media: str,  # Can be local path or URL, Image or Video
        hashtags: Optional[List[str]] = None,
        published: bool = True,
    ) -> dict:
        temp_path = None
        local_file_path = media

        try:
            # 1. If it's a URL, download it to a temp file first
            if isinstance(media, str) and media.startswith(("http://", "https://")):
                temp_path = self._download_media(media)
                local_file_path = temp_path
            
            if not os.path.isfile(local_file_path):
                raise ValueError(f"File not found: {local_file_path}")

            # 2. Detect Mime Type
            mime_type, _ = mimetypes.guess_type(local_file_path)
            
            # Fallback for extensions mimetypes might miss
            if not mime_type:
                ext = Path(local_file_path).suffix.lower()
                if ext in ['.mp4', '.mov', '.avi', '.mkv']:
                    mime_type = 'video/mp4'
                elif ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    mime_type = 'image/jpeg'
                else:
                    raise ValueError(f"Could not determine media type for file: {local_file_path}")

            # 3. Configure Endpoint based on type
            final_caption = build_caption(message, hashtags)
            
            if mime_type.startswith("image/"):
                endpoint = f"{self.BASE_URL}/{self.page_id}/photos"
                # Photos API uses 'caption'
                data = {
                    "caption": final_caption,
                    "published": str(published).lower(),
                }
            elif mime_type.startswith("video/"):
                endpoint = f"{self.BASE_URL}/{self.page_id}/videos"
                # Videos API uses 'description'
                data = {
                    "description": final_caption,
                    "published": str(published).lower(),
                }
            else:
                raise ValueError(f"Unsupported media type: {mime_type}")

            # 4. Upload
            with open(local_file_path, "rb") as f:
                # Facebook accepts 'source' for both endpoints
                files = {"source": (os.path.basename(local_file_path), f, mime_type)}
                return self._request("POST", endpoint, data=data, files=files)

        finally:
            # 5. Cleanup temp file if we created one
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def _download_media(self, url: str) -> str:
        """
        Helper to download a file from a URL to a temp path.
        Returns the path to the temporary file.
        """
        try:
            response = requests.get(
                url, 
                stream=True, 
                timeout=60,
                headers={"User-Agent": "FacebookPoster/1.0"}
            )
            response.raise_for_status()
            
            # Try to guess extension from content-type or url
            content_type = response.headers.get("content-type", "")
            ext = mimetypes.guess_extension(content_type)
            if not ext:
                ext = Path(urlparse(url).path).suffix or ".tmp"
                
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, suffix=ext, prefix="fb_media_"
            )
            
            with open(temp_file.name, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return temp_file.name
            
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to download media: {e}")