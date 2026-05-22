# External Integrations

**Analysis Date:** 2026-05-22

## APIs & External Services

**AI / LLM:**
- Google Gemini Flash (`gemini-flash-latest`) — SaaS website analysis, script generation, Hebrew nikkud vocalization, Google Search grounding for web research
  - SDK/Client: `google-genai>=0.8.0` (`google.genai.Client`)
  - Auth: `GEMINI_API_KEY` env var or `X-Gemini-Key` request header
  - Used in: `backend/saasshorts.py` (`research_saas_online`, `analyze_saas`, `generate_scripts`), `backend/content.py` (`generate_content_script`, `_vocalize_hebrew`)
  - Notable: uses `types.Tool(google_search=types.GoogleSearch())` for grounded web research

**Text-to-Speech:**
- ElevenLabs TTS — voiceover generation for both pipelines
  - REST API base: `https://api.elevenlabs.io/v1`
  - Models used: `eleven_v3` (preferred, with Hebrew `language_code` hint), falls back to `eleven_multilingual_v2`
  - Auth: `ELEVENLABS_API_KEY` env var or `X-Elevenlabs-Key` request header
  - Used in: `backend/saasshorts.py` (`generate_voiceover`), `backend/content.py` (`_generate_voiceover_content`)
  - Default voice IDs: Rachel `21m00Tcm4TlvDq8ikWAM` (UGC pipeline), Daniel `onwK4e9ZLuTAKqWW03F9` (content pipeline)

**AI Image & Video Generation (fal.ai):**
- fal.ai queue API (`https://queue.fal.run`) — all generative media except TTS
  - Auth: `FAL_API_KEY` env var or `X-Fal-Key` request header
  - Client: raw `httpx` with polling loop (`backend/saasshorts.py` `_fal_run`)
  - File upload: `https://rest.alpha.fal.ai/storage/upload/initiate` (presigned PUT)
  - Models used:
    - `fal-ai/flux-2-pro` — actor portraits (UGC), b-roll stills (UGC), background images (content)
    - `fal-ai/kling-video/ai-avatar/v2/standard` — premium talking head (Kling Avatar v2)
    - `fal-ai/minimax/hailuo-2.3-fast/standard/image-to-video` — low-cost talking head base video (Hailuo 2.3 Fast)
    - `veed/lipsync` — lip-sync for low-cost talking head pipeline

**Social Publishing:**
- Upload-Post API (`https://api.upload-post.com/api/upload`) — publish videos to TikTok, Instagram Reels, YouTube
  - Auth: `UPLOAD_POST_API_KEY` env var or `X-Upload-Post-Key` header; user ID via `UPLOAD_POST_USER_ID` / `X-Upload-Post-User`
  - Used in: `backend/app.py` (`social_post`, `social_user` endpoints)
  - Platforms supported: `tiktok`, `instagram` (REELS), `youtube`

## Data Storage

**Databases:**
- No database. Job state stored in-process in a Python dict (`jobs: Dict[str, dict]` in `backend/app.py`). Jobs expire after `JOB_RETENTION_SECONDS` (default 1h). Data is lost on restart.

**File Storage — Two-Bucket AWS S3 (optional):**
- Private bucket (`AWS_S3_PRIVATE_BUCKET`, default: `hebrew-shorts-private`) — generated video clips, served via 2-hour presigned URLs
- Public bucket (`AWS_S3_PUBLIC_BUCKET`, default: `hebrew-shorts-public`) — gallery videos, actor thumbnails, metadata JSON; public CDN URLs (`https://<bucket>.s3.<region>.amazonaws.com/<key>`)
- Client: `boto3>=1.34.0` with SigV4 (`backend/s3_uploader.py`)
- Connection: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- **Fallback:** When AWS credentials absent, all storage uses local filesystem under `OUTPUT_DIR` (`backend/output/` by default). Gallery reads `metadata.json` files from output subdirectories.

**Local Filesystem:**
- `backend/output/<job_id>/` — per-job intermediate + final video files
- `backend/uploads/` — uploaded actor images
- `backend/assets/music/` — generated ambient music MP3s (synthesized via FFmpeg on first run)
- `backend/fonts/` — NotoSansHebrew-Bold.ttf, NotoSerif-Bold.ttf (downloaded from GitHub on demand)

**Gallery Cache:**
- In-memory dict `_gallery_cache` in `backend/s3_uploader.py` with 5-minute TTL (300s)

## Authentication & Identity

**Auth Provider:** None — no user authentication or sessions.

**API Key Passthrough:** The frontend stores API keys in browser `localStorage` (via `frontend/src/lib/storage.js` and `frontend/src/hooks/useApiKeys.js`) and forwards them per-request via custom headers. Backend accepts keys from headers first, then falls back to server-side env vars.

## AI Transcription

**Faster-Whisper (local, no external API):**
- Used for subtitle generation (word-level timestamps → ASS format)
- Model `small` for Hebrew, `base` for English/auto-detect
- CPU inference, int8 quantization
- Called from `backend/saasshorts.py` (`transcribe_audio_for_subs`, `generate_tiktok_subs`)
- Also standalone in `backend/subtitles.py` (`transcribe_audio`, `generate_srt_from_video`)

## Video Processing (local)

**FFmpeg / ffprobe (system binary):**
- Ken Burns zoom/pan effect on still images
- Talking head + b-roll compositing with filter_complex
- Subtitle burn-in (ASS format via `ass=` filter; degrades gracefully if libass absent)
- Background music mixing (loop + volume envelope)
- Audio fade-out on video tail
- Ambient music synthesis from sine waves (content pipeline `backend/content.py` `_ensure_music_files`)
- Thumbnail extraction for gallery (`backend/s3_uploader.py` `_extract_thumbnail`)

## Monitoring & Observability

**Error Tracking:** None.

**Logs:** `print()` statements throughout backend pipeline modules with emoji prefixes (e.g. `[SaaSShorts] ✅`). Standard Python `logging` module used in `backend/s3_uploader.py`. No structured logging or external log aggregation.

**Job progress:** Streamed via polling — clients poll `GET /api/ugc/status/{job_id}` which returns `{status, logs: [{time, msg}], result}`.

## CI/CD & Deployment

**Hosting:** Self-hosted Docker container (single service defined in `docker-compose.yml`).

**CI Pipeline:** None detected.

**Build:** Multi-stage `Dockerfile` — Node 20 builds React SPA, Python 3.11 runtime serves everything on port 8000.

## Webhooks & Callbacks

**Incoming:** None.

**Outgoing:** None (Upload-Post uses async upload with `async_upload=true` but no callback endpoint is registered).

## Website Scraping

**BeautifulSoup4 (`beautifulsoup4>=4.12.0`):**
- Scrapes product URLs during UGC analyze step
- Fetches main page + up to 3 subpages matching pricing/features/about/product keywords
- Used in: `backend/saasshorts.py` (`scrape_website`)

## External Font Sources

- NotoSansHebrew-Bold.ttf — downloaded from `github.com/googlefonts/noto-fonts` on demand (`backend/hooks.py`, `Dockerfile`)
- NotoSerif-Bold.ttf — same source, for non-Hebrew hook overlays

---

*Integration audit: 2026-05-22*
