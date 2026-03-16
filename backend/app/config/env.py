from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ENV_PATH = Path(__file__).resolve().parents[2] / '.env'
DEFAULT_OPENWAVE_MODE = 'debug'
SUPPORTED_OPENWAVE_MODES = {'debug', 'live'}


def load_backend_env() -> None:
    load_dotenv(BACKEND_ENV_PATH, override=False)


def get_openwave_mode() -> str:
    load_backend_env()
    raw_mode = os.getenv('OPENWAVE_MODE', DEFAULT_OPENWAVE_MODE).strip().lower()
    return raw_mode if raw_mode in SUPPORTED_OPENWAVE_MODES else DEFAULT_OPENWAVE_MODE
