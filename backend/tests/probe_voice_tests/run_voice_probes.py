from __future__ import annotations

import json
import sys
from pathlib import Path

PROBE_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = PROBE_DIR.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(PROBE_DIR) not in sys.path:
    sys.path.insert(0, str(PROBE_DIR))

from voice_probe_01 import run_probe as run_probe_01
from voice_probe_02 import run_probe as run_probe_02


def main() -> None:
    results = []
    for runner in (run_probe_01, run_probe_02):
        result = runner()
        results.append(result)
        print(f"Generated {result['probe_id']} with {len(result['segments'])} segments.")
        for url in result['segments']:
            print(f"  - {url}")

    print('\nSummary:')
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
