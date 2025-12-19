# schemas/platform.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class PlatformListItem(BaseModel):
    platform_id: str
    name: str
    api_name: Optional[str]
    expires_at: Optional[datetime]
    is_active: bool

class PlatformUpdateBase(BaseModel):
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None

class FacebookUpdate(PlatformUpdateBase):
    page_id: Optional[str] = None
    page_access_token: Optional[str] = None

class InstagramUpdate(PlatformUpdateBase):
    page_id: Optional[str] = None
    ll_user_access_token: Optional[str] = None

class ThreadsUpdate(PlatformUpdateBase):
    threads_user_id: Optional[str] = None
    threads_long_lived_token: Optional[str] = None  # we'll store this in ll_user_access_token for simplicity
    threads_username: Optional[str] = None

class XUpdate(PlatformUpdateBase):
    consumer_key: Optional[str] = None
    consumer_secret: Optional[str] = None
    access_token: Optional[str] = None
    access_token_secret: Optional[str] = None
    bearer_token: Optional[str] = None