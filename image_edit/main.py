from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List

app = FastAPI()

# 1. Mount Static folders
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")


LOGO_DB = [
    {"name": "FireLab Logo Light", "filename": "logo_dark.png"},
    {"name": "FireLab Logo Dark", "filename": "logo_light.png"}
]

@app.get("/api/logos")
async def get_logos():
    return LOGO_DB

@app.get("/")
async def read_index():
    return FileResponse('static/designstudio.html')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)