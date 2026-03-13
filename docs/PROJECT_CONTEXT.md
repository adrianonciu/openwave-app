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

Current backend infrastructure also includes a conservative story summary generator that turns one selected story cluster into one short Romanian radio-style item with explicit policy-compliance checks.

Current backend infrastructure also includes a briefing assembly layer that turns generated story summaries into a coherent Romanian radio-style bulletin draft with intro, outro, ordering rationale, and estimated duration.

Current backend infrastructure also includes a bulletin sizing layer that enforces a target duration window on briefing drafts and reports explicit keep/remove sizing actions.

Current backend infrastructure also includes an editorial pipeline orchestration layer that turns fetched articles into a final sized text briefing package, carrying forward counts and explanations from clustering through sizing and staying ready for later segmented audio generation.
Current backend infrastructure also includes an editorial-to-audio bridge layer that converts a final sized editorial briefing into a segmented audio-generation package with intro, per-story segments, outro, and preserved topic/source metadata for the existing TTS pipeline.
Current backend infrastructure also includes an end-to-end bulletin generation layer that can run articles through the editorial pipeline, convert the result into segmented audio input, and trigger the existing TTS segment generation flow to produce final audio files.
Current backend infrastructure also includes a refined story summary generator that now adds a short editorial headline and one conservative attribution element per story, while preserving the existing three-sentence Romanian radio-style structure.
Current backend infrastructure also includes a further refined story summary generator that can expand major stories to 4 or 5 sentences and must mention casualties when deaths or injuries are clearly present in high-priority conflict, attack, disaster, or accident coverage.
Current backend infrastructure also applies an attribution-first radio rule in story summaries so generated statements begin with the speaker, institution, or source instead of using post-attributed audio-ambiguous forms.
Current backend infrastructure also includes radio lead generation in the story summary generator, so sentence one is now built from a configurable lead type heuristic instead of mostly mirroring the representative article title.

Current backend infrastructure also filters radio summaries more aggressively by keeping memorable short quotes, removing secondary numbers, and exposing simple pacing labels in briefing assembly so bulletins sound more balanced in audio.
