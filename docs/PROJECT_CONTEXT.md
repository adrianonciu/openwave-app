# OpenWave Project Context

OpenWave is an AI audio-first news briefing mobile app.

Main idea:
Users listen to daily briefings instead of reading articles.

Tech stack:
- Flutter mobile app
- FastAPI backend
- PostgreSQL
- LLM summarization
- TTS audio

MVP features:
- news ingestion
- article summarization
- audio generation
- player screen
- onboarding

# OpenWave

OpenWave is an AI audio-first mobile app that generates personalized daily news briefings.

Users listen to short audio briefings instead of reading many articles.

## Current MVP

Backend:
- FastAPI
- endpoints: /articles, /briefing/today

Frontend:
- Flutter mobile app
- Home screen
- Player screen

Repository structure:

backend/
flutter_app/
docs/

Next goal:
Generate Daily Brief from real RSS news articles.
Current backend infrastructure also includes a unified source watcher layer for
detecting the newest published content across news and commentary sources.
This layer is intentionally limited to content detection and state tracking.

