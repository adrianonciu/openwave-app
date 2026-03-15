## 2026-03-13

- resumed backend-only work on source discovery infrastructure
- added a unified source watcher for news and commentary
- enforced latest-by-publication-time detection instead of homepage prominence
- added JSON-backed watcher state persistence for last seen content
- exposed a minimal backend endpoint for running all watcher checks
- added an article fetch-and-clean service for extracting readable editorial text from article pages
- added conservative news clustering to group clearly related articles without editorial ranking
- added transparent story scoring with explicit weighted breakdowns for clustered stories
- added bounded story selection with explicit selection and rejection explanations
- added an explicit Romanian radio-style summary policy with machine-readable rules and examples
- added a conservative story summary generator with explicit policy-compliance checks
- added text-only briefing assembly with intro, outro, ordering rationale, and estimated duration
- added bulletin sizing with explainable duration control and tail-story removal

## 2026-03-14

- retuned OpenAI probe voices for stronger Ana/Paul separation while keeping ElevenLabs as the default production path
- expanded the main source watcher registry with Romanian national and international sources while preserving the separate county-local registry
- added normalized watcher metadata for source scope, category, country, language, enabled state, and notes so the existing config path can carry broader source coverage conservatively
- added conservative `editorial_priority` metadata across the loaded source registry so future scoring can distinguish wire, major, standard, niche, and low-relevance sources without changing selection logic yet
- changed probe OpenAI default voices to Ana `marin` and Paul `cedar`, with env overrides still supported
- added presenter-local OpenAI probe style instructions and a modest speed increase for slightly brisker radio pacing
- regenerated the existing probe bulletin set through the OpenAI provider override without changing probe script structure

# OpenWave Development Log

This file records important milestones and architectural decisions during the development of OpenWave.

It is not intended to list every commit.

## 2026-03-06

Major milestone: OpenWave MVP rebuilt with stable structure.

Completed:
- Created GitHub repository: adrianonciu/openwave-app
- Connected Codex environment to repository
- Standardized project structure:
  - backend/
  - flutter_app/
  - docs/

Backend:
- Implemented FastAPI skeleton
- Added endpoints:
  - GET /articles
  - GET /briefing/today
- Created models:
  - Article
  - DailyBrief
  - BriefingSegment
- Created services:
  - ArticleService
  - BriefingService

Frontend:
- Created Flutter app skeleton in flutter_app/
- Implemented:
  - HomeScreen
  - PlayerScreen
  - ApiService
  - Article and DailyBrief models

Docs:
- PROJECT_CONTEXT.md
- TASKS.md
- ARCHITECTURE.md
- DAILY_LOG.md

Next steps:
- RSS ingestion service
- article summarization
- Daily Brief generation from real articles
- connect Flutter Home screen to real briefing
## 2026-03-06

Major milestone.

- Git repository initialized locally
- Connected to GitHub repository: adrianonciu/openwave-app
- Saved initial project structure
- Resolved nested git repository issues
- Cleaned local folder structure
- Project now version-controlled and safely stored in GitHub

Current repository structure:
- ai_pipeline
- audio_system
- backend
- data
- docs
- frontend
- services

Next step:
Continue MVP development and migrate toward clean architecture:
backend / flutter_app / docs.
## 2026-03-07

Completed:
- switched from Codex Cloud workflow to Codex Local workflow
- created working FastAPI backend scaffold
- fixed backend files manually where Codex created placeholders
- verified local backend startup with uvicorn
- verified Swagger UI at /docs
- added RSS ingestion service using Python standard library
- committed:
  - af8d40a Create minimal backend scaffold files
  - 68a1244 Implement RSS ingestion service with stdlib parsing

Current status:
- backend runs locally
- /docs works
- /articles and /briefing/today exist
- RSS ingestion service exists but is not yet connected to ArticleService

Next:
- connect RSS ingestion to ArticleService
- make /articles return real RSS articles
- then update BriefingService to build briefing from real articles
Completed later the same day:

Backend:
- connected RSS ingestion to ArticleService
- /articles now returns real RSS articles
- added article sorting by publish date
- mapped RSS description to summary
- implemented HTML stripping in summaries

Briefing:
- DailyBrief now generated from first 5 articles
- dynamic headline generation

Flutter:
- created DailyBrief model
- implemented ApiService
- implemented HomeScreen
- connected Flutter to FastAPI /briefing/today

Result:
First working end-to-end pipeline:

RSS
→ FastAPI backend
→ /briefing/today
→ Flutter app
→ HomeScreen displays real news briefing

This is the first fully working OpenWave MVP.
## 2026-03-08

Major milestone: First real audio playback in OpenWave.

Completed:
- implemented Flutter TTS playback
- Play button reads article title + summary
- PlayerScreen supports play/pause
- Up Next indicator added
- summary and duration shown in player
- fixed Flutter Web API integration
- enabled CORS in FastAPI backend
- verified end-to-end pipeline in browser

Pipeline now:

RSS
→ Article
→ Segment
→ DailyBrief
→ Flutter Player
→ TTS voice playback

OpenWave can now read the daily briefing aloud.
## 2026-03-08 (Session 2)

Major milestone: OpenWave audio player significantly improved.

Implemented in PlayerScreen:

- auto-start briefing playback
- auto-play between articles
- voice cue between articles ("Next story")
- interactive playlist with article selection
- highlight for currently playing article
- estimated narration duration based on text length
- progress bar based on estimated duration
- current / total / remaining playback time
- estimated duration displayed in playlist items

Player now behaves like a real audio briefing player.

Pipeline verified:

RSS → Article → Segment → DailyBrief → Flutter Player → TTS playback

OpenWave MVP now supports continuous audio news briefing with playlist navigation.
## 2026-03-08

Major milestone: OpenWave audio player upgraded.

PlayerScreen improvements:
- auto-start briefing playback
- auto-play between articles
- voice cue between articles
- interactive playlist
- highlight for current article
- estimated narration duration
- progress bar based on narration duration
- playback timer (current / total / remaining)
- duration visible in playlist items

OpenWave now behaves like a real audio news briefing player.
## 2026-03-09

Major milestone: OpenWave audio briefing experience significantly improved.

PlayerScreen upgrades:

Audio experience
- Added spoken Daily Brief intro
- Intro now dynamically reflects article count
- Intro now includes estimated total briefing duration
- Added "Top story." cue before the first article
- Added "Next story." cue between subsequent articles

Playback
- Continuous auto-play between articles
- Stable TTS playback using flutter_tts
- Improved playback flow using cue states

Timing and duration
- Estimated narration duration per article
- Total briefing duration estimation
- Progress timer synced with narration duration
- Display of current / total / remaining time

Playlist UI improvements
- Interactive playlist
- Highlight for currently playing article
- Estimated duration displayed for each playlist item

Pipeline confirmed working end-to-end:

RSS
→ rss_ingestion_service
→ ArticleService
→ SegmentService
→ BriefingService
→ /briefing/today endpoint
→ Flutter HomeScreen
→ PlayerScreen
→ TTS playback

Current user experience:

Your OpenWave Daily Brief.
Five stories today. About two minutes.

Top story.
Article 1…

Next story.
Article 2…

OpenWave now behaves like a real audio news briefing player.

Next planned improvements:
- Display total briefing duration in PlayerScreen UI
- Introduce basic editorial section cues
- Improve visual structure of PlayerScreen
- Added estimated total briefing duration to PlayerScreen UI under the briefing title.
- Reused the same total duration estimation logic already used by the audio intro via a shared helper method.
- Kept changes minimal and limited to flutter_app/lib/screens/player_screen.dart.
- Added radio-like briefing sections in backend Daily Brief output.
- Introduced DailyBriefingArticle with a section field.
- Marked the first article as Top story and added minimal keyword-based section inference for Economy and Tech, with International as fallback.
- Kept /briefing/today backward-compatible apart from the new per-article section field.
- Improved PlayerScreen playlist UI to make the upcoming story more visible.
- Added a subtle "Next:" label and arrow indicator for the item immediately after the active article.
- Kept playback logic, TTS behavior, and data flow unchanged.
- Added simple in-memory RSS caching with a 10-minute TTL in rss_ingestion_service.
- RSS feeds are now reused between requests while the cache is valid, reducing repeated fetches.
- Kept the existing service API and endpoint behavior unchanged.
- Reviewed current backend services against the target architecture.
- Confirmed the existing pipeline already aligns well with RSS → Article → Segment → DailyBrief.
- Fixed a small mismatch by exposing RSS description content in rss_ingestion_service so ArticleService can populate summaries correctly.
- Extended Segment model with narration_text, section and duration_estimate fields.
- Added compatibility fallbacks to preserve existing pipeline behavior.
- Segment model now better reflects the audio-first architecture.
- Clarified BriefingService responsibilities as the main Daily Brief orchestrator.
- Extracted explicit internal steps for article selection, segment creation, and highlights generation.
- Kept DailyBrief structure and app behavior unchanged.
- Extended Article model with optional metadata fields: topic, geography, content_type, importance_score.
- Change is backward compatible and does not affect the current pipeline.
- Prepares the data model for future personalization and event ranking features.
- Aligned section handling with the target pipeline by making Segment.section the source of truth.
- BriefingService now resolves section on segments first, then propagates it into DailyBrief articles.
- Preserved existing section behavior while making the Article → Segment → DailyBrief flow more explicit.
- Added infrastructure support for section cue segments.
- Introduced Segment.TYPE_SECTION_CUE and a helper method in SegmentService to create cue segments.
- This prepares the backend for radio-style briefing sections without changing current behavior.
- Added internal support in BriefingService for inserting section cue segments when briefing sections change.
- Kept the change as internal preparation only, since DailyBrief does not expose playback segments yet.
- Preserved current API and app behavior while preparing the backend for radio-style playback structure.
- Extended DailyBrief to expose optional playback segments in a backward-compatible way.
- BriefingService now returns the generated playback segment list, including internal section cues.
- Existing articles and highlights output remain unchanged, so current clients continue to work as before.
- Added Flutter support for optional playback segments in DailyBrief.
- PlayerScreen now consumes segments when available, with full fallback to articles for backward compatibility.
- Section cue segments are now playable through TTS, enabling the first radio-style transitions in the app.
- Added infrastructure support for intro segments in the backend.
- Extended Segment with TYPE_INTRO and added create_intro_segment() in SegmentService.
- Kept the change as backend preparation only; intro segments are not inserted into playback yet.
- Added a real intro segment at the beginning of playback segments in BriefingService.
- Intro uses the briefing headline and is now included in the segment list returned by DailyBrief.
- Playback structure now supports intro + article segments + section cues in a radio-style order.
- Improved intro segment text to sound more natural for audio playback.
- Intro now says “Good morning. Here are the top stories today.” and includes the story count when available.
- Kept the existing playback pipeline unchanged.

- Added infrastructure support for perspective segments in the backend.
- Extended Segment with TYPE_PERSPECTIVE and added create_perspective_segment() in SegmentService.
- Kept the change as preparation only; perspective segments are not inserted into briefing playback yet.

- Inserted the first demo perspective segment into playback flow after the first article.
- Reused the existing perspective segment infrastructure from SegmentService.
- This is a static demonstration step that prepares the path toward Perspective Mode in OpenWave.

- Replaced the single demo perspective segment with a Perspective Pair after the first article.
- Added consecutive “Supporters say” and “Critics argue” segments using the existing perspective segment infrastructure.
- Kept the implementation static and backward-compatible as a first demonstration of Perspective Mode.

- Improved PlayerScreen playlist UX for special segment types.
- Added distinct icons and subtitles for intro, section cue, and perspective segments.
- Kept article playback behavior and overall player layout unchanged.

- Updated the demo Perspective Pair to derive its text from the first article summary instead of using fully static strings.
- Kept the implementation template-based and deterministic as a preparation step before introducing AI-generated perspectives.
- Preserved the existing playback pipeline and API structure.

- Added a simple editorial filter for demo Perspective Pair generation.
- Perspectives are now inserted only for relevant sections: Top story, International, and Economy.
- This keeps the radio flow more credible and avoids perspective segments on unsuitable topics.

- Added a small “Two perspectives” indicator in PlayerScreen when a Perspective Pair starts.
- The indicator appears only on the first perspective segment and helps explain the feature to the user.
- Kept playback logic and playlist behavior unchanged.

## 2026-03-09

### Backend
- Added Segment infrastructure for:
  - intro
  - section_cue
  - perspective
- Implemented Perspective Pair prototype (supporters vs critics).
- Added editorial filter: perspectives only for Top story / International / Economy.
- DailyBrief now exposes playback `segments`.

### Flutter
- Player now supports segments pipeline (fallback to articles).
- Playlist shows icons for:
  - intro
  - section
  - perspective
- Added UI indicator: “⚖️ Two perspectives”.

### Experiments
- Created `backend/experiments/ai_news_brief_test.py`
- Tested AI pipeline:
  RSS → AI selection → radio narration
- Initial result: AI over-selects stories from the same global event cluster.

### Observations
- AI selection works but needs editorial diversity constraints.
- Radio-style summaries are usable for TTS.

### Next
Task 20:
Improve visual grouping of the two Perspective segments in playlist.

Editorial exploration:
Test Romanian radio-style summaries for OpenWave.

Task 20 completed and manually verified in app. Perspective Pair is now rendered as a single editorial block in the Flutter playlist, with working tap behavior and active-state highlight across both perspective segments. Backend section cue constant issue was also fixed so /briefing/today loads correctly again.

Task 21 completed: polished Perspective Pair playlist tile in Flutter player with clearer editorial grouping, subtle bordered/tinted container, badge-style header, and divider between Supporters/Critics viewpoints. UI-only change; playback behavior unchanged.

Task 22 completed: added a subtle progress indicator for the currently playing playlist segment, including correct support for grouped Perspective Pair blocks. UI-only change; playback logic unchanged.

Task 23 completed: fixed player transition sequencing so intro advances correctly to the first editorial segment, segment narration uses narrationText when available, story-to-perspective transition flows directly, and no “Next story” cue is inserted inside a Perspective Pair.

Task 25 completed: added playlist auto-scroll to keep the active visible item near the top of the playlist, including correct handling for grouped Perspective Pair tiles. Verified controller cleanup in player_screen.dart.

Task 27 completed: extended story + perspective playlist grouping to also handle the real raw sequence with an intermediate section cue, and added bounds guards to keep the grouping logic safe.

Task 29 completed: fixed story narration generation in backend so each news segment now starts with the article title before the summary, while avoiding duplicate-title narration.

Task 31 completed: updated playlist numbering to use visible editorial blocks instead of raw segment indices, so grouped story + perspective items now consume a single playlist number and later items renumber correctly.

Task 32 completed: tightened vertical spacing in player layout so the playlist appears higher on screen and more items are visible immediately, without changing player structure or playback behavior.

Task 33 completed: simplified the top player area by removing the large Now Playing card and duplicated metadata, leaving only the current title, progress bar, timing, and transport controls so the playlist becomes the main visible focus.

Task 34 completed: removed intro from visible playlist rendering while keeping intro audio playback intact, and replaced the top summary area with a compact single-line header showing total duration and real story count only.

Task 35 completed: removed the redundant pre-player briefing preview screen and now open the Daily Brief directly in PlayerScreen while preserving existing loading and error handling in HomeScreen.

Task 36 completed: restored intro playback by triggering it on the first explicit Play action after direct player entry, and fixed compact header story count by parsing the intended editorial count from the briefing headline when available.

Task 37 completed: playlist taps now start playback immediately, Perspective blocks were simplified to compact label-only rows with internal active-state highlighting, and the compact header now uses the real computed story count.

Task 38 completed: compact header now uses the real visible playlist block count, keeping duration/story summary aligned with the numbered playlist and excluding intro from the visible count.

Task 39 completed: removed the spoken “Next story” TTS cue and switched regular story-to-story transitions to direct advancement, preserving intro handoff and no-separator behavior inside grouped editorial blocks.

Task 40 completed: integrated a short asset-based news stinger between independent story blocks using audioplayers, while preserving intro flow and no-separator behavior inside grouped story/perspective blocks.

Task 41 completed: updated stinger playback to trigger on transitions between visible editorial story blocks rather than only raw adjacent article segments, making story-to-story jingle behavior consistent while preserving separator-free grouped perspective playback.

Task 42 completed: intro narration now uses the real story count, and stinger playback now triggers on transitions between visible story blocks only, skipping section cues and preserving separator-free grouped perspective playback.

Task 44 completed: fixed stinger triggering by resolving both current and next playback positions through the same real story-block anchor helper, preventing separators inside grouped perspective blocks and restoring stinger playback before the next real story block.

Task 45 completed: fixed the remaining final-story stinger transition and simplified the playlist to compact title-only rows, using an inline “(Two perspectives)” marker for stories with grouped perspective coverage.

Task 46 completed: fixed stinger timing so the transition sound now plays only after completed story blocks, including the final story, while keeping grouped perspective transitions separator-free and updating the playlist marker to (⚖ Two perspectives).

Defined and added the first full OpenWave editorial architecture docs set under docs/, covering editorial policy, radio writing rules, AI models, personalization, architecture, product vision, roadmap, and risks.

### OpenWave — Daily Log

**Date:** 11 March 2026

**Main focus:** Finalizing the editorial model and documentation for the OpenWave news briefing format.

**Work completed:**

* Completed **Pilot 03**, testing a strongly personalized briefing (sport + entertainment profile, 30% national / 70% international).
* Applied final refinements to Pilot 03:

  * added mid-briefing user-name reference (“Pentru tine, Adrian…”)
  * improved the closing of the Mbappé story with a concrete consequence
  * diversified source attribution to avoid repeated Agerpres references.
* Consolidated editorial documentation in the repository:

  * extended `editorial_selection_rules.md` with:

    * User Personalization Rule
    * Avoid Meta Commentary Rule
    * Source Diversity Rule
  * created `openwave_radio_style.md` (OpenWave radio writing style guide)
  * created `openwave_transitions_ro.md` (recommended Romanian transition phrases).
* Confirmed product behavior for **personalized intro/outro and bulletin slot logic**.

**Editorial status:**

The OpenWave briefing format has now been validated through three pilots:

* **Pilot 01** — general news structure
* **Pilot 02** — rhythm and clarity improvements
* **Pilot 03** — strong personalization scenario

Documentation now fully reflects the editorial model used in the pilots.

**Project status:**

Editorial phase completed.
Next steps (after break):

* real audio testing with TTS
* bulletin generation pipeline
* lead story selection logic
* presenter voice profile (“Corina”).

## 2026-03-12

### Major milestone
First end-to-end OpenWave audio test completed.

Editorial pilots were converted into real audio using the backend TTS pipeline and played through the Flutter player.

Pipeline validated:

RSS / editorial pilot  
→ speech pacing  
→ TTS provider (ElevenLabs)  
→ audio generation  
→ saved file  
→ playback in app

### Editorial work
Reviewed and tested Pilot 01, Pilot 02 and Pilot 03.

Observations:
- Pilot 02 currently has the best general-news structure.
- Pilot 03 works well for personalization tests.
- Pilot 01 remains mainly a technical reference.

New editorial rules confirmed:
- Lead Story Continuity Rule
- Current Year Omission Rule
- Acronym Expansion Rule
- Numbers Spoken Rule (all numbers written in words in audio scripts)

### TTS / audio system
Implemented working TTS generation for editorial pilots.

New endpoint:
POST /api/tts/generate-from-pilot

Audio files now saved in:
backend/generated_audio/

Speech pacing system added:
- pause_after_intro
- pause_between_stories
- pause_before_quotes
- pause_before_outro

### Voice tests
Tested two voices:

Corina
- Moldovan accent
- flat prosody
- not ideal for news

Traian
- more professional tone
- closer to radio presenter
- slightly slow speed

Voice tuning parameters adjusted in ElevenLabs.

### Audio test results
Generated audio for pilots.

Approximate durations:
- Pilot 02: < 5 minutes
- Pilot 03: ~3:40

Conclusion:
current pilots are still shorter than the target 7–8 minute briefing.

### Issues discovered
TTS struggles with:
- Romanian acronyms (CSAT, CNAIR)
- large numbers
- some abbreviations

Planned solution:
TTS normalization layer for:
- acronyms
- numbers
- dates

### Next steps
1. Implement TTS normalization layer.
2. Generate segmented audio (intro / stories / outro).
3. Integrate news stinger between stories.
4. Finalize presenter voice.
5. Start automated briefing builder.

### Project status
OpenWave reached the stage of a working AI radio prototype with real audio generation and playback.

# OpenWave — Daily Log
Date: 2026-03-12

## Work completed

### TTS normalization layer

Implemented Romanian TTS normalization pipeline:

1. romanian_audio_lexicon
- institutions
- political parties

2. romanian_numbers_normalizer
supports:
- numbers
- percentages
- decimal percentages
- years
- simple money amounts
- millions / billions
- simple times
- compact dates

Examples:
3,5% -> trei virgulă cinci la sută
14:30 -> paisprezece și treizeci
12.03.2026 -> douăsprezece martie

### Editorial rules implemented

- do not pronounce current year in news
- pronounce year only if different from current year

### TTS pipeline order

text
→ romanian_numbers_normalizer
→ romanian_audio_lexicon
→ romanian_tts_normalizer
→ ElevenLabs TTS

### Audio architecture

segmented audio:
intro
stories
outro

news stinger between stories implemented in Flutter.

## Current project status

Completed:
- TTS normalization layer
- segmented audio generation
- news stinger integration

In progress:
- voice tuning
- editorial automation

## Next steps

1. voice tuning
2. editorial automation pipeline








- added editorial pipeline orchestration to connect clustering, scoring, selection, summary generation, assembly, and sizing into one final text briefing package
- added an editorial-to-audio bridge that converts final editorial briefings into segmented audio-generation packages for the existing TTS pipeline
- added an end-to-end bulletin generator that reuses the editorial pipeline, the editorial-to-audio bridge, and the existing segmented TTS flow to produce final audio segment files
- refined story summaries with short editorial headlines and conservative attribution logic for quotes, official statements, or source fallback
- refined story summaries again so major stories can expand to 4-5 sentences and must mention casualties when deaths or injuries are clearly present
- added an attribution-first radio rule so generated summary lines now begin with the speaker, institution, or source instead of using post-attributed audio-ambiguous phrasing
- added structured radio lead generation so sentence one now follows one of six editorial lead types instead of mostly mirroring the representative title

- refined story summaries to preserve only short memorable quotes and to remove non-essential numbers more aggressively
- refined briefing assembly with simple heavy/medium/light pacing labels and a secondary flow rule that avoids long runs of heavy stories when alternatives exist

- added a deterministic radio-language variation layer so summary attribution openings now rotate between equivalent attribution-first structures instead of repeating `Potrivit ...` across consecutive items

- added dual-presenter bulletin draft support so briefing assembly now alternates female and male presenter voices, picks intro/outro variants deterministically, and inserts at most two short microphone-pass phrases between suitable story transitions

- added optional listener first-name personalization in briefing assembly so intro and optional outro can mention the listener by name at most twice per bulletin, while story summaries remain unchanged

- added optional short stinger support in the editorial-to-audio layer so audio packages can now include configurable `stinger` segments between stories without changing the TTS provider flow
- reintegrated the legacy `Two Perspectives` feature into the modern editorial pipeline by moving perspective insertion to briefing assembly for controversial stories
- limited perspective output to one supporters-vs-critics pair per bulletin and preserved the existing perspective segment model for downstream audio
- removed demo-only perspective insertion from the legacy `BriefingService` playback path so perspective behavior now has one canonical integration point

## 2026-03-13

### Major progress
Implemented and connected the full OpenWave editorial backend pipeline end-to-end.

### Backend editorial pipeline completed
Added or finalized:
- unified source watcher
- article fetch and clean layer
- conservative news clustering
- transparent story scoring
- bounded story selection
- summary policy
- story summary generator
- briefing assembly
- bulletin sizing
- editorial pipeline orchestration
- editorial-to-audio bridge
- end-to-end bulletin generation

### Editorial refinements implemented
Added or refined:
- short editorial headlines
- attribution-first rule
- source attribution fallback
- memorable short quote support
- aggressive non-essential number filtering
- mandatory casualty mention when clearly present
- 4–5 sentence expansion for major stories
- radio lead generation with 6 lead types:
  - impact
  - decision
  - warning
  - conflict
  - change
  - event
- pacing labels inside briefing assembly:
  - heavy
  - medium
  - light

### Perspective feature
Audited the old “Two Perspectives” feature.
Confirmed it was legacy/demo in the old briefing flow.
Reconnected it properly into the modern assembly pipeline:
- only for controversial/disputed stories
- maximum one pair per bulletin
- order:
  - main story
  - perspective_supporters
  - perspective_critics

### Documentation added
Created canonical project documentation:
- `docs/OPENWAVE_EDITORIAL_RULES_v1.md`
- `docs/OPENWAVE_ARCHITECTURE_v1.md`

### Current status
OpenWave now has:
- MVP editorial backend completed
- end-to-end backend bulletin generation completed
- editorial rules documented
- architecture documented

### Remaining work
Still open:
- real end-to-end live-content validation
- commentary pipeline
- dual presenter mode
- intro/outro variation
- attribution variation engine
- stinger / micro-transition logic
- final voice tuning
- beta testing workflow

### Next recommended step
Run full real-news bulletins and audit:
- story quality
- pacing
- attribution quality
- audio realism
- summary completeness
- audited the old user-preference slider concept and confirmed it was no longer connected to the modern editorial pipeline
- added a canonical editorial preference profile for geography and domain sliders in backend models
- reconnected preference flow from end-to-end API input into the editorial pipeline and final editorial package without yet changing scoring or selection behavior
- applied editorial preferences conservatively inside story selection so geography and domain sliders now influence only near-tie decisions
- kept score as the primary driver and avoided rigid quotas or preference overrides against clearly stronger stories
- exposed preference influence in story-selection explanations and examples
- promoted personalization to a first-class pipeline contract through a canonical `UserPersonalization` object
- added safe defaults and normalization for listener profile plus editorial preference mixes
- exposed explicit personalization usage and default fallback flags in final pipeline outputs
- made the local personalization anchor explicit: listener region/county is now the primary local editorial anchor, while city remains stored only as secondary metadata and fallback
- applied the regional anchor conservatively in story selection so region-matching local coverage can win only in near-ties when local preference is enabled
- added lightweight bulletin continuity detection so recurring clusters can be marked as updates or major updates in summary leads without changing scoring or selection
- added a Romanian county-based local source registry and made it available to the source watcher and editorial pipeline explainability for region-first local personalization
- connected the county registry to SourceWatcher operational resolution so `local_county` sources activate only when region exists and local preference is above zero
- activated county local sources inside SourceWatcher monitoring so region-based local media are appended conservatively to the monitored source set only when local preference is enabled
- added a real Flutter personalization flow with two-step onboarding, reusable settings, and local persistence for the canonical backend personalization contract
- connected Flutter bulletin generation requests to send listener profile plus editorial preferences to the existing end-to-end backend payload
- added player-screen settings access so personalization changes are saved for the next bulletin without interrupting the current playback session

## 2026-03-14

- Added a conservative TTS budget preflight for end-to-end bulletins, using normalized segment text length and segment count before ElevenLabs synthesis starts.
- Structured quota failures now return `tts_budget_exceeded` with estimated required credits and remaining credits when available.
- Flutter home screen now shows a product-style quota message with estimate details and fallback suggestions instead of surfacing raw provider exceptions.

- Added a temporary OpenAI TTS test provider path using `gpt-4o-mini-tts` through the existing provider factory.
- Added presenter voice mapping for `Ana -> alloy` and `Paul -> verse`, while preserving segmented file naming and storage behavior.
- TTS provider failures are now surfaced as structured provider errors in backend TTS routes and preserved more cleanly in the end-to-end generation path.

- Added a conservative dual presenter test mode in `EditorialToAudioService` with `presenter_mode`, `presenter_a`, and `presenter_b` config.
- In `dual_test`, intro/outro now use Ana, story blocks alternate Ana then Paul, and perspective segments inherit the presenter of the parent story block.
- Propagated `presenter_name` through audio segment models and TTS segment blocks while preserving the existing single-presenter flow when the mode stays `single`.

Date: 2026-03-14

Task: Dual presenter test mode (Ana / Paul)

Implemented backend-only dual presenter test mode for the OpenWave Probe flow.

Key changes:
- Added presenter configuration file:
  backend/app/config/audio_presenter_config.json
- Introduced presenter_mode with two supported values:
  - single (default)
  - dual_test
- Added presenter_name propagation through audio generation models:
  - AudioStorySegment
  - AudioSegmentBlock
- Implemented presenter assignment logic in:
  backend/app/services/editorial_to_audio_service.py

Behavior in dual_test mode:
- intro → Ana
- story_01 → Ana
- story_02 → Paul
- story_03 → Ana
- story_04 → Paul
- perspective_* segments inherit the presenter of the parent story
- outro → Ana

Additional notes:
- headline and story body remain a single story block and therefore keep the same presenter
- presenter_name is forwarded into the TTS pipeline via TtsService
- single-presenter mode remains unchanged and fully compatible
- no changes were required in Flutter
- no editorial logic redesign
- no TTS provider redesign

Validation:
- python -m py_compile passed for modified backend files
- manual verification pending via bulletin generation

Commit:
0572236 — Add dual presenter test audio mode

Next step:
Run Probe bulletin tests to validate presenter alternation and audio flow.

- Added OpenAI-backed probe execution for `backend/tests/probe_voice_tests`, using env-configured `OPENAI_TTS_VOICE_ANA` and `OPENAI_TTS_VOICE_PAUL` while leaving the default ElevenLabs path unchanged.
- Added `EditorialContractValidationService` as a mandatory gate between final editorial assembly and the editorial-to-audio bridge.
- Added structured validation models plus `backend/debug_output/editorial_validation_report.json` for blocking violations, warnings, and deterministic auto-fixes.
- End-to-end bulletin generation now stops with `editorial_contract_validation_failed` when blocking editorial rules fail, instead of silently continuing to audio generation.
- Refactored `story_summary_generator_service.py` into the explicit Story Editorial Composition stage, so selected clusters now become structured editorial stories before briefing assembly.
- `GeneratedStorySummary` now carries `story_type`, `headline`, `lead`, `body`, `source_attribution`, `quotes`, and `editorial_notes` while preserving `summary_text` for downstream compatibility.
- Written bulletin debug output now exposes the composed story structure directly for manual editorial inspection.

Improved major-story editorial composition in story_summary_generator_service. Added a dedicated major-story headline path, reduced generic lead fallback, shortened Romanian source-attribution phrasing, broadened quote extraction to scan cluster titles, and explicitly record no_usable_quotes_detected when no attributed statements are available. Major-story output is now structurally stronger and more radio-ready, though short-story headline quality still needs follow-up.

# OpenWave — Daily Log

## Date

Development session covering the last ~20 conversation steps.

---

# Summary

Today's work focused on **stabilizing the editorial selection pipeline**, especially for:

* international news clustering
* source diversity
* Romanian national news selection
* candidate pool diagnostics
* preparation for classifier precision improvements

The goal of the session was to move the system from **experimental ingestion + clustering** to a **more editorially plausible bulletin output**.

---

# Major Architecture Progress

## 1. International clustering improvements

A new **event-family clustering system** was introduced.

Event families implemented:

* regional_conflict
* military_movement
* energy_shipping_disruption
* political_crisis
* attack_or_strike
* economic_shock

Regional context buckets added:

* gulf_escalation
* black_sea_security
* eu_security

This allowed clustering to merge related articles even when lexical similarity was low but the **event context was shared**.

Example improvement:

AP + CNA + ABC Australia → merged into a single Iran/Gulf escalation cluster.

Result:

* multi-source clusters began appearing
* cluster confirmation became stronger

---

# 2. International source mix overhaul

The international ingestion mix was redesigned to avoid BBC dominance.

BBC sources were disabled.

New active international mix includes:

* Associated Press
* NPR
* Al Jazeera
* DW
* ABC News Australia
* CBC
* Sky News
* NBC News
* Kyodo News
* CNA
* CNBC
* The Guardian

Result:

* more editorial diversity
* stronger multi-source confirmation
* clusters with **3–4 sources began appearing**

---

# 3. International selection validation

New debug runner created:

run_top5_scope_selection.py

New debug artifacts:

* story_selection_debug.json
* international_merge_debug.json
* candidate_pool_audit.json
* international_source_coverage.json

These allowed inspection of:

* clustering decisions
* source overlap
* merge reasoning
* candidate pool size

Important discovery:

The main bottleneck was **source diversity**, not clustering logic.

After expanding the source mix, cluster strength improved.

---

# 4. Romanian source mix redesign

The national ingestion mix was replaced with a **hard-news oriented Romanian source set**:

* Agerpres
* News.ro
* HotNews
* G4Media
* Digi24
* Stirile ProTV
* Libertatea
* Adevarul
* ZF
* Cotidianul
* Europa Libera Romania
* Ziare.com
* Gandul
* Antena3
* SpotMedia

Non-editorial placeholders were filtered:

* ACTUALITATE
* STIRI
* LIVE
* context

Result:

* cleaner candidate pool
* fewer junk headlines entering clustering.

---

# 5. Romanian candidate pool diagnostics

New debugging artifacts introduced:

romanian_source_coverage.json
romanian_candidate_pool_audit.json

Findings:

* 12 of 15 Romanian sources produced candidates
* but **multi-source overlap was initially zero**

Each outlet produced one story, but about **different events**.

Therefore clustering had nothing to merge.

---

# 6. National-first discovery preference

To increase overlap, a **Romanian source prioritization mechanism** was introduced.

Romanian candidates are now bucketed into:

* domestic_hard_news
* external_direct_impact
* off_target

Selection preference:

1 → domestic_hard_news
2 → external_direct_impact
3 → off_target

Result:

* domestic candidate density increased
* off-target stories disappeared

Bucket distribution in test run:

domestic_hard_news → 8
external_direct_impact → 2
off_target → 0

---

# 7. First Romanian multi-source cluster

After enabling national-first discovery, the first Romanian multi-source cluster appeared:

News.ro + SpotMedia

Story example:

Ukraine war update referenced by Romanian outlets.

Result:

Romanian clusters with **unique_sources ≥2** finally appeared.

This confirms that the national-first mechanism works.

---

# 8. Breaking bulletin runner

A simplified editorial runner was created:

run_top5_breaking_bulletin.py

Purpose:

Test **selection-only output** without invoking:

* editorial composition
* audio
* TTS

Output files:

top5_breaking_bulletin.txt
top5_breaking_bulletin.json

Used to validate:

* selection quality
* cluster strength
* editorial plausibility

---

# Current Weakness Identified

The **domestic classifier is too permissive**.

Examples incorrectly treated as domestic hard news:

* lifestyle financial advice
* generic global business stories
* soft feature pieces

Examples observed:

* Economisirea dusă la extrem
* Meta concediază angajați

These should not rank in the top national bulletin.

---

# Next Planned Task

Improve **domestic_hard_news classifier precision**.

Planned improvements:

1. Stronger negative signals

Deprioritize:

* lifestyle
* personal finance advice
* wellness
* feature stories
* generic corporate news without Romania impact.

2. Stronger Romanian institutional signals

Boost stories referencing:

* Romanian government
* parliament
* ministries
* courts
* BNR
* ANAF
* infrastructure
* taxes
* public policy.

3. Use entity density instead of article length.

Prefer articles containing:

* Romanian institutions
* public actors
* policy decisions.

---

# System Status

Pipeline health:

RSS ingestion ✔
clustering ✔
international clustering ✔
international source diversity ✔
Romanian source mix ✔
national-first discovery ✔

Remaining bottleneck:

domestic classifier precision.

---

# Editorial Target

The system should produce a **credible Romanian radio-style bulletin** with:

* 5–12 stories depending on event intensity
* balanced national and international coverage
* multi-source confirmation prioritized
* coherent event clustering.

---

# Next Development Step

Implement **domestic classifier tightening** and rerun the breaking bulletin runner to confirm:

* improved national story quality
* continued multi-source clustering.

DATE: 2026-03-15
PROJECT: OpenWave
FOCUS: Romanian editorial pipeline stabilization + domestic breadth recovery

SUMMARY

Major improvement in Romanian bulletin quality and stability.

The Romanian editorial pipeline successfully transitioned from a thin bulletin
(~1 domestic story per run) to a stable pattern:

    1 domestic_hard_news
    + 2 recovered_domestic_candidate
    = 3 Romanian stories in Top 5

This was achieved without weakening the main domestic classifier and without
reintroducing lifestyle / corporate noise.

KEY IMPLEMENTATIONS

1. Recovery diagnostics
Added explicit debugging fields to identify why Romanian candidates fail recovery:

- recovery_rejection_reason
- failed_threshold_name
- threshold_required_value
- candidate_current_value

This significantly improved observability of near-miss domestic stories.

2. Recovery threshold adjustment
Recovery-only purity threshold relaxed to:

    purity ≥ 0.35

This allows legitimate institutional / justice / fiscal stories to enter
the recovered_domestic_candidate path without affecting the main classifier.

3. Justice / fiscal scoring improvements
Expanded romania_impact_evidence_hits signals to include:

Justice signals:
- csm
- dna
- diicot
- audieri
- procuror_sef

Fiscal / policy signals:
- deficit bugetar
- amendamente buget
- taxe
- salariu minim

These changes improved recovery of real public-interest stories.

4. Recovery path activation confirmed
Recovered stories now consistently appear:

Recovered examples:
- "CSM reia luni votul... DNA..."
- "Toti ochii pe sedinta PSD... voteaza bugetul propriului Guvern"

Observed stable pattern across repeat runs:

    domestic_hard_news = 1
    recovered_domestic_candidate = 2
    Romanian items in Top 5 = 3

Coverage summary now reports:

    1 hard-news / 2 recovered / 0 near-miss -> balance: GOOD

5. External dominance protection confirmed
External clusters remain capped and do not dominate Top 5
when domestic coverage exists.

PRECISION STATUS

No regressions observed.

Still excluded correctly:
- lifestyle content
- wellness
- entertainment
- personal finance advice
- generic corporate stories

NEXT DEVELOPMENT FOCUS

Move from logic tuning → **editorial stability validation**.

Planned next steps:

1. Run spaced snapshots across multiple hours/days
2. Monitor coverage summary stability (GOOD / THIN / WEAK)
3. Strengthen Justice domain coverage across:
   - local
   - national
   - international
4. Improve event-family persistence for justice and institutional decisions

Current Romanian pipeline state:

Classifier: stable  
Ranking: stable  
Recovery path: active  
Domestic breadth: significantly improved  
Debug visibility: strong

The system is now ready for stability validation across real-time news cycles.

DATE: 2026-03-15
PROJECT: OpenWave
FOCUS: Justice domain integration and Romanian editorial pipeline stabilization

SUMMARY

Justice is now implemented as a full editorial domain in the Romanian news
selection pipeline.

The system can now detect, score, and recover justice-related stories across:

- local justice events (courts, police, prosecutors)
- national institutional decisions (CSM, DNA, DIICOT)
- anti-corruption cases and prosecutorial appointments

Justice stories now enter the Romanian national Top 5 through persistence
and recovery mechanisms when appropriate.

KEY IMPLEMENTATIONS

1. Justice signal expansion

Extended justice signal detection in:

story_selection_config.json

New Romanian justice phrases added:

- tentativa omor
- grupare rivala
- maceta
- audieri csm
- procuror sef dna
- aviz negativ csm
- dosar anti-coruptie

These signals contribute to:

- romania_impact_evidence_hits
- justice event-family hints
- recovery scoring
- persistence activation

Justice recovery purity floor remains unchanged:

purity ≥ 0.2

2. Justice event-family hints

Justice coverage now uses explicit hints:

- romanian_justice_case
- romanian_prosecutor_decision
- romanian_high_court_decision
- romanian_anti_corruption_case

These hints trigger:

- persistence bonus
- recovery scoring
- Romanian relevance signals

3. Justice debug visibility

Added new debug section:

JUSTICE BOOSTED STORIES

in:

backend/debug_output/top5_breaking_bulletin.txt

Example format:

JUSTICE BOOSTED STORIES

- story_title
  reason: romanian_anti_corruption_case + persistence
  recovery_score: 0.0

This makes justice-related ranking behavior transparent during debugging.

4. Validation result

Example justice story successfully entering the national bulletin:

CSM reia luni votul pentru Alex Florenta si Marius Voineag... candidatul la sefia DNA

Signals detected:

romanian_anti_corruption_case  
persistence boost

Justice story appeared in Romanian national Top 5.

5. Precision status

No regressions observed.

Still correctly excluded:

- lifestyle content
- wellness
- entertainment
- personal finance
- generic corporate news

Romanian classifier remains strict and stable.

CURRENT PIPELINE STATE

Classifier: stable  
Ranking: stable  
Recovery path: active  
Justice domain: integrated  
Debug visibility: improved  

Romanian bulletin pattern currently fluctuates between:

1 hard-news  
+ 1 recovered  
+ 1 borderline  

Balance status:

THIN → approaching GOOD when justice/fiscal stories overlap.

NEXT DEVELOPMENT FOCUS

Shift from logic changes → stability validation.

Planned next steps:

1. Run spaced bulletin snapshots (evening + next morning).
2. Observe justice persistence across real-time feed changes.
3. Monitor coverage summary (GOOD / THIN / WEAK).
4. Evaluate whether justice stories appear consistently across runs.

If stability is confirmed, the next domain candidates for expansion are:

- energy_security_ro
- pnrr_closing_2026
- fiscal_policy_followups

The Romanian editorial pipeline is now approaching a stable production shape.


2026-03-15

- extracted a shared `EditorialSelectionCoreService` for debug Top 5 routing
- added config-backed `EditorialProfile` definitions for `national_ro`, `international`, and placeholder `local`
- updated `run_top5_scope_selection.py` and `run_top5_breaking_bulletin.py` to support `--profile` routing through the shared core
- preserved current national/international behavior broadly while validating that `--profile=local` returns a clean zero-candidate result instead of failing


2026-03-15

- extended story-family state with lifecycle metadata (`first_seen`, `last_seen`, `run_count`)
- added conservative family lifecycle scoring and debug visibility to scored clusters
- capped Top 5 selection at two stories per story family to prevent event-arc spam
- validated the national breaking-bulletin profile with repeated immediate runs and confirmed lifecycle metadata in debug artifacts

# DAILY_LOG — Task 5 Completed (Local Selection Phase 1)

## Date

15 March 2026

## Milestone

Local editorial selection became operational inside the shared newsroom architecture.

This closes the **first-level selection layer** across all three editorial lenses:

* local
* national
* international

All three now run through the **same shared editorial core**.

---

# What was implemented

Commit:
`9dc5f70 — Enable phase1 local relevance selection`

Local news detection was implemented conservatively using:

```
geographic signal
+
local-domain signal
```

The system now recognizes local relevance through:

* county / city geographic signals
* public-safety / emergency keywords
* local-domain signals
* propagated county tags from local sources

Local candidate admission is intentionally strict:

```
only clusters with a real local_relevance_boost
enter the local candidate pool
```

This prevents filler content from local domains.

Example filtered correctly:

```
Cuvinte cu ghi din 3 silabe
```

---

# First successful local selection

Local debug run:

```
python run_top5_breaking_bulletin.py --profile=local
```

Before implementation:

```
candidate_clusters={"local":0}
selected={"local":0}
```

After implementation:

```
candidate_clusters={"local":1}
selected={"local":1}
```

Selected story example:

```
Accident rutier in Iasi
Au fost implicate doua autoturisme
```

Detected signals:

```
editorial_profile_used: local
geographic_signal_detected: iasi
local_domain_signal_hits: accident
local_relevance_boost: 0.3
local_county_tag: iasi
```

This confirms:

* geographic detection works
* local-domain detection works
* county tagging works
* shared editorial core routing works

---

# Architecture status after Task 5

OpenWave editorial pipeline now supports:

```
Shared Editorial Core
        ↓
National profile
International profile
Local profile
```

All profiles share:

* clustering
* scoring
* recovery
* story-family continuity
* lifecycle scoring
* diversity protection
* debug instrumentation

Differences between editorial lenses are now entirely **profile-driven**.

---

# Current system capabilities

The system now includes:

* national story selection
* international story selection
* local story selection (phase 1)
* justice editorial domain
* story-family continuity tracking
* lifecycle scoring
* editorial profile routing
* shared newsroom architecture

The pipeline has effectively moved from a **snapshot aggregator** to a **memory-aware editorial system**.

---

# Next development focus

With the first-level selection layer complete, the next development stage shifts toward:

**editorial continuity and bulletin structure refinement**

Future tasks will focus on:

* validation on spaced runs
* follow-up story continuity across bulletins
* refining editorial ordering
* improving story lifecycle behavior
* later expansion of local relevance rules

Local selection Phase 2 (future):

* county lists
* stronger geofilters
* local administration signals
* utilities / infrastructure signals

---

# Status

Task 5 is considered **successfully completed**.

The system now has a working **three-lens newsroom architecture** ready for the next editorial layer.


---

# Task 6 - Editorial Stability Validation

Date: 2026-03-15 14:42:58 +02:00

## Scope

This task was a validation pass only.
No ranking or pipeline logic was added.
The goal was to observe whether the three-lens newsroom architecture behaves consistently under the shared editorial core.

Validated profiles:

* national
* international
* local

Debug runners used:

* `backend\venv\Scripts\python.exe backend/tools/editorial_debug/run_top5_breaking_bulletin.py --profile=national`
* `backend\venv\Scripts\python.exe backend/tools/editorial_debug/run_top5_breaking_bulletin.py --profile=international`
* `backend\venv\Scripts\python.exe backend/tools/editorial_debug/run_top5_breaking_bulletin.py --profile=local`

Reviewed artifacts:

* `backend/debug_output/top5_breaking_bulletin.txt`
* `backend/debug_output/top5_breaking_bulletin.json`
* `backend/debug_output/romanian_candidate_pool_audit.json`
* `backend/data/story_family_state.json`

## Validation summary

### Shared core routing

All three profiles still route through the same shared path.
Observed debug fields remained stable:

* `editorial_profile_used`
* `profile_config_name`
* `shared_core_path_used = true`

This confirms the architecture has not regressed into profile-specific pipelines.

### Story-family continuity

Story families continue to persist and evolve across repeated runs.
Observed examples from `story_family_state.json`:

* `domestic_politics`
  * `run_count: 14`
  * `first_seen: 2026-03-15T11:18:27.158472Z`
  * `last_seen: 2026-03-15T12:42:31.313645Z`
* `accident_autoturisme_doua`
  * `run_count: 3`
  * `first_seen: 2026-03-15T12:25:48.458992Z`
  * `last_seen: 2026-03-15T12:42:31.313645Z`
* `chiefs_china_clear`
  * `run_count: 11`

This confirms family attachment and persistence are functioning.

### Lifecycle scoring behavior

Lifecycle boosts are still being applied gradually and predictably.
Observed values:

* mature families repeatedly reached `family_lifecycle_boost: 0.4`
* newer local family `accident_autoturisme_doua` reached `family_lifecycle_boost: 0.25`
* local family metadata updated correctly:
  * `family_run_count: 3`
  * `family_age_hours: 0.28`

This is consistent with the intended gradual boost behavior.

### National profile stability

The national profile remained on the shared core and continued attaching family metadata.
However, the output is still weak editorially in this baseline.

Observed baseline:

* `selected_count: 1`
* the selected story was external-leaning rather than domestic hard news
* `romanian_candidate_pool_audit.json` showed:
  * `national_cluster_count: 11`
  * `multi_source_clusters: 1`
  * `national_preference_bucket_distribution` heavily skewed to `off_target`

Conclusion:

* family continuity is stable
* lifecycle scoring is stable
* diversity/recovery code still runs
* but current national candidate quality remains weak and fragmented

### International profile stability

The international profile remained isolated from Romanian domestic balancing in ranking explanation.
Observed output remained profile-correct:

* `selected_count: 4`
* top international cluster had `unique_source_count: 5`
* the strongest cluster attached consistently to family `chiefs_china_clear`
* debug explanations still said:
  * `non-national cluster: Romanian domestic balancing not applied`

This confirms national logic is not leaking into the international lens.

### Local profile stability

Local Phase 1 remained precise after the Task 5 fixes.
Observed local baseline:

* `selected_count: 1`
* selected story:
  * `Accident rutier in Iasi Au fost implicate doua autoturisme`
* local debug signals:
  * `geographic_signal_detected: iasi`
  * `local_domain_signal_hits: accident`
  * `local_relevance_boost: 0.3`
  * `local_county_tag: iasi`

This confirms:

* geographic detection works
* local-domain matching works
* local relevance boost is visible in debug output
* low-signal local filler did not survive the local candidate gate in the validated baseline

### Diversity protections

No regressions were observed in the current diversity protections.
In this baseline there was no case where more than two stories from the same family or county entered Top 5.
So the caps were not stress-tested by overflow in this run, but they also did not fail.

## What this task confirms today

Confirmed stable now:

* shared-core routing
* story-family persistence
* lifecycle metadata progression
* local relevance precision
* profile-specific debug fields

Not yet fully validated by this single session:

* true spaced-run continuity across 1 to 2 hours and next-day intervals
* whether justice or domestic policy families remain editorially competitive later in the day
* whether diversity caps activate under heavier same-family pressure

## Conclusion

Task 6 is partially validated as a same-session editorial stability baseline.

The architecture is stable enough to confirm:

* no routing regression
* no lifecycle regression
* no local selection regression

But the full spaced-snapshot requirement still needs scheduled follow-up runs later today and next morning to complete the time-separation validation properly.

## 2026-03-15 - Task 7 national editorial signal upgrade

Goal for this pass:

* increase credible Romanian domestic hard-news candidates without changing the shared core
* keep lifecycle and ranking formulas unchanged
* improve the signal quality feeding national clustering and scoring

Changes made:

* expanded Romanian impact evidence in [backend/app/services/story_scoring_service.py](D:/aplicatie_telefon/openwave-app/backend/app/services/story_scoring_service.py)
  * added policy / fiscal / justice signals such as:
    * `guvernul romaniei`
    * `parlamentul romaniei`
    * `coalitie de guvernare`
    * `amendamente buget`
    * `deficit bugetar`
    * `pachet solidaritate`
    * `salariu minim`
    * `aviz csm`
    * `procuror sef dna`
    * `tva`
    * `evaziune fiscala`
    * `antifrauda`
* expanded Romanian family hints in [backend/tools/editorial_debug/run_top5_scope_selection.py](D:/aplicatie_telefon/openwave-app/backend/tools/editorial_debug/run_top5_scope_selection.py)
  * added / strengthened:
    * `fiscal_policy_ro`
    * `government_coalition`
    * `justice_procedure`
    * `economic_policy_ro`
    * `public_safety_local_admin`
* fixed a classifier ordering bug:
  * family hints were being added to `positive_score` after `domestic_score_total` had already been calculated
  * this meant real Romanian policy/fiscal stories were carrying hints but not actually benefiting from them in the threshold decision
* added narrower Romanian public-interest signals for:
  * `tva`
  * `evaziune`
  * `antifrauda`
  * `petarde`
  * `artificii`
  * `capitala`
* kept lifecycle logic unchanged
* kept the selection formula unchanged

Validation run:

* `backend\venv\Scripts\python.exe backend/tools/editorial_debug/run_top5_breaking_bulletin.py --profile=national`

Observed improvement after the signal upgrade:

* `selected_count` improved from `2` to `4`
* `national_cluster_count` improved from `9-10` baseline range to `10`
* `national_preference_bucket_distribution` improved from:
  * `domestic_hard_news: 1`
  * `external_direct_impact: 1`
  * `off_target: 8`
  to:
  * `domestic_hard_news: 3`
  * `external_direct_impact: 1`
  * `off_target: 6`

More credible domestic candidates now selected:

* `Mierea din Mercosur fara taxe ameninta sa falimenteze producatorii romani...`
* `Consiliul General a adoptat initiativa REPER privind reguli mai stricte pentru petarde si artificii in Capitala`
* `ANAF s-a prins Cum se fura TVA...`

Lifecycle interaction remained stable:

* `domestic_politics` family continued to accumulate cleanly
* `family_run_count` increased to `17`
* `family_lifecycle_boost` remained predictable at `0.4`
* no lifecycle scoring changes were needed

Diversity protection stress test:

* created a controlled synthetic case with `4` clusters in the same `justice_procedure` family
* selection result kept only `2` stories from that family
* this confirms the family diversity cap still works under overflow pressure

Current limitation after Task 7:

* national quality is materially better, but still not fully healthy
* `multi_source_clusters` remained `0` in this particular post-upgrade run
* some off-target national candidates still exist in the pool and can backfill when the domestic pool is thin

Conclusion:

* Task 7 improved Romanian domestic signal detection without changing ranking logic
* more hard-news candidates now clear the national gate
* lifecycle behavior remains stable
* diversity protections remain active
* the next bottleneck is now stronger same-story overlap across Romanian outlets, not missing domestic signal vocabulary

## 2026-03-15 - Task 8 Romanian multi-source convergence

Goal for this pass:

* improve Romanian multi-source convergence without changing the shared editorial core
* keep the ranking formula structurally unchanged
* add only small, safe coverage and confirmation improvements

Changes made:

* enabled two already-modeled Romanian mainstream sources in [backend/app/config/source_watchers.json](D:/aplicatie_telefon/openwave-app/backend/app/config/source_watchers.json)
  * `Mediafax`
  * `Ziarul Financiar`
* added a source-limited discovery fallback in [backend/app/services/source_watcher_service.py](D:/aplicatie_telefon/openwave-app/backend/app/services/source_watcher_service.py)
  * if generic listing discovery returns no dated items for `Mediafax` or `Ziarul Financiar`
  * the watcher now scans clean anchor candidates and resolves dates from article pages
  * this keeps the parser change conservative and source-specific
* added canonical Romanian source normalization in [backend/app/services/news_clustering_service.py](D:/aplicatie_telefon/openwave-app/backend/app/services/news_clustering_service.py)
  * `Mediafax -> Mediafax`
  * `Ziarul Financiar -> ZF.ro`
* added one narrow Romanian public-affairs merge clause in [backend/app/services/news_clustering_service.py](D:/aplicatie_telefon/openwave-app/backend/app/services/news_clustering_service.py)
  * requires:
    * compatible national buckets
    * shared Romanian family hints
    * shared institutional hits
    * some minimum overlap in public-affairs topics or event overlap
  * this was added to improve same-event convergence without loosening general clustering globally
* added a small Romanian multi-source confirmation bonus in [backend/app/services/story_scoring_service.py](D:/aplicatie_telefon/openwave-app/backend/app/services/story_scoring_service.py)
  * applies only inside the existing Romanian domestic-balance component
  * `+0.05` for `2` Romanian sources
  * `+0.10` for `3+` Romanian sources
  * no lifecycle logic was changed
* exposed the new debug fields in:
  * [backend/app/models/story_score.py](D:/aplicatie_telefon/openwave-app/backend/app/models/story_score.py)
  * [backend/tools/editorial_debug/run_top5_breaking_bulletin.py](D:/aplicatie_telefon/openwave-app/backend/tools/editorial_debug/run_top5_breaking_bulletin.py)
  * fields:
    * `romanian_source_count`
    * `romanian_multi_source_bonus_applied`

Validation run:

* `backend\venv\Scripts\python.exe backend/tools/editorial_debug/run_top5_breaking_bulletin.py --profile=national`

Observed results in this live window:

* `selected_count: 5`
* `national_candidate_clusters: 9`
* `national_preference_bucket_distribution`:
  * `domestic_hard_news: 4`
  * `external_direct_impact: 2`
  * `off_target: 3`
* `multi_source_clusters: 0`

What improved:

* `Mediafax` moved from `0 discovered / 0 candidates` to:
  * `articles_discovered: 1`
  * `candidate_articles_produced: 1`
* `Ziarul Financiar` remained active but still produced `0` usable candidates in this run
* the national debug output now shows Romanian confirmation metadata explicitly
* source overlap visibility improved:
  * `Libertatea` now shows overlap candidates including `Mediafax`
  * `Digi24` now shows overlap candidates including `Mediafax`

What did not improve enough yet:

* the current live run still produced `0` actual Romanian multi-source clusters
* that means the remaining bottleneck is still live same-event overlap in the fetched Romanian pool, not only clustering rules
* the multi-source confirmation bonus was implemented, but no cluster in this run qualified to receive it

Interpretation:

* Task 8 improved Romanian source breadth and convergence diagnostics
* we now have one more mainstream source producing live candidates
* we also have a safer national-only merge path and an explicit confirmation bonus ready for real multi-source clusters
* however, this specific live fetch window still did not produce enough same-event overlap for `multi_source_clusters > 0`

Conclusion:

* the convergence layer is improved technically
* the next real bottleneck is still Romanian same-event coverage overlap in live fetches
* future work should focus on:
  * improving Romanian source discovery yield further
  * tightening off-target selection at source level so national sources spend their primary candidate on domestic public-affairs stories more consistently

Validation note:

* true spaced validation across evening and next-morning runs was not possible within this single implementation turn
* this task documents the immediate live baseline after the convergence changes

## 2026-03-15 - Task 9 editorial bulletin shaping

Goal for this pass:

- keep story scoring and story selection unchanged
- add a lightweight deterministic shaping layer after selection
- turn the selected set into a more radio-style bulletin order

Changes made:

- added [backend/app/models/bulletin_shaping.py](D:/aplicatie_telefon/openwave-app/backend/app/models/bulletin_shaping.py)
  - `BulletinShapingDecision`
  - `BulletinShapingResult`
- added [backend/app/services/bulletin_shaping_service.py](D:/aplicatie_telefon/openwave-app/backend/app/services/bulletin_shaping_service.py)
  - deterministic lead-story choice
  - family-aware ordering
  - topic-diversity ordering
  - confirmation-aware tie breaking
- updated [backend/app/services/editorial_pipeline_service.py](D:/aplicatie_telefon/openwave-app/backend/app/services/editorial_pipeline_service.py)
  - inserted `BulletinShapingService` after selection and before story editorial composition / briefing assembly
- updated [backend/app/services/briefing_assembly_service.py](D:/aplicatie_telefon/openwave-app/backend/app/services/briefing_assembly_service.py)
  - added `preserve_input_order` so the assembly layer can keep the editorially shaped order
- updated [backend/app/models/final_editorial_briefing.py](D:/aplicatie_telefon/openwave-app/backend/app/models/final_editorial_briefing.py)
  - carries `bulletin_shaping_explanation` in the final package
- updated [backend/tools/editorial_debug/run_top5_breaking_bulletin.py](D:/aplicatie_telefon/openwave-app/backend/tools/editorial_debug/run_top5_breaking_bulletin.py)
  - prints a `BULLETIN SHAPING` section with lead choice and per-position reasons

Validation run:

- `backend\venv\Scripts\python.exe backend/tools/editorial_debug/run_top5_breaking_bulletin.py --profile=national`

Observed result after the shaping fix:

- lead story is now chosen from a `domestic_hard_news` cluster instead of an `off_target` cluster
- the shaped order separates topic buckets and story families more cleanly
- current example lead: `Italia studiaza revenirea la energia nucleara pe fondul cresterii costurilor energiei`
- next placements kept a government story separate from the lead and pushed the external off-target cluster later

Important note:

- shaping is working as intended structurally
- the national pool itself still needs stronger Romanian same-event convergence and cleaner domestic classification
- shaping improves the order of the available selected set, but it does not and should not repair upstream candidate-quality issues
