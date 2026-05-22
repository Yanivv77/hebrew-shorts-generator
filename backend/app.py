import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Optional

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from s3_uploader import upload_actor, upload_clip
from saasshorts import (
    analyze_saas,
    generate_actor_images,
    generate_full_video,
    generate_scripts,
    research_saas_online,
    scrape_website,
)

MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "3"))
JOB_RETENTION_SECONDS = int(os.environ.get("JOB_RETENTION_SECONDS", "3600"))

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))
UPLOADS_DIR = os.environ.get("UPLOADS_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads"))

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

jobs: Dict[str, dict] = {}
job_queue: asyncio.Queue = asyncio.Queue()
concurrency_semaphore: asyncio.Semaphore


@asynccontextmanager
async def lifespan(app):
    global concurrency_semaphore
    concurrency_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
    asyncio.create_task(process_job_queue())
    asyncio.create_task(cleanup_old_jobs())
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# --- Pydantic models ---

class AnalyzeRequest(BaseModel):
    url: str
    description: Optional[str] = None
    num_scripts: int = 3
    language: str = "he"
    actor_gender: str = "female"


class ActorOptionsRequest(BaseModel):
    actor_description: str
    num_options: int = 3


# --- Endpoints ---

@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/api/ugc/analyze")
async def analyze(req: AnalyzeRequest, x_gemini_key: Optional[str] = Header(None)):
    gemini_key = x_gemini_key or os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(400, "Gemini API key required (X-Gemini-Key header or GEMINI_API_KEY env)")

    loop = asyncio.get_event_loop()
    scraped = await loop.run_in_executor(None, scrape_website, req.url)
    web_research = await loop.run_in_executor(None, research_saas_online, req.url, gemini_key)
    analysis = await loop.run_in_executor(None, analyze_saas, scraped, gemini_key, web_research)
    scripts = await loop.run_in_executor(
        None, generate_scripts, analysis, gemini_key, req.num_scripts, "ugc", req.language, req.actor_gender
    )

    return {"analysis": analysis, "scripts": scripts}


@app.post("/api/ugc/actor-options")
async def actor_options(req: ActorOptionsRequest, x_fal_key: Optional[str] = Header(None)):
    fal_key = x_fal_key or os.environ.get("FAL_API_KEY")
    if not fal_key:
        raise HTTPException(400, "fal.ai API key required (X-Fal-Key header or FAL_API_KEY env)")

    title_slug = f"opt_{uuid.uuid4().hex[:8]}"
    loop = asyncio.get_event_loop()
    paths = await loop.run_in_executor(
        None, generate_actor_images, req.actor_description, fal_key, UPLOADS_DIR, title_slug, req.num_options
    )

    urls = []
    for path in paths:
        s3_url = upload_actor(path)
        urls.append(s3_url if s3_url else f"/uploads/{os.path.basename(path)}")

    return {"images": urls}


@app.post("/api/ugc/actor-upload")
async def actor_upload(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "actor.png")[1] or ".png"
    filename = f"actor_{uuid.uuid4().hex}{ext}"
    dest = os.path.join(UPLOADS_DIR, filename)
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    return {"url": f"/uploads/{filename}"}


# --- Background workers (stubs until commit 7/8) ---

async def process_job_queue():
    while True:
        await asyncio.sleep(1)


async def cleanup_old_jobs():
    while True:
        await asyncio.sleep(300)


# --- Static file mounts (after all routes) ---

app.mount("/videos", StaticFiles(directory=OUTPUT_DIR), name="videos")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
