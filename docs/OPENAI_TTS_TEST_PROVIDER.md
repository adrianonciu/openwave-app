# OpenAI TTS Test Provider

This is a temporary lower-cost test path for segmented OpenWave audio generation.

## Provider switch

Set the backend environment to prefer OpenAI TTS:

```env
TTS_PROVIDER=openai
TTS_FALLBACK_PROVIDER=elevenlabs
OPENAI_API_KEY=your_key_here
OPENAI_TTS_MODEL=gpt-4o-mini-tts
```

## Presenter mapping

- `Ana` -> `alloy`
- `Paul` -> `verse`
- any other presenter -> configured `OPENAI_TTS_VOICE`, fallback `alloy`

## Example test calls

Ana test segment:

```json
{
  "briefing_text": "Buna dimineata. Acesta este un test scurt OpenWave.",
  "presenter_name": "Ana",
  "file_stem": "ana_test"
}
```

Paul test segment:

```json
{
  "briefing_text": "Buna seara. Acesta este un test scurt OpenWave.",
  "presenter_name": "Paul",
  "file_stem": "paul_test"
}
```

## Segmented output

Segmented generation remains unchanged and still writes files like:

- `bulletin_id_intro.mp3`
- `bulletin_id_story_01.mp3`
- `bulletin_id_story_02.mp3`
- `bulletin_id_outro.mp3`
