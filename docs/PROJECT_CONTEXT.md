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

Current backend infrastructure also includes an article fetch-and-clean layer that downloads a detected article page, extracts the main text, and returns cleaned editorial content for future pipelines.

Current backend infrastructure also includes a conservative news clustering layer that groups clearly related fetched articles into story clusters before later editorial processing.

Current backend infrastructure also includes a transparent story scoring layer that assigns editorial priority scores and score breakdowns to story clusters before later selection decisions.

Current backend infrastructure also includes a story selection layer that turns scored clusters into a bounded candidate set with explicit selection and rejection reasons before later briefing assembly.

Current backend infrastructure also includes an explicit story summary policy layer that defines how one selected story should be compressed into a short Romanian radio-style item before any future automated summarization.

