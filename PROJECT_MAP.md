# OpenWave – Project Map

## Project summary

OpenWave is an AI audio-first news briefing application.

Instead of reading many articles, users listen to a short Daily Brief generated from news sources.

The application aggregates articles, summarizes them, and presents them as an audio playlist.

## MVP goal

Build a minimal product that supports the following pipeline:

RSS feed
→ article ingestion
→ summarization
→ Daily Brief generation
→ mobile app display
→ audio playback (later)

## Repository structure

backend/
flutter_app/
docs/

## Backend architecture

FastAPI backend responsible for:

- retrieving articles
- generating Daily Brief
- serving API endpoints

Backend structure:

backend/app/main.py  
FastAPI entrypoint

backend/app/api/routes.py  
API routes

backend/app/models/article.py  
Article model

backend/app/models/briefing.py  
DailyBrief and BriefingSegment models

backend/app/services/article_service.py  
article retrieval

backend/app/services/briefing_service.py  
Daily Brief generation

Future services:

backend/app/services/rss_ingestion_service.py  
backend/app/services/summarization_service.py  

## Mobile architecture

Flutter mobile application.

Structure:

flutter_app/lib/main.dart  
application bootstrap

flutter_app/lib/models/article.dart  
Article model

flutter_app/lib/models/daily_brief.dart  
Daily Brief model

flutter_app/lib/services/api_service.dart  
API communication

flutter_app/lib/screens/home_screen.dart  
Home UI

flutter_app/lib/screens/player_screen.dart  
Player UI

## API endpoints

GET /articles  
returns article list

GET /briefing/today  
returns Daily Brief with segments

## Core models

Article

fields:
title  
source  
summary  
audio_url  

BriefingSegment

fields:
title  
source  
summary  
audio_url  

DailyBrief

fields:
title  
duration  
segments[]

## MVP scope

Included:

- FastAPI backend
- article model
- DailyBrief model
- /articles endpoint
- /briefing/today endpoint
- Flutter Home screen
- Flutter Player screen
- API integration

Not included yet:

authentication  
notifications  
analytics  
Explain Mode  
Reality Mixer  
Smart Commute  
personalization engine  
advanced fact-checking  
real TTS orchestration

## Development priority

1. Stabilize repository structure
2. Implement RSS ingestion
3. Implement summarization
4. Generate Daily Brief from real articles
5. Connect briefing to Flutter
6. Add mock audio
7. Add real audio playback

## Important rule

Do not create alternative project structures.

Do NOT create:

mobile/  
frontend/  
client/  

Use only:

backend/  
flutter_app/  
docs/
## Current status

Implemented:
- backend/app/main.py
- backend/app/api/routes.py
- backend/app/models/article.py
- backend/app/models/briefing.py
- backend/app/services/article_service.py
- backend/app/services/briefing_service.py
- backend/app/services/rss_ingestion_service.py

Working locally:
- FastAPI backend starts successfully
- Swagger UI works at /docs

Next step:
- connect rss_ingestion_service.py to article_service.py
- make /articles return real RSS-based Article objects