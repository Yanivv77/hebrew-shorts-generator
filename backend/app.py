import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

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


class GenerateRequest(BaseModel):
    script_index: int
    scripts: List[dict]
    actor_image_url: Optional[str] = None
    voice_id: Optional[str] = None
    video_mode: str = "lowcost"


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


@app.post("/api/ugc/generate")
async def generate_video(
    req: GenerateRequest,
    x_fal_key: Optional[str] = Header(None),
    x_elevenlabs_key: Optional[str] = Header(None),
):
    fal_key = x_fal_key or os.environ.get("FAL_API_KEY")
    elevenlabs_key = x_elevenlabs_key or os.environ.get("ELEVENLABS_API_KEY")

    job_id = uuid.uuid4().hex
    jobs[job_id] = {
        "status": "queued",
        "logs": [],
        "result": None,
        "created_at": time.time(),
        "request": req.model_dump(),
        "fal_key": fal_key,
        "elevenlabs_key": elevenlabs_key,
    }
    await job_queue.put(job_id)
    return {"job_id": job_id, "status": "queued"}


# --- Background workers ---

async def process_job_queue():
    while True:
        job_id = await job_queue.get()
        asyncio.create_task(run_job(job_id))
        job_queue.task_done()


async def run_job(job_id: str):
    import httpx as _httpx

    async with concurrency_semaphore:
        job = jobs[job_id]
        job["status"] = "processing"
        req = job["request"]

        def log(msg: str):
            jobs[job_id]["logs"].append({"time": time.time(), "msg": msg})

        try:
            # Resolve actor_image_url to a local filesystem path
            actor_url = req.get("actor_image_url") or ""
            actor_path = None
            if actor_url.startswith("/uploads/"):
                actor_path = os.path.join(UPLOADS_DIR, actor_url[len("/uploads/"):])
            elif actor_url:
                log(f"Downloading actor image from {actor_url}")
                resp = _httpx.get(actor_url, timeout=30, follow_redirects=True)
                resp.raise_for_status()
                actor_path = os.path.join(UPLOADS_DIR, f"actor_{job_id}.png")
                with open(actor_path, "wb") as f:
                    f.write(resp.content)

            script = req["scripts"][req["script_index"]]
            config = {
                "fal_key": job["fal_key"],
                "elevenlabs_key": job["elevenlabs_key"],
                "voice_id": req.get("voice_id"),
                "selected_actor_path": actor_path,
                "video_mode": req.get("video_mode", "lowcost"),
            }
            output_dir = os.path.join(OUTPUT_DIR, job_id)
            os.makedirs(output_dir, exist_ok=True)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, generate_full_video, script, config, output_dir, log
            )

            video_url = upload_clip(result["video_path"], job_id)
            if not video_url:
                video_url = f"/videos/{job_id}/{result['video_filename']}"

            job["result"] = {"video_url": video_url, "cost": result["cost_estimate"]}
            job["status"] = "completed"

        except Exception as e:
            log(f"Error: {e}")
            job["status"] = "failed"


async def cleanup_old_jobs():
    while True:
        await asyncio.sleep(300)


# --- Static file mounts (after all routes) ---

app.mount("/videos", StaticFiles(directory=OUTPUT_DIR), name="videos")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
