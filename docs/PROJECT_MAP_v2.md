# OpenWave / Angle – PROJECT_MAP v2

## 1. Project summary

OpenWave (future commercial name: Angle / AngleFM) is an AI audio-first news briefing application.

The product transforms articles from multiple sources into short, structured listening sessions.

Users should not be forced into a black-box algorithm. They should be able to control source balance, editorial mix, and session style.

Core principle:

Article = raw content
Segment = playable editorial unit
Session = assembled listening experience

---

## 2. Product direction

Current MVP focus:
- ingest real news articles
- generate a daily briefing
- expose backend API
- display briefing in Flutter

Future product direction:
- dynamic session assembly
- source balancing and editorial control
- challenge mode / opposing perspective insertion
- fact-check contextualization
- AI-generated audio playback
- commute-length adaptive sessions
- music layer integration later

---

## 3. Repository structure

The repository must keep this exact structure:

backend/
flutter_app/
docs/

Do NOT create alternative project roots such as:
- mobile/
- frontend/
- client/
- app/

If a folder is missing, recreate the expected folder instead of inventing a new one.

---

## 4. Current architecture

### Backend
FastAPI backend is responsible for:
- article retrieval
- summarization pipeline
- segment generation
- briefing/session generation
- API endpoints

### Mobile
Flutter app is responsible for:
- fetching briefing/session data from backend
- rendering session UI
- later audio playback

---

## 5. Backend structure

backend/app
├── main.py
├── api
│   ├── routes.py
│   └── schemas.py              # optional later
├── models
│   ├── article.py
│   ├── briefing.py
│   ├── segment.py              # add next
│   ├── session.py              # add later
│   └── source_profile.py       # add later
├── services
│   ├── rss_ingestion_service.py
│   ├── article_service.py
│   ├── summarization_service.py
│   ├── segment_service.py
│   ├── briefing_service.py
│   ├── playlist_service.py
│   ├── source_selection_service.py
│   ├── fact_check_service.py
│   └── audio_orchestration_service.py
└── core
    ├── settings.py
    └── constants.py

Important:
Not all files must exist immediately.
Add them incrementally when needed.

---

## 6. Core domain models

### Article
Raw normalized news item from RSS or other sources.

Typical fields:
- id
- title
- source
- summary
- url
- published_at
- tier (later)
- language (later)
- tags (later)
- content_type (later)

Article is the raw content layer.

### Segment
Playable editorial unit derived from one or more articles.

Typical fields:
- id
- type
- title
- summary
- source
- source_tier
- audio_url
- estimated_duration_seconds
- tags
- stance
- challenge_level
- article_id

Segment types may include:
- news
- analysis
- opinion
- fact_check
- local
- breaking
- joke

Segment is the core unit for playlists and audio sessions.

### Session
A dynamically assembled listening experience.

Typical fields:
- id
- session_type
- title
- duration_seconds
- segments
- created_at

Session types may include:
- briefing
- commute
- deep_dive
- breaking

### DailyBriefing
For MVP compatibility, DailyBriefing remains available as a simple session-like response.

Long term:
DailyBriefing should be treated as a specialized session of type "briefing".

---

## 7. Service responsibilities

### rss_ingestion_service.py
Reads RSS feeds and normalizes feed items.

Responsibilities:
- fetch RSS feeds
- parse feed items
- return normalized raw entries

### article_service.py
Builds Article objects from normalized feed items.

Responsibilities:
- convert RSS items into Article objects
- clean summaries
- sort by published date
- limit result sets
- later deduplicate and filter

### summarization_service.py
Creates short transformatively rewritten summaries.

Responsibilities:
- produce short summaries for playback
- adapt summary density by session type
- later support copyright-safe rewriting

### segment_service.py
Converts Article objects into Segment objects.

Responsibilities:
- assign segment type
- estimate duration
- attach metadata and tags
- prepare content for briefing/session use

This service is the next key backend step.

### briefing_service.py
Builds the DailyBriefing response.

Current MVP responsibilities:
- take top articles
- generate a simple briefing
- expose headline, highlights, articles

Future responsibilities:
- build briefing from Segment objects
- include challenge/context/fact-check segments

### playlist_service.py
Builds sessions with target duration.

Responsibilities:
- assemble segment playlists
- fit content to target duration
- support briefing / commute / deep-dive session generation

### source_selection_service.py
Applies editorial balance rules.

Future responsibilities:
- mainstream / progressive / traditional balancing
- facts vs opinions balancing
- challenge me logic

### fact_check_service.py
Adds context or contradiction notes to questionable claims.

Future responsibilities:
- verify selected viral or opinion content
- attach short factual context

### audio_orchestration_service.py
Handles TTS generation and audio metadata.

Future responsibilities:
- choose TTS provider
- generate segment audio
- store audio_url and voice metadata

---

## 8. Flutter structure

flutter_app/lib
├── main.dart
├── models
│   ├── article.dart            # optional later
│   ├── daily_brief.dart
│   ├── segment.dart            # later
│   └── session.dart            # later
├── services
│   └── api_service.dart
├── screens
│   ├── home_screen.dart
│   └── player_screen.dart
└── widgets
    └──                         # optional later

Important:
Keep Flutter code minimal and incremental.
Do not redesign the app architecture unless clearly needed.

---

## 9. Current API endpoints

Implemented:
- GET /health
- GET /articles
- GET /briefing/today

Planned later:
- GET /sessions/today
- GET /sessions/commute
- GET /breaking/live
- GET /sources
- POST /preferences

---

## 10. Current MVP status

Implemented:
- FastAPI backend scaffold
- RSS ingestion service
- article generation from RSS
- cleaned article summaries
- sorting articles by date
- DailyBriefing generation from real articles
- Flutter API integration
- Flutter HomeScreen showing real briefing data

Current working pipeline:
RSS
→ Article
→ DailyBriefing
→ FastAPI endpoint
→ Flutter API call
→ HomeScreen

---

## 11. Next backend priority

Next architectural step:
- add Segment model
- add segment_service.py
- make briefing generation rely on Segment objects instead of raw Article objects

Reason:
This is the bridge from article ingestion to audio-first playlist architecture.

---

## 12. Near-term development priority

1. Stabilize current MVP
2. Introduce Segment model
3. Introduce segment generation service
4. Build session/playlist logic
5. Add PlayerScreen
6. Add mock audio
7. Add real TTS orchestration
8. Add source balancing and challenge logic

---

## 13. Working rules for agents

Agents must:
1. modify only the necessary files
2. keep repository structure unchanged
3. avoid unnecessary refactors
4. prefer small incremental diffs
5. show modified files and diff
6. stop after each task
7. commit after each task
8. not install dependencies unless explicitly requested
9. not run server/tests unless explicitly requested

---

## 14. Product alignment rule

All new code should move the project toward this chain:

Article
→ Segment
→ Session
→ Audio playlist
→ Mobile listening experience

If a proposed change does not fit this direction, reconsider it before implementation.