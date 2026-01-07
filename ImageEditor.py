from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Any, Dict
from pydantic import BaseModel
from Database import get_db, DesignTemplate
from datetime import datetime

class TemplateCreate(BaseModel):
    name: str
    canvas_json: Dict[str, Any]  
    canvas_width: int
    canvas_height: int

class TemplateResponse(BaseModel):
    template_id: str
    name: str
    canvas_json: Dict[str, Any]
    canvas_width: int
    canvas_height: int
    created_at: datetime

    class Config:
        from_attributes = True
        
def init(app):
    @app.post("/api/templates", response_model=TemplateResponse)
    async def create_template(
        template_data: TemplateCreate, 
        db: AsyncSession = Depends(get_db)
    ):
        new_template = DesignTemplate(
            name=template_data.name,
            canvas_json=template_data.canvas_json,
            canvas_width=template_data.canvas_width,
            canvas_height=template_data.canvas_height
        )
        
        db.add(new_template)
        await db.commit()
        await db.refresh(new_template)
        
        return new_template

    @app.get("/api/templates", response_model=List[TemplateResponse])
    async def get_templates(db: AsyncSession = Depends(get_db)):
        result = await db.execute(
            select(DesignTemplate).order_by(desc(DesignTemplate.created_at))
        )
        templates = result.scalars().all()
        return templates

    @app.delete("/api/templates/{template_id}")
    async def delete_template(template_id: str, db: AsyncSession = Depends(get_db)):
        result = await db.execute(
            select(DesignTemplate).where(DesignTemplate.template_id == template_id)
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
            
        await db.delete(template)
        await db.commit()
        
        return {"status": "deleted", "template_id": template_id}
    

