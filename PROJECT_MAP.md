# OpenWave – Project Map

## Project summary
OpenWave is an AI audio-first news briefing application.

Users do not read multiple articles.
They listen to a short Daily Brief generated from news sources.

## Current project goal
Build the MVP that supports this flow:

RSS / test feed
→ article ingestion
→ summarization
→ Daily Brief generation
→ mobile app display
→ player screen
→ audio playback later

## Current repository structure

backend/
flutter_app/
docs/

## Backend structure

backend/app/main.py
- FastAPI entrypoint

backend/app/api/routes.py
- API routes
- /articles
- /briefing/today

backend/app/models/article.py
- Article model

backend/app/models/briefing.py
- DailyBrief and BriefingSegment models

backend/app/services/article_service.py
- article retrieval / management

backend/app/services/briefing_service.py
- Daily Brief generation

Future backend services:
- rss_ingestion_service.py
- summarization_service.py

## Flutter app structure

flutter_app/lib/main.dart
- app bootstrap

flutter_app/lib/models/article.dart
- Article model for Flutter

flutter_app/lib/models/daily_brief.dart
- DailyBrief and BriefingSegment for Flutter

flutter_app/lib/services/api_service.dart
- backend API communication

flutter_app/lib/screens/home_screen.dart
- Home screen
- shows articles or briefing

flutter_app/lib/screens/player_screen.dart
- Player screen
- shows title, source, summary, audio state

## Docs structure

docs/PROJECT_CONTEXT.md
- stable project context

docs/TASKS.md
- current task list

docs/DAILY_LOG.md
- daily progress log

docs/ARCHITECTURE.md
- technical notes and architecture decisions

## MVP scope
Included:
- backend FastAPI
- /articles endpoint
- /briefing/today endpoint
- article model
- DailyBrief model
- Flutter Home screen
- Flutter Player screen
- API integration
- RSS ingestion next
- summarization next

Not included yet:
- authentication
- notifications
- analytics
- explain mode
- reality mixer
- smart commute
- personalization engine
- real TTS orchestration
- advanced fact-checking

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
Do not create folders like:
- mobile/
- frontend/
- app/

Use only:
- backend/
- flutter_app/
- docs/
