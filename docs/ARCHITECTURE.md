# OpenWave / Angle – System Architecture

This document describes the current technical architecture of the OpenWave system.

For conceptual architecture see:

docs/PROJECT_MAP_v2.md

---

# 1. System Overview

OpenWave is an AI-assisted news briefing platform.

It transforms news articles into structured listening experiences.

Current system flow:

RSS feeds
→ Article ingestion
→ Article normalization
→ Briefing generation
→ FastAPI API
→ Flutter mobile client

Future architecture will extend this pipeline toward:

Article
→ Segment
→ Session
→ Audio playlist
→ Mobile listening experience

---

# 2. Backend Architecture

Backend is implemented using **FastAPI**.

Responsibilities:

- ingest news sources
- normalize article content
- generate briefings
- expose API endpoints
- orchestrate audio generation (future)

Backend directory:
backend/app
main.py
api/routes.py
models/
services/
core/

---

# 3. Data Flow

Current data pipeline:
RSS feed
↓
rss_ingestion_service
↓
article_service
↓
Article objects
↓
briefing_service
↓
DailyBriefing
↓
API endpoint
↓
Flutter client

---

# 4. Core Models

## Article

Represents a normalized news item retrieved from RSS feeds.

Fields:

- id
- title
- source
- summary
- url
- published_at

Articles are the raw content layer.

---

## DailyBriefing

Represents the daily briefing delivered to the user.

Fields:

- date
- headline
- highlights
- articles

DailyBriefing is currently generated directly from Articles.

Future versions will generate briefings from Segments.

---

# 5. Services

## rss_ingestion_service

Fetches and parses RSS feeds.

Responsibilities:

- retrieve RSS data
- parse feed entries
- normalize feed items

---

## article_service

Transforms RSS entries into Article objects.

Responsibilities:

- map feed fields
- clean summaries
- strip HTML
- sort by publish date

---

## briefing_service

Generates the DailyBriefing response.

Responsibilities:

- retrieve articles
- select top items
- generate headline
- build highlight list

---

# 6. API Layer

Implemented endpoints:

GET /health

System health check.

GET /articles

Returns normalized articles from RSS feeds.

GET /briefing/today

Returns the generated DailyBriefing.

---

# 7. Flutter Client Architecture

Flutter is responsible for:

- calling backend APIs
- rendering briefing UI
- later audio playback

Structure:
flutter_app/lib
main.dart
models/
services/api_service.dart
screens/

---

# 8. Current MVP State

Working features:

- RSS ingestion
- Article generation
- Briefing generation
- FastAPI API
- Flutter UI displaying briefing

Current pipeline:
RSS
→ Article
→ DailyBriefing
→ FastAPI
→ Flutter UI

---

# 9. Planned Evolution

Next architectural step:

Introduce **Segment** model.

Future pipeline:
Article
→ Segment
→ Session
→ Audio playlist
→ Mobile listening experience

Segments will allow:

- dynamic playlist assembly
- commute-length sessions
- opinion insertion
- fact-check segments
- AI-generated audio

---

# 10. Architecture Principles

The system follows these principles:

- modular services
- clear domain models
- incremental evolution
- API-first backend
- mobile-first user experience

Avoid premature complexity.

The system should evolve gradually from a minimal MVP toward a full audio-first news platform.
