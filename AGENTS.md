# OpenWave – Agent Guidelines

This repository contains the OpenWave AI audio-first news briefing application.

Agents (Codex or other AI coding assistants) must follow these rules.

## Repository structure

The project must keep the following structure:

backend/
flutter_app/
docs/

Do NOT create alternative folders such as:

mobile/
frontend/
app/
client/

If a folder is missing, recreate it instead of inventing a new structure.

## Backend

Backend is built with FastAPI.

Main responsibilities:

- article retrieval
- Daily Brief generation
- API endpoints

Core endpoints:

GET /articles  
GET /briefing/today

Backend structure:

backend/app/main.py  
backend/app/api/routes.py  
backend/app/models/article.py  
backend/app/models/briefing.py  
backend/app/services/article_service.py  
backend/app/services/briefing_service.py  

Future services:

rss_ingestion_service.py  
summarization_service.py  

## Mobile app

Mobile app is built with Flutter.

Main screens:

HomeScreen  
PlayerScreen

Flutter structure:

flutter_app/lib/main.dart  
flutter_app/lib/models/  
flutter_app/lib/services/api_service.dart  
flutter_app/lib/screens/home_screen.dart  
flutter_app/lib/screens/player_screen.dart  

## Development rules

When implementing tasks:

1. Modify only the necessary files.
2. Do not change the repository structure unless explicitly requested.
3. Commit changes after completing a task.
4. Show the list of modified files.
5. Do not introduce new frameworks or major dependencies without justification.

## Documentation

When architecture changes, update documentation:

docs/PROJECT_CONTEXT.md  
docs/TASKS.md  
docs/DAILY_LOG.md  
docs/ARCHITECTURE.md
## Execution rules

- Do not run tests unless explicitly requested.
- Do not install dependencies unless explicitly requested.
- Do not run the development server unless explicitly requested.
- Prefer small, incremental diffs.
- Stop after showing the diff for each task.