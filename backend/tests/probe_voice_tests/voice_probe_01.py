from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.audio_generation_package import AudioSegmentBlock
from app.services.tts_service import TtsService

PROBE_ID = 'voice_probe_01'
PROBE_TITLE = 'Voice Probe 01'


def build_segments() -> list[AudioSegmentBlock]:
    return [
        AudioSegmentBlock(
            segment_name='intro',
            segment_type='intro',
            presenter_name='Ana',
            text='Bun găsit. Asculți un test OpenWave cu doi prezentatori. Iată principalele știri.',
        ),
        AudioSegmentBlock(
            segment_name='story_01',
            segment_type='story',
            presenter_name='Ana',
            topic_label='economy',
            text='Comisia Europeană spune că economia din zona euro dă semne de stabilizare după un început de an ezitant.',
        ),
        AudioSegmentBlock(
            segment_name='story_02',
            segment_type='story',
            presenter_name='Paul',
            topic_label='international',
            text='Liderii occidentali continuă negocierile asupra unui nou pachet de sprijin pentru securitatea regională.',
        ),
        AudioSegmentBlock(
            segment_name='outro',
            segment_type='outro',
            presenter_name='Ana',
            text='Acesta a fost testul OpenWave pentru modul dual presenter.',
        ),
    ]


def run_probe() -> dict[str, object]:
    tts_service = TtsService()
    segment_blocks = [
        {
            'segment_name': segment.segment_name,
            'text': segment.text or '',
            'presenter_name': segment.presenter_name,
        }
        for segment in build_segments()
    ]
    result = tts_service.generate_audio_segments(
        segment_blocks=segment_blocks,
        file_stem=PROBE_ID,
        provider_override='openai',
    )
    return {
        'probe_id': PROBE_ID,
        'title': PROBE_TITLE,
        'segments': [segment.segment_name for segment in build_segments()],
        **result,
    }


if __name__ == '__main__':
    print(run_probe())
