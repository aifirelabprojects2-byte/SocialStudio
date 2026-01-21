import requests
import json
import os
import uuid
from typing import List, Dict, Any

from fastapi import Depends, HTTPException
from sqlalchemy import update, select 
from sqlalchemy.ext.asyncio import AsyncSession 
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from Database import DesignRecord, get_db 

load_dotenv()

class Variation(BaseModel):
    heading: str = Field(..., max_length=40, description="Short catchy heading. STRICTLY 3 to 5 words maximum.")
    body: str = Field(..., max_length=180, description="Brief body text")
    unsplash_query: str
    text_color: str
    bg_color: str

class BatchDesignResponse(BaseModel):
    templates_output: List[Variation]
    common_caption: str = Field(..., description="A single engaging social media caption for this post batch.")

class GenerateRequest(BaseModel):
    prompt: str

class RegenerateCaptionRequest(BaseModel):
    batch_id: str
    topic: str 

class CaptionResponse(BaseModel):
    caption: str

GPT_CLIENT = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Logic Class ---
class MultiTemplateGenerator:
    def __init__(self, template_folder: str):
        self.template_folder = template_folder
        self.client = GPT_CLIENT
        self.templates = {}
        if os.path.exists(template_folder):
            files = [f for f in os.listdir(template_folder) if f.endswith('.json')]
            for file in files:
                with open(os.path.join(template_folder, file), 'r') as f:
                    self.templates[file] = json.load(f)
        else:
            print(f"Warning: {template_folder} not found.")

    async def get_batch_ai_content(self, user_prompt: str, count: int) -> BatchDesignResponse:
        response = await self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": (
                        f"Generate {count} unique design variations and ONE overall social media caption. "
                        "CRITICAL CONSTRAINT: Each 'heading' must be between 3 and 5 words long. "
                        "Do not exceed 5 words. Keep body under 180 chars. "
                        "COLOR GUIDELINES: Select professional, sophisticated color palettes. "
                        "Avoid high-saturation neon or 'vibrant' default colors. "
                        "Focus on muted tones, deep neutrals, or elegant pastel combinations. "
                        "Ensure high contrast between background and text for readability. "
                    )
                },
                {"role": "user", "content": user_prompt},
            ],
            response_format=BatchDesignResponse,
        )
        return response.choices[0].message.parsed

    def get_unsplash_images(self, query: str, count: int) -> List[str]:
        # Note: requests is synchronous. For a truly async app, consider using 'httpx'
        url = "https://api.unsplash.com/search/photos"
        params = {
            "query": query,
            "client_id": os.getenv("UNSPLASH_ACCESS_KEY"),
            "per_page": count,
            "orientation": "landscape"
        }
        try:
            resp = requests.get(url, params=params, timeout=5)
            if resp.status_code == 200:
                results = resp.json().get('results', [])
                return [img['urls']['regular'] for img in results]
        except Exception as e:
            print(f"Unsplash Error: {e}")
        return ["https://via.placeholder.com/800x600?text=No+Image"] * count

    def process_all(self, batch_data: BatchDesignResponse) -> List[Dict[str, Any]]:
        generated_results = []
        template_names = list(self.templates.keys())
        if not template_names:
            return []

        count = len(batch_data.templates_output)
        for i in range(count):
            design = batch_data.templates_output[i]
            template_name = template_names[i % len(template_names)]
            template_json = self.templates[template_name]

            images = self.get_unsplash_images(design.unsplash_query, 1)
            img_url = images[0] if images else ""

            new_data = json.loads(json.dumps(template_json))
            new_data['background'] = design.bg_color 

            for obj in new_data.get('objects', []):
                if obj['type'] in ['textbox', 'i-text', 'text']:
                    if len(obj.get('text', '')) < 20 or "Heading" in obj.get('text', ''): 
                        obj['text'] = design.heading
                        obj['fill'] = design.text_color
                    else:
                        obj['text'] = design.body
                        obj['fill'] = design.text_color
                elif obj['type'] == 'image':
                    obj['src'] = img_url

            generated_results.append({
                "id": str(uuid.uuid4()),
                "canvas_data": new_data
            })
        return generated_results

generator = MultiTemplateGenerator("./my_templates")

# --- API Routes ---
def init(app):
    @app.post("/api/generate/design")
    async def generate_designs(req: GenerateRequest, db: AsyncSession = Depends(get_db)):
        count = 6
        batch_id = str(uuid.uuid4())

        batch_info = await generator.get_batch_ai_content(req.prompt, count=count)
        processed_designs = generator.process_all(batch_info)
        
        final_output = []
        for item in processed_designs:
            db_record = DesignRecord(
                id=item["id"],
                batch_id=batch_id, 
                json_data=item["canvas_data"],
                caption=batch_info.common_caption
            )
            db.add(db_record)
            
            final_output.append({
                "id": item["id"],
                "design": item["canvas_data"]
            })
        
        await db.commit() # Await the commit

        return {
            "batch_id": batch_id,
            "caption": batch_info.common_caption,
            "designs": final_output
        }

    @app.get("/get-template-data/{template_id}")
    async def get_template_data(template_id: str, db: AsyncSession = Depends(get_db)):
        # Async query using select()
        result = await db.execute(select(DesignRecord).where(DesignRecord.id == template_id))
        record = result.scalars().first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Template not found")

        return {
            "json": record.json_data,
            "caption": record.caption
        }
        
    @app.post("/api/regenerate/caption")
    async def regenerate_caption(req: RegenerateCaptionRequest, db: AsyncSession = Depends(get_db)):
        try:
            completion = await GPT_CLIENT.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a social media expert. Write a clean, engaging, and professional social media caption. No hashtags or emojis."},
                    {"role": "user", "content": f"Write a caption for a post about: {req.topic}"}
                ],
                response_format=CaptionResponse,
            )
            
            new_caption = completion.choices[0].message.parsed.caption

            # Async update execution
            stmt = (
                update(DesignRecord)
                .where(DesignRecord.batch_id == req.batch_id)
                .values(caption=new_caption)
            )
            await db.execute(stmt)
            await db.commit()

            return {"caption": new_caption}

        except Exception as e:
            print(f"Error regenerating caption: {e}")
            raise HTTPException(status_code=500, detail="Caption generation failed")