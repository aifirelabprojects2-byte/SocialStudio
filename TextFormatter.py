import time
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse
import json
import Accounts
from Configs import GPT_MODEL,client
from CostCalc import calculate_llm_cost, count_tokens
from Database import  LLMUsage, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import StreamingResponse


class FormatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000, description="The text to format")
    style: Optional[Literal["professional", "concise", "formal"]] = Field(
        None, description="Predefined style (optional if custom_instruction is used)"
    )
    custom_instruction: Optional[str] = Field(
        None,
        max_length=1000,
        description="Custom formatting instructions. If provided, overrides 'style'."
    )

    @field_validator("custom_instruction")
    @classmethod
    def validate_custom_instruction(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) < 5:
                raise ValueError("custom_instruction must be at least 5 characters long")
        return v

    @field_validator("style")
    @classmethod
    def validate_style_with_custom(cls, v: Optional[str], info):
        values = info.data
        custom = values.get("custom_instruction")
        if v is None and (custom is None or custom.strip() == ""):
            raise ValueError("Either 'style' or 'custom_instruction' must be provided")
        return v


PREDEFINED_STYLES = {
    "professional": "Rewrite in clear, polished, professional business tone. Keep it natural and confident.",
    "concise": "Make it significantly shorter while keeping all key information. Be direct and crisp.",
    "formal": "Use formal language suitable for official letters or academic writing. Avoid contractions.",
}


async def generate_formatted_text_stream(text: str, instruction: str,db: AsyncSession):
    system_prompt = (
        "You are an expert editor. "
        "Rewrite the given text exactly according to the user's instruction. "
        "Output ONLY the formatted text — no quotes, no explanations, no markdown, "
        "no headers, no 'Here is...', nothing except the clean final text."
    )

    user_prompt = f"Instruction: {instruction}\n\nText to rewrite:\n{text}"
    input_text = user_prompt+system_prompt
    input_tokens = count_tokens(input_text,GPT_MODEL)
    output_tokens = 0
    generated_text = []
    start = time.time()
    strm_status = "success"
    try:
        stream = await client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            stream=True,
            max_tokens=2000,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                text = chunk.choices[0].delta.content
                yield text
                output_tokens += count_tokens(text,GPT_MODEL)
                generated_text.append(text)
                
    except Exception as e:
        strm_status = "failed"
        error_msg = json.dumps({"error": "Generation failed", "details": str(e)})
        yield error_msg
        
    finally:
        latency_ms = int((time.time() - start) * 1000)
        total_cost = calculate_llm_cost(
            model=GPT_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        db.add(LLMUsage(
            feature="text_formating",
            model=GPT_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=total_cost,
            latency_ms=latency_ms,
            status=strm_status,
        ))
        await db.commit()
def init(app):
    @app.post("/format-text")
    async def format_text(request: FormatRequest,db: AsyncSession = Depends(get_db),_=Depends(Accounts.get_current_user)):
        if not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")

        # Determine instruction
        if request.custom_instruction and request.custom_instruction.strip():
            instruction = request.custom_instruction.strip()
        elif request.style:
            instruction = PREDEFINED_STYLES.get(request.style, PREDEFINED_STYLES["professional"])
        else:
            raise HTTPException(status_code=400, detail="Either 'style' or 'custom_instruction' is required")

        return StreamingResponse(
            generate_formatted_text_stream(request.text, instruction,db),
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Content-Type-Options": "nosniff",
                "Access-Control-Allow-Origin": "*",
            },
        )

