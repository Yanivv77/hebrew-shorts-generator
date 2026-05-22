# Codebase Concerns

**Analysis Date:** 2026-05-22

---

## CRITICAL

### No Tests Anywhere

**Files:** All of `backend/`, `frontend/src/`
**What's missing:** Zero test files found. No pytest setup, no vitest config, no `*.test.*` or `*.spec.*` files in either backend or frontend (excluding node_modules).
**Risk:** Every pipeline change — FFmpeg filter tweaks, Gemini prompt changes, ASS subtitle logic — ships with no regression safety net. Recent bugs (social post URL, Whisper language, vocalization truncation) had no automated catch.
**Fix approach:** Start with smoke tests for `_vocalize_hebrew`, `generate_tiktok_subs`, `composite_video` in pytest. Frontend: vitest + react-testing-library for `api.js` and key step components.

---

## HIGH

### 1. Monolithic `backend/app.py` — All Concerns in One File

**Files:** `backend/app.py` (730 lines)
**Issue:** Pydantic models, 4 endpoint domains (UGC, content, gallery, social), job queue, worker loop, and static mounts all in one file. The `jobs: Dict[str, dict]` blob is an opaque dict without a typed schema — fields like `"type"`, `"fal_key"`, `"gemini_key"` are string keys discovered only by reading worker code.
**Impact:** Bug localization is slow (confirmed: social post URL bug, "Missing Upload-Post user ID" required full-file inspection). Adding a new pipeline type requires editing the single job router `run_job()`.
**Fix approach:** Split into `routers/ugc.py`, `routers/content.py`, `routers/gallery.py`, `routers/social.py`. Extract `JobRecord` as a typed `TypedDict` or Pydantic model. Move queue/worker logic to `worker.py`.

### 2. In-Memory Job State — Lost on Every Restart

**Files:** `backend/app.py:49` (`jobs: Dict[str, dict]`)
**Issue:** All job state, logs, and results live in a module-level dict. Any restart (deploy, crash, `--reload` trigger) drops all in-flight and completed jobs. Frontend polling an active job after a restart gets 404.
**Impact:** During long renders (Flux + Kling, 5–10 min), a process restart loses the job silently. No way to query past jobs.
**Fix approach:** Replace with SQLite via `aiosqlite` (zero infra) or Redis. Minimum viable: persist job metadata to `output/<job_id>/job.json` on each status transition.

### 3. Render-Worker Runs in Same Process as API

**Files:** `backend/app.py:269–401` (`process_job_queue`, `run_job`, `_run_ugc_job`, `_run_content_job`)
**Issue:** All rendering (Flux image gen, VEED lipsync, FFmpeg compositing) runs in the default asyncio thread pool inside the uvicorn process. Long `run_in_executor` calls (5–10 min) block thread slots. Under load or during `--reload`, `/health` returns 504. There is no worker process isolation.
**Impact:** Health checks fail during renders. SIGTERM during a render kills the job. `--reload` can deadlock on open long-poll connections (requires `--timeout-graceful-shutdown 1` workaround).
**Fix approach:** Move rendering to a separate Celery worker or at minimum a standalone `python worker.py` process consuming from a Redis/SQLite queue. The API process should only enqueue and poll.

### 4. API Keys Stored in In-Memory Job Dict (Credential Exposure Risk)

**Files:** `backend/app.py:203–213`, `backend/app.py:247–258`
**Issue:** `fal_key` and `elevenlabs_key` (passed by the frontend per-request) are stored verbatim inside the `jobs[job_id]` dict. They persist there for up to `JOB_RETENTION_SECONDS` (default 1 hour). Any future endpoint that serializes job state (e.g., a debug dump, persistent storage) would leak credentials.
**Impact:** Medium risk currently (no persistence), but becomes high if job state is ever written to disk or a database.
**Fix approach:** Strip API keys from the job dict immediately after the worker reads them, or pass them directly to the worker function rather than storing them.

### 5. FFmpeg Filter-Graph Fragility

**Files:** `backend/saasshorts.py:1183–1313` (`composite_video`), `backend/content.py:556–670` (`_composite_content_video`)
**Issue:** Filter graphs are built by string concatenation with f-strings. `ass=filename=` path handling requires manual escaping of `\`, `:`, `'` — known to break on FFmpeg 8.x and on paths with special characters. `subprocess.run(cmd, check=True)` on lines 1220 and 1311 of `saasshorts.py` have no `capture_output=True`, so FFmpeg stderr is swallowed — CalledProcessError shows no diagnostic.
**Impact:** Any path with spaces, colons (macOS volume names), or apostrophes silently fails. FFmpeg version upgrades (e.g., 8.1 `ass=path` parser change) require manual filter string fixes.
**Fix approach:** Always pass `capture_output=True` to subprocess calls and include `stderr` in exception messages. Consider generating `.ass` files to a temp dir with sanitized filenames, or use `-vf subtitles=` with proper escaping helpers.

### 6. No CI / No Linting Enforcement on Backend

**Files:** Project root (no `.github/` directory), `backend/` (no `pyproject.toml`, no `ruff.toml`, no `.flake8`)
**Issue:** Frontend has `eslint --max-warnings 0` in `package.json` scripts but no CI to run it. Backend has zero linting tooling. Dead code at `backend/saasshorts.py:741–751` (unreachable loop after `return sorted(paths)`) exists undetected.
**Impact:** Regressions introduced by edits go undetected until runtime. The dead code block in `generate_actor_images` (lines 741–751) is a latent confusion risk.
**Fix approach:** Add GitHub Actions workflow: `pytest` for backend, `npm run lint` for frontend, on every push. Add `ruff` as backend linter (`pyproject.toml`).

---

## MEDIUM

### 7. `asyncio.get_event_loop()` — Deprecated Pattern

**Files:** `backend/app.py:139`, `169`, `228`, `319`, `372`
**Issue:** Five uses of `asyncio.get_event_loop()` inside `async def` handlers. Deprecated in Python 3.10+; in Python 3.12 this raises `DeprecationWarning` inside async context and will break in a future release.
**Impact:** Will break on Python 3.14 when the deprecation becomes an error. Currently emits warnings that pollute logs.
**Fix approach:** Replace with `asyncio.get_running_loop()` inside async functions.

### 8. UGC Subtitle Generation Missing `language` Parameter

**Files:** `backend/saasshorts.py:1467`
```python
generate_tiktok_subs(audio_path, srt_path, max_words=2)
```
**Issue:** The UGC pipeline calls `generate_tiktok_subs` without `language=` (defaults to `"en"`). For Hebrew-language UGC videos, Whisper is called without `language="he"`, the `base` model is used instead of `small`, and the Hebrew RTL tag is not applied in the ASS output.
**Impact:** Hebrew UGC subtitles may be mis-transcribed (base model, auto-detect) and rendered LTR.
**Fix approach:** Pass `language=req.get("language", "en")` through the job config and into the `generate_tiktok_subs` call inside `generate_full_video`.

### 9. Presigned S3 URLs Expire Before Social Post Window

**Files:** `backend/s3_uploader.py:75` (`ExpiresIn=7200`)
**Issue:** Presigned clip URLs expire in 2 hours. The `/api/ugc/social/post` endpoint accepts `scheduled_date` — a video scheduled 3+ hours out will have an expired URL when the social posting service tries to use it. The endpoint downloads video bytes at post time, but only from the presigned URL — which may be expired.
**Impact:** Scheduled social posts fail silently with a 403 from S3.
**Fix approach:** Either extend `ExpiresIn` to 24 hours for the clip bucket, or store the S3 key (not the presigned URL) and generate a fresh presigned URL at post time.

### 10. `DEFAULT_VOICES` Contains Placeholder Hebrew Voice IDs

**Files:** `backend/saasshorts.py:31–32`
```python
"Noa (Female, Hebrew)": "hebrew_female_voice_id",
"Amir (Male, Hebrew)": "hebrew_male_voice_id",
```
**Issue:** These are literal placeholder strings, not real ElevenLabs voice IDs. If a user selects either Hebrew-named voice from the UI, ElevenLabs will return a 422 error.
**Impact:** Selecting the Hebrew voice options causes a hard failure mid-render.
**Fix approach:** Replace with real ElevenLabs Hebrew voice IDs or remove them from the map until populated.

### 11. `content.py` No-Music Path Audio Map Bug

**Files:** `backend/content.py:656`
```python
"-map", "[finalv]", f"-map", f"{n}:a",
```
**Issue:** The no-music branch defines `[finala]` in `filter_complex` (via `pad_voice` → `final_audio`) but maps raw input stream `{n}:a` instead of `[finala]`. This means fade-out and apad effects in `final_audio` are built but never used — the raw unprocessed audio stream is mapped instead.
**Impact:** When music is absent, the tail silence padding and audio fade-out are silently skipped. Videos end abruptly instead of fading.
**Fix approach:** Change the no-music map to `"-map", "[finala]"` to match the music path pattern.

### 12. Gallery HTML Renders Unescaped User Data (XSS Vector)

**Files:** `backend/app.py:455–466`, `app.py:523–554`
**Issue:** Gallery page and video detail page interpolate S3/DB metadata (`title`, `product`, `description`, `src`, `thumb`) directly into HTML f-strings with no HTML entity escaping. Any metadata field containing `<script>` or `"` can inject JavaScript into the gallery page.
**Impact:** If the public S3 bucket is writable or metadata is tampered with, stored XSS is possible.
**Fix approach:** Use `html.escape()` on all user-derived values before interpolating into the HTML template, or switch to a real template engine (Jinja2).

### 13. Stale Orphan Uvicorn Processes Hold Port 8000

**Files:** Process management (no supervisor config)
**Issue:** No process supervisor (systemd, supervisord, Docker restart policy) is configured. If uvicorn is started manually, crashes or SIGKILL leave orphan processes holding port 8000. New starts fail with `Address already in use`.
**Impact:** Development and deploy restarts require manual `kill $(lsof -ti:8000)`.
**Fix approach:** Use `--workers 1 --timeout-graceful-shutdown 1` (already documented in known bugs) and add a start script or supervisord config to the repo. Docker Compose already exists but doesn't enforce restart policy.

### 14. Mixed Content Pipelines Share One Job Dict and Queue

**Files:** `backend/app.py:49`, `app.py:278–282`
**Issue:** UGC and philosophical/content jobs share `jobs: Dict[str, dict]` and the single `job_queue`. Job type is distinguished by an optional `"type"` key (`"content"` vs implicit `"ugc"`). There is no per-pipeline queue depth monitoring, priority, or throttling.
**Impact:** A flood of content jobs blocks UGC jobs (and vice versa) up to `MAX_CONCURRENT_JOBS`. Adding a third pipeline type requires modifying the central `run_job` router. Adding `"philosophical"` as a future type (`backend/philosophical.py` is listed as untracked but does not yet exist) will require careful branching here.
**Fix approach:** Separate queues per pipeline type, or tag jobs with a pipeline enum and route to separate semaphores. Define a `JobType` enum to replace string-keyed dispatch.

---

## LOW

### 15. `backend/hooks.py` Uses Relative `fonts/` Path

**Files:** `backend/hooks.py:9–11`
```python
FONT_DIR = "fonts"
FONT_PATH = os.path.join(FONT_DIR, "NotoSerif-Bold.ttf")
```
**Issue:** Font paths are relative to the working directory, not the script's location. If uvicorn is started from a directory other than `backend/`, font files are not found and `create_hook_image` falls back to PIL's default bitmap font, producing low-quality hook overlays.
**Impact:** Silently degrades hook overlay quality when CWD != `backend/`.
**Fix approach:** Replace with `os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", ...)` (same pattern used in `content.py` and `s3_uploader.py`).

### 16. `subtitles.py` Uses `base` Whisper Model Without Language Hint

**Files:** `backend/subtitles.py:16`
```python
model = WhisperModel("base", device="cpu", compute_type="int8")
```
**Issue:** This legacy transcription function (used by `generate_srt_from_video`) always uses `base` model with auto language detection. It also imports `cv2` (OpenCV) which is not in `requirements.txt`.
**Impact:** If called for Hebrew audio, it will mis-detect language (known Hindi mis-detection issue). `cv2` import will fail on a clean install.
**Fix approach:** Either remove the unused file or align it with `saasshorts.py`'s `transcribe_audio_for_subs` (which has the language fix). Add `opencv-python-headless` to `requirements.txt` if kept.

### 17. Dead Code Block in `generate_actor_images`

**Files:** `backend/saasshorts.py:741–751`
**Issue:** 11 lines of unreachable code after `return sorted(paths)` — a leftover loop from a prior refactor.
**Impact:** No runtime impact, but confuses readers and will be picked up as a defect by any future linter.
**Fix approach:** Delete lines 741–751.

### 18. `gemini-flash-latest` — Unstable Model Alias

**Files:** `backend/saasshorts.py:42` (`GEMINI_MODEL = "gemini-flash-latest"`)
**Issue:** `"gemini-flash-latest"` is a rolling alias that Gemini may redirect to different model versions over time without notice. A model upgrade in this alias could silently change JSON output structure, prompt adherence, or token limits.
**Impact:** Prompt regressions (wrong script structure, JSON parse failures) without any code change.
**Fix approach:** Pin to a specific model version (e.g., `"gemini-2.0-flash"`) and update deliberately. Keep `GEMINI_MODEL` as a single constant (already done) for easy version bumps.

### 19. No `philosophical.py` Backend — Frontend Components Unrouted

**Files:** `backend/philosophical.py` (does not exist, listed as untracked in git status), `frontend/src/components/philosophical/` (does not exist), `frontend/src/pages/PhilosophicalPage.jsx` (does not exist)
**Issue:** Git status lists `backend/philosophical.py`, `frontend/src/components/philosophical/`, and `frontend/src/pages/PhilosophicalPage.jsx` as untracked — but none of these files actually exist on disk. The philosophical content pipeline is fully served by `backend/content.py` and routed through `ContentPage`. The untracked entries in git status are ghosts (possibly deleted working files not yet staged).
**Impact:** No functional impact. But the memory note (`MEMORY.md`) treats philosophical as a separate pipeline — if someone creates `philosophical.py` expecting a separate backend route, it won't be wired into `app.py`.
**Fix approach:** Clarify in `PLAN.md` that philosophical content is `backend/content.py` + `frontend/src/pages/ContentPage.jsx`. Clean up ghost git status entries.

---

*Concerns audit: 2026-05-22*
