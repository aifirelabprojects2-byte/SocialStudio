from pydantic import BaseModel, Field
from typing import  Optional


class ImageThemeCreate(BaseModel):
    name: str = Field(..., description="Unique name of the theme")
    description: Optional[str] = None


class ImageThemeResponse(BaseModel):
    theme_id: str
    name: str
    description: Optional[str]
    created_at: str
