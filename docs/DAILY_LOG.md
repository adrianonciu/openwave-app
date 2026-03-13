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
