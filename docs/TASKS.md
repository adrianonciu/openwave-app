# OpenWave / Angle – Development Tasks

This document tracks the current development tasks and priorities.

Agents must respect the order of priorities and should not implement future-stage features unless explicitly requested.

Architecture reference:
docs/PROJECT_MAP_v2.md

Agent rules:
docs/AGENTS_v2.md

---

# Current Phase

MVP Stabilization

The system already includes:

- RSS ingestion
- Article generation
- DailyBriefing generation
- FastAPI endpoints
- Flutter API integration
- Flutter HomeScreen displaying briefing

Current pipeline:

RSS
→ Article
→ DailyBriefing
→ FastAPI endpoint
→ Flutter API call
→ HomeScreen

Goal of this phase:

Stabilize the pipeline and prepare for the Segment architecture.

---

# Immediate Tasks (Next)

## Task 1 – Introduce Segment Model

Add a new backend model:

backend/app/models/segment.py

Segment represents a playable editorial unit.

Fields (initial):

id  
type  
title  
summary  
source  
estimated_duration_seconds  
tags  
article_id

Do not remove Article usage yet.

Segment will coexist with Article during migration.

---

## Task 2 – Implement Segment Service

Create:

backend/app/services/segment_service.py

Responsibilities:

- convert Article → Segment
- estimate duration
- assign basic tags

Example duration logic:

150 words ≈ 45 seconds

Segment service must not modify existing APIs yet.

---

## Task 3 – Update Briefing Generation

Modify:

backend/app/services/briefing_service.py

Instead of building the briefing directly from Articles,
generate Segments first and then assemble the briefing.

Pipeline should become:

Article
→ Segment
→ DailyBriefing

API response format must remain unchanged.

---

## Task 4 – Add Segment Metadata

Enhance Segment model with:

source_tier  
content_type  
language  
tags

This prepares future features such as:

- source balancing
- challenge mode
- fact checking

No UI change required.

---

## Task 5 – Prepare Session Model

Add new model:

backend/app/models/session.py

Session represents a listening experience.

Fields:

id  
session_type  
title  
duration_seconds  
segments  
created_at

Do not replace DailyBriefing yet.

Session model is preparation for dynamic playlists.

---

# Medium-Term Tasks

These tasks are important but should not be implemented yet unless requested.

## Playlist Service

backend/app/services/playlist_service.py

Responsible for assembling segments into sessions based on duration.

Example:

Briefing → 5 minutes  
Commute → 24 minutes  
Deep Dive → 20+ minutes

---

## Source Selection Engine

backend/app/services/source_selection_service.py

Implements editorial balancing:

- mainstream
- progressive
- traditional

Supports sliders in onboarding.

---

## Fact Check Service

backend/app/services/fact_check_service.py

Adds contextual notes to questionable statements.

Example:

"Context: official statistics contradict this claim."

---

## Audio Orchestration

backend/app/services/audio_orchestration_service.py

Responsible for:

- selecting TTS provider
- generating audio
- storing audio_url

---

# Flutter Tasks (Upcoming)

## PlayerScreen

Add:

flutter_app/lib/screens/player_screen.dart

Responsibilities:

- display segment playlist
- allow navigation between segments
- prepare for audio playback

---

## Segment UI

Extend HomeScreen to display:

- source
- summary
- duration

instead of only titles.

---

# Tasks Explicitly NOT Allowed Yet

Agents must NOT implement:

- Spotify integration
- Apple Music integration
- AI voice cloning
- full personalization engine
- influencer ingestion
- user preference profiles
- real-time breaking streams

These belong to later phases.

---

# Development Philosophy

OpenWave must evolve in small steps.

The priority order is:

1. stable ingestion
2. clean domain models
3. segment architecture
4. session assembly
5. audio playback
6. personalization

Avoid implementing complex systems too early.

---

## Completed Infrastructure

### Unified Source Watcher

Backend now includes a unified source watcher for:

- news
- commentary

Current scope:

- prefer RSS when available
- fall back to listing page detection
- fall back to page metadata parsing
- detect latest content by publication time
- persist watcher state in JSON

Still intentionally excluded from this task:

- summarization
- clustering
- TTS integration
- audio generation changes

### Article Fetch And Clean Layer

Backend now includes a fetch-and-clean layer for detected articles.

Current scope:

- download article HTML
- extract main article text
- prefer JSON-LD article body when available
- fall back to `<article>` extraction
- fall back to heuristic block extraction
- clean paragraph text for future editorial pipelines
- reject very small or broken extractions

Still intentionally excluded from this task:

- summarization
- clustering
- editorial scoring
- briefing assembly

### News Clustering V1

Backend now includes a conservative clustering layer for fetched news articles.

Current scope:

- cluster only clearly related articles
- combine recency window checks with title similarity
- use shared entities and keyword overlap as supporting signals
- keep borderline stories separate when overlap is weak
- choose a representative title with a simple explicit rule

Still intentionally excluded from this task:

- summarization
- editorial scoring
- briefing assembly

### Story Scoring V1

Backend now includes an explainable story scoring layer for clustered stories.

Current scope:

- score clusters with explicit weighted heuristics
- increase score for fresher and multi-source stories
- add modest bonuses for important entities and hard-news topics
- expose score breakdowns and explanations for inspection
- keep scoring independent from final story selection

Still intentionally excluded from this task:

- story selection
- summarization
- briefing assembly
