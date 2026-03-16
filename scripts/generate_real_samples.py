from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
PREVIEW_SCRIPT = REPO_ROOT / "backend" / "tools" / "editorial_debug" / "run_radio_editing_preview.py"
DEFAULT_SAMPLES_ROOT = REPO_ROOT / "tests" / "real_samples"
BACKEND_PYTHON = REPO_ROOT / "backend" / "venv" / "Scripts" / "python.exe"


def _normalize_slug(value: str) -> str:
    return "_".join(str(value or "").strip().lower().split())


def build_output_dir(user: str, county: str) -> Path:
    sample_date = datetime.now().date().isoformat()
    return DEFAULT_SAMPLES_ROOT / f"{sample_date}_{_normalize_slug(user)}_{_normalize_slug(county)}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a saved real-sample OpenWave bulletin from live sources.")
    parser.add_argument("--county", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else build_output_dir(args.user, args.county)
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["OPENWAVE_MODE"] = "live"
    python_executable = str(BACKEND_PYTHON if BACKEND_PYTHON.exists() else Path(sys.executable))
    command = [python_executable, str(PREVIEW_SCRIPT), "--user", args.user, "--county", args.county, "--save-real-sample-dir", str(output_dir)]
    subprocess.run(command, cwd=REPO_ROOT, env=env, check=True)
    print(output_dir)


if __name__ == "__main__":
    main()
