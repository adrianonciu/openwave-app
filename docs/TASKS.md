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
