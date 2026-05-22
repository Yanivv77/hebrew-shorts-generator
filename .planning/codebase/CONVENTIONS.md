# Coding Conventions

**Analysis Date:** 2026-05-22

## Naming Patterns

**Python files:**
- `snake_case` modules: `saasshorts.py`, `s3_uploader.py`, `content.py`
- Private helpers prefixed with `_`: `_fal_run`, `_fal_upload_file`, `_build_music_filter`, `_get_media_duration`, `_format_ass_time`, `_vocalize_hebrew`, `_s3_client`, `_local_list_gallery`
- Public pipeline functions use verb_noun: `generate_scripts`, `generate_voiceover`, `generate_broll`, `composite_video`

**Python variables:**
- `snake_case` throughout; config dicts use `snake_case` keys
- Constants: `SCREAMING_SNAKE_CASE` (`ELEVENLABS_API_BASE`, `FAL_QUEUE_BASE`, `GEMINI_MODEL`, `MUSIC_TRACKS`, `MUSIC_DIR`)

**Frontend files:**
- React components: `PascalCase.jsx` (`AnalyzeStep.jsx`, `GenerateStep.jsx`, `VideoCard.jsx`)
- Hooks: `camelCase.js` prefixed with `use` (`useApiKeys.js`)
- Utility modules: `camelCase.js` (`api.js`, `storage.js`)
- Pages: `PascalCase` suffixed with `Page` (`ProductPage.jsx`, `ContentPage.jsx`, `GalleryPage.jsx`)

**Frontend identifiers:**
- Component functions: `PascalCase` default export
- Handler functions: `handle` prefix (`handleSubmit`, `handleSelect`)
- State variables: `camelCase` nouns (`scripts`, `selectedScript`, `actorImageUrl`, `voiceId`)
- API functions exported from `api.js`: verb + noun camelCase (`analyzeProduct`, `generateVideo`, `getJobStatus`, `generateContentScripts`)

## Code Style

**Python formatting:**
- No formatter config detected (no `.black`, `.isort`, `pyproject.toml` with tool sections)
- PEP 8 style followed manually: 4-space indents, 2 blank lines between top-level functions
- Module docstrings present on `saasshorts.py`, `content.py`, `s3_uploader.py`; absent on `subtitles.py`, `hooks.py`
- Section separators using `═══` comment banners in `saasshorts.py` to group pipeline phases

**Frontend formatting:**
- No Prettier config detected
- 2-space indentation in JSX
- Single-quoted strings in JS, double-quoted in JSX attributes
- ESLint configured via `package.json` scripts: `eslint . --ext js,jsx --max-warnings 0`

## Import Organization

**Python:**
1. Standard library (`os`, `re`, `json`, `time`, `subprocess`)
2. Third-party (`httpx`, `fastapi`, `pydantic`)
3. Local modules (`from saasshorts import ...`, `from content import ...`)
4. Lazy imports inside functions for optional/heavy deps (`from google import genai`, `from faster_whisper import WhisperModel`, `from bs4 import BeautifulSoup`, `import boto3`) — done to avoid import-time failures when optional deps absent

**Frontend:**
1. React core (`import { useState, useEffect } from 'react'`)
2. Third-party (`lucide-react`, `react-router-dom`)
3. Local lib (`../../lib/api`, `../../lib/storage`)
4. Local hooks (`../../hooks/useApiKeys`)
5. Local components (`../shared/Spinner`, `../product/AnalyzeStep`)

## Error Handling

**Python backend pattern:**
- FastAPI endpoints raise `HTTPException(status_code, detail)` directly on validation failures
- Background job workers catch all `Exception` with a bare `except Exception as e` block, log to job's `logs` array via the `log()` closure, set `job["status"] = "failed"` — never re-raise
- External API calls check `resp.status_code` explicitly before using response: `if resp.status_code != 200: raise Exception(...)`
- fal.ai polling retries on network errors (`except Exception as e: print(...); time.sleep(5); continue`)
- S3 functions return `None` on any failure (never raise); callers check for `None` return
- Gemini responses: strip markdown fences then `json.loads` with explicit `except json.JSONDecodeError as e: raise Exception(...)` — consistent across `saasshorts.py` and `content.py`
- Optional features (nikkud vocalization, S3 upload) use best-effort try/except that returns original value on failure

**Frontend pattern:**
- `try/catch` inside `async function` handlers, set `error` state on failure
- `catch (e) { setError(e.message) }` — always propagate `e.message` to UI
- API helper `json()` in `api.js` throws `new Error(text || 'HTTP ${res.status}')` when `!res.ok`
- Job polling clears interval on both `completed` and `failed`

## Logging

**Python:**
- `print(f"[ModuleName] emoji action: detail")` pattern throughout — no structured logger in pipeline code
- `logger = logging.getLogger(__name__)` used only in `s3_uploader.py` (infrastructure layer)
- Progress prefixes: `[SaaSShorts]`, `[fal.ai]`, `[Content]`
- Emoji conventions: `🔍` research, `🌐` scrape, `🧠` analyze, `📝` scripts, `🎨` image gen, `🎙️` voiceover, `🗣️` talking head, `🎬` broll/compositing, `✅` success, `⚠️` warning/skip, `❌` error
- Job logging uses a `log: Callable[[str], None]` parameter passed into pipeline functions, defaulting to `print` — allows app.py to capture logs into the jobs dict

**Frontend:**
- No structured logging; `console.error`/`console.log` not used — errors surfaced directly to UI state

## FFmpeg Filter-Graph Patterns

**Core pattern — Ken Burns (zoompan) on still images:**
```python
# backend/saasshorts.py:generate_broll, backend/content.py:_apply_ken_burns
zoompan_filter = (
    f"scale=2160:3840,"
    f"zoompan=z='1+0.15*on/{total_frames}':"
    f"x='iw/2-(iw/zoom/2)+10*on/{total_frames}':"
    f"y='ih/2-(ih/zoom/2)':"
    f"d={total_frames}:s=1080x1920:fps={fps},"
    f"setsar=1"
)
# Always paired with: -loop 1 -i img, -f lavfi -i anullsrc, -map 0:v -map 1:a
```
Directions: `in` (zoom forward + slight pan), `out` (zoom backward), `pan_right`.

**Composite video pattern (concat + subtitle burn-in):**
```python
# backend/saasshorts.py:composite_video
norm = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1"
# Each segment: [N:v]trim=start=X:end=Y,setpts=PTS-STARTPTS,{norm}[label]
# Audio always comes from stream 0 (talking head), even under b-roll segments
# concat=n={n}:v=1:a=1 then sub_filter appended: [outv]{sub_filter}[finalv]
```

**Subtitle filter selection:**
```python
# backend/saasshorts.py:composite_video
if srt_path.endswith(".ass"):
    sub_filter = f"ass={safe_sub}"          # ASS: use ass= filter directly
else:
    sub_filter = f"subtitles={safe_sub}:force_style='{sub_style}'"  # SRT fallback
# Path escaping: replace('\\', '/').replace(':', '\\:').replace("'", "\\'")
```

**Music mix with voice (content pipeline):**
```python
# backend/content.py:_composite_content_video
# aloop=-1 loops music infinitely, then atrim to total_duration
# amix=inputs=2:duration=longest:dropout_transition=2 mixes voice + music
# Music volume: 0.15 (background level)
# Tail padding: apad=pad_dur={tail_seconds} on voice so music persists during fade-out
# Audio/video fade-out: afade/fade at same st= and d=
```

**Ambient music synthesis via FFmpeg lavfi:**
```python
# backend/content.py:_build_music_filter, _ensure_music_files
# Multiple sine inputs → volume+tremolo per voice → amix → LFO swell (volume with sin()) → aecho cascade → bass+lowpass+compand
# LFO swell: volume='0.55+0.45*sin(2*PI*{lfo_hz}*t)':eval=frame
# Reverb chain: aecho=0.88:{decay}:{delay_ms}:{wet}
```

**Subtitle burn via `subtitles=` with force_style (legacy SRT path):**
```python
# backend/subtitles.py:burn_subtitles
f"subtitles='{safe_srt_path}':force_style='{style_string}'"
```

**ASS subtitle format:**
- `PlayResX: 1080`, `PlayResY: 1920` (9:16 vertical)
- TikTok style: `Fontsize=90`, `Bold=-1`, `Outline=4`, `Alignment=5` (center)
- Hebrew RTL: `{\an5}` inline tag prepended to each dialogue line
- Font: `Arial Hebrew` on macOS for Hebrew; `Arial Black` for Latin

## Hebrew/RTL Handling

**Detection — two methods used:**
```python
# Method 1: Unicode block range check (backend/saasshorts.py, content.py)
is_hebrew = language == "he" or any('א' <= ch <= 'ת' for ch in all_text_raw)

# Method 2: Broader Unicode range (backend/hooks.py)
def _is_hebrew(text: str) -> bool:
    return any('֐' <= c <= '׿' for c in text)
```

**Subtitle rendering:**
- Hebrew text is NOT uppercased (ASS subtitles): `text = joined if is_hebrew else joined.upper()`
- ASS alignment tag `{\an5}` added per-event for Hebrew (center alignment code 5)
- Font: `Arial Hebrew` (macOS built-in) — noted in code that Linux needs `fonts-noto-sans-hebrew`

**Whisper transcription:**
- Hebrew: `model_size = "small"` (base model misclassifies accented Hebrew TTS)
- Language hint always passed when known: `language=language` in `model.transcribe()`
- Auto-detect explicitly documented to fail for Hebrew (`backend/saasshorts.py:1066`)

**ElevenLabs TTS for Hebrew:**
- Content pipeline: tries `eleven_v3` with `language_code: "he"` → `eleven_v3` without → `eleven_multilingual_v2` fallback
- UGC pipeline: uses `eleven_multilingual_v2` directly
- Nikkud (vowel marks) added before TTS via `_vocalize_hebrew()` in `content.py` to improve pronunciation

**Frontend RTL:**
- URL input: `dir="ltr"` explicitly set (Hebrew UI but URLs are LTR)
- All UI labels are in Hebrew but no `dir="rtl"` on container elements — relies on browser auto-detect
- Script card buttons: `text-right` Tailwind class for RTL text alignment

## Prompt Engineering Patterns (Gemini / ElevenLabs)

**Gemini JSON output mode:**
```python
config=types.GenerateContentConfig(response_mime_type="application/json")
# Used for: analyze_saas, generate_scripts, generate_content_script
# For text responses: response_mime_type omitted, parse manually
```

**JSON parsing defensive pattern (used in every Gemini call):**
```python
text = raw.strip()
if text.startswith("```"):
    text = re.sub(r"^```(?:json)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
start = text.find("{")   # or text.find("[") for arrays
end = text.rfind("}")    # or text.rfind("]")
if start != -1 and end != -1:
    text = text[start : end + 1]
json.loads(text)
# Location: backend/saasshorts.py:133-145, 347-360, 546-553; backend/content.py:317-326
```

**Script generation prompt structure:**
- Language instructions injected as a dedicated section: `lang_instructions = ""` then `if language == "he": ...`
- Schema defined in-prompt as a JSON template with comments (not a system prompt)
- Constraints repeated at end as `RULES:` list for emphasis
- Actor descriptions always forced to English regardless of script language (prevents image generation from breaking)
- Hebrew UGC hook examples provided inline as few-shots: `"רגע, לא ידעתם שזה קיים?..."`

**Vocalization prompt (nikkud):**
```python
# backend/content.py:_vocalize_hebrew
# temperature=0.0 for deterministic output
# Integrity check: Hebrew letter sequence must be identical before/after
# Falls back to original text on any alteration
```

**Gemini Google Search grounding:**
```python
config=types.GenerateContentConfig(
    tools=[types.Tool(google_search=types.GoogleSearch())]
)
# Used only in research_saas_online (backend/saasshorts.py)
# Grounding sources extracted from response.candidates[0].grounding_metadata
```

**ElevenLabs voice settings:**
- UGC/SaaS: `stability=0.5, similarity_boost=0.75, style=0.4, use_speaker_boost=True`
- Content/philosophical: `stability=0.45, similarity_boost=0.80, style=0.6, use_speaker_boost=True` (more expressive)
- Model: `eleven_multilingual_v2` (UGC), `eleven_v3` preferred (content)

## Function Design

**Python:**
- Pipeline functions accept `log: Callable[[str], None] = print` — allows log capture without coupling to FastAPI
- Config passed as flat `dict` rather than typed dataclass (pragmatic approach)
- Asset caching via `_exists(path)` helper: `os.path.exists(path) and os.path.getsize(path) > 0`
- Parallel execution via `ThreadPoolExecutor` with `as_completed` — used for: actor image + voiceover, multiple b-roll clips, background images

**Frontend:**
- Components are single-responsibility step components; each manages its own loading/error state
- No shared state manager (no Zustand/Redux) — state passed via `onComplete(result)` callbacks between steps
- API keys stored in `localStorage`, read via `useApiKeys` hook, passed to every API call

## Module Design

**Python:**
- `saasshorts.py` is the core pipeline module; `content.py` imports and reuses internal helpers (`_fal_run`, `_get_media_duration`, `generate_tiktok_subs`)
- `app.py` orchestrates: imports from `saasshorts`, `content`, `s3_uploader`; wraps sync pipeline in `loop.run_in_executor(None, fn, *args)` for async compatibility
- No barrel `__init__.py` — direct imports by module name

**Frontend:**
- `src/lib/api.js`: all fetch calls, single `json(res)` error helper
- `src/lib/storage.js`: localStorage key/value (2 functions)
- `src/hooks/useApiKeys.js`: single hook, reads/writes storage
- No barrel `index.js` files — components imported by full path

---

*Convention analysis: 2026-05-22*
