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

Current backend infrastructure also includes a deterministic variation layer inside the story summary generator so attribution-first lines can rotate between equivalent radio-safe phrasings without introducing randomness.

Current backend infrastructure also supports a dual-presenter bulletin draft mode in briefing assembly, with alternating female/male story voices, deterministic intro/outro variants, and short pass-phrase markers kept separate from TTS generation for now.

Current backend infrastructure also supports optional listener first-name personalization in briefing assembly, but only for intro/outro lines and with a hard cap of two mentions per bulletin.

Current backend infrastructure also supports optional short news stingers in the audio-generation package, inserted only between stories and kept configurable without changing TTS provider internals.

Current backend infrastructure also reintegrates the `Two Perspectives` editorial feature into the modern assembly pipeline. Perspective pairs are now decided in briefing assembly, are limited to one pair per bulletin, appear only for controversial or disputed stories, and are carried forward as existing `Segment.TYPE_PERSPECTIVE` blocks for downstream audio generation.

The older demo-only perspective insertion in the legacy `BriefingService` path is no longer used, so perspective behavior now has one canonical integration point in the editorial pipeline.

Current backend infrastructure also includes a canonical editorial preference profile for geography and domain sliders. The modern end-to-end request path can now carry these values into the editorial pipeline and preserve them in the final editorial package, even though scoring, selection, and bulletin-composition weighting are still pending.

Current backend infrastructure also applies editorial preferences conservatively inside story selection. Geography and domain sliders now act as soft near-tie signals in selection, while score remains the main driver and clearly stronger stories are not displaced just to satisfy the requested mix.

Current backend infrastructure now treats personalization as a permanent pipeline contract through a canonical `UserPersonalization` object. Listener identity, listener location, and editorial preferences are resolved at request time, transported through the editorial pipeline, and exposed in final output together with explicit default/fallback explainability. For local editorial anchoring, the listener region or county is the primary location signal; city remains stored as secondary metadata and fallback only. Story selection now uses that regional anchor conservatively as a soft near-tie signal when local preference is enabled.

Current backend infrastructure also includes a canonical Romanian county-based local source registry used by the source monitoring layer. When a listener region is available and local preference is enabled, SourceWatcher can operationally ingest and actively monitor region-first local media sources such as `ziaruldeiasi.ro`, `bzi.ro`, and `ieseanul.ro` for Iasi, with a conservative per-region cap. City remains metadata only and does not activate local source monitoring.
Current backend infrastructure also includes an expanded non-local source registry in the main watcher config. SourceWatcher now carries normalized scope/category metadata for Romanian national and international sources while preserving the existing county-local registry as a separate activation path.
That watcher metadata now also includes a conservative `editorial_priority` field so later scoring layers can distinguish between wire services, major outlets, standard publications, niche analysis, and lower-relevance entertainment or aggregator sources without changing the current pipeline behavior yet.

Current backend infrastructure also keeps a lightweight continuity state for the most recent bulletin so recurring clusters can be marked as updates in later summaries without affecting scoring or selection.
Current Flutter app infrastructure now includes a real personalization flow with a two-step onboarding wizard, reusable settings editing, local device persistence, and request payload integration for backend bulletin generation. Listener profile and editorial preferences are now captured in-app and reused for future briefings without interrupting the current playback session.

Current backend infrastructure also includes a conservative TTS budget preflight layer for end-to-end bulletins. Before segmented audio generation starts, the backend estimates normalized TTS size, checks provider quota when available, and returns structured budget errors plus estimate metadata so Flutter can fail gracefully without exposing raw provider exceptions.

Current backend infrastructure also supports a temporary OpenAI TTS test provider mode alongside ElevenLabs. Provider selection still flows through the existing presenter config and factory, segmented output naming is unchanged, and presenter-name mapping now allows Ana/alloy and Paul/verse for lower-cost bulletin audio tests.

Current backend infrastructure also supports a conservative dual presenter test mode in the editorial-to-audio bridge. When enabled, intro/outro use Ana, story blocks alternate Ana/Paul by story index, perspective segments inherit the parent story presenter, and the existing single-presenter path remains unchanged for normal use.
Current backend infrastructure also includes a mandatory editorial contract validation gate. After briefing assembly and sizing produce the final editorial package, `EditorialContractValidationService` validates story-level and bulletin-level rules, writes a structured debug report, and blocks invalid bulletins before the editorial-to-audio bridge starts.
Current backend infrastructure also treats `story_summary_generator_service.py` as the explicit Story Editorial Composition stage. Selected clusters are now composed into structured editorial stories with story type, headline, lead, body, source attribution, quotes, and editorial notes before briefing assembly and before the editorial contract validation gate.


Shared editorial profile routing now exists in backend debug selection flows. National RO and international Top 5 runs are routed through a common `EditorialSelectionCoreService`, while a skeletal `local` profile already validates the future local path without changing Flutter or audio behavior.


Story families now provide light lifecycle support in ranking. Recurring families persist `first_seen`, `last_seen`, and `run_count`, and can add a small continuity boost while still respecting profile selection logic and family diversity limits.
