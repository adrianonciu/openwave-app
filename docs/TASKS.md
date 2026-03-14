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

Probe-only TTS note:
- OpenAI probe generation remains opt-in through provider override; default production TTS stays on ElevenLabs.
- Current probe contrast defaults are Ana `marin` and Paul `cedar`.
- Quick fallback pair for listening comparison: Ana `shimmer`, Paul `onyx`.

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

### Story Selection V1

Backend now includes a bounded story selection layer for scored clusters.

Current scope:

- select clusters primarily by score descending
- apply a minimum score threshold
- enforce a simple story-count limit
- use modest source and topic diversity soft caps
- expose explicit selection and rejection reasons

Still intentionally excluded from this task:

- summarization
- briefing assembly
- final radio ordering

### Story Summary Policy V1

Backend now includes an explicit editorial summary policy for selected stories.

Current scope:

- define Romanian radio-style structure for one story item
- prefer story compression over article compression
- define sentence and word-count targets
- define attribution and conflict-handling rules
- provide concrete examples by story category

Still intentionally excluded from this task:

- full summary generation
- briefing assembly
- TTS wording optimization

### Story Summary Generator V1

Backend now includes a conservative per-story summary generator guided by the summary policy.

Current scope:

- generate one Romanian radio-style story item at a time
- use the representative cluster title as the primary basis
- apply policy-compliance checks for sentence and word targets
- keep wording template-based and conservative
- remain independent from briefing assembly

Still intentionally excluded from this task:

- briefing assembly
- audio generation
- final bulletin duration optimization

### Briefing Assembly V1

Backend now includes a text-only briefing assembly layer for generated story summaries.

Current scope:

- assemble summaries into one Romanian radio-style bulletin draft
- open with the strongest available story
- use simple flow adjustments to avoid stacking very similar stories
- add templated intro and outro lines
- estimate total duration from total word count

Still intentionally excluded from this task:

- audio generation
- TTS integration changes
- aggressive bulletin duration optimization

### Bulletin Sizing V1

Backend now includes a bulletin sizing layer for duration control after briefing assembly.

Current scope:

- accept drafts already inside the target duration window
- flag drafts that are too short without expanding text
- trim trailing lower-priority stories when drafts are too long
- preserve story ordering for kept items
- expose explicit sizing actions and before/after durations

Still intentionally excluded from this task:

- audio generation
- TTS integration changes
- story text rewriting

### Editorial Pipeline Integration V1

Backend now includes an end-to-end orchestration layer for the editorial text pipeline.

Current scope:

- run clustering on fetched articles
- score clusters with the existing explainable scoring service
- select a bounded story set
- generate one Romanian radio-style summary per selected cluster
- assemble the summaries into a draft briefing
- size the draft to the target duration window
- expose final counts and sizing status in one package

Still intentionally excluded from this task:

- audio generation
- TTS redesign
- Flutter changes
- commentary pipeline integration
- advanced scheduling

### Editorial To Audio Integration V1

Backend now includes a minimal bridge from the editorial pipeline output to segmented audio-generation input.

Current scope:

- convert a final editorial briefing package into intro, story, and outro audio segments
- preserve topic and source metadata on story segments
- expose a package shape that can be consumed by the existing segmented TTS flow
- validate missing intro, story, or outro text with structured errors

Still intentionally excluded from this task:

- TTS provider changes
- ElevenLabs integration changes
- audio file generation changes
- Flutter changes
- normalization or pacing changes

### End-To-End Automatic Bulletin Generation V1

Backend now includes a minimal end-to-end orchestrator for automatic bulletin generation.

Current scope:

- run the existing editorial pipeline on fetched articles
- convert the final briefing into an audio generation package
- reuse the existing segmented TTS generation flow
- return generated segment URLs and filesystem paths with execution stats
- expose a lightweight backend route for developer-facing end-to-end runs

Still intentionally excluded from this task:

- Flutter changes
- TTS provider redesign
- editorial policy redesign
- commentary integration
- scheduling automation

### Story Summary Refinement V2

Backend now includes a refinement pass for per-story summary generation.

Current scope:

- generate a short 3-6 word editorial headline per story
- add one attribution element using quote, official statement, or source fallback
- keep the existing three-sentence structure
- stay conservative and explainable

Still intentionally excluded from this task:

- Flutter changes
- TTS provider changes
- wider editorial pipeline redesign
- aggressive rewriting beyond summary generation

### Story Summary Refinement V3

Backend now includes a second refinement pass for per-story summary generation.

Current scope:

- include deaths and injuries when clearly present in source titles
- allow 4-sentence summaries for major stories when needed
- allow 5-sentence summaries only for casualties plus short essential context
- expose flags for expanded summary, casualty line, and context line

Still intentionally excluded from this task:

- Flutter changes
- TTS provider changes
- editorial pipeline redesign
- background explainer generation

### Attribution-First Rule For Radio Summaries

Backend now applies attribution-first phrasing in per-story summaries.

Current scope:

- rewrite attributed statements into attribution-first radio form
- avoid post-attributed quote structures in generated summaries
- keep short quotes only when they remain clear in audio
- preserve the rest of the summary pipeline unchanged

Still intentionally excluded from this task:

- Flutter changes
- TTS provider changes
- wider editorial redesign

### Radio Lead Generation V4

Backend now includes structured radio lead generation in per-story summaries.

Current scope:

- classify stories into six lead types before sentence generation
- generate sentence one from the selected radio lead type
- keep attribution-first and expansion rules in place
- expose `lead_type` on generated summaries

Still intentionally excluded from this task:

- Flutter changes
- TTS provider changes
- wider editorial redesign

### Editorial Refinement V5

Backend now refines story summaries and briefing flow with:

- memorable short quote preservation when the quote improves radio clarity
- aggressive removal of secondary numbers that do not change story meaning
- pacing-aware bulletin ordering with `heavy`, `medium`, and `light` labels

Still intentionally excluded from this task:

- Flutter changes
- TTS provider changes
- wider editorial redesign

### Variation Engine For Radio Language

Backend now refines per-story summaries with deterministic attribution variation.

Current scope:

- rotate between attribution-first phrasings such as `Potrivit X`, `X spune ca`, `X afirma ca`, and `X arata ca`
- avoid a third consecutive repetition of the same attribution structure inside one bulletin run
- expose `attribution_variant` and `summary_variation_used` on generated summaries

Still intentionally excluded from this task:

- Flutter changes
- TTS provider changes
- random language generation

### Dual Presenter Bulletin Mode

Backend now supports a dual-presenter assembly mode for briefing drafts.

Current scope:

- alternate female and male presenters across ordered stories
- choose intro and outro from deterministic variant lists
- insert at most two short microphone-pass phrases between suitable topic shifts
- expose `presenter_voice`, `pass_phrase_used`, `intro_variant`, and `outro_variant` in briefing outputs

Still intentionally excluded from this task:

- Flutter changes
- TTS provider changes
- audio-generation redesign

### Listener First Name Personalization

Backend now supports optional listener-name personalization inside briefing assembly.

Current scope:

- allow `listener_first_name` in briefing assembly config
- personalize intro once when a listener name is configured
- optionally personalize outro once more without exceeding two total mentions
- expose `listener_name_mentions` on briefing outputs
- keep story summaries completely unaffected

Still intentionally excluded from this task:

- Flutter changes
- TTS provider changes
- personalization inside story text

### News Stingers And Micro-Transitions

Backend now supports optional stinger segments inside the audio generation layer.

Current scope:

- insert optional `stinger` audio blocks only between story segments
- keep stingers configurable and lightly rotated without consecutive repeats
- avoid stingers after intro, before outro, or when fewer than two stories exist
- preserve existing TTS segment generation by filtering stingers out of the spoken TTS block list

Still intentionally excluded from this task:

- Flutter changes
- TTS provider changes
- long jingles or music-bed logic

### Two Perspectives Reintegration

Backend now reconnects the `Two Perspectives` feature to the modern editorial pipeline.

Current scope:

- perspective pairs are assembled only for controversial or disputed stories
- reuse the existing perspective segment model and creator helper
- allow at most one supporters-vs-critics pair per bulletin
- place the pair immediately after the triggering main story
- keep the legacy `/briefing/today` path free of demo-only perspective insertion

Still intentionally excluded from this task:

- Flutter changes
- TTS provider changes
- multiple perspective pairs per bulletin
- perspective generation outside briefing assembly

### User Preference Reconnection

Backend now includes a canonical editorial preference profile for the modern pipeline.

Current scope:

- define one canonical model for geography and domain slider values
- accept preferences in the end-to-end bulletin generation request
- propagate preferences into the editorial pipeline and final editorial package
- document future influence points for scoring, selection, and briefing composition

Still intentionally excluded from this task:

- Flutter UI rewrite
- hard quotas
- full personalization balancing logic
- direct scoring or selection reweighting

### Preference-Aware Story Selection

Backend now applies editorial preferences conservatively inside story selection.

Current scope:

- use geography and domain preferences as soft near-tie tie-breakers
- keep score as the primary decision signal
- expose when a selection or rejection was influenced by editorial preferences
- avoid rigid quotas and avoid displacing clearly stronger stories

Still intentionally excluded from this task:

- Flutter changes
- preference-weighted story scoring
- quota-based editorial balancing
- aggressive bulletin recomposition

### User Personalization Contract

Backend now treats personalization as a permanent pipeline contract.

Current scope:

- canonical top-level `UserPersonalization` object
- listener identity and location fields carried through the pipeline
- normalized editorial preference mixes carried through the pipeline
- explicit explainability for personalization usage vs defaults
- safe neutral defaults when no personalization payload is provided

Still intentionally excluded from this task:

- Flutter redesign
- hard quotas
- city-based local ranking
- deeper listener-profile personalization logic
- continuity-aware selection or scoring changes
- aggressive crawling or ingestion expansion across all county registry sources
- city-driven local source activation
- aggressive crawling across the county source registry

### County Local Source Monitoring Activation

Backend now activates county-based local sources inside SourceWatcher when local preference is enabled.

Current scope:

- resolve county sources from the canonical Romanian local-source registry
- use listener region or county as the only local monitoring anchor
- append a conservative capped set of `local_county` watcher configs to the normal monitored source list
- expose whether county local monitoring was active through pipeline explainability

Still intentionally excluded from this task:

- Flutter changes
- aggressive crawling
- city-based source activation
- replacement of the core national/international watcher set
### Flutter Personalization Onboarding

Flutter now includes a production-oriented personalization flow.

Current scope:

- step 1 onboarding for first name, country, county or region, and optional city
- step 2 onboarding for geography and domain preference mixes
- local persistence of the canonical personalization object
- settings access from the player screen without breaking the current playback session
- request payload integration for the existing backend end-to-end bulletin generation contract

Still intentionally excluded from this task:

- Flutter player redesign
- backend contract redesign
- TTS logic changes
- new editorial rules

## Recently completed stabilization work

- Added conservative TTS budget preflight and structured quota handling for end-to-end personalized bulletin generation.
- Flutter now translates backend TTS budget failures into a user-facing recovery message with shorter-bulletin and lower-cost-mode suggestions.

- Added temporary OpenAI TTS test-provider support for segmented bulletin audio using `gpt-4o-mini-tts`, with Ana and Paul voice presets routed through the existing provider factory.

- Added backend-only `dual_test` presenter assignment in the editorial-to-audio bridge so story blocks alternate Ana/Paul, intro/outro use Ana, and perspective segments inherit the parent story presenter without requiring Flutter changes.

- Probe voice test scripts now force `provider_override="openai"` so Ana and Paul can be validated through OpenAI TTS without changing the default ElevenLabs production path.
