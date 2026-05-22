<!-- refreshed: 2026-05-22 -->
# Architecture

**Analysis Date:** 2026-05-22

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    React SPA (Vite, port 5173 dev)                  │
│  ProductPage (4 steps)  │  ContentPage (3 steps)  │  GalleryPage    │
│  `frontend/src/pages/`      `frontend/src/lib/api.js`               │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ HTTP (fetch, custom headers for API keys)
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│              FastAPI app  `backend/app.py`  (uvicorn)               │
│                                                                     │
│  /api/ugc/*  (analyze, actor-options, actor-upload, generate,       │
│              status, social/post, social/user)                      │
│  /api/content/*  (scripts, generate, music)                         │
│  /api/gallery, /gallery, /gallery/{id}, /sitemap.xml                │
│  Static: /videos/, /uploads/, /assets/music/                        │
│  SPA fallback: backend/static/index.html                            │
│                                                                     │
│  jobs: Dict[str, dict]  (module-level in-memory store)              │
│  job_queue: asyncio.Queue                                           │
│  concurrency_semaphore: asyncio.Semaphore(MAX_CONCURRENT_JOBS=3)    │
└──────┬────────────────────────────┬───────────────────────────────┘
       │ loop.run_in_executor(None) │ loop.run_in_executor(None)
       ▼                            ▼
┌──────────────┐          ┌──────────────────┐
│ saasshorts.py│          │  content.py       │
│ ~1500 lines  │          │  ~786 lines       │
│              │          │                  │
│ UGC pipeline │          │ Philosophical     │
│ (blocking)   │          │ pipeline          │
│              │          │ (blocking)        │
└──────┬───────┘          └────────┬──────────┘
       │                           │
       │  subprocess.run()         │  subprocess.run()
       ▼                           ▼
   FFmpeg/ffprobe              FFmpeg/ffprobe
       │                           │
       ├── httpx (ElevenLabs TTS)
       ├── httpx (fal.ai queue polling)
       └── google-genai (Gemini)
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  s3_uploader.py  — AWS S3 (2-bucket) + local filesystem fallback    │
│  Private bucket: generated clips (presigned URLs)                   │
│  Public bucket: gallery videos + metadata.json per video_id         │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| FastAPI app | HTTP routing, request validation, job lifecycle | `backend/app.py` |
| In-memory job store | Tracks job state (queued/processing/completed/failed), logs, result | `backend/app.py:49` — `jobs: Dict[str, dict]` |
| `process_job_queue` | Infinite async loop: dequeues job_id, spawns `run_job` task | `backend/app.py:269` |
| `run_job` | Acquires semaphore, dispatches to `_run_ugc_job` or `_run_content_job` | `backend/app.py:276` |
| `_run_ugc_job` | Orchestrates UGC render: downloads actor, calls `generate_full_video`, uploads result | `backend/app.py:285` |
| `_run_content_job` | Orchestrates content render: calls `generate_content_video`, uploads result | `backend/app.py:350` |
| `cleanup_old_jobs` | Prunes completed/failed jobs older than `JOB_RETENTION_SECONDS` (1h) | `backend/app.py:403` |
| UGC pipeline | All UGC rendering: scraping, Gemini analysis, script gen, actor gen, TTS, talking head, b-roll, composite | `backend/saasshorts.py` |
| Content pipeline | Philosophical video: Gemini scripts, Hebrew TTS, Flux2Pro backgrounds, Ken Burns, ASS subs, composite | `backend/content.py` |
| S3 uploader | Upload clips/gallery to AWS S3; transparent local fallback via `metadata.json` files | `backend/s3_uploader.py` |
| hooks.py | PIL-based hook text overlay image generation + FFmpeg overlay command | `backend/hooks.py` |
| subtitles.py | (legacy) SRT generation utilities; main path now uses `generate_tiktok_subs` in saasshorts.py | `backend/subtitles.py` |
| Frontend API client | Thin fetch wrappers passing API keys as custom headers | `frontend/src/lib/api.js` |
| API key storage | `localStorage` persistence per key name | `frontend/src/lib/storage.js` |
| `useApiKeys` hook | React state + localStorage sync for Gemini/fal/ElevenLabs keys | `frontend/src/hooks/useApiKeys.js` |

## Pattern Overview

**Overall:** Queue-isolated render worker within a single FastAPI process — no separate worker process, no message broker.

**Key Characteristics:**
- Sync-heavy pipeline functions (`saasshorts.py`, `content.py`) are offloaded to the default `ThreadPoolExecutor` via `loop.run_in_executor(None, fn, ...)`. This keeps the event loop responsive during long renders.
- FFmpeg subprocess calls (`subprocess.run(cmd, check=True, capture_output=True)`) happen inside the executor threads — they are blocking but do not block the asyncio event loop because they run in the thread pool.
- Internal parallelism within each pipeline is handled by `concurrent.futures.ThreadPoolExecutor` (not asyncio tasks): actor image + voiceover run in parallel, b-roll clips run 3 at a time.
- There is **no API/render-worker boundary** at the process level. The HTTP server and the render workers share the same Python process and the same `jobs` dict. Restart = all in-flight jobs lost.
- API keys are not stored server-side. The frontend passes them as `X-Gemini-Key`, `X-Fal-Key`, `X-Elevenlabs-Key` headers on every request; the job worker stashes them in the `jobs` dict entry.

## Layers

**HTTP Layer:**
- Purpose: Validate requests, enqueue jobs, serve status/gallery
- Location: `backend/app.py`
- Contains: Pydantic models, route handlers, middleware, static mounts, SPA fallback
- Depends on: `saasshorts.py`, `content.py`, `s3_uploader.py`
- Used by: Frontend SPA, direct API consumers

**Pipeline Layer (UGC):**
- Purpose: End-to-end video production for product UGC
- Location: `backend/saasshorts.py`
- Contains: `scrape_website`, `research_saas_online`, `analyze_saas`, `generate_scripts`, `generate_actor_images`, `generate_voiceover`, `generate_talking_head`, `generate_talking_head_lowcost`, `generate_broll`, `generate_tiktok_subs`, `composite_video`, `generate_full_video` (top-level orchestrator)
- Depends on: httpx, google-genai, faster-whisper, FFmpeg subprocess
- Used by: `_run_ugc_job` in `app.py`

**Pipeline Layer (Content):**
- Purpose: End-to-end philosophical Hebrew video production
- Location: `backend/content.py`
- Contains: `generate_content_script`, `_vocalize_hebrew`, `_generate_voiceover_content`, `_generate_bg_image`, `_apply_ken_burns`, `_composite_content_video`, `generate_content_video` (top-level orchestrator), ambient music synthesis (`_ensure_music_files`, `_build_music_filter`)
- Depends on: `saasshorts._fal_run`, `saasshorts.generate_tiktok_subs`, httpx, google-genai, FFmpeg subprocess
- Used by: `_run_content_job` in `app.py`

**Storage Layer:**
- Purpose: Persist videos and metadata; dual-mode (S3 or local)
- Location: `backend/s3_uploader.py`
- Contains: `upload_clip`, `upload_to_gallery`, `upload_actor`, `list_gallery`, `_local_upload_to_gallery`, `_local_list_gallery`; module-level `_gallery_cache` dict (5 min TTL)
- Depends on: boto3 (optional), FFmpeg (for thumbnail extraction)
- Used by: `app.py` (import at module level), `_run_ugc_job`, `_run_content_job`

**Frontend SPA:**
- Purpose: Step-based UI for driving both pipelines + gallery browsing
- Location: `frontend/src/`
- Contains: 3 pages, step components per pipeline, shared API key modal
- Depends on: React 18, React Router, Tailwind, Lucide icons
- Used by: Served from `backend/static/` in production; Vite dev server in development

## Data Flow

### UGC Pipeline Request

1. `POST /api/ugc/generate` → `app.py:193` — Pydantic `GenerateRequest` validated; job dict created with `status="queued"`, API keys embedded; `job_id` pushed onto `job_queue`
2. `process_job_queue` dequeues job_id → `run_job` acquires semaphore → `_run_ugc_job` (`app.py:285`)
3. `_run_ugc_job` calls `loop.run_in_executor(None, generate_full_video, script, config, output_dir, log)` — executes in thread pool
4. `generate_full_video` (`saasshorts.py:1320`) runs 6 sequential steps with internal parallelism: actor image + voiceover (parallel), talking head, b-roll clips (parallel, 3 workers), subtitles (Whisper), FFmpeg composite
5. Result written to `backend/output/{job_id}/`; `upload_clip` → S3 presigned URL or `/videos/{job_id}/{file}` fallback; `upload_to_gallery` → S3 public bucket or local `metadata.json`
6. `job["status"] = "completed"`, `job["result"]` set; frontend polls `GET /api/ugc/status/{job_id}` every N seconds

### Content Pipeline Request

1. `POST /api/content/generate` → `app.py:235` — `ContentGenerateRequest` validated; job dict includes `type="content"` discriminator
2. Same queue/semaphore path → `_run_content_job` (`app.py:350`)
3. `loop.run_in_executor(None, generate_content_video, script, config, output_dir, log)`
4. `generate_content_video` (`content.py:673`) runs: nikkud vocalization (Gemini, optional), voiceover + 3 background images (parallel, 4-worker pool), Ken Burns per segment, Whisper subtitles, FFmpeg composite with music mix
5. Same upload/gallery path as UGC

### Analysis (Sync, No Queue)

`POST /api/ugc/analyze` (`app.py:131`) is synchronous within the request — `scrape_website`, `research_saas_online`, `analyze_saas`, `generate_scripts` all run via `loop.run_in_executor` chained inline, blocking the HTTP response until complete (typically 15–45s). No job is created.

**State Management:**
- Job state: module-level `jobs: Dict[str, dict]` in `backend/app.py` — lost on restart
- Gallery cache: module-level `_gallery_cache` in `backend/s3_uploader.py` — 5-min TTL
- Music generation: version-stamped files on disk in `backend/assets/music/` — regenerated at import time if spec version changes
- API keys (frontend): `localStorage` via `frontend/src/lib/storage.js`
- API keys (backend): passed per-request as HTTP headers, never persisted

## Key Abstractions

**Job Dict:**
- Purpose: Serializable record of a render job's lifecycle
- Schema: `{"status": str, "logs": list, "result": dict|None, "created_at": float, "type": str, "request": dict, "fal_key": str, "elevenlabs_key": str, "gemini_key": str}`
- Location: `backend/app.py:49` (`jobs` dict)

**Pipeline Orchestrator Functions:**
- `generate_full_video(script, config, output_dir, log)` → `backend/saasshorts.py:1320`
- `generate_content_video(script, config, output_dir, log)` → `backend/content.py:673`
- Both accept a `log: Callable[[str], None]` parameter; `app.py` passes a closure that appends to `jobs[job_id]["logs"]`

**`_fal_run(model_id, input_data, fal_key, timeout)`:**
- Purpose: Submit to fal.ai queue, poll until COMPLETED, return result dict
- Location: `backend/saasshorts.py:563`
- Shared by both pipelines; `content.py` imports it directly

**Pydantic Request Models (all in `backend/app.py`):**
- `AnalyzeRequest` (line 76) — UGC analyze
- `ActorOptionsRequest` (line 84) — actor image generation
- `GenerateRequest` (line 89) — UGC video job submission
- `SocialPostRequest` (line 98) — social publishing via Upload-Post
- `ContentScriptRequest` (line 107) — content script generation
- `ContentGenerateRequest` (line 113) — content video job submission

## Entry Points

**FastAPI Application:**
- Location: `backend/app.py:68`
- Start: `uvicorn backend.app:app` or `uvicorn app:app` from `backend/`
- Lifespan: `asynccontextmanager` at line 54 — creates semaphore, starts `process_job_queue` and `cleanup_old_jobs` as asyncio tasks

**Frontend Dev:**
- Location: `frontend/src/main.jsx`
- Start: `npm run dev` (Vite, proxies `/api` to `localhost:8000`)

**Frontend Production:**
- Built to `frontend/dist/`, copied to `backend/static/` — served by SPA fallback at `backend/app.py:725`

## Architectural Constraints

- **Threading model:** asyncio event loop (single thread) + default `ThreadPoolExecutor` for all blocking I/O. FFmpeg `subprocess.run` calls are blocking but run inside executor threads — safe from the event loop's perspective, but they consume thread pool slots for their full duration (2–15 min per render).
- **Global state:** Three module-level mutable singletons: `jobs` (app.py:49), `job_queue` (app.py:50), `concurrency_semaphore` (app.py:51), `_gallery_cache` (s3_uploader.py:21). All are lost on process restart.
- **No persistence:** Jobs are in-memory only. A crash or restart loses all queued and in-flight jobs.
- **Single process:** API server and render workers are co-located. A hung render (e.g., fal.ai polling for 600s) ties up a semaphore slot but does not affect HTTP routing.
- **API key transport:** Keys flow: browser localStorage → HTTP header → `jobs` dict entry → pipeline config dict. Never written to disk or env at runtime.
- **Circular imports:** `content.py` imports from `saasshorts.py` (`_fal_run`, `_get_media_duration`, `generate_tiktok_subs`, constants). `app.py` imports from both. No reverse dependency.
- **Music synthesis at import time:** `content.py:170` calls `_ensure_music_files()` at module load. If FFmpeg is not installed, the import succeeds but music generation silently fails.

## Anti-Patterns

### Analyze endpoint blocks the HTTP response for 15–45s

**What happens:** `POST /api/ugc/analyze` chains four `run_in_executor` calls inline within the route handler (`app.py:131–158`), holding the HTTP connection open until all complete.
**Why it's wrong:** Long-held connections can time out at proxy/load balancer layer and provide no progress feedback to the user.
**Do this instead:** Enqueue a job (same pattern as `/api/ugc/generate`) and poll for completion; or stream progress via SSE.

### `social_post` mixes async httpx and sync httpx in the same handler

**What happens:** `app.py:619` uses `async with httpx.AsyncClient()` to download the video, then `app.py:668` uses `with httpx.Client()` (sync) to POST to Upload-Post API inside the same async route handler.
**Why it's wrong:** The sync `httpx.Client.post` at line 668 blocks the event loop thread for up to 120 seconds.
**Do this instead:** Use `async with httpx.AsyncClient()` for both calls, or offload the sync call to `run_in_executor`.

### Dead code after `return` in `generate_actor_images`

**What happens:** `saasshorts.py:740–750` contains unreachable code after `return sorted(paths)` at line 738.
**Why it's wrong:** Suggests an incomplete refactor; the dead loop still iterates `result.get("images", [])`.
**Do this instead:** Remove lines 740–750.

## Error Handling

**Strategy:** Try/except at the job worker level. Exceptions inside `_run_ugc_job` or `_run_content_job` set `job["status"] = "failed"` and append to `job["logs"]`. Individual pipeline steps raise `Exception` on failure; the worker catches all.

**Patterns:**
- `_fal_run` raises `Exception` on HTTP errors, timeout, or FAILED status from fal.ai
- FFmpeg failures: `subprocess.run(cmd, check=True)` raises `CalledProcessError`; `_composite_content_video` captures stderr for diagnostics
- ElevenLabs TTS: cascading model fallback (eleven_v3 → eleven_multilingual_v2) before raising
- S3 operations: all wrapped in try/except; failures return `None` (graceful fallback to local URLs)
- Gallery HTML endpoints: inline `next(... None)` checks with 404 HTML responses

## Cross-Cutting Concerns

**Logging:** `print()` calls throughout `saasshorts.py` and `content.py` with prefix tags (`[SaaSShorts]`, `[Content]`, `[fal.ai]`). No structured logger. Job progress also appended to `jobs[job_id]["logs"]` via the `log` callback.
**Validation:** Pydantic v2 `BaseModel` for all request bodies in `app.py`. No output schema validation.
**Rate limiting:** `slowapi` limiter on `/api/ugc/analyze` and `/api/content/scripts` — `1/10 seconds` per IP.
**CORS:** Configurable via `ALLOWED_ORIGINS` env var; defaults to `*`.
**Hebrew RTL:** `dir="rtl"` set on server-rendered gallery HTML (`app.py:472`); frontend uses Tailwind with RTL layout classes.

---

*Architecture analysis: 2026-05-22*
