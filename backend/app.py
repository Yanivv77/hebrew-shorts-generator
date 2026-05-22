import asyncio
import os
from contextlib import asynccontextmanager
from typing import Dict, Optional

from fastapi import FastAPI, Header, HTTPException
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
