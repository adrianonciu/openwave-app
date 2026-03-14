# OPENWAVE_EDITORIAL_CONTRACT

This document translates the current OpenWave editorial rules into deterministic backend validation rules.

It complements, and does not replace:
- `docs/OPENWAVE_EDITORIAL_RULES_v1.md`
- `docs/OPENWAVE_ARCHITECTURE_v1.md`
- `docs/PROJECT_CONTEXT.md`

## Purpose

The editorial contract is a mandatory validation gate that runs after briefing assembly and sizing, and before `EditorialToAudioService`.

Pipeline stage:

`SourceWatcher -> ArticleFetchService -> NewsClusteringService -> StoryScoringService -> StorySelectionService -> StorySummaryGeneratorService -> BriefingAssemblyService -> BulletinSizingService -> EditorialContractValidationService -> EditorialToAudioService -> TtsService`

The validator does three things:
- validates each story
- validates bulletin-level structure
- records violations, warnings, and deterministic auto-fixes

If any blocking rule fails, the pipeline stops before audio generation.

## Validation Result Types

### Violation severities

- `blocking`
  Meaning: bulletin cannot continue toward audio generation.
- `auto_fix`
  Meaning: deterministic correction was applied and recorded.
- `warning`
  Meaning: bulletin can continue, but the issue is visible in the report.

### Result models

- `EditorialContractViolation`
- `EditorialContractAutoFix`
- `StoryValidationResult`
- `BulletinValidationResult`

## Story-Level Rules

### 1. Title required
- rule: `title_required`
- blocking if the final story title is empty

### 2. Title max words
- rule: `title_max_words`
- target maximum: 8 words
- deterministic truncation may be applied first
- warning if a title still exceeds the preferred max after cleanup

### 3. Source attribution required
- rule: `source_required`
- every story must contain an on-air source reference in body text
- deterministic auto-fix may prepend `Potrivit {source}, ...` when safe
- blocking if source labels are missing entirely

### 4. Language cleanliness
- rule: `mixed_language`
- Romanian/English mixed story body must not pass to audio
- blocking when the body remains English-heavy

### 5. Quote source precedes statement
- rule: `quote_source_precedes_statement`
- post-attributed constructions are reported
- safe deterministic rewrites may convert patterns such as `..., a declarat X` into `X a declarat ca ...`
- warning if a quote still lacks a clearly named source before the statement

### 6. Quote count
- rules: `quote_count`, `major_story_quote_count`
- short stories should keep at most one direct quote
- major stories prefer 2-3 attributed quotes when available
- missing quotes on major stories are warnings, not blocking failures

### 7. User name restriction
- rule: `user_name_allowed_only_in_intro_outro`
- listener first name must not appear inside story title or story body
- blocking if violated

### 8. Headline quality
- rule: `headline_quality`
- title cleanup removes noisy prefixes such as `LIVE`, `VIDEO`, `BREAKING`
- SEO-style fragments are stripped when deterministic cleanup is possible
- generic placeholders such as `Subiect important acum` remain warnings unless the final title is unusable
- blocking only if no usable title remains after cleanup

## Bulletin-Level Rules

### 1. Intro required
- rule: `intro_required`
- blocking if missing

### 2. Outro required
- rule: `outro_required`
- blocking if missing

### 3. Story count
- rule: `story_count_range`
- required range: 6-10 stories
- blocking outside this range

### 4. Presenter alternation in `dual_test`
- rule: `presenter_alternation`
- when `presenter_mode=dual_test`, story presenters should alternate Ana/Paul through the underlying female/male assembly metadata
- warning if alternation is broken

### 5. Perspective adjacency
- rule: `perspective_adjacency`
- perspective supporters/critics pair must stay consecutive and tied to the parent story
- warning if malformed

### 6. Local anchor expectation
- rule: `local_anchor_story_missing`
- if local candidates existed, the bulletin should include at least one local story
- warning if missing

### 7. User name placement at bulletin level
- rule: `user_name_allowed_only_in_intro_outro`
- listener name may appear only in intro/outro
- blocking if found inside stories

### 8. Intro/outro variants remain visible
- rules: `intro_variant_missing`, `outro_variant_missing`
- variant support is not blocking yet
- warning if variant metadata is missing

## Auto-Fix Policy

The validator applies only conservative, deterministic auto-fixes.

Current examples:
- remove noisy title prefixes
- strip obvious SEO fragments
- truncate overlong title to 8 words
- prepend safe source attribution when source labels exist but story text omitted them
- normalize simple post-attributed quote structure into named-source-first order

The validator does not attempt open-ended rewriting or generative editorial repair.

## Enforcement

`EditorialContractValidationService` is called from `EndToEndBulletinService` after the editorial text package is produced and before `EditorialToAudioService` runs.

If validation fails:
- pipeline stage returns `editorial_contract_validation_failed`
- audio generation does not start
- a debug report is written to `backend/debug_output/editorial_validation_report.json`

## Debug Report

Report path:
- `backend/debug_output/editorial_validation_report.json`

Report includes:
- bulletin summary
- blocking violation count
- warning count
- auto-fix count
- per-story validation results
- bulletin-level violations
- all violations and all auto-fixes in one consolidated list

## Current Boundary

This contract is intentionally conservative.

It validates and reports. It does not redesign:
- Flutter
- TTS provider flow
- story scoring architecture
- briefing assembly strategy
- summary generation strategy beyond deterministic cleanup already in pipeline
