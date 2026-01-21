import os
import re
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import  HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Text,
)

from openai import AsyncOpenAI
from dotenv import load_dotenv
from Database import Company,SyncSessionLocal
load_dotenv()


def human_copy_text(url: str, timeout: int = 20000) -> str:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = browser.new_page()
            page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            except:
                page.goto(url, wait_until="load", timeout=timeout)
            
            text = page.evaluate("""() => {
                const scripts = document.querySelectorAll('script, style, noscript');
                scripts.forEach(el => el.remove());
                return document.body.innerText || '';
            }""")
        finally:
            browser.close()
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:100000]

COMPANY_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "company_profile",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "company_name": {"type": ["string", "null"]},
                "company_details": {"type": ["string", "null"]},
                "company_products": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": ["string", "null"]},
                            "description": {"type": ["string", "null"]},
                            "url": {"type": ["string", "null"]},
                        },
                        "required": ["name", "description"]
                    }
                },
                "company_location": {"type": ["string", "null"]},
                "website_url": {"type": ["string", "null"]},
            },
            "required": ["company_name", "company_details", "company_products", "company_location"]
        }
    }
}

async def extract_company_info(page_text: str, page_url: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key: raise RuntimeError("OPENAI_API_KEY not set.")
    async with AsyncOpenAI(api_key=api_key) as client:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format=COMPANY_SCHEMA,
            messages=[
                {"role": "system", "content": "Extract professional company profile data."},
                {"role": "user", "content": f"URL: {page_url}\n\nText: {page_text[:30000]}"}
            ]
        )
        return json.loads(response.choices[0].message.content)

def to_dict(obj):
    if not obj: return None
    return {
        "id": obj.id,
        "website_url": obj.website_url,
        "company_name": obj.company_name,
        "company_details": obj.company_details,
        "company_location": obj.company_location,
        "company_products": obj.company_products,
        "created_at": obj.created_at.isoformat(),
        "updated_at": obj.updated_at.isoformat()
    }

def db_get_single():
    with SyncSessionLocal() as session:
        return to_dict(session.query(Company).first())

def db_replace_single(url: str, data: dict):
    with SyncSessionLocal() as session:
        session.query(Company).delete()
        
        obj = Company(
            website_url=url,
            company_name=data.get("company_name"),
            company_details=data.get("company_details"),
            company_location=data.get("company_location"),
            company_products=data.get("company_products")
        )
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return to_dict(obj)

def db_update_single(id: int, data: dict):
    with SyncSessionLocal() as session:
        obj = session.query(Company).filter(Company.id == id).first()
        if not obj: raise ValueError("Not found")
        if "company_name" in data: obj.company_name = data["company_name"]
        if "company_details" in data: obj.company_details = data["company_details"]
        if "company_location" in data: obj.company_location = data["company_location"]
        if "company_products" in data: obj.company_products = data["company_products"]
        obj.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(obj)
        return to_dict(obj)

def db_delete_single():
    with SyncSessionLocal() as session:
        deleted = session.query(Company).delete()
        session.commit()
        return deleted > 0

class FetchRequest(BaseModel):
    url: str

class UpdateRequest(BaseModel):
    company_name: Optional[str] = None
    company_details: Optional[str] = None
    company_location: Optional[str] = None
    company_products: Optional[List[Dict[str, Any]]] = None

def init(app):
    @app.get("/api/company")
    async def get_current_company():
        company = await asyncio.to_thread(db_get_single)
        return JSONResponse({"exists": bool(company), "company": company})

    @app.post("/api/company/fetch")
    async def fetch_and_replace_company(body: FetchRequest):
        url = body.url.strip()
        if not url: raise HTTPException(400, "URL required")
        try:
            page_text = await asyncio.to_thread(human_copy_text, url)
            extracted = await extract_company_info(page_text, url)
            created = await asyncio.to_thread(db_replace_single, url, extracted)
            return JSONResponse({"status": "replaced", "company": created})
        except Exception as e:
            raise HTTPException(500, str(e))

    @app.put("/api/company/{company_id}")
    async def update_company(company_id: int, body: UpdateRequest):
        try:
            updated = await asyncio.to_thread(db_update_single, company_id, body.dict(exclude_unset=True))
            return JSONResponse({"status": "ok", "company": updated})
        except Exception as e:
            raise HTTPException(500, str(e))

    @app.delete("/api/company")
    async def delete_company():
        try:
            deleted = await asyncio.to_thread(db_delete_single)
            return JSONResponse({
                "status": "deleted",
                "deleted": deleted
            })
        except Exception as e:
            raise HTTPException(500, str(e))
