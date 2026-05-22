# Testing Patterns

**Analysis Date:** 2026-05-22

## Test Framework

**No test framework is configured or installed.**

- No `pytest`, `unittest`, `jest`, `vitest`, or any test runner found
- No test files exist anywhere in the repository (confirmed via `find` for `*.test.*`, `*.spec.*`, `test_*.py`, `*_test.py`)
- `backend/requirements.txt` has no test dependencies
- `frontend/package.json` has no test script, no `vitest`, no `jest`, no `@testing-library/*`

## Test File Organization

**None.** No test directory, no co-located test files.

## Coverage

**None.** No coverage tooling configured.

## What Should Be Tested (Gaps)

These are the highest-risk areas with zero test coverage:

**Critical backend logic:**
- `backend/saasshorts.py:generate_tiktok_subs` — Hebrew/RTL detection, word chunking, ASS file format correctness
- `backend/saasshorts.py:composite_video` — FFmpeg filter_complex string construction; segment ordering logic; b-roll duration clamping
- `backend/content.py:_build_music_filter` — FFmpeg filter chain string construction for layered ambient audio
- `backend/content.py:_vocalize_hebrew` — Hebrew letter integrity check (`in_letters != out_letters` guard)
- `backend/saasshorts.py:_format_ass_time` — Time formatting for ASS subtitles (pure function, trivial to test)
- `backend/s3_uploader.py` — Local fallback path (`_local_upload_to_gallery`, `_local_list_gallery`) when S3 absent

**API layer:**
- `backend/app.py` — FastAPI endpoint validation (missing API keys, missing url+description, job status 404)
- Rate limiting behavior (`slowapi` 1/10s limits)

**Frontend:**
- `frontend/src/lib/api.js` — Error propagation from `json()` helper
- `frontend/src/lib/storage.js` — localStorage read/write
- `frontend/src/hooks/useApiKeys.js` — Key persistence across renders

## How to Add Tests (If Introduced)

**Python — recommended approach:**
```bash
pip install pytest pytest-asyncio httpx[testing]
```

Place test files as `backend/tests/test_saasshorts.py`, `backend/tests/test_content.py`, etc.

Pure functions to start with (no mocking required):
- `_format_ass_time(seconds)` — `backend/saasshorts.py:1050`
- `_is_hebrew(text)` — `backend/hooks.py:14`
- `_build_music_filter(spec)` — `backend/content.py:91`
- `hex_to_ass_color(hex_color, opacity)` — `backend/subtitles.py:136`

FastAPI endpoints via `httpx.AsyncClient(app=app, base_url="http://test")`.

**Frontend — recommended approach:**
```bash
npm install -D vitest @testing-library/react @testing-library/user-event jsdom
```

Add to `frontend/package.json`:
```json
"test": "vitest"
```

Place tests co-located: `frontend/src/lib/api.test.js`, `frontend/src/hooks/useApiKeys.test.js`.

---

*Testing analysis: 2026-05-22*
