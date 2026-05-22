# Technology Stack

**Analysis Date:** 2026-05-22

## Languages

**Primary:**
- Python 3.11 — backend API, both video pipelines, all AI integrations
- JavaScript (ES Modules) — React frontend

**Secondary:**
- HTML/CSS — gallery SSR pages rendered directly by FastAPI (`backend/app.py` lines 424–557)

## Runtime

**Environment:**
- Python 3.11 (pinned in `Dockerfile` base image `python:3.11-slim`)
- Node 20 (build stage only — `Dockerfile` line 2, `node:20-slim`)

**Package Manager:**
- Python: pip with `backend/requirements.txt` (no lockfile)
- Node: npm with `frontend/package-lock.json` (lockfile present)

## Frameworks

**Core:**
- FastAPI 0.136.1 — REST API + SSR gallery pages + SPA fallback (`backend/app.py`)
- Uvicorn 0.46.0 — ASGI server, launched via `CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]`
- React 18.2.0 — frontend SPA (`frontend/src/`)
- React Router DOM 7.15.1 — client-side routing

**UI:**
- Tailwind CSS 3.4.19 — utility-first styling, config at `frontend/tailwind.config.js`
- Lucide React 0.344.0 — icon set

**Rate Limiting:**
- slowapi 0.1.9 — per-IP rate limiting on analyze endpoints (`backend/app.py` lines 63–71)

**Build/Dev:**
- Vite 4.5.3 — frontend build tool, config at `frontend/vite.config.js`
- `@vitejs/plugin-react` 4.2.1 — JSX transform
- PostCSS + autoprefixer — CSS processing

## Key Dependencies

**Critical (backend):**
- `google-genai>=0.8.0` — Gemini Flash (script gen, SaaS analysis, Hebrew nikkud vocalization)
- `httpx==0.28.1` — all outbound HTTP: fal.ai API, ElevenLabs API, Upload-Post API, image downloads
- `faster-whisper>=1.0.0` — Whisper STT for subtitle generation (CPU, int8 quantization)
- `boto3>=1.34.0` — AWS S3 for two-bucket gallery/clip storage (`backend/s3_uploader.py`)
- `beautifulsoup4>=4.12.0` — website scraping for UGC product analysis (`backend/saasshorts.py`)
- `Pillow>=10.0.0` — hook overlay image generation (`backend/hooks.py`)
- `python-multipart==0.0.27` — multipart file uploads (actor image upload endpoint)
- `python-dotenv==1.2.2` — `.env` loading at app startup

**Critical (frontend):**
- `react-helmet-async 3.0.0` — `<head>` meta tags for SEO
- `react-router-dom 7.15.1` — SPA routing

## System Dependencies

**FFmpeg** — all video compositing, Ken Burns effect, subtitle burn-in, audio mixing, thumbnail extraction. Must be present in `PATH`. Installed in Docker via `apt-get install ffmpeg`. Required filters: `libx264`, `libmp3lame`, `libass` (optional, subtitle burn-in degrades gracefully without it).

**ffprobe** — media duration probing (`backend/saasshorts.py` `_get_media_duration`, `backend/hooks.py`)

**Whisper model files** — downloaded on first use to local cache by `faster-whisper`. Models used: `base` (English/auto), `small` (Hebrew).

## Configuration

**Environment:**
- Root `.env` loaded by `backend/app.py` via `python-dotenv` at startup
- `backend/.env.example` documents backend-specific overrides (same vars)
- API keys passed per-request via HTTP headers (`X-Gemini-Key`, `X-Fal-Key`, `X-Elevenlabs-Key`, `X-Upload-Post-Key`, `X-Upload-Post-User`) or fall back to server env vars

**Key env vars (see `.env.example`):**
- `GEMINI_API_KEY` — required for all AI generation
- `ELEVENLABS_API_KEY` — required for TTS
- `FAL_API_KEY` — required for image/video generation
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` — optional S3; falls back to local disk
- `AWS_S3_PRIVATE_BUCKET` / `AWS_S3_PUBLIC_BUCKET` — S3 bucket names
- `UPLOAD_POST_API_KEY` / `UPLOAD_POST_USER_ID` — optional social publishing
- `MAX_CONCURRENT_JOBS` (default: 3), `JOB_RETENTION_SECONDS` (default: 3600)
- `ALLOWED_ORIGINS` (default: `*`), `OUTPUT_DIR`, `UPLOADS_DIR`

**Build:**
- Multi-stage Dockerfile: Node 20 builds frontend → Python 3.11 runtime serves both
- Frontend `dist/` copied to `backend/static/` for SPA serving
- `docker-compose.yml` mounts `./output` and `./uploads` as volumes

## Platform Requirements

**Development:**
- Python 3.11+, Node 20+, FFmpeg + ffprobe in PATH
- API keys: Gemini, ElevenLabs, fal.ai (minimum set)
- Vite dev server proxies `/api`, `/health`, `/uploads`, `/videos`, `/assets/music` → `http://localhost:8000`

**Production:**
- Single Docker container (port 8000)
- FastAPI serves frontend SPA via `StaticFiles` mount + SPA fallback (`backend/app.py` lines 723–730)
- Optional: AWS S3 for persistent video/gallery storage; falls back to local filesystem without it

---

*Stack analysis: 2026-05-22*
