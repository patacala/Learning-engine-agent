from abc import ABC, abstractmethod
from typing import Any


class BaseEngine(ABC):
    """Base interface for all cognitive engines."""

    @abstractmethod
    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        """Process pipeline state and return updates."""
        ...


class BaseDetector(ABC):
    """Base interface for analyzers/detectors."""

    @abstractmethod
    async def detect(self, text: str, context: dict[str, Any] | None = None) -> Any:
        """Analyze text and return detection result."""
        ...
