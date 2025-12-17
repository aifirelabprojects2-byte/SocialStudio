from pydantic import BaseModel, Field
from typing import  Optional
from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from Database import ImageTheme, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import  select, delete


class ImageThemeCreate(BaseModel):
    name: str = Field(..., description="Unique name of the theme")
    description: Optional[str] = None


class ImageThemeResponse(BaseModel):
    theme_id: str
    name: str
    description: Optional[str]
    created_at: str

def init(app):
    
    @app.get("/api/themes")
    async def get_themes(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(ImageTheme).order_by(ImageTheme.created_at.desc()))
        themes = result.scalars().all()

        return [
            {
                "theme_id": t.theme_id,
                "name": t.name,
                "description": t.description or "",
                "created_at": t.created_at.isoformat(),
            }
            for t in themes
        ]


    @app.post("/api/themes/create")
    async def create_theme(
        payload: ImageThemeCreate,
        db: AsyncSession = Depends(get_db)
    ):
        # Check if name already exists
        exists = await db.execute(select(ImageTheme).where(ImageTheme.name == payload.name))
        if exists.scalars().first():
            raise HTTPException(400, "Theme name already exists")

        theme = ImageTheme(
            name=payload.name,
            description=payload.description
        )
        db.add(theme)
        await db.commit()
        await db.refresh(theme)

        return {"message": "Theme created successfully", "theme_id": theme.theme_id}


    @app.delete("/api/themes/{theme_id}")
    async def delete_theme(theme_id: str, db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(ImageTheme).filter(ImageTheme.theme_id == theme_id))
        theme = result.scalars().first()
        if not theme:
            raise HTTPException(status_code=404, detail="Theme not found")

        await db.execute(delete(ImageTheme).where(ImageTheme.theme_id == theme_id))
        await db.commit()

        return JSONResponse(status_code=200, content={"message": "Theme deleted successfully"})

