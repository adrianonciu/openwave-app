from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


BACKEND_ENV_PATH = Path(__file__).resolve().parents[2] / '.env'


def load_backend_env() -> None:
    load_dotenv(BACKEND_ENV_PATH, override=False)
