# OPENWAVE_EDITORIAL_RULES_v1

This document describes the editorial behavior currently implemented in the OpenWave codebase.

Rule labels:
- `Implemented in code`
- `Partially implemented`
- `Not yet implemented`

Primary code areas:
- `backend/app/services/story_summary_generator_service.py`
- `backend/app/config/story_summary_policy.json`
- `backend/app/services/briefing_assembly_service.py`
- `backend/app/services/bulletin_sizing_service.py`
- `backend/app/services/editorial_to_audio_service.py`
- `backend/app/services/tts/romanian_numbers_normalizer.py`
- `backend/app/services/tts/romanian_audio_lexicon.py`

## A. Core Editorial Principle

- `Implemented in code` `Nu rezuma articolul. Rezuma povestea.`
  Code area: `backend/app/config/story_summary_policy.json`, `backend/app/services/story_summary_policy_service.py`
  Meaning: generated output is designed to compress the underlying story and its consequence, not mirror article structure.

## B. Story Structure Rules

- `Implemented in code` Default structure is 3 sentences.
  Code area: `backend/app/config/story_summary_policy.json`, `backend/app/services/story_summary_generator_service.py`

- `Implemented in code` Minimum is 2 sentences and normal maximum is 4 by policy compliance checks.
  Code area: `backend/app/config/story_summary_policy.json`, `backend/app/services/story_summary_generator_service.py`

- `Implemented in code` Major stories may expand to 4 or 5 sentences.
  Code area: `backend/app/services/story_summary_generator_service.py`
  Trigger: casualty presence, important topic, important keywords, or score above the expansion threshold.

- `Implemented in code` Sentence priority is:
  1. event / lead
  2. detail plus attribution
  3. casualties when present outside impact leads
  4. consequence / immediate effect for expanded important stories
  5. short context only when directly justified
  Code area: `backend/app/services/story_summary_generator_service.py`

- `Implemented in code` Context is added only for important stories and only when configured trigger keywords are present; if there are no casualties, the cluster must also have at least 2 member articles.
  Code area: `backend/app/services/story_summary_generator_service.py`

- `Implemented in code` Casualties are inserted as a dedicated line when detected and relevant.
  Code area: `backend/app/services/story_summary_generator_service.py`

## C. Lead Rules

- `Implemented in code` `impact`
  Code area: `backend/app/services/story_summary_generator_service.py`
  Trigger: any detected casualty line. Priority: consequence first, then event/location.

- `Implemented in code` `decision`
  Code area: `backend/app/services/story_summary_generator_service.py`
  Trigger: decision keywords in cluster text. Priority: institution plus decision plus short context.

- `Implemented in code` `warning`
  Code area: `backend/app/services/story_summary_generator_service.py`
  Trigger: warning/risk keywords in cluster text. Priority: risk plus who warns plus domain.

- `Implemented in code` `conflict`
  Code area: `backend/app/services/story_summary_generator_service.py`
  Trigger: political dispute keywords in cluster text. Priority: tension plus actors/cause.

- `Implemented in code` `change`
  Code area: `backend/app/services/story_summary_generator_service.py`
  Trigger: indicator/statistics/change keywords in cluster text. Priority: indicator or trend plus change context.

- `Implemented in code` `event`
  Code area: `backend/app/services/story_summary_generator_service.py`
  Trigger: fallback when other lead types do not match, including neutral events and sport. Priority: event plus participants/purpose.

## D. Attribution Rules

- `Implemented in code` Attribution is mandatory in generated story summaries through one of three modes.
  Code area: `backend/app/services/story_summary_generator_service.py`

- `Implemented in code` Attribution priority is:
  1. direct quote
  2. official statement
  3. source attribution fallback
  Code area: `backend/app/services/story_summary_generator_service.py`

- `Implemented in code` Attribution-first rule is enforced.
  Code area: `backend/app/services/story_summary_generator_service.py`
  Preferred patterns include `Potrivit X, ...`, `X spune ca ...`, `X transmite ca ...`, `X arata ca ...`.

- `Implemented in code` Post-attributed quote structures are avoided in generated summaries.
  Code area: `backend/app/services/story_summary_generator_service.py`

- `Implemented in code` Deterministic attribution variation avoids using the same opening structure for a third consecutive story.
  Code area: `backend/app/services/story_summary_generator_service.py`, `backend/app/services/editorial_pipeline_service.py`

- `Partially implemented` Avoid repeating the same source twice in a short story.
  Code area: `backend/app/services/story_summary_generator_service.py`
  Current behavior: one attribution element is generated per story and the templates avoid source-heavy repetition, but there is no deeper discourse-level rewrite beyond that single generated attribution sentence.

## E. Quote Rules

- `Implemented in code` Short memorable quotes may be preserved.
  Code area: `backend/app/services/story_summary_generator_service.py`
  Current rule: quotes are extracted from titles, must be short, vivid, and audio-friendly.

- `Implemented in code` Long quotes are avoided.
  Code area: `backend/app/services/story_summary_generator_service.py`
  Current rule: memorable quotes have a maximum word limit and a maximum character length.

- `Implemented in code` Vague or bureaucratic quotes are avoided.
  Code area: `backend/app/services/story_summary_generator_service.py`
  Current rule: configured bureaucratic quote terms are filtered out.

## F. Number Rules

- `Implemented in code` Essential numbers are kept.
  Code area: `backend/app/services/story_summary_generator_service.py`

- `Implemented in code` Nonessential numbers are removed more aggressively.
  Code area: `backend/app/services/story_summary_generator_service.py`

- `Implemented in code` Casualty counts, percentages, money amounts, and key value markers stay when they change the meaning of the story.
  Code area: `backend/app/services/story_summary_generator_service.py`

- `Implemented in code` Secondary technical counts are dropped when they do not alter story understanding.
  Code area: `backend/app/services/story_summary_generator_service.py`

## G. Casualty Rules

- `Implemented in code` Deaths and injuries must be mentioned when clearly present.
  Code area: `backend/app/services/story_summary_generator_service.py`

- `Implemented in code` This rule has priority for war, attack, disaster, accident, explosion, crash, and fire-style stories through casualty keyword detection.
  Code area: `backend/app/services/story_summary_generator_service.py`

- `Implemented in code` Impact leads automatically switch to casualty-first framing when casualties are detected.
  Code area: `backend/app/services/story_summary_generator_service.py`

## H. Context Rules

- `Implemented in code` Context can be added for major stories.
  Code area: `backend/app/services/story_summary_generator_service.py`

- `Implemented in code` Context must be short and directly relevant.
  Code area: `backend/app/services/story_summary_generator_service.py`
  Current behavior: context comes from short topic templates rather than free-form expansion.

- `Implemented in code` The generator avoids turning summaries into explainers by adding context only under narrow trigger conditions.
  Code area: `backend/app/services/story_summary_generator_service.py`

## I. Briefing Flow Rules

- `Implemented in code` The strongest available story opens the bulletin.
  Code area: `backend/app/services/briefing_assembly_service.py`

- `Implemented in code` The bulletin avoids long heavy-heavy-heavy runs when suitable alternatives exist.
  Code area: `backend/app/services/briefing_assembly_service.py`

- `Implemented in code` Every story receives a pacing label: `heavy`, `medium`, or `light`.
  Code area: `backend/app/services/briefing_assembly_service.py`

- `Implemented in code` A lighter close is preferred when possible.
  Code area: `backend/app/services/briefing_assembly_service.py`

- `Implemented in code` Score remains the main ordering signal; pacing and topic-flow adjustments are secondary.
  Code area: `backend/app/services/briefing_assembly_service.py`

- `Implemented in code` For controversial or disputed stories, one `Two Perspectives` pair may be inserted immediately after the main story.
  Code area: `backend/app/services/briefing_assembly_service.py`
  Current limits: maximum one supporters-vs-critics pair per bulletin.

- `Implemented in code` Bulletin sizing trims only low-priority trailing stories when duration is too long; it does not rewrite the kept stories.
  Code area: `backend/app/services/bulletin_sizing_service.py`

## J. Listener And Presentation Rules

- `Implemented in code` Listener first-name personalization is optional.
  Code area: `backend/app/services/briefing_assembly_service.py`

- `Implemented in code` Local personalization uses the listener region or county as the primary local editorial anchor.
  Code area: `backend/app/models/user_personalization.py`, `backend/app/services/editorial_pipeline_service.py`
  Current behavior: `city` is preserved in the listener profile, but the pipeline exposes `region` first for any local editorial anchoring and only falls back to city when region is missing.

- `Implemented in code` County-based Romanian local news sources are available as a registry for the monitoring layer.
  Code area: `backend/app/config/romanian_local_sources_by_county.json`, `backend/app/services/local_source_registry_service.py`, `backend/app/services/source_watcher_service.py`
  Current behavior: when a listener has a region and local geography preference is enabled, the pipeline can resolve county sources for that region and exposes whether the registry was used. Example for `Iasi`: `ziaruldeiasi.ro`, `bzi.ro`, `ieseanul.ro`.

- `Implemented in code` Story selection can use the listener region as a soft local near-tie signal.
  Code area: `backend/app/services/story_selection_service.py`
  Current behavior: when local geography preference is above zero and two clusters are close in score, a cluster with `regional_relevance = region_match` can be favored over a near-tie national or international cluster. Clearly stronger stories are not displaced.

- `Implemented in code` The listener name may appear at most twice per bulletin.
  Code area: `backend/app/services/briefing_assembly_service.py`
  Current behavior: once in intro, optionally once in outro, never inside story summaries.

- `Implemented in code` Intro/outro variation exists.
  Code area: `backend/app/config/briefing_assembly_config.json`, `backend/app/services/briefing_assembly_service.py`
  Current behavior: 3 intro variants and 3 outro variants are selected deterministically.

- `Implemented in code` Dual presenter mode exists.
  Code area: `backend/app/services/briefing_assembly_service.py`
  Current behavior: story presenters alternate `female` / `male`.

- `Implemented in code` Microphone pass phrases exist.
  Code area: `backend/app/config/briefing_assembly_config.json`, `backend/app/services/briefing_assembly_service.py`
  Current behavior: short pass phrases are inserted only on suitable shifts and capped at 2 per bulletin.

## K. Romanian Audio-Language Rules Already Tied To Editorial Output

- `Implemented in code` Each story gets a short editorial headline.
  Code area: `backend/app/services/story_summary_generator_service.py`
  Current behavior: a 3-6 word headline-like cue is generated from the representative title.

- `Implemented in code` Source mention discipline is applied through single attribution sentences and attribution-variant rotation.
  Code area: `backend/app/services/story_summary_generator_service.py`

- `Implemented in code` Current-year omission is applied in compact date normalization for TTS.
  Code area: `backend/app/services/tts/romanian_numbers_normalizer.py`
  Current behavior: `12.03.2026` becomes `douasprezece martie` when the year matches the current year.

- `Implemented in code` Romanian audio normalization converts times, percentages, years, money amounts, and basic numbers into TTS-friendly spoken forms.
  Code area: `backend/app/services/tts/romanian_numbers_normalizer.py`

- `Partially implemented` Institutional naming clarity exists through the Romanian audio lexicon.
  Code area: `backend/app/services/tts/romanian_audio_lexicon.py`
  Current behavior: the lexicon stores first mention, later mention, and TTS hints for institutions and acronyms, but final script wording still depends on upstream editorial text.

- `Implemented in code` Audio-friendly phrasing principles are enforced indirectly through banned-pattern checks, attribution-first templates, short-context templates, and number filtering.
  Code area: `backend/app/services/story_summary_generator_service.py`

- `Implemented in code` Story continuity is detected against the previous bulletin and changes only the lead wording.
  Code area: `backend/app/services/editorial_pipeline_service.py`, `backend/app/services/story_summary_generator_service.py`
  Current behavior: if a cluster appeared in the previous bulletin it is marked as `update`; if it returns with a clearly higher score or more sources it can be marked as `major_update`; otherwise it stays `new_story`. Continuity does not change scoring or selection.

## L. Features Discussed But Not Yet Implemented

- `Not yet implemented` Commentary pipeline integration in the editorial pipeline.
  Current state: the watcher can track commentary sources, but the modern editorial assembly path is still focused on news article flow.

- `Not yet implemented` Automatic expansion of too-short bulletins by adding or regenerating material.
  Current state: sizing reports short bulletins but does not expand them.

- `Not yet implemented` Full explainer/background mode inside story summaries.
  Current state: only short context lines are supported for major stories.

- `Not yet implemented` Multi-pair perspective handling across several controversial stories in one bulletin.
  Current state: the system allows only one perspective pair per bulletin.

- `Not yet implemented` Randomized editorial language generation.
  Current state: variation is deterministic by design.

- `Implemented in code` Personalization is a first-class pipeline contract, not a UI-only feature.
  Code area: `backend/app/models/user_personalization.py`, `backend/app/services/end_to_end_bulletin_service.py`, `backend/app/services/editorial_pipeline_service.py`
  Current behavior: listener profile and editorial preferences are always resolved explicitly, with neutral defaults when payload data is missing.

- `Implemented in code` Default fallback is visible in output explainability.
  Code area: `backend/app/models/final_editorial_briefing.py`, `backend/app/models/end_to_end_bulletin_result.py`
  Current behavior: pipeline output exposes `personalization_used`, `listener_profile_used`, `editorial_preferences_used`, `personalization_defaults_applied`, `local_editorial_anchor`, `local_editorial_anchor_scope`, `local_source_region_used`, `local_source_count`, and `local_source_registry_used`.
