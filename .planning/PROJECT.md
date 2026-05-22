# Hebrew Shorts Generator

## What This Is

A Hebrew-first SaaS for generating Instagram-format short videos. Two flows: **Product/Service videos** (UGC-style with AI actor, narrating a website or product) and **Content videos** (poetic/educational text over AI-generated or user-uploaded imagery). Built for creators who want Hebrew shorts that sound and read like a native speaker made them — not an afterthought of an English-first tool.

## Core Value

**Hebrew that sounds and reads right.** Correct pronunciation (via auto-nikud) and correct subtitles (RTL, well-segmented, well-styled) are the non-negotiable. If the video pipeline produces fluent, professional Hebrew end-to-end, the product works; if not, nothing else matters.

## Requirements

### Validated

(None yet — ship to validate)

### Active

**Flow A — Product/Service video (UGC):**
- [ ] User inputs source (URL or text description) and picks a script angle/hook style
- [ ] User selects AI-generated actor (or uploads one) and a Hebrew voice/tone
- [ ] System generates b-roll visuals (auto from script or uploaded screenshots) with optional music bed
- [ ] Output is a 9:16 talking-head video with burned Hebrew subtitles and a hook overlay

**Flow B — Content video (poetic/free-text):**
- [ ] User provides free Hebrew text OR a topic prompt that the LLM expands into a script
- [ ] User picks visual aesthetic, music track, and voice character per video
- [ ] User chooses (per generation) AI-generated images OR uploads their own — system animates them across the voiceover
- [ ] Output is a 9:16 video with Hebrew voiceover, ambient music, and burned subtitles

**Hebrew Quality (cross-cutting):**
- [ ] Auto-add nikud to any Hebrew text before TTS, using an LLM (Gemini) or dedicated diacritization service
- [ ] TTS provider bake-off: compare ElevenLabs vs alternatives (Hume / PlayHT / OpenAI / others) on Hebrew pronunciation; pick the winner
- [ ] Subtitle segmentation: smart RTL line breaks, no awkward mid-phrase splits, punctuation-aware
- [ ] Subtitle styling: polished burn-in (font, weight, animation, optional word-level highlight)

**Platform:**
- [ ] BYO API keys (no auth in v1) — users paste own Gemini/ElevenLabs/fal keys, stored client-side
- [ ] Public gallery showcasing generated videos (existing pattern), SEO-indexable

### Out of Scope

- **Accounts, auth, billing in v1** — BYO keys ships faster; revisit once Hebrew quality is undeniable
- **Languages other than Hebrew** — focus is the wedge; English/Spanish complicate decisions about TTS providers and subtitle stacks
- **Long-form video (>~60s)** — Instagram shorts only; explicit format constraint
- **Mobile native apps** — web-only; mobile-responsive web is sufficient
- **Built-in social posting/scheduling for v1** — keep scope tight; the existing Upload-Post integration can stay but isn't a v1 deliverable

## Context

**Existing codebase (brownfield, but Hebrew-first rewrite of pipelines):**
- FastAPI backend (`backend/app.py`) with in-process queue worker, two pipelines: `saasshorts.py` (UGC) and `content.py` (philosophical/content).
- React/Vite frontend with ProductPage (UGC wizard), ContentPage (content wizard), GalleryPage.
- S3 (private + public buckets) with local-filesystem fallback for dev.
- Codebase map already exists in `.planning/codebase/` (ARCHITECTURE.md, STACK.md, CONVENTIONS.md, CONCERNS.md, STRUCTURE.md, INTEGRATIONS.md, TESTING.md).
- Reference pipeline lives at `/Users/yaniv/hebrew-shorts-generator/openshorts` (OpenShorts — the project this was forked from in concept).

**Prior work to preserve as scaffold (not auto-Validated):**
- Queue architecture (`process_job_queue` + semaphore in `app.py`) — keep
- S3 + local fallback uploader — keep
- BYO-keys via custom HTTP headers — keep
- FFmpeg composite + Ken Burns logic — keep, refine for Hebrew

**What's being rewritten Hebrew-first:**
- Script generation prompts (Hebrew templates with hook patterns that work in Hebrew)
- TTS layer (abstracted so we can swap providers during the bake-off)
- Nikud step (new — sits between script generation and TTS)
- Subtitle segmentation + styling (RTL-aware splitter, polished ASS templates)

**User's framing:** "Most important aspect is good Hebrew voices and correct subtitles in Hebrew."

## Constraints

- **Tech stack**: FastAPI (Python) + React/Vite — keep. Justified by existing codebase + ecosystem fit (Gemini, ElevenLabs, fal, FFmpeg).
- **Format**: 9:16 vertical, ~15–60s — Instagram Reels native.
- **Dependencies**: Gemini (scripts + nikud), ElevenLabs (TTS baseline, possibly replaced), fal.ai (image gen), AWS S3 (storage). Pipeline depends on FFmpeg subprocess.
- **Auth model (v1)**: BYO keys only — no server-side key storage, no accounts.
- **Performance**: Single user job in <5 min end-to-end (the v1 ship test).
- **Quality bar**: Hebrew TTS pronunciation must be indistinguishable-from-native to a native speaker (the user) for v1 to be considered ready.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hebrew-first rewrite of pipelines, keep architecture | Existing scaffold (queue, S3, FFmpeg, FastAPI) is solid; Hebrew quality lives in scripts/TTS/subs which need from-scratch attention | — Pending |
| Auto-add nikud via LLM (Gemini) in v1 | Hybrid editable UI is more work; dedicated APIs (Dicta/Nakdimon) are a v2 swap if LLM quality insufficient | — Pending |
| Run TTS provider bake-off before committing | "Best Hebrew voice" is the moat — picking blindly is too risky | — Pending |
| BYO keys, no auth in v1 | Ships faster; SaaS auth/billing only matters after Hebrew quality is proven | — Pending |
| Two distinct flows (Product UGC + Content) coexist | User wants both; they're product-shaped differently and shouldn't be forced into one wizard | — Pending |
| Ship test = end-to-end demo in <5 min | Concrete, demoable — closes a user in one sitting | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-23 after initialization*
