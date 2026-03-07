# OpenWave / Angle – Agent Guidelines (v2)

This repository contains the OpenWave AI audio-first news briefing application.

AI coding agents (Codex or similar assistants) must follow these rules when interacting with the repository.

The purpose of this document is to ensure that the project evolves in a controlled and maintainable way.

Agents must always respect the architecture defined in:

docs/PROJECT_MAP_v2.md

---

# 1. Core Concept

OpenWave converts news content into structured listening experiences.

Conceptual chain:

Article
→ Segment
→ Session
→ Audio Playlist
→ Mobile Listening Experience

Current MVP stage:

RSS
→ Article
→ DailyBriefing
→ FastAPI endpoint
→ Flutter UI

Future development must progressively evolve toward the full architecture without breaking the MVP pipeline.

---

# 2. Repository Structure

The repository must always keep this structure:

backend/
flutter_app/
docs/

Do NOT create alternative roots such as:

mobile/
frontend/
client/
app/

If a folder appears missing, recreate the expected folder rather than inventing a new one.

---

# 3. Backend Architecture

Backend is implemented using **FastAPI**.

Backend responsibilities:

- ingest news sources
- normalize article content
- generate segments
- assemble sessions/briefings
- expose API endpoints
- orchestrate audio generation (later)

Backend structure:

backend/app

main.py  
FastAPI application entrypoint

api/routes.py  
HTTP endpoints

models/  
Domain models

services/  
Application logic

core/  
Configuration and constants

---

# 4. Domain Model Hierarchy

Agents must understand the hierarchy of content.

Article  
Raw normalized news content from RSS or other sources.

Segment  
Editorial unit derived from one or more articles.

Session  
Listening experience composed of multiple segments.

DailyBriefing  
A specialized session type used by the MVP.

Agents must avoid bypassing this architecture.

New features should respect this pipeline.

---

# 5. Backend Services

Services implement application logic.

Agents should keep services small and single-purpose.

Current services:

rss_ingestion_service.py  
Fetches and parses RSS feeds.

article_service.py  
Builds Article objects from feed items.

briefing_service.py  
Builds the DailyBriefing response.

summarization_service.py  
Handles summary generation (future expansion).

Future services:

segment_service.py  
Transforms Article → Segment.

playlist_service.py  
Builds dynamic sessions based on duration.

source_selection_service.py  
Applies editorial balance rules.

fact_check_service.py  
Adds contextual fact verification.

audio_orchestration_service.py  
Handles TTS generation and audio metadata.

Agents should not implement future services unless explicitly requested.

---

# 6. Flutter Application

Flutter is responsible for:

- calling backend APIs
- rendering briefing/session UI
- controlling audio playback (later)

Flutter structure:

flutter_app/lib

main.dart  
Application bootstrap.

models/  
Client-side data models.

services/api_service.dart  
Backend API communication.

screens/  
UI screens.

widgets/  
Reusable UI components (optional later).

Agents must not redesign the Flutter architecture without explicit instruction.

---

# 7. API Endpoints

Currently implemented:

GET /health  
Health check endpoint.

GET /articles  
Returns normalized article list.

GET /briefing/today  
Returns the current DailyBriefing.

Future endpoints may include:

GET /sessions/today  
GET /sessions/commute  
GET /breaking/live  
GET /sources  
POST /preferences

Agents should not introduce new endpoints unless requested.

---

# 8. Coding Rules

Agents must follow these rules strictly.

1. Modify only the necessary files.

2. Do not refactor unrelated code.

3. Avoid architectural changes unless requested.

4. Prefer small incremental diffs.

5. Show the list of modified files.

6. Stop after showing the diff.

7. Create a commit after each completed task.

8. Do not introduce new frameworks.

9. Do not install dependencies unless explicitly requested.

10. Do not run servers or tests unless explicitly requested.

These rules exist to keep development deterministic and easy to review.

---

# 9. Commit Style

Commits should follow this pattern:

Short, descriptive, and focused.

Examples:

Add RSS ingestion service  
Connect article service to RSS ingestion  
Sort articles by publish date  
Generate DailyBrief from articles  
Add Flutter API integration

Avoid large multi-feature commits.

---

# 10. Documentation Rules

When architecture evolves, agents must update documentation in:

docs/

Relevant documents:

PROJECT_CONTEXT.md  
PROJECT_MAP.md  
PROJECT_MAP_v2.md  
TASKS.md  
DAILY_LOG.md  
ARCHITECTURE.md

Documentation should evolve together with code.

---

# 11. MVP Development Priority

Agents must respect the current development phase.

Current stage: MVP stabilization.

Priority order:

1. Stabilize article ingestion.
2. Generate consistent briefings.
3. Maintain clean API responses.
4. Ensure Flutter integration works.
5. Introduce Segment model.
6. Build session/playlist logic.
7. Implement PlayerScreen.
8. Introduce mock audio.
9. Add real TTS orchestration.

Agents should avoid implementing advanced features too early.

---

# 12. Product Alignment Rule

All future development must move the system toward:

Article
→ Segment
→ Session
→ Audio playlist
→ Mobile listening experience

If a proposed change does not align with this chain, reconsider the implementation.

---

# 13. Safety Rule

Agents must prioritize:

- simplicity
- clarity
- maintainability
- incremental progress

Avoid overengineering.

OpenWave is intentionally evolving from a minimal MVP toward a full audio-first platform.
