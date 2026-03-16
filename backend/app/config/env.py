from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ENV_PATH = Path(__file__).resolve().parents[2] / '.env'
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OPENWAVE_MODE = 'debug'
SUPPORTED_OPENWAVE_MODES = {'debug', 'live'}
DEFAULT_REAL_SAMPLES_ROOT = REPO_ROOT / 'tests' / 'real_samples'


def load_backend_env() -> None:
    load_dotenv(BACKEND_ENV_PATH, override=False)


def get_openwave_mode() -> str:
    load_backend_env()
    raw_mode = os.getenv('OPENWAVE_MODE', DEFAULT_OPENWAVE_MODE).strip().lower()
    return raw_mode if raw_mode in SUPPORTED_OPENWAVE_MODES else DEFAULT_OPENWAVE_MODE


def get_openwave_real_samples_root() -> Path:
    load_backend_env()
    configured_root = os.getenv('OPENWAVE_REAL_SAMPLES_ROOT', '').strip()
    return Path(configured_root) if configured_root else DEFAULT_REAL_SAMPLES_ROOT


def get_openwave_debug_sample_dir() -> Path | None:
    load_backend_env()
    configured_dir = os.getenv('OPENWAVE_DEBUG_SAMPLE_DIR', '').strip()
    if not configured_dir:
        return None
    return Path(configured_dir)
