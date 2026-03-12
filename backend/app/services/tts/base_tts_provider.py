from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseTtsProvider(ABC):
    provider_name: str

    @property
    @abstractmethod
    def voice_id(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def model(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def output_format(self) -> str:
        raise NotImplementedError

    @property
    def output_extension(self) -> str:
        return self.output_format.split("_")[0].lower()

    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def synthesize(self, text: str, output_path: Path) -> None:
        raise NotImplementedError
