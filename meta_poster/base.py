# meta_poster/base.py
import os
import logging
import requests
from dotenv import load_dotenv
from typing import Optional
from .exceptions import MetaAPIError

load_dotenv()
logger = logging.getLogger("meta_poster")

class BaseMetaPoster:
    BASE_URL = "https://graph.facebook.com/v24.0"
    TIMEOUT = 30

    def __init__(
        self,
        page_id: Optional[str] = None,
        access_token: Optional[str] = None
    ):
        self.page_id = page_id 
        self.access_token = access_token 

        if not self.page_id or not self.access_token:
            raise ValueError("PAGE_ID and FB_LONG_LIVED_USER_ACCESS_TOKEN are required")

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "MetaPoster/1.0"})

    def _request(self, method: str, url: str, **kwargs) -> dict:
        try:
            response = self.session.request(
                method, url, timeout=self.TIMEOUT, **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_data = response.json().get("error", {})
            logger.error(f"API Error: {error_data}")
            raise MetaAPIError(
                message=error_data.get("message", "Unknown error"),
                error_code=error_data.get("code"),
                subcode=error_data.get("error_subcode")
            ) from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {e}")
            raise MetaAPIError("Network request failed") from e
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise MetaAPIError("Unexpected error occurred") from e