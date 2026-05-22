import asyncio
import os
import time
import uuid

import httpx
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from s3_uploader import upload_actor, upload_clip, upload_to_gallery, list_gallery
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
    product_name: Optional[str] = None


class SocialPostRequest(BaseModel):
    video_url: str
    platforms: List[str]
    title: Optional[str] = None
    caption: Optional[str] = None
    scheduled_date: Optional[str] = None
    timezone: Optional[str] = "UTC"


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

            video_url = upload_clip(job_id, result["video_path"])
            if not video_url:
                video_url = f"/videos/{job_id}/{result['video_filename']}"

            job["result"] = {"video_url": video_url, "cost": result["cost_estimate"]}
            job["status"] = "completed"

            gallery_result = upload_to_gallery(
                video_path=result["video_path"],
                meta={
                    "title": script.get("title", ""),
                    "product_name": req.get("product_name") or script.get("title", ""),
                    "description": script.get("caption", ""),
                    "hashtags": script.get("hashtags", []),
                    "actor_image_path": result.get("actor_image"),
                },
            )
            if gallery_result:
                job["result"]["gallery_id"] = gallery_result["video_id"]
                job["result"]["thumbnail_url"] = gallery_result.get("actor_url", "")

        except Exception as e:
            log(f"Error: {e}")
            job["status"] = "failed"


async def cleanup_old_jobs():
    while True:
        await asyncio.sleep(300)
        cutoff = time.time() - JOB_RETENTION_SECONDS
        stale = [
            jid
            for jid, j in list(jobs.items())
            if j["created_at"] < cutoff and j["status"] in ("completed", "failed")
        ]
        for jid in stale:
            del jobs[jid]


@app.get("/api/ugc/status/{job_id}")
def job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {"status": job["status"], "logs": job["logs"], "result": job["result"]}


@app.get("/gallery", response_class=HTMLResponse)
def gallery_page():
    import json as _json
    videos = list_gallery()
    items_ld = [
        {
            "@type": "VideoObject",
            "name": v.get("title", ""),
            "description": v.get("description", ""),
            "thumbnailUrl": v.get("actor_url", ""),
            "contentUrl": v.get("video_url", ""),
            "uploadDate": v.get("created_at", ""),
        }
        for v in videos
    ]
    schema_ld = _json.dumps({
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "item": item}
            for i, item in enumerate(items_ld)
        ],
    }, ensure_ascii=False)

    cards_html = ""
    for v in videos:
        vid_id = v.get("video_id", "")
        thumb = v.get("actor_url", "")
        src = v.get("video_url", "")
        title = v.get("title", "")
        product = v.get("product_name", "")
        cards_html += f"""
        <a href="/gallery/{vid_id}" style="display:block;text-decoration:none;color:inherit;">
          <div style="background:#1a1a2e;border-radius:12px;overflow:hidden;">
            <video src="{src}" poster="{thumb}" muted loop preload="none"
              style="width:100%;aspect-ratio:9/16;object-fit:cover;display:block;"
              onmouseenter="this.play()" onmouseleave="this.pause();this.currentTime=0"></video>
            <div style="padding:12px;">
              <div style="font-weight:600;font-size:14px;margin-bottom:4px;">{title}</div>
              <div style="font-size:12px;color:#888;">{product}</div>
            </div>
          </div>
        </a>"""

    og_image = videos[0].get("actor_url", "") if videos else ""
    html = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>גלריית סרטונים | Hebrew Shorts</title>
<meta name="description" content="סרטונים שיווקיים קצרים עם שחקנים מבוססי AI">
<meta property="og:type" content="website">
<meta property="og:title" content="גלריית סרטונים | Hebrew Shorts">
<meta property="og:description" content="סרטונים שיווקיים קצרים עם שחקנים מבוססי AI">
<meta property="og:image" content="{og_image}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="גלריית סרטונים | Hebrew Shorts">
<meta name="twitter:image" content="{og_image}">
<script type="application/ld+json">{schema_ld}</script>
<style>
  body{{margin:0;background:#0d0d1a;color:#fff;font-family:system-ui,sans-serif;}}
  h1{{text-align:center;padding:32px 0 16px;font-size:28px;}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;padding:16px 24px 48px;max-width:1400px;margin:0 auto;}}
</style>
</head>
<body>
<h1>גלריית סרטונים</h1>
<div class="grid">{cards_html or '<p style="text-align:center;color:#888;">אין סרטונים עדיין</p>'}</div>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/gallery/{video_id}", response_class=HTMLResponse)
def gallery_video_page(video_id: str):
    import json as _json
    videos = list_gallery()
    v = next((x for x in videos if x.get("video_id") == video_id), None)
    if not v:
        return HTMLResponse(content="<h1>404 — Video not found</h1>", status_code=404)

    title = v.get("title", "")
    description = v.get("description", "")
    thumb = v.get("actor_url", "")
    src = v.get("video_url", "")
    upload_date = v.get("created_at", "")
    product = v.get("product_name", "")

    schema_ld = _json.dumps({
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": title,
        "description": description,
        "thumbnailUrl": thumb,
        "contentUrl": src,
        "uploadDate": upload_date,
    }, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | Hebrew Shorts</title>
<meta name="description" content="{description}">
<meta property="og:type" content="video.other">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{thumb}">
<meta property="og:video" content="{src}">
<meta property="og:video:type" content="video/mp4">
<meta name="twitter:card" content="player">
<meta name="twitter:title" content="{title}">
<meta name="twitter:image" content="{thumb}">
<meta name="twitter:player" content="{src}">
<script type="application/ld+json">{schema_ld}</script>
<style>
  body{{margin:0;background:#0d0d1a;color:#fff;font-family:system-ui,sans-serif;display:flex;flex-direction:column;align-items:center;padding:32px 16px;}}
  video{{max-width:360px;width:100%;border-radius:16px;}}
  h1{{margin:24px 0 8px;font-size:22px;text-align:center;}}
  p{{color:#aaa;text-align:center;max-width:400px;}}
  .back{{color:#888;text-decoration:none;margin-bottom:24px;display:block;}}
</style>
</head>
<body>
<a class="back" href="/gallery">← חזרה לגלריה</a>
<video src="{src}" poster="{thumb}" autoplay loop playsinline controls></video>
<h1>{title}</h1>
<p>{product}</p>
<p>{description}</p>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/sitemap.xml")
def sitemap():
    videos = list_gallery()
    urls = ["<url><loc>/gallery</loc></url>"]
    for v in videos:
        vid_id = v.get("video_id", "")
        if vid_id:
            urls.append(f"<url><loc>/gallery/{vid_id}</loc></url>")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += "\n".join(urls)
    xml += "\n</urlset>"
    return Response(content=xml, media_type="application/xml")


@app.get("/api/gallery")
def get_gallery(refresh: bool = False):
    videos = list_gallery(force_refresh=refresh)
    return [
        {
            "id": v.get("video_id"),
            "title": v.get("title", ""),
            "video_url": v.get("video_url", ""),
            "thumbnail_url": v.get("actor_url", ""),
            "product_name": v.get("product_name", ""),
            "created_at": v.get("created_at", ""),
        }
        for v in videos
    ]


@app.get("/api/gallery/{video_id}")
def get_gallery_item(video_id: str):
    videos = list_gallery()
    item = next((v for v in videos if v.get("video_id") == video_id), None)
    if not item:
        raise HTTPException(404, "Video not found")
    return item


# --- Social Publishing ---

@app.post("/api/ugc/social/post")
async def social_post(
    req: SocialPostRequest,
    x_upload_post_key: Optional[str] = Header(None),
    x_upload_post_user: Optional[str] = Header(None),
):
    api_key = x_upload_post_key or os.environ.get("UPLOAD_POST_API_KEY", "")
    user_id = x_upload_post_user or os.environ.get("UPLOAD_POST_USER_ID", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing Upload-Post API key")
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing Upload-Post user ID")

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(req.video_url)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch video")
        video_bytes = r.content

    final_title = req.title or "Hebrew Short"
    final_desc = req.caption or final_title

    data_payload: dict = {
        "user": user_id,
        "title": final_title,
        "platform[]": req.platforms,
        "async_upload": "true",
    }
    if req.scheduled_date:
        data_payload["scheduled_date"] = req.scheduled_date
        if req.timezone:
            data_payload["timezone"] = req.timezone
    if "tiktok" in req.platforms:
        data_payload["tiktok_title"] = final_desc
    if "instagram" in req.platforms:
        data_payload["instagram_title"] = final_desc
        data_payload["media_type"] = "REELS"
    if "youtube" in req.platforms:
        data_payload["youtube_title"] = final_title
        data_payload["youtube_description"] = final_desc
        data_payload["privacyStatus"] = "public"

    files = {"video": ("video.mp4", video_bytes, "video/mp4")}
    headers = {"Authorization": f"Apikey {api_key}"}

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            "https://api.upload-post.com/api/upload",
            headers=headers,
            data=data_payload,
            files=files,
        )

    if response.status_code not in [200, 201, 202]:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Upload-Post error: {response.text}",
        )
    return response.json()


@app.get("/api/ugc/social/user")
async def social_user(x_upload_post_key: Optional[str] = Header(None)):
    api_key = x_upload_post_key or os.environ.get("UPLOAD_POST_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing Upload-Post API key")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            "https://api.upload-post.com/api/uploadposts/users",
            headers={"Authorization": f"Apikey {api_key}"},
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Failed to fetch user: {resp.text}",
        )

    data = resp.json()
    profiles = []
    for p in data.get("profiles", []):
        username = p.get("username")
        if not username:
            continue
        socials = p.get("social_accounts", {})
        connected = [pl for pl in ["tiktok", "instagram", "youtube"]
                     if isinstance(socials.get(pl), dict)]
        profiles.append({"username": username, "connected": connected})
    return {"profiles": profiles}


# --- Static file mounts (after all routes) ---

app.mount("/videos", StaticFiles(directory=OUTPUT_DIR), name="videos")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
