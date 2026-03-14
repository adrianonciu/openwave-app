from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TtsProviderErrorInfo:
    provider: str
    code: str
    message: str
    status_code: int | None = None


class TtsProviderError(RuntimeError):
    def __init__(self, *, provider: str, code: str, message: str, status_code: int | None = None) -> None:
        self.info = TtsProviderErrorInfo(
            provider=provider,
            code=code,
            message=message,
            status_code=status_code,
        )
        super().__init__(message)
