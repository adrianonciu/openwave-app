from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.audio_generation_package import AudioSegmentBlock
from app.services.tts_service import TtsService

PROBE_ID = 'voice_probe_02'
PROBE_TITLE = 'Voice Probe 02'


def build_segments() -> list[AudioSegmentBlock]:
    return [
        AudioSegmentBlock(
            segment_name='intro',
            segment_type='intro',
            presenter_name='Ana',
            text='Bun găsit. Acesta este al doilea test OpenWave pentru ritm, alternanță și segmentare audio.',
        ),
        AudioSegmentBlock(
            segment_name='story_01',
            segment_type='story',
            presenter_name='Ana',
            topic_label='technology',
            text='Mai multe companii europene accelerează investițiile în centre de date și proiecte de inteligență artificială. Analiștii spun că ritmul este important pentru competitivitate, dar și pentru controlul costurilor energetice. Următoarele trimestre vor arăta cât de repede se transformă aceste planuri în rezultate concrete.',
        ),
        AudioSegmentBlock(
            segment_name='story_02',
            segment_type='story',
            presenter_name='Paul',
            topic_label='international',
            text='Negocierile diplomatice privind securitatea regională continuă într-un climat tensionat. Oficialii încearcă să păstreze un mesaj comun, în timp ce fiecare capitală își calculează atent marja bugetară. Potrivit surselor diplomatice, un acord rămâne posibil dacă presiunea politică nu crește în zilele următoare.',
        ),
        AudioSegmentBlock(
            segment_name='story_03',
            segment_type='story',
            presenter_name='Ana',
            topic_label='economy',
            text='Piața europeană urmărește cu atenție noile date despre inflație și consum. Semnalele sunt mixte: unele sectoare încetinesc, în timp ce altele recuperează mai repede decât era estimat. Pentru investitori, concluzia este că perioada următoare cere mai multă prudență decât optimism.',
        ),
        AudioSegmentBlock(
            segment_name='outro',
            segment_type='outro',
            presenter_name='Ana',
            text='Acesta a fost testul OpenWave pentru ritm și alternanță între Ana și Paul.',
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
    )
    return {
        'probe_id': PROBE_ID,
        'title': PROBE_TITLE,
        'segments': [segment.segment_name for segment in build_segments()],
        **result,
    }


if __name__ == '__main__':
    print(run_probe())
